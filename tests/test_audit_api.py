"""Denetim izi listesi, detay ve geçmiş (ekran 26, fonksiyon 98; K-108): yetki, maske, okunur biçim, görünüm izi."""
import io
import json
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import text

from app.api import audit_format
from app.api.main import create_app
from app.api.permissions import ADMIN, END_USER, KEY_USER, SYSTEM_OWNER
from app.api.repositories import audit

from auth_helpers import auth, delete_users, ensure_user

pytestmark = pytest.mark.db

PREFIX = "pytest.iz."
ROLES = (SYSTEM_OWNER, ADMIN, KEY_USER, END_USER)


def clean(engine):
    with engine.begin() as c:
        ids = [r[0] for r in c.execute(text("SELECT Id FROM adm.AppUser WHERE UserName LIKE :p"), {"p": PREFIX + "%"})]
        c.execute(text("DELETE FROM adm.AuditLog WHERE ObjectKey LIKE N'pytest%' OR ObjectType = N'audit-log' OR ObjectType = N'TableView'"))
        c.execute(text("DELETE FROM adm.TableView WHERE ListName = N'audit-log'"))
        delete_users(c, ids)


@pytest.fixture
def people(db_engine):
    clean(db_engine)
    with db_engine.begin() as c:
        out = {r: ensure_user(c, PREFIX + r.replace(" ", "-").lower(), r, f"Ad {r}") for r in ROLES}
    yield out
    clean(db_engine)


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def write(engine, action, user_id, object_type, key, new=None, old=None):
    from sqlalchemy.orm import Session
    with Session(engine) as s:
        audit.write_audit(s, action, user_id, object_type, key, new, old)
        s.commit()
        return s.execute(text("SELECT MAX(Id) FROM adm.AuditLog")).scalar_one()


def rows(client, people, role=ADMIN, **filters):
    body = {"fields": ["At", "ActorName", "Action", "ObjectTypeLabel", "ObjectShown", "OldText", "NewText", "OldValue", "NewValue"],
            "limit": 100, "filters": [{"field": "ObjectShown", "op": "starts_with", "value": "pytest"}], **filters}
    r = client.post("/api/audit-log/query", headers=auth(people[role]), json=body)
    assert r.status_code == 200, r.text
    return r.json()["rows"]


# --- yetki ---

@pytest.mark.parametrize("url", ["/api/audit-log/columns", "/api/audit-log/1", "/api/audit-log/1/history"])
def test_end_user_cannot_read(client, people, url):
    assert client.get(url, headers=auth(people[END_USER])).status_code == 403


def test_admin_sees_all_key_user_own(db_engine, client, people):
    key, admin = people[KEY_USER], people[ADMIN]
    own = write(db_engine, "İş iptali", key, "Job", "pytest-1", {"status": "İptal"})
    other = write(db_engine, "İş iptali", admin, "Job", "pytest-1", {"status": "İptal"})
    assert {r["Id"] for r in rows(client, people)} == {own, other}
    assert [r["Id"] for r in rows(client, people, KEY_USER)] == [own]

    h = auth(key)
    assert client.get(f"/api/audit-log/{own}", headers=h).status_code == 200
    missing = client.get(f"/api/audit-log/{other}", headers=h)
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "audit_not_found"
    assert client.get(f"/api/audit-log/{other}/history", headers=h).status_code == 404
    assert [x["id"] for x in client.get(f"/api/audit-log/{own}/history", headers=h).json()["rows"]] == [own]

    # değer listesi ve Excel de kendi kapsamında
    values = client.post("/api/audit-log/values", headers=h, json={"field": "ActorName"}).json()
    assert [v["value"] for v in values] == [f"Ad {KEY_USER}"]
    r = client.post("/api/audit-log/export", headers=h, json={"fields": ["ActorName"], "filters": [{"field": "ObjectShown", "op": "equals", "value": "pytest-1"}]})
    assert r.status_code == 200, r.text
    data = list(load_workbook(io.BytesIO(r.content)).worksheets[0].iter_rows(values_only=True))
    assert data[1:] == [(f"Ad {KEY_USER}",)]


# --- K-101: System owner kayıtları ---

def test_system_owner_actor_masked_but_action_visible(db_engine, client, people):
    owner = people[SYSTEM_OWNER]
    audit_id = write(db_engine, "Ayar değişikliği", owner, "SystemSetting", "pytest-ayar", {"Value": 30}, {"Value": 85})
    row = rows(client, people)[0]
    assert row["ActorName"] == "Smartchain"
    assert (row["ObjectTypeLabel"], row["OldText"], row["NewText"]) == ("Ayar", "Değer: 85", "Değer: 30")
    assert client.get(f"/api/audit-log/{audit_id}", headers=auth(people[ADMIN])).json()["actor"] == "Smartchain"
    assert client.get(f"/api/audit-log/{audit_id}", headers=auth(owner)).json()["actor"] == f"Ad {SYSTEM_OWNER}"


def test_system_owner_account_masked(db_engine, client, people):
    owner = people[SYSTEM_OWNER]
    name = PREFIX + "system-owner"
    audit_id = write(db_engine, "Giriş", owner, "Kullanıcı", name, {"address": "10.0.0.5", "session_id": 3})
    h = auth(people[ADMIN])
    r = client.post("/api/audit-log/query", headers=h, json={"fields": ["ObjectShown", "NewText", "NewValue", "ActorName"], "limit": 5, "sort": [{"field": "At", "dir": "desc"}]})
    row = next(x for x in r.json()["rows"] if x["Id"] == audit_id)
    assert row["ObjectShown"] == "Smartchain hesabı" and row["NewText"] is None and row["NewValue"] is None

    seen = client.get(f"/api/audit-log/{audit_id}", headers=h).json()
    assert seen["object"] == "Smartchain hesabı" and seen["changes"] == [] and seen["has_object"] is True
    assert name not in json.dumps(seen)
    assert name not in json.dumps(client.get(f"/api/audit-log/{audit_id}/history", headers=h).json())

    real = client.get(f"/api/audit-log/{audit_id}", headers=auth(owner)).json()
    assert real["object"] == name and {c["field"]: c["new"] for c in real["changes"]}["IP adresi"] == "10.0.0.5"

    r = client.post("/api/audit-log/export", headers=h, json={"fields": ["ObjectShown", "NewText", "NewValue"], "filters": [{"field": "ObjectShown", "op": "equals", "value": "Smartchain hesabı"}]})
    assert name.encode() not in r.content and "10.0.0.5" not in str(list(load_workbook(io.BytesIO(r.content)).worksheets[0].iter_rows(values_only=True)))
    with db_engine.begin() as c:
        c.execute(text("DELETE FROM adm.AuditLog WHERE Id = :i"), {"i": audit_id})


def test_raw_and_detail_fields_are_not_queryable(client, people):
    for field in ("RawKey", "RawOld", "RawNew", "RealActor", "UserId"):
        r = client.post("/api/audit-log/query", headers=auth(people[ADMIN]), json={"fields": [field]})
        assert r.status_code == 422, field


# --- okunur biçim ---

def test_readable_format():
    assert audit_format.readable(None) is None
    assert audit_format.readable('{"Role": "Admin", "FullName": "Ayşe"}') == "Rol: Admin · Ad soyad: Ayşe"
    assert audit_format.readable('{"IsActive": false, "columns": ["a", "b"], "bilinmeyen": 3}') == "Aktif: Hayır · Kolonlar: a, b · bilinmeyen: 3"
    assert audit_format.readable("düz metin") == "Değer: düz metin"
    at = datetime(2026, 11, 3, 15, 0, tzinfo=timezone.utc).astimezone()
    assert audit_format.readable('{"locked_until": "2026-11-03 15:00:00.123"}') == f"Kilit bitişi: {at:%d.%m.%Y %H:%M}"
    assert audit_format.changes('{"Role": "Admin"}', '{"Role": "Key user", "Name": "x"}') == [
        {"field": "Rol", "old": "Admin", "new": "Key user"}, {"field": "Ad", "old": "—", "new": "x"}]
    assert audit_format.changes(None, None) == []


def test_list_columns_and_excel(db_engine, client, people):
    h = auth(people[ADMIN])
    cols = {c["field"]: c for c in client.get("/api/audit-log/columns", headers=h).json()["columns"]}
    assert [f for f, c in cols.items() if not c["default_visible"]] == ["OldValue", "NewValue"]
    assert cols["OldValue"]["label"] == "Eski değer (ham)" and cols["OldText"]["label"] == "Eski değer"
    assert cols["ActorName"]["filter"] == "list" and cols["ObjectShown"]["filter"] == "text" and cols["At"]["type"] == "datetime"

    write(db_engine, "Rol değişikliği", people[ADMIN], "Kullanıcı", "pytest-burak", {"Role": "Key user"}, {"Role": "End user"})
    r = client.post("/api/audit-log/export", headers=h, json={
        "fields": ["ObjectShown", "OldText", "NewText", "OldValue", "NewValue"], "filters": [{"field": "ObjectShown", "op": "equals", "value": "pytest-burak"}]})
    assert r.status_code == 200, r.text
    assert "smartchain_denetim-izi_" in r.headers["content-disposition"]
    data = list(load_workbook(io.BytesIO(r.content)).worksheets[0].iter_rows(values_only=True))
    assert data[0] == ("Nesne", "Eski değer", "Yeni değer", "Eski değer (ham)", "Yeni değer (ham)")
    assert data[1] == ("pytest-burak", "Rol: End user", "Rol: Key user", '{"Role": "End user"}', '{"Role": "Key user"}')

    # aktarımın kendisi de ize yazılır, görüntüleme yazılmaz
    with db_engine.connect() as c:
        trace = c.execute(text("SELECT COUNT(*) FROM adm.AuditLog WHERE Action = N'Dışa aktarım' AND ObjectType = N'audit-log' AND UserId = :u"), {"u": people[ADMIN]}).scalar_one()
        before = c.execute(text("SELECT COUNT(*) FROM adm.AuditLog")).scalar_one()
    assert trace == 1
    rows(client, people)
    with db_engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM adm.AuditLog")).scalar_one() == before


@pytest.mark.parametrize("object_type, action, label", [
    ("Fonksiyon", "Yetkisiz istek", "Yetki"), ("FieldDefinition", "Alan etiketi değişikliği", "Veri sözlüğü"), ("SystemSetting", "Ayar değişikliği", "Ayar"),
    ("Job", "İş iptali", "İş"), ("TableView", "Paylaşılan görünüm silindi", "Görünüm"), ("materials", "Dışa aktarım", "Dışa aktarım"), ("Kullanıcı", "Giriş", "Kullanıcı"),
])
def test_object_type_labels(db_engine, client, people, object_type, action, label):
    write(db_engine, action, people[ADMIN], object_type, "pytest-tip")
    assert rows(client, people)[0]["ObjectTypeLabel"] == label


def test_setting_shown_with_form_name(db_engine, client, people):
    """Ekran, arama, Excel ve detay formdaki adı gösterir; ham anahtar saklanır, geçmiş ona göre bulur (K-108)."""
    owner, admin = people[SYSTEM_OWNER], people[ADMIN]
    first = write(db_engine, "Ayar değişikliği", admin, "SystemSetting", "DiskWarnPercent", {"Value": 30}, {"Value": 85})
    second = write(db_engine, "Ayar değişikliği", owner, "SystemSetting", "DiskWarnPercent", {"Value": 40}, {"Value": 30})
    other = write(db_engine, "Giriş", admin, "Kullanıcı", "DiskWarnPercent")  # başka tipte aynı metin çevrilmez
    bilinmeyen = write(db_engine, "Ayar değişikliği", admin, "SystemSetting", "pytest-bilinmeyen")
    label = "Disk uyarı eşiği (%)"
    try:
        found = rows(client, people, filters=[{"field": "ObjectShown", "op": "contains", "value": "Disk uyarı"}])
        assert {r["Id"] for r in found} == {first, second} and {r["ObjectShown"] for r in found} == {label}
        assert rows(client, people, filters=[{"field": "ObjectShown", "op": "equals", "value": "DiskWarnPercent"}])[0]["Id"] == other
        assert rows(client, people, filters=[{"field": "ObjectShown", "op": "equals", "value": "pytest-bilinmeyen"}])[0]["Id"] == bilinmeyen

        h = auth(admin)
        r = client.post("/api/audit-log/export", headers=h, json={"fields": ["ObjectShown"], "filters": [{"field": "ObjectShown", "op": "contains", "value": "Disk uyarı"}]})
        assert r.status_code == 200, r.text
        assert list(load_workbook(io.BytesIO(r.content)).worksheets[0].iter_rows(values_only=True))[1:] == [(label,), (label,)]

        for user in (admin, owner):  # System owner'da da ad: maske değil, okunur biçim
            assert client.get(f"/api/audit-log/{first}", headers=auth(user)).json()["object"] == label
        assert [x["id"] for x in client.get(f"/api/audit-log/{first}/history", headers=h).json()["rows"]] == [first, second]
        with db_engine.connect() as c:
            assert c.execute(text("SELECT ObjectKey FROM adm.AuditLog WHERE Id = :i"), {"i": first}).scalar_one() == "DiskWarnPercent"
    finally:
        with db_engine.begin() as c:
            c.execute(text("DELETE FROM adm.AuditLog WHERE Id IN (:a, :b, :c)"), {"a": first, "b": second, "c": other})


def test_system_row_without_user(db_engine, client, people):
    write(db_engine, "Kullanıcı oluşturuldu", None, "Kullanıcı", "pytest-ilk", {"source": "kurulum"})
    row = rows(client, people)[0]
    assert row["ActorName"] == "Sistem" and row["NewText"] == "Kaynak: Kurulum"


def test_date_filter_uses_local_day(db_engine, client, people):
    """Gün sınırı sunucunun yerel gece yarısı; saklanan zaman UTC."""
    audit_id = write(db_engine, "İş iptali", people[ADMIN], "Job", "pytest-gun")
    local_midnight = datetime.combine(date.today(), datetime.min.time()).astimezone()
    just_after = (local_midnight + timedelta(minutes=1)).astimezone(timezone.utc).replace(tzinfo=None)
    with db_engine.begin() as c:
        c.execute(text("UPDATE adm.AuditLog SET At = :t WHERE Id = :i"), {"t": just_after, "i": audit_id})
    today = date.today().isoformat()
    filters = [{"field": "ObjectShown", "op": "equals", "value": "pytest-gun"}, {"field": "At", "op": "between", "from": today, "to": today}]
    found = rows(client, people, filters=filters)
    assert [r["Id"] for r in found] == [audit_id]
    assert found[0]["At"].endswith("+00:00")  # arayüz yerel saate çevirir


# --- geçmiş ---

def test_history_order_limit_and_scope(db_engine, client, people, monkeypatch):
    from app.api.services import audit_log as service
    ids = [write(db_engine, f"İşlem {i}", people[ADMIN], "Job", "pytest-gecmis") for i in range(4)]
    write(db_engine, "Başka", people[ADMIN], "Job", "pytest-baska")
    write(db_engine, "Başka tip", people[ADMIN], "SystemSetting", "pytest-gecmis")
    body = client.get(f"/api/audit-log/{ids[1]}/history", headers=auth(people[ADMIN])).json()
    assert [r["id"] for r in body["rows"]] == ids and body["truncated"] is False

    monkeypatch.setattr(service, "HISTORY_LIMIT", 2)
    body = client.get(f"/api/audit-log/{ids[0]}/history", headers=auth(people[ADMIN])).json()
    assert [r["id"] for r in body["rows"]] == ids[2:] and body["truncated"] is True


def test_no_object_has_no_history(db_engine, client, people):
    audit_id = write(db_engine, "Sistem işlemi", people[ADMIN], None, None)
    h = auth(people[ADMIN])
    assert client.get(f"/api/audit-log/{audit_id}", headers=h).json()["has_object"] is False
    assert client.get(f"/api/audit-log/{audit_id}/history", headers=h).json() == {"rows": [], "truncated": False}
    with db_engine.begin() as c:
        c.execute(text("DELETE FROM adm.AuditLog WHERE Id = :i"), {"i": audit_id})


# --- paylaşılan görünüm izi ---

def view_trace(engine, user_id):
    with engine.connect() as c:
        return [tuple(r) for r in c.execute(text("SELECT Action, OldValue, NewValue FROM adm.AuditLog WHERE ObjectType = N'TableView' AND UserId = :u ORDER BY Id"), {"u": user_id})]


def test_shared_view_changes_are_traced(db_engine, client, people):
    end = people[END_USER]
    key = people[KEY_USER]
    h = auth(key)
    definition = {"v": 1, "columns": [{"field": "At"}], "sort": [], "filters": []}
    private = client.post("/api/audit-log/views", headers=h, json={"name": "Kişisel", "is_shared": False, "definition": definition})
    assert private.status_code in (200, 201), private.text
    assert view_trace(db_engine, key) == []  # kişisel görünüm izsiz
    view_id = private.json()["id"]
    assert client.put(f"/api/audit-log/views/{view_id}", headers=h, json={"name": "Kişisel 2"}).status_code == 200
    assert view_trace(db_engine, key) == []
    assert client.put(f"/api/audit-log/views/{view_id}", headers=h, json={"is_shared": True}).status_code == 200
    trace = view_trace(db_engine, key)
    assert trace[-1][0] == "Paylaşılan görünüm değiştirildi" and json.loads(trace[-1][2]) == {"IsShared": True}
    assert client.delete(f"/api/audit-log/views/{view_id}", headers=h).status_code in (200, 204)
    assert view_trace(db_engine, key)[-1][0] == "Paylaşılan görünüm silindi"

    shared = client.post("/api/materials/views", headers=auth(end), json={"name": "pytest paylaşılan", "is_shared": True, "definition": {"v": 1, "columns": [{"field": "Code"}]}})
    assert shared.status_code in (200, 201), shared.text
    assert view_trace(db_engine, end)[-1][0] == "Paylaşılan görünüm oluşturuldu"
    assert client.delete(f"/api/materials/views/{shared.json()['id']}", headers=auth(end)).status_code in (200, 204)

"""Veri sözlüğü API'si (fonksiyon 96, K-104): liste, etiket, etiketin görünüm ve kurallara etkisi, yetki."""
import io
import json

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.lists import MATERIALS
from app.api.lists.query import ListQueryError
from app.api.lists.request import ExportRequest
from app.api.main import create_app
from app.api.permissions import ADMIN, END_USER, KEY_USER, SYSTEM_OWNER
from app.api.services import export as export_service

from auth_helpers import auth, delete_users, ensure_user

pytestmark = pytest.mark.db

PREFIX = "pytest.sozluk."
FIELD = "/api/field-definitions/Material/AdditionalText2"
MATERIAL_FIELD = "AdditionalText2"


def clean(engine):
    with engine.begin() as c:
        delete_users(c, [r[0] for r in c.execute(text("SELECT Id FROM adm.AppUser WHERE UserName LIKE :p"), {"p": PREFIX + "%"})])
        c.execute(text("DELETE FROM adm.AuditLog WHERE ObjectType = N'FieldDefinition'"))
        c.execute(text("UPDATE adm.FieldDefinition SET Label = NULL WHERE Label LIKE N'pytest%'"))


@pytest.fixture
def people(db_engine):
    clean(db_engine)
    with db_engine.begin() as c:
        out = {r: ensure_user(c, PREFIX + r.replace(" ", "-").lower(), r) for r in (SYSTEM_OWNER, ADMIN, KEY_USER, END_USER)}
    yield out
    clean(db_engine)


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def label(client, owner, value, path=FIELD):
    return client.put(f"{path}/label", headers=auth(owner), json={"label": value})


def error(r):
    return r.status_code, r.json()["error"]["code"]


def test_list_columns_filter_group_and_keys(client, people):
    h = auth(people[SYSTEM_OWNER])
    cols = {c["field"]: c for c in client.get("/api/field-definitions/columns", headers=h).json()["columns"]}
    assert list(cols) == ["TableName", "FieldName", "DisplayLabel", "Description", "FieldClass", "ValuePriority", "ManualOverrides",
                          "EditableInWorkspace", "IsRequired", "IfEmpty", "IsAdditional"]
    assert cols["Description"]["label"] == "Açıklama"
    assert [f for f, c in cols.items() if not c["default_visible"]] == ["Description"]  # Alanlar panelinden açılır
    assert [cols[f]["label"] for f in ("ManualOverrides", "EditableInWorkspace", "IfEmpty")] == ["Manuel", "Senaryo", "Boşsa"]
    assert cols["FieldClass"]["values"] == ["Ana veri", "Parametre", "İşlem verisi"]
    assert cols["IsAdditional"]["type"] == "bool" and cols["TableName"]["values_from_server"] is True

    # görünmeyen kolonda da anahtar döner (satır işlemi)
    r = client.post("/api/field-definitions/query", headers=h, json={"fields": ["DisplayLabel"], "limit": 5, "filters": [
        {"field": "TableName", "op": "in", "values": ["Material"]}, {"field": "IsAdditional", "op": "in", "values": [True]}]})
    assert r.status_code == 200, r.text
    row = r.json()["rows"][0]
    assert row["TableName"] == "Material" and row["FieldName"].startswith("Additional") and "Id" in row
    assert r.json()["filtered"] == 10

    r = client.post("/api/field-definitions/groups", headers=h, json={"group_by": ["FieldClass"], "fields": ["FieldName"]})
    assert {g["key"][0] for g in r.json()["groups"]} == {"Ana veri", "Parametre", "İşlem verisi"}


def test_excel(client, people):
    r = client.post("/api/field-definitions/export", headers=auth(people[SYSTEM_OWNER]), json={
        "fields": ["TableName", "FieldName", "DisplayLabel", "IsRequired", "ManualOverrides", "EditableInWorkspace", "IfEmpty"],
        "filters": [{"field": "TableName", "op": "in", "values": ["Material"]}]})
    assert r.status_code == 200, r.text
    assert "smartchain_veri-sozlugu_2" in r.headers["content-disposition"]
    sheet = load_workbook(io.BytesIO(r.content)).worksheets[0]
    assert [c.value for c in next(sheet.iter_rows())] == ["Tablo", "Alan", "Etiket", "Zorunlu", "Manuel", "Senaryo", "Boşsa"]

    # açıklama kolon açıksa ya da Sütunlar "Tümü" seçilirse çıkar
    r = client.post("/api/field-definitions/export", headers=auth(people[SYSTEM_OWNER]), json={
        "fields": ["FieldName"], "scope": {"columns": "all"},
        "filters": [{"field": "TableName", "op": "in", "values": ["Resource"]}, {"field": "FieldName", "op": "equals", "value": "IsCritical"}]})
    assert r.status_code == 200, r.text
    rows = list(load_workbook(io.BytesIO(r.content)).worksheets[0].iter_rows(values_only=True))
    at = rows[0].index("Açıklama")
    assert rows[1][at] == "1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır)"


def test_detail_and_unknown(client, people):
    h = auth(people[SYSTEM_OWNER])
    d = client.get(FIELD, headers=h).json()
    assert d["standard_label"] == "Ek metin alanı 2" and d["is_additional"] is True and d["label"] is None
    assert d["field_class"] == "Ana veri" and d["used_in_views"] == 0
    assert d["description"] == "Ek metin alanları"
    assert d["options"]["field_class"] == ["Ana veri", "Parametre", "İşlem verisi"]
    assert d["options"]["value_priority"] == ["ERP ezer", "Kural ezer"]
    assert client.get("/api/field-definitions/Material/Name", headers=h).json()["is_additional"] is False
    assert error(client.get("/api/field-definitions/Material/Yok", headers=h)) == (404, "field_not_found")
    assert error(label(client, people[SYSTEM_OWNER], "x", "/api/field-definitions/Yok/Yok")) == (404, "field_not_found")


def test_label_rules_and_audit(db_engine, client, people):
    owner = people[SYSTEM_OWNER]
    r = label(client, owner, "  pytest Müşteri grubu  ")
    assert r.status_code == 200 and r.json()["label"] == "pytest Müşteri grubu"
    assert error(label(client, owner, "x" * 41)) == (422, "validation")

    # aynı tabloda aynı etiket; başka tabloda serbest
    r = label(client, owner, "PYTEST müşteri grubu", "/api/field-definitions/Material/AdditionalText3")
    assert error(r) == (409, "label_taken")
    assert error(label(client, owner, "Malzeme adı", "/api/field-definitions/Material/AdditionalText3")) == (409, "label_taken")
    assert label(client, owner, "pytest Müşteri grubu", "/api/field-definitions/Customer/AdditionalText1").status_code == 200

    # aynı değer iz yazmaz
    with db_engine.connect() as c:
        def count():
            return c.execute(text("SELECT COUNT(*) FROM adm.AuditLog WHERE ObjectKey = N'Material.AdditionalText2'")).scalar_one()
        assert count() == 1
        label(client, owner, "pytest Müşteri grubu")
        assert count() == 1
        row = c.execute(text("SELECT Action, UserId, ObjectType, OldValue, NewValue FROM adm.AuditLog "
                             "WHERE ObjectKey = N'Material.AdditionalText2'")).one()
    assert tuple(row)[:3] == ("Alan etiketi değişikliği", owner, "FieldDefinition")
    assert json.loads(row[3]) == {"Label": None} and json.loads(row[4]) == {"Label": "pytest Müşteri grubu"}


def test_standard_field_label_overrides_and_returns(client, people):
    owner = people[SYSTEM_OWNER]
    path = "/api/field-definitions/Material/Name"
    h = auth(owner)
    def name_label():
        return next(c["label"] for c in client.get("/api/materials/columns", headers=h).json()["columns"] if c["field"] == "Name")
    assert name_label() == "Malzeme adı"
    assert label(client, owner, "pytest Ad", path).status_code == 200
    assert name_label() == "pytest Ad"
    r = client.post("/api/materials/export", headers=h, json={"fields": ["Code", "Name"]})
    assert "pytest Ad" in [c.value for c in next(load_workbook(io.BytesIO(r.content)).worksheets[0].iter_rows())]
    assert label(client, owner, "", path).json()["label"] is None
    assert name_label() == "Malzeme adı"


def test_label_effect_on_views_and_rules(db_engine, client, people):
    """K-104: görünüm alan adını saklar. Etiket silinince alan düşer, kayıt değişmez; etiket dönünce görünüm döner."""
    owner = people[SYSTEM_OWNER]
    h = auth(owner)
    fields = lambda: [c["field"] for c in client.get("/api/materials/columns", headers=h).json()["columns"]]
    assert MATERIAL_FIELD not in fields()
    assert label(client, owner, "pytest Müşteri grubu").status_code == 200
    assert MATERIAL_FIELD in fields()

    rule = {"id": "k1", "enabled": True, "field": MATERIAL_FIELD, "condition": {"op": "empty"}, "format": {"bold": True}}
    r = client.post("/api/materials/views", headers=h, json={"name": "pytest Sözlük", "is_shared": True, "definition": {
        "columns": [{"field": "Code"}, {"field": MATERIAL_FIELD}], "sort": [{"field": MATERIAL_FIELD, "dir": "asc"}], "rules": [rule]}})
    assert r.status_code == 201, r.text
    view_id = r.json()["id"]
    d = client.get(FIELD, headers=h).json()
    assert (d["used_in_views"], d["used_in_rules"]) == (1, 1)

    def view(user):
        return next(v for v in client.get("/api/materials/views", headers=auth(user)).json()["views"] if v["id"] == view_id)

    # etiket değişince yalnız başlık değişir
    assert label(client, owner, "pytest Yeni ad").status_code == 200
    assert view(owner)["warnings"] == []

    # ek alan etiketi silinince alan listeden kalkar; görünüm ayıklanır, herkes için; uyarı okunur adla
    assert label(client, owner, "").json()["label"] is None
    assert MATERIAL_FIELD not in fields()
    for user in (owner, people[END_USER]):
        got = view(user)
        assert got["warnings"] == ["'Ek metin alanı 2' artık listede yok; görünümden çıkarıldı."]
        assert [c["field"] for c in got["definition"]["columns"]] == ["Code"]
        assert got["definition"]["sort"] == [] and got["definition"]["rules"] == []
    with db_engine.connect() as c:
        stored = c.execute(text("SELECT Definition FROM adm.TableView WHERE Id = :i"), {"i": view_id}).scalar_one()
    assert MATERIAL_FIELD in stored  # kayıt değişmedi

    # açık sekmedeki eski istek ve sıradaki arka plan işi hata alır
    assert client.post("/api/materials/query", headers=h, json={"fields": ["Code", MATERIAL_FIELD]}).status_code == 422
    with Session(db_engine) as s, pytest.raises(ListQueryError):
        export_service._plan(s, MATERIALS, owner, ExportRequest(fields=["Code", MATERIAL_FIELD]))

    # etiket dönünce görünüm eski hâliyle
    assert label(client, owner, "pytest Müşteri grubu").status_code == 200
    got = view(owner)
    assert got["warnings"] == [] and [c["field"] for c in got["definition"]["columns"]] == ["Code", MATERIAL_FIELD]
    assert got["definition"]["rules"][0]["field"] == MATERIAL_FIELD


def test_field_ref_rule_counts_and_drops(client, people):
    owner = people[SYSTEM_OWNER]
    h = auth(owner)
    assert label(client, owner, "pytest Sayı", "/api/field-definitions/Material/AdditionalNumber1").status_code == 200
    rule = {"id": "k1", "enabled": True, "field": "SafetyStock", "condition": {"op": "gt", "field_ref": "AdditionalNumber1"}, "format": {"bold": True}}
    r = client.post("/api/materials/views", headers=h, json={"name": "pytest Referans", "definition": {
        "columns": [{"field": "Code"}, {"field": "SafetyStock"}], "rules": [rule]}})
    assert r.status_code == 201, r.text
    d = client.get("/api/field-definitions/Material/AdditionalNumber1", headers=h).json()
    assert (d["used_in_views"], d["used_in_rules"]) == (1, 1)
    assert label(client, owner, "", "/api/field-definitions/Material/AdditionalNumber1").status_code == 200
    got = next(v for v in client.get("/api/materials/views", headers=h).json()["views"] if v["id"] == r.json()["id"])
    assert got["definition"]["rules"] == [] and got["warnings"] == ["'Ek sayı alanı 1' artık listede yok; görünümden çıkarıldı."]


@pytest.mark.parametrize("role", [ADMIN, KEY_USER, END_USER])
def test_only_system_owner(client, people, role):
    h = auth(people[role])
    for r in (client.get("/api/field-definitions/columns", headers=h), client.post("/api/field-definitions/query", headers=h, json={}),
              client.get(FIELD, headers=h), client.put(f"{FIELD}/label", headers=h, json={"label": "x"}),
              client.post("/api/field-definitions/export", headers=h, json={"fields": ["FieldName"]})):
        assert error(r) == (403, "forbidden"), r.url
        assert "System owner yetkisi gerekir" in r.json()["error"]["message"]


def test_no_write_path_for_other_attributes(client, people):
    h = auth(people[SYSTEM_OWNER])
    assert client.put(FIELD, headers=h, json={"is_required": True}).status_code == 405
    r = client.put(f"{FIELD}/label", headers=h, json={"label": "pytest", "is_required": True})
    assert r.status_code == 200 and client.get(FIELD, headers=h).json()["is_required"] is False

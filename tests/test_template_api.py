"""Excel şablonu API'si (ekran 02, fonksiyon 02; K-110): yetki, etiket, kod listesi, iz, varlık listesi."""
import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import text

from app.api.main import create_app
from app.api.permissions import ADMIN, END_USER, KEY_USER, SYSTEM_OWNER
from app.integration import contract

from auth_helpers import auth, delete_users, ensure_user

pytestmark = pytest.mark.db

PREFIX = "pytest.sablon."
TRIGGER = "adm.TR_AuditLog_Sablon"
ROLES = (SYSTEM_OWNER, ADMIN, KEY_USER, END_USER)


def clean(engine):
    with engine.begin() as c:
        c.execute(text(f"DROP TRIGGER IF EXISTS {TRIGGER}"))
        ids = [r[0] for r in c.execute(text("SELECT Id FROM adm.AppUser WHERE UserName LIKE :p"), {"p": PREFIX + "%"})]
        c.execute(text("DELETE FROM adm.AuditLog WHERE ObjectType = N'Template' OR ObjectType = N'data-entities'"))
        c.execute(text("UPDATE adm.FieldDefinition SET Label = NULL WHERE TableName = N'Resource' AND FieldName IN (N'AdditionalNumber1', N'Name')"))
        c.execute(text("DELETE FROM adm.SystemEvent WHERE Component = N'Denetim izi'"))
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


def sheet(response, name="Kaynak"):
    return load_workbook(io.BytesIO(response.content))[name]


@pytest.mark.parametrize("role, allowed", [(SYSTEM_OWNER, True), (ADMIN, True), (KEY_USER, True), (END_USER, False)])
@pytest.mark.parametrize("url", ["/api/templates/Resource", "/api/templates/Resource/info", "/api/data-entities/columns"])
def test_roles(client, people, role, allowed, url):
    assert client.get(url, headers=auth(people[role])).status_code == (200 if allowed else 403)


@pytest.mark.parametrize("url", ["/api/templates/Yok", "/api/templates/Yok/info"])
def test_unknown_entity(client, people, url):
    r = client.get(url, headers=auth(people[KEY_USER]))
    assert r.status_code == 404 and r.json()["error"]["code"] == "entity_not_found" and r.json()["error"]["message"] == "Tablo bulunamadı."


def test_download_writes_trace_and_info_does_not(db_engine, client, people):
    h = auth(people[KEY_USER])
    assert client.get("/api/templates/Resource/info", headers=h).status_code == 200
    with db_engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM adm.AuditLog WHERE ObjectType = N'Template'")).scalar_one() == 0

    r = client.get("/api/templates/Resource", headers=h)
    assert r.status_code == 200 and "smartchain_kaynak_v3.xlsx" in r.headers["content-disposition"]
    assert [c.value for c in sheet(r)[1]] == [f.name for f in contract.fields("Resource")]

    with db_engine.connect() as c:
        row = c.execute(text("SELECT TOP 1 Id, Action, UserId, ObjectKey FROM adm.AuditLog WHERE ObjectType = N'Template' ORDER BY Id DESC")).one()
    assert (row.Action, row.UserId, row.ObjectKey) == ("Şablon indirme", people[KEY_USER], "smartchain_kaynak_v3.xlsx")
    seen = client.get(f"/api/audit-log/{row.Id}", headers=auth(people[ADMIN])).json()
    assert seen["object_type"] == "Şablon"
    assert {c["field"]: c["new"] for c in seen["changes"]} == {"Tablo": "Kaynak", "Sürüm": "3", "Alan sayısı": "17"}


def test_no_file_without_trace(db_engine, client, people):
    with db_engine.begin() as c:
        c.execute(text(f"CREATE TRIGGER {TRIGGER} ON adm.AuditLog INSTEAD OF INSERT AS THROW 50001, 'iz yazılamıyor', 1;"))
    r = client.get("/api/templates/Resource", headers=auth(people[KEY_USER]))
    assert r.status_code == 503 and r.json()["error"]["code"] == "audit_failed" and not r.content.startswith(b"PK")
    with db_engine.connect() as c:
        assert c.execute(text("SELECT Message FROM adm.SystemEvent WHERE Component = N'Denetim izi'")).scalars().all() == ["Denetim kaydı yazılamadı · Şablon indirme"]


def test_labels_from_dictionary_version_stays(db_engine, client, people):
    with db_engine.begin() as c:
        c.execute(text("UPDATE adm.FieldDefinition SET Label = N'Birim ağırlık' WHERE TableName = N'Resource' AND FieldName = N'AdditionalNumber1'"))
        c.execute(text("UPDATE adm.FieldDefinition SET Label = N'Tezgâh adı' WHERE TableName = N'Resource' AND FieldName = N'Name'"))
    h = auth(people[KEY_USER])
    r = client.get("/api/templates/Resource", headers=h)
    assert "smartchain_kaynak_v3.xlsx" in r.headers["content-disposition"]
    assert "AdditionalNumber1" in [c.value for c in sheet(r)[1]]
    labels = {row[0]: row[1] for row in sheet(r, "Açıklama").iter_rows(min_row=3, values_only=True)}
    assert labels["AdditionalNumber1"] == "Birim ağırlık" and labels["Name"] == "Tezgâh adı"
    info = client.get("/api/templates/Resource/info", headers=h).json()
    assert info["field_count"] == 18 and info["version"] == 3

    body = {"fields": ["Name", "FieldCount"], "filters": [{"field": "Name", "op": "equals", "value": "Kaynak"}]}
    assert client.post("/api/data-entities/query", headers=h, json=body).json()["rows"][0]["FieldCount"] == 18


def test_info_lists_required_fields(client, people):
    info = client.get("/api/templates/Resource/info", headers=auth(people[KEY_USER])).json()
    assert info["required"] == ["Lokasyon kodu", "Kaynak kodu"]
    assert set(info) == {"entity", "name", "version", "file_name", "field_count", "required"}


def test_entity_list_sorts_filters_and_exports(client, people):
    h = auth(people[KEY_USER])
    cols = {c["field"]: c for c in client.get("/api/data-entities/columns", headers=h).json()["columns"]}
    assert list(cols) == ["Name", "Method", "IsPullEnabled", "Validation", "EntityClass", "Description", "Version", "FieldCount", "RequiredCount", "LastLoadAt", "CatalogOrder", "Entity", "ViewName"]
    assert {f: c["label"] for f, c in cols.items()} == {"Name": "Tablo", "Method": "Yöntem", "IsPullEnabled": "Çekim", "Validation": "Validasyon", "ViewName": "View", "EntityClass": "Kategori", "Description": "Açıklama", "Version": "Sürüm", "FieldCount": "Toplam alan", "RequiredCount": "Zorunlu alan",
                                                        "LastLoadAt": "Son yükleme zamanı", "CatalogOrder": "Yükleme sırası", "Entity": "Teknik tablo adı"}
    assert [f for f, c in cols.items() if not c["default_visible"]] == ["Entity", "ViewName"] and cols["EntityClass"]["values"] == ["Ana veri", "İşlem verisi"]

    # satır menüsü gizli kolonları da okur
    only = client.post("/api/data-entities/query", headers=h, json={"fields": ["EntityClass"], "limit": 1}).json()["rows"][0]
    assert only["Entity"] == "Location" and only["Name"] == "Lokasyon" and only["Version"] == 3

    fields = ["Name", "EntityClass", "Description", "Version", "FieldCount", "RequiredCount"]
    body = client.post("/api/data-entities/query", headers=h, json={"fields": fields, "limit": 100}).json()
    assert [r["Name"] for r in body["rows"]] == [e.name for e in contract.ENTITIES] and body["total"] == 25
    assert all(r["Entity"] for r in body["rows"])  # satır menüsü gizli kolonu da okur
    resource = next(r for r in body["rows"] if r["Name"] == "Kaynak")
    assert (resource["Version"], resource["FieldCount"], resource["RequiredCount"]) == (3, 17, 2)
    assert resource["Description"] == "Makine, işçi ve fason kaynakları"

    sorted_rows = client.post("/api/data-entities/query", headers=h, json={"fields": fields, "limit": 100, "sort": [{"field": "FieldCount", "dir": "desc"}]}).json()["rows"]
    assert sorted_rows[0]["FieldCount"] >= sorted_rows[-1]["FieldCount"]
    only = client.post("/api/data-entities/query", headers=h, json={"fields": fields, "limit": 100, "filters": [{"field": "EntityClass", "op": "in", "values": ["İşlem verisi"]}]}).json()
    assert only["filtered"] == sum(e.data_class == "İşlem verisi" for e in contract.ENTITIES)

    r = client.post("/api/data-entities/export", headers=h, json={"fields": fields})
    assert r.status_code == 200, r.text
    rows = list(load_workbook(io.BytesIO(r.content)).worksheets[0].iter_rows(values_only=True))
    assert rows[0][0] == "Tablo" and len(rows) == 26

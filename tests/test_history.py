"""Değişiklik geçmişi ve detay kartı (K-171, K-173; fonksiyon 14): aktarım, manuel değer ve Lokasyon adm.FieldChange'e yazar; eski geçmişin
doldurulması; Geçmiş listesi (biçim, kaynak metni, End user okur); kaydın kartı ve İlişkili kayıtlar; denetim izinde "Kayda git" hedefi.

Aktarım testleri aktarım testinin verisiyle commit'siz oturumda (geri alınır); API testleri sentetik v0'da, kendi yazdıklarını geri alır.
"""
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import history
from app.api.main import create_app
from app.api.permissions import END_USER, KEY_USER, SYSTEM_OWNER
from app.api.services import audit_log as audit_service, manual_values as manual_service
from app.history.backfill import backfill
from app.manual import core_table
from app.transfer import engine as transfer

from auth_helpers import auth, ensure_user
from test_transfer import DATA, L1, core_rows, loc_id, set_prc
from test_validation_references import put
from validation_helpers import clean


# ------------------------------------------------------------------ biçim (veritabanısız)

@pytest.mark.parametrize("table, field, text, expected", [
    ("Material", "SafetyStock", "1234.5", "1.234,5"), ("Material", "GoodsReceiptDays", "3", "3"), ("Material", "ScrapRatio", "0.05", "%5,00"),
    ("Material", "IsCritical", "1", "Evet"), ("Material", "IsCritical", "0", "Hayır"), ("SalesOrderLine", "RequestedDate", "2026-11-13", "13.11.2026"),
    ("Material", "MaterialGroup", "Alt montaj", "Alt montaj"), ("Material", None, "x", "x"), ("Material", "SafetyStock", None, None),
])
def test_format_value(table, field, text, expected):
    decimals = {"GoodsReceiptDays": 0, "ScrapRatio": 2}
    assert history.format_value(table, field, text, decimals, frozenset({"ScrapRatio"})) == expected


# ------------------------------------------------------------------ aktarım ve manuel değer yazar (commit'siz)

@pytest.fixture(scope="module")
def staged(db_engine):
    clean(db_engine)
    put(db_engine, DATA)
    yield db_engine
    clean(db_engine)


@pytest.fixture
def s(staged):
    with Session(staged) as session:
        yield session
        session.rollback()


@pytest.fixture(scope="module")
def actor(db_engine):
    with db_engine.begin() as c:
        return SimpleNamespace(id=ensure_user(c, "pytest.fc.actor", KEY_USER))


def changes(s, table, key, version=None) -> list[dict]:
    q = "SELECT * FROM adm.FieldChange WHERE TableName = :t AND RecordKey = :k" + (" AND DataVersionId = :v" if version else "") + " ORDER BY Id"
    return [dict(r) for r in s.execute(sa.text(q), {"t": table, "k": str(key), "v": version}).mappings()]


def material_id(s, code="T-OK"):
    return core_rows(s, "Material", "Code = :c AND LocationId = :l", c=code, l=loc_id(s, L1))[0]["Id"]


def test_transfer_writes_created_changed_closed(s, actor):
    v1 = transfer.run_transfer(s, actor.id)["data_version"]
    mid = material_id(s)
    created = changes(s, "Material", mid, v1)
    assert [(c["ChangeType"], c["FieldName"], c["Source"], c["UserId"]) for c in created] == [("Oluştu", None, "Aktarım", actor.id)]
    set_prc(s, "Material", "Code = N'T-OK' AND LocationCode = N'TL-1'", MaterialGroup="G2", SafetyStock=12.5)
    v2 = transfer.run_transfer(s, None)["data_version"]
    rows = {c["FieldName"]: c for c in changes(s, "Material", mid, v2)}
    assert (rows["MaterialGroup"]["OldValue"], rows["MaterialGroup"]["NewValue"], rows["MaterialGroup"]["ChangeType"]) == ("G1", "G2", "Değişti")
    assert rows["SafetyStock"]["OldValue"] is None and float(rows["SafetyStock"]["NewValue"]) == 12.5
    assert set(rows) == {"MaterialGroup", "SafetyStock"}                                             # yalnız değişen alanlar
    pas = material_id(s, "T-PAS")
    set_prc(s, "Material", "Code = N'T-PAS'", IsActive=False)
    v3 = transfer.run_transfer(s, None)["data_version"]
    assert [c["ChangeType"] for c in changes(s, "Material", pas, v3)] == ["Kapandı"]
    assert changes(s, "Material", mid, v3) == []                                                      # değişmeyen kayıtta satır yok


def test_manual_value_and_kept_underlying(s, actor):
    transfer.run_transfer(s, None)
    mid = material_id(s)
    mat = manual_service.Target("materials", "Material", "Malzeme listesi")
    manual_service._write(s, actor, mat, core_table("Material"), str(mid), "MaterialGroup", "ELLE")
    row = changes(s, "Material", mid)[-1]
    assert (row["Source"], row["OldValue"], row["NewValue"], row["UserId"], row["FieldName"]) == ("Manuel değer", "G1", "ELLE", actor.id, "MaterialGroup")
    set_prc(s, "Material", "Code = N'T-OK' AND LocationCode = N'TL-1'", MaterialGroup="G3")             # ERP değişti, manuel değer korunur
    v = transfer.run_transfer(s, None)["data_version"]
    kept = [c for c in changes(s, "Material", mid, v) if c["FieldName"] == "MaterialGroup"]
    assert [(c["OldValue"], c["NewValue"], c["Note"]) for c in kept] == [("G1", "G3", history.MANUAL_KEPT)]
    rows = s.execute(sa.text("SELECT * FROM adm.ManualValue WHERE TableName = N'Material' AND RecordKey = :k"), {"k": str(mid)}).all()
    manual_service._restore(s, actor, mat, core_table("Material"), rows)
    row = changes(s, "Material", mid)[-1]
    assert (row["Source"], row["OldValue"], row["NewValue"]) == ("Manuel değer kaldırma", "ELLE", "G3")


def test_location_changes(s):
    transfer.run_transfer(s, None)
    lid = loc_id(s, L1)
    set_prc(s, "Location", "Code = N'TL-1'", Name="Test 1 yeni")
    v = transfer.run_transfer(s, None)["data_version"]
    assert [(c["FieldName"], c["OldValue"], c["NewValue"]) for c in changes(s, "Location", lid, v)] == [("Name", "Test 1", "Test 1 yeni")]
    set_prc(s, "Location", "Code = N'TL-2'", IsActive=False)
    v = transfer.run_transfer(s, None)["data_version"]
    assert [c["ChangeType"] for c in changes(s, "Location", loc_id(s, "TL-2"), v)] == ["Kapandı"]


def test_backfill_from_versions(s):
    transfer.run_transfer(s, None)
    mid = material_id(s)
    set_prc(s, "Material", "Code = N'T-OK' AND LocationCode = N'TL-1'", MaterialGroup="G9")
    v = transfer.run_transfer(s, None)["data_version"]
    s.execute(sa.text("DELETE FROM adm.FieldChange"))
    counts = backfill(s.connection())
    assert counts["Material"] > 0 and counts["Location"] > 0
    rows = changes(s, "Material", mid)
    assert rows[0]["ChangeType"] == "Oluştu"
    assert [(c["OldValue"], c["NewValue"], c["DataVersionId"]) for c in rows if c["FieldName"] == "MaterialGroup"] == [("G1", "G9", v)]
    assert backfill(s.connection()) == {}                                                             # bir kez


# ------------------------------------------------------------------ API (sentetik v0)

@pytest.fixture(scope="module")
def people(db_engine):
    with db_engine.begin() as c:
        return {SYSTEM_OWNER: ensure_user(c, "pytest.fc.owner", SYSTEM_OWNER), KEY_USER: ensure_user(c, "pytest.fc.key", KEY_USER),
                END_USER: ensure_user(c, "pytest.fc.end", END_USER, "Gecmis End")}


@pytest.fixture
def api(db_engine, people):
    client = TestClient(create_app(), raise_server_exceptions=False)
    yield client
    with db_engine.begin() as c:  # artık kalmasın: testin manuel değeri ve geçmiş satırları
        c.execute(sa.text("DELETE FROM adm.FieldChange WHERE TableName = N'Customer' AND Source LIKE N'Manuel%'"))
        c.execute(sa.text("UPDATE adm.FieldDefinition SET ManualOverrides = 0 WHERE TableName = N'Customer'"))


def customer(db_engine) -> dict:
    with db_engine.connect() as c:
        return dict(c.execute(sa.text("SELECT TOP 1 Id, Code, Name FROM core.Customer WHERE VersionTo IS NULL ORDER BY Code")).mappings().one())


def history_rows(api, headers, table, key):
    return api.post("/api/record-history/query", headers=headers, json={
        "fields": ["At", "DataVersion", "FieldLabel", "OldValue", "NewValue", "SourceText"],
        "filters": [{"field": "TableName", "op": "in", "values": [table]}, {"field": "RecordKey", "op": "in", "values": [str(key)]}]})


def test_history_list_record_card_and_audit_target(api, people, db_engine):
    c0 = customer(db_engine)
    key = auth(people[KEY_USER])
    assert api.put("/api/field-definitions/Customer/Name/manual", headers=auth(people[SYSTEM_OWNER]), json={"on": True}).status_code == 200
    assert api.post("/api/manual-values", headers=key, json={"list": "master-customer", "changes": [{"id": c0["Id"], "field": "Name", "value": "Geçmiş adı"}]}).status_code == 200
    assert api.post("/api/manual-values/remove", headers=key, json={"list": "master-customer", "items": [{"id": c0["Id"], "field": "Name"}]}).status_code == 200
    r = history_rows(api, auth(people[END_USER]), "Customer", c0["Id"])                                # End user okur (K-173)
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    assert rows[0]["SourceText"] == "Manuel değer kaldırıldı · pytest.fc.key" and rows[0]["FieldLabel"] == "Müşteri adı"
    assert (rows[1]["OldValue"], rows[1]["NewValue"], rows[1]["SourceText"]) == (c0["Name"], "Geçmiş adı", "Manuel değer · pytest.fc.key")
    created = next(x for x in rows if x["NewValue"] == "Kayıt oluştu")
    assert created["FieldLabel"] == "—" and created["SourceText"].startswith("Aktarım · ") and created["DataVersion"].startswith("v")
    card = api.get(f"/api/records/master-customer/{c0['Id']}", headers=auth(people[END_USER])).json()
    assert (card["code"], card["name"], card["current"], card["closed_version"]) == (c0["Code"], c0["Name"], True, None)
    rel = {x["key"]: x for x in card["relations"]}
    assert set(rel) == {"sales-order", "project"} and rel["sales-order"]["list"] == "transaction-sales-order"
    ids = rel["sales-order"]["filters"][0]["values"]
    q = api.post("/api/transaction-sales-order/query", headers=key, json={"fields": ["OrderNo"], "filters": rel["sales-order"]["filters"]}).json()
    assert q["filtered"] == len(ids) == rel["sales-order"]["count"]
    assert api.get("/api/records/master-customer/999999999", headers=key).status_code == 404
    assert api.get("/api/records/nope/1", headers=key).status_code == 404
    with db_engine.connect() as c:
        audit_id = c.execute(sa.text("SELECT MAX(Id) FROM adm.AuditLog WHERE ObjectType = N'Manuel değer'")).scalar()
    detail = api.get(f"/api/audit-log/{audit_id}", headers=key).json()
    assert detail["target"] == {"list": "master-customer", "id": str(c0["Id"])}


def test_material_relations(api, people, db_engine):
    with db_engine.connect() as c:
        mid = c.execute(sa.text("SELECT TOP 1 m.Id FROM core.Material m WHERE m.VersionTo IS NULL AND EXISTS (SELECT 1 FROM core.ProductionVersion p "
                                "WHERE p.MaterialId = m.Id AND p.VersionTo IS NULL) ORDER BY m.Code")).scalar()
    card = api.get(f"/api/records/materials/{mid}", headers=auth(people[KEY_USER])).json()
    keys = [x["key"] for x in card["relations"]]
    assert keys == ["production-version", "bom", "where-used", "routing", "material-supplier", "uom-conversion", "material-reference"]
    pv = next(x for x in card["relations"] if x["key"] == "production-version")
    assert pv["count"] > 0
    tx = api.get(f"/api/records/transaction-sales-order/{customer_order(db_engine)}", headers=auth(people[KEY_USER])).json()
    assert tx["relations"] == [] and tx["current"] is True                                            # İşlem verisi'nde İlişkili kayıtlar yok


def test_multi_selection_ids_card_and_history(api, people, db_engine):
    """Çoklu seçim (K-171): filtredeki kimlikler, seçili kayıtların ilişkilerinin birleşimi, Geçmiş'te Kayıt kolonu, çok değerli filtre."""
    key = auth(people[KEY_USER])
    with db_engine.connect() as c:
        rows = c.execute(sa.text("SELECT Id, Code FROM core.Customer WHERE VersionTo IS NULL ORDER BY Code")).mappings().all()
    r = api.post("/api/master-customer/ids", headers=key, json={"filters": []})
    assert r.status_code == 200, r.text
    assert r.json() == {"ids": [str(x["Id"]) for x in rows], "truncated": False}
    first = api.post("/api/master-customer/ids", headers=key, json={"filters": [{"field": "Code", "op": "equals", "value": rows[0]["Code"]}]}).json()
    assert first["ids"] == [str(rows[0]["Id"])]
    ids = [str(x["Id"]) for x in rows]
    many = api.post("/api/records/master-customer/many", headers=auth(people[END_USER]), json={"ids": ids}).json()
    singles = [api.get(f"/api/records/master-customer/{i}", headers=key).json() for i in ids]
    union = {k: sorted({v for card in singles for rel in card["relations"] if rel["key"] == k for v in rel["filters"][0]["values"] if v != "0"}, key=int)
             for k in ("sales-order", "project")}
    got = {rel["key"]: sorted((v for v in rel["filters"][0]["values"] if v != "0"), key=int) for rel in many["relations"]}
    assert got == union and many["ids"] == ids and many["table"] == "Customer"
    assert api.post("/api/records/nope/many", headers=key, json={"ids": ids}).status_code == 404
    assert api.post("/api/records/master-customer/many", headers=key, json={"ids": ["x"]}).status_code == 422
    # Geçmiş: Kayıt kolonu kaydın kodu
    h = api.post("/api/record-history-many/query", headers=key, json={
        "fields": ["RecordLabel", "NewValue"],
        "filters": [{"field": "TableName", "op": "in", "values": ["Customer"]}, {"field": "RecordKey", "op": "in", "values": ids}]})
    assert h.status_code == 200, h.text
    assert {x["RecordLabel"] for x in h.json()["rows"]} <= {x["Code"] for x in rows} and h.json()["rows"]
    sales = api.post("/api/record-history-many/query", headers=key, json={
        "fields": ["RecordLabel"], "filters": [{"field": "TableName", "op": "in", "values": ["SalesOrderLine"]}, {"field": "RecordKey", "op": "in", "values": [str(customer_order(db_engine))]}]}).json()
    assert all(" / " in x["RecordLabel"] for x in sales["rows"])                                       # sipariş satırında "kod / satır"
    # Çok değerli liste filtresi: 2.100 parametre sınırını aşar (metin olarak gömülür)
    big = [str(i) for i in range(1, 3000)] + ids
    q = api.post("/api/master-customer/query", headers=key, json={"fields": ["Code"], "filters": [{"field": "Id", "op": "in", "values": big}]})
    assert q.status_code == 200, q.text
    assert q.json()["filtered"] == len(rows)


def customer_order(db_engine) -> int:
    with db_engine.connect() as c:
        return c.execute(sa.text("SELECT TOP 1 Id FROM core.SalesOrderLine WHERE VersionTo IS NULL ORDER BY Id")).scalar()


def test_audit_target_from_old_row_by_code(db_engine):
    with Session(db_engine) as s:
        c0 = s.execute(sa.text("SELECT TOP 1 Id, Code FROM core.Customer WHERE VersionTo IS NULL ORDER BY Code")).one()
        got = audit_service.record_target(s, "Manuel değer", f"Müşteri · {c0.Code}", '{"list": "master-customer", "field": "Name", "Value": "x"}')
        assert got == {"target": {"list": "master-customer", "id": str(c0.Id)}}
        assert audit_service.record_target(s, "Manuel değer", "Müşteri · YOK-KOD", '{"list": "master-customer"}')["target_reason"] == audit_service.TARGET_NOT_FOUND
        assert audit_service.record_target(s, "Kullanıcı", "x", None) == {}

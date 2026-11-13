"""Manuel değer (K-170; fonksiyon 11, 12, 13): Manuel olabilecek alan, aktarımda koruma, alttaki değer değişince işaret, kaldırma, kaydetme ve
doğrulama, veri sözlüğünde Manuel, liste kolonu ve hücre kaynağı, yetki.

Aktarım testleri aktarım testinin verisiyle commit'siz oturumda (geri alınır); API testleri sentetik v0'da, kendi değişikliklerini geri alır.
"""
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.api.permissions import END_USER, KEY_USER, SYSTEM_OWNER
from app.api.services import manual_values as service
from app.manual import ACTIVE_REASON, CAPACITY_REASON, KEY_REASON, RELATION_REASON, SYSTEM_REASON, TABLE_REASON, core_table, not_manual_reason, state_column
from app.transfer import engine as transfer

from auth_helpers import auth, ensure_user
from test_transfer import DATA, L1, core_rows, loc_id, set_prc
from test_validation_references import put
from validation_helpers import clean


# ------------------------------------------------------------------ hangi alan Manuel olabilir (veritabanısız)

@pytest.mark.parametrize("table, field, reason", [
    ("Material", "Name", None), ("Material", "MaterialGroup", None), ("Material", "SafetyStock", None), ("UnitOfMeasure", "Decimals", None),
    ("Material", "Code", KEY_REASON), ("Routing", "RouteCode", KEY_REASON), ("SalesOrderLine", "OrderNo", KEY_REASON),
    ("BOM", "ComponentMaterialId", KEY_REASON), ("SalesOrderLine", "CustomerId", RELATION_REASON), ("Routing", "ResourceId", RELATION_REASON), ("ProductionVersion", "BOMCode", RELATION_REASON),
    ("Material", "Id", SYSTEM_REASON), ("Material", "UpdatedAt", SYSTEM_REASON), ("WorkOrderComponent", "RemainingQuantity", SYSTEM_REASON),
    ("Material", "IsActive", ACTIVE_REASON), ("Resource", "DailyCapacity", CAPACITY_REASON), ("Calendar", "Name", TABLE_REASON),
])
def test_manual_capable_fields(table, field, reason):
    assert not_manual_reason(table, field) == reason


# ------------------------------------------------------------------ aktarımda koruma (commit'siz)

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
        return SimpleNamespace(id=ensure_user(c, "pytest.elle.actor", KEY_USER))


MAT = service.Target("materials", "Material", "Malzeme listesi")
LOC = service.Target("master-location", "Location", "Lokasyon")


def manual_row(s, table, key, field):
    return s.execute(sa.text("SELECT * FROM adm.ManualValue WHERE TableName = :t AND RecordKey = :k AND FieldName = :f"),
                     {"t": table, "k": str(key), "f": field}).mappings().first()


def material(s):
    return core_rows(s, "Material", "Code = N'T-OK' AND LocationId = :l", l=loc_id(s, L1))[0]


def test_manual_value_survives_transfer_and_marks_changed_underlying(s, actor):
    v1 = transfer.run_transfer(s, None)["data_version"]
    m = material(s)
    service._write(s, actor, MAT, core_table("Material"), str(m["Id"]), "MaterialGroup", "ELLE")
    service._write(s, actor, MAT, core_table("Material"), str(m["Id"]), "SafetyStock", 12.5)
    after = material(s)
    assert (after["MaterialGroup"], float(after["SafetyStock"]), after["VersionFrom"]) == ("ELLE", 12.5, v1)  # yerinde, yeni versiyon yok
    mv = manual_row(s, "Material", m["Id"], "MaterialGroup")
    assert (mv["Value"], mv["BaseValue"], mv["UnderlyingValue"], mv["UnderlyingSource"], mv["IsBaseChanged"]) == ("ELLE", "G1", "G1", "ERP", False)

    r2 = transfer.run_transfer(s, None)  # ERP aynı: manuel değer kalır, yalnız elle farkı yeni versiyon açmaz
    again = material(s)
    assert (again["MaterialGroup"], float(again["SafetyStock"]), again["VersionFrom"]) == ("ELLE", 12.5, v1)
    assert {t["entity"]: t for t in r2["tables"]}["Material"]["changed"] == 0
    assert manual_row(s, "Material", m["Id"], "SafetyStock")["IsBaseChanged"] is False  # sayı metni tipli karşılaştırılır

    set_prc(s, "Material", "Code = N'T-OK' AND LocationCode = N'TL-1'", MaterialGroup="G2")  # ERP değişti
    transfer.run_transfer(s, None)
    third = material(s)
    assert third["MaterialGroup"] == "ELLE"
    mv = manual_row(s, "Material", m["Id"], "MaterialGroup")
    assert (mv["BaseValue"], mv["UnderlyingValue"], mv["IsBaseChanged"]) == ("G1", "G2", True)
    t = core_table("Material")
    state = lambda: s.execute(sa.select(state_column("Material", t)).where(t.c.Id == m["Id"], t.c.VersionTo.is_(None))).scalar()
    assert state() == "Var / ERP Güncellendi"  # K-172
    s.execute(sa.text("UPDATE adm.ManualValue SET UnderlyingSource = N'Kural' WHERE TableName = N'Material' AND RecordKey = :k"), {"k": str(m["Id"])})
    assert state() == "Var / Kural Güncellendi"
    s.execute(sa.text("UPDATE adm.ManualValue SET UnderlyingSource = N'ERP' WHERE TableName = N'Material' AND RecordKey = :k"), {"k": str(m["Id"])})

    rows = s.execute(sa.text("SELECT * FROM adm.ManualValue WHERE TableName = N'Material' AND RecordKey = :k"), {"k": str(m["Id"])}).all()
    assert service._restore(s, actor, MAT, core_table("Material"), rows) == 2  # kaldırınca son alttaki değer
    back = material(s)
    assert (back["MaterialGroup"], back["SafetyStock"]) == ("G2", None)
    assert manual_row(s, "Material", m["Id"], "MaterialGroup") is None


def test_manual_value_on_location_is_kept_without_update(s, actor):
    transfer.run_transfer(s, None)
    lid = loc_id(s, L1)
    service._write(s, actor, LOC, core_table("Location"), str(lid), "Name", "Elle ad")
    r = transfer.run_transfer(s, None)
    assert s.execute(sa.text("SELECT Name FROM core.Location WHERE Id = :i"), {"i": lid}).scalar() == "Elle ad"
    assert {t["entity"]: t for t in r["tables"]}["Location"]["changed"] == 0
    assert s.execute(sa.text("SELECT Name FROM core.Location WHERE Code = N'TL-2'")).scalar() == "Test 2"  # yalnız kendi kaydı
    mv = manual_row(s, "Location", lid, "Name")
    assert (mv["UnderlyingValue"], mv["IsBaseChanged"]) == ("Test 1", False)


# ------------------------------------------------------------------ API (sentetik v0, geri alınır)

@pytest.fixture(scope="module")
def people(db_engine):
    with db_engine.begin() as c:
        return {SYSTEM_OWNER: ensure_user(c, "pytest.elle.owner", SYSTEM_OWNER), KEY_USER: ensure_user(c, "pytest.elle.key", KEY_USER),
                END_USER: ensure_user(c, "pytest.elle.end", END_USER)}


@pytest.fixture
def api(db_engine, people):
    client = TestClient(create_app(), raise_server_exceptions=False)
    yield client
    with db_engine.begin() as c:  # artık kalmasın
        c.execute(sa.text("DELETE FROM adm.ManualValue WHERE TableName = N'Customer'"))
        c.execute(sa.text("UPDATE adm.FieldDefinition SET ManualOverrides = 0 WHERE TableName = N'Customer'"))


def customer(db_engine) -> dict:
    with db_engine.connect() as c:
        return dict(c.execute(sa.text("SELECT TOP 1 Id, Code, Name, Priority FROM core.Customer WHERE VersionTo IS NULL ORDER BY Code")).mappings().one())


def manual(api, people, field, on, confirm=False):
    return api.put(f"/api/field-definitions/Customer/{field}/manual", headers=auth(people[SYSTEM_OWNER]), json={"on": on, "confirm": confirm})


def test_save_lists_and_remove(api, people, db_engine):
    c0 = customer(db_engine)
    key = auth(people[KEY_USER])
    body = {"list": "master-customer", "changes": [{"id": c0["Id"], "field": "Name", "value": "Elle müşteri"}]}
    r = api.post("/api/manual-values", headers=key, json=body)
    assert r.status_code == 422 and r.json()["error"]["details"][0]["problem"] == "Manuel değer girilemez."
    assert manual(api, people, "Code", True).status_code == 422                                     # anahtar alan
    r = manual(api, people, "Name", True)
    assert r.status_code == 200 and r.json()["manual_overrides"] is True and r.json()["manual_reason"] is None
    cols = {c["field"]: c for c in api.get("/api/master-customer/columns", headers=key).json()["columns"]}
    assert cols["Name"]["manual"] and not cols["Code"]["manual"] and cols["ManualState"]["label"] == "Manuel değer"
    with db_engine.connect() as c:
        version = c.execute(sa.text("SELECT MAX(Id) FROM adm.DataVersion")).scalar()
    assert api.post("/api/manual-values", headers=key, json=body).status_code == 200
    with db_engine.connect() as c:
        assert c.execute(sa.text("SELECT MAX(Id) FROM adm.DataVersion")).scalar() == version          # yeni veri versiyonu yok
        assert c.execute(sa.text("SELECT Name FROM core.Customer WHERE Id = :i AND VersionTo IS NULL"), {"i": c0["Id"]}).scalar() == "Elle müşteri"
        assert c.execute(sa.text("SELECT TOP 1 Action FROM adm.AuditLog ORDER BY Id DESC")).scalar() == service.SAVE_ACTION
    rows = api.post("/api/master-customer/query", headers=key, json={"fields": ["Code", "Name", "ManualState"],
                                                                     "filters": [{"field": "ManualState", "op": "in", "values": ["Var"]}]}).json()["rows"]
    assert [(x["Code"], x["ManualState"]) for x in rows] == [(c0["Code"], "Var")]
    cell = rows[0]["_sources"]["Name"]
    assert (cell["source"], cell["base"], cell["underlying"], cell["changed"]) == ("Manuel", c0["Name"], c0["Name"], False) and cell["by"]
    r = api.post("/api/manual-values/remove", headers=key, json={"list": "master-customer", "items": [{"id": c0["Id"], "field": "Name"}]})
    assert r.status_code == 200 and r.json() == {"removed": 1}
    assert customer(db_engine)["Name"] == c0["Name"]


def test_validation_type_and_value_list(api, people, db_engine):
    c0 = customer(db_engine)
    manual(api, people, "Priority", True)
    manual(api, people, "AllowPartialDelivery", True)
    key = auth(people[KEY_USER])
    r = api.post("/api/manual-values", headers=key, json={"list": "master-customer", "changes": [
        {"id": c0["Id"], "field": "Priority", "value": "çok"}, {"id": c0["Id"], "field": "AllowPartialDelivery", "value": True}]})
    assert r.status_code == 422 and [d["field"] for d in r.json()["error"]["details"]] == ["Priority"]   # hiçbiri yazılmaz
    d = r.json()["error"]["details"][0]
    assert (r.json()["error"]["message"], d["problem"], d["record"]) == ("Kaydedilmedi.", "Tam sayı girilmeli.", c0["Code"])  # K-172 kalıbı
    assert customer(db_engine)["Priority"] == c0["Priority"]


def test_dictionary_off_asks_and_removes(api, people, db_engine):
    c0 = customer(db_engine)
    manual(api, people, "Name", True)
    api.post("/api/manual-values", headers=auth(people[KEY_USER]), json={"list": "master-customer", "changes": [{"id": c0["Id"], "field": "Name", "value": "X"}]})
    r = manual(api, people, "Name", False)
    assert r.status_code == 409 and r.json()["error"]["message"] == "1 kayıtta manuel değer kaldırılacak."
    r = manual(api, people, "Name", False, confirm=True)
    assert r.status_code == 200 and r.json()["manual_overrides"] is False and r.json()["manual_count"] == 0
    assert customer(db_engine)["Name"] == c0["Name"]


def test_roles(api, people, db_engine):
    c0 = customer(db_engine)
    manual(api, people, "Name", True)
    body = {"list": "master-customer", "changes": [{"id": c0["Id"], "field": "Name", "value": "X"}]}
    assert api.post("/api/manual-values", headers=auth(people[END_USER]), json=body).status_code == 403
    assert api.post("/api/manual-values/remove", headers=auth(people[END_USER]), json={"list": "master-customer", "items": [{"id": c0["Id"]}]}).status_code == 403
    assert api.put("/api/field-definitions/Customer/Name/manual", headers=auth(people[KEY_USER]), json={"on": False}).status_code == 403



@pytest.mark.parametrize("field, value, problem", [
    ("SafetyStock", "çok", "Sayı girilmeli."), ("SafetyStock", "1,12345", "En çok 4 ondalık."),  # decimal(18,4) ("MaterialLevel", "Yok böyle", "Listedeki değerlerden biri girilmeli."),
    ("IsCritical", "belki", "Evet ya da Hayır girilmeli."), ("ShelfLifeDays", "1,5", "Tam sayı girilmeli."), ("IsCritical", "Evet", None), ("SafetyStock", "1.234,5", None),
])
def test_parse_messages(field, value, problem):
    col = core_table("Material").c[field]
    assert service._parse("Material", col, value, False)[1] == problem

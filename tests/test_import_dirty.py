"""Kirli Excel gerçek girdi (docs/11, K-129): 23 dosya yüklenir; ön kontrol yalnız H4'ü yakalar; H1 ve H2 referans (4.4), H3 mantıksal kontrol sonraki adımların işi."""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.main import create_app
from app.api.permissions import KEY_USER
from app.data.synthetic.dataset import generate
from app.data.synthetic.excel import stg_entities, to_staging, write_excel

from auth_helpers import auth, delete_users, ensure_user

pytestmark = pytest.mark.db

PREFIX = "pytest.kirli."
DAY = date(2026, 10, 27)


def clean(engine):
    with engine.begin() as c:
        for entity in stg_entities():
            c.execute(text(f"DELETE FROM stg.[{entity}]"))
        c.execute(text("DELETE FROM adm.ImportFinding"))
        c.execute(text("DELETE FROM adm.ImportBatch"))
        ids = [r[0] for r in c.execute(text("SELECT Id FROM adm.AppUser WHERE UserName LIKE :p"), {"p": PREFIX + "%"})]
        delete_users(c, ids)


@pytest.fixture(scope="module")
def uploaded(db_engine, tmp_path_factory):
    clean(db_engine)
    with db_engine.begin() as c:
        user = ensure_user(c, PREFIX + "key", KEY_USER, "Ad")
    ds = generate(DAY)
    out = tmp_path_factory.mktemp("kirli")
    manifest = write_excel(ds, out)
    client = TestClient(create_app(), raise_server_exceptions=False)
    results = {}
    for entity in stg_entities():
        r = client.post(f"/api/imports/{entity}", content=(out / f"{entity}.xlsx").read_bytes(), headers={**auth(user), "X-File-Name": f"{entity}.xlsx"})
        assert r.status_code == 200, (entity, r.text)
        results[entity] = r.json()
    yield ds, manifest, results, client, user
    clean(db_engine)


def test_every_file_is_read(uploaded):
    _, manifest, results, _, _ = uploaded
    assert len(results) == 23
    for entity, s in results.items():
        assert s["read"] == manifest["files"][f"{entity}.xlsx"], entity
        assert s["template_version"] == s["current_version"], entity


def test_only_the_duplicate_is_an_error(uploaded):
    _, _, results, _, _ = uploaded
    assert {e: s["errors"] for e, s in results.items() if s["errors"]} == {"Material": 2}
    assert {e: s["notes"] for e, s in results.items() if s["notes"]} == {"Material": 1}  # liste dışı değer örneği V-MAT-8 (K-137): bilgi


def test_duplicate_matches_the_manifest(db_engine, uploaded):
    _, manifest, results, client, user = uploaded
    h4 = next(e for e in manifest["errors"] if e["code"] == "H4")
    s = results["Material"]
    assert (s["read"], s["valid"], s["errors"]) == (214, 212, 2)  # 10 hazır kural örneği, 1 pasif ebeveyn yardımcısı ve 2 veri kuralı örneği dahil (docs/11)
    body = {"fields": ["RowNo", "RowKey", "Message", "Severity"], "sort": [{"field": "RowNo", "dir": "asc"}],
            "filters": [{"field": "ImportBatchId", "op": "eq", "value": s["batch_id"]}, {"field": "Severity", "op": "in", "values": ["Hata"]}], "offset": 0, "limit": 10}
    rows = client.post("/api/import-findings/query", json=body, headers=auth(user)).json()["rows"]
    assert [r["RowNo"] for r in rows] == h4["rows"] and {r["Message"] for r in rows} == {h4["message"]} and rows[0]["RowKey"] == "ORM-01 · SAT-040"
    with db_engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM stg.Material")).scalar() == 212
        assert c.execute(text("SELECT COUNT(*) FROM stg.Material WHERE Code = N'SAT-040'")).scalar() == 0


@pytest.mark.parametrize("entity, where", [
    ("SalesOrderLine", "MaterialCode = N'MAM-099'"),               # H2: referans, 4.4
    ("BOM", "ComponentMaterialCode = N'SAT-999'"),                  # H2
    ("PurchaseOrderLine", "OpenQuantity = -50"),                    # H3: mantıksal, 3.4
    ("BOM", "Quantity = -2"),                                       # H3
    ("ProductionVersion", "RouteCode = N'R-PRC-033'"),              # H1: referans, 4.4 (PV.REF_ROUTE)
])
def test_later_errors_pass_the_precheck(db_engine, uploaded, entity, where):
    with db_engine.connect() as c:
        assert c.execute(text(f"SELECT COUNT(*) FROM stg.[{entity}] WHERE {where}")).scalar() == 1


def test_values_survive_the_round_trip(db_engine, uploaded):
    ds, _, _, _, _ = uploaded
    clean_rows = {r["LotNo"]: r for r in to_staging(ds)["Stock"] if r["LotNo"]}
    with db_engine.connect() as c:
        lot = c.execute(text("SELECT * FROM stg.Stock WHERE LotNo = N'L-2410-07'")).mappings().one()
    want = clean_rows["L-2410-07"]
    assert (lot["Status"], float(lot["Quantity"]), lot["IsInQuality"], lot["IsAvailable"]) == (want["Status"], want["Quantity"], True, False)
    assert lot["QualityEntryDate"] == want["QualityEntryDate"] and lot["ExpectedAcceptanceDate"] == want["ExpectedAcceptanceDate"] and lot["SourceRowNo"] >= 2

"""Ana veri (ekran 03, fonksiyon 10) ve İşlem verisi (ekran 29, fonksiyon 102) ekranları (K-168, K-169): tablolar, kod eşlemesi, sayı biçimi,
Standart görünüm (aktarılan bütün alanlar, Aktif gizli), kayıt sayıları ve yetki.

Liste tanımı testleri veritabanısız; API testleri Smartchain_test'te sentetik v0 ile (docs/11).
"""
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.api.deps import COOKIE
from app.api.lists import LISTS
from app.api.lists.definition import columns
from app.api.lists.master_data import BY_NAME, MASTER_LISTS, MASTER_TABS, TRANSACTION_LISTS, TRANSACTION_TABS
from app.api.main import create_app
from app.api.permissions import END_USER, KEY_USER

from auth_helpers import auth, ensure_user, token


def cols(name: str) -> dict[str, dict]:
    return {c["field"]: c for c in columns(BY_NAME[name], {})}


# ------------------------------------------------------------------ liste tanımları (veritabanısız)

def test_tabs_and_registration():
    master = [n for _, lists in MASTER_TABS for n in lists]
    tx = [n for _, lists in TRANSACTION_TABS for n in lists]
    assert len(master) == len(set(master)) == 14 and len(tx) == len(set(tx)) == 12
    assert [k for k, _ in MASTER_TABS] == ["malzeme", "urun-agaci-ve-rota", "kaynak", "tedarikci-ve-musteri", "lokasyon-ve-birim"]
    assert [k for k, _ in TRANSACTION_TABS] == ["talep", "stok", "uretim", "satin-alma", "izin"]
    assert {"transaction-project", "transaction-project-group"} <= set(tx)
    assert set(master + tx) <= {d.name for d in LISTS}
    assert {BY_NAME[n].function for n in master} == {10} and {BY_NAME[n].function for n in tx} == {102}


def test_relations_show_codes_not_ids():
    for d in (*MASTER_LISTS, *TRANSACTION_LISTS):
        assert not {f for f in cols(d.name) if f.endswith("Id")}, d.name
    assert {"MaterialCode", "ComponentMaterialCode", "LocationCode"} <= set(cols("master-bom"))
    assert {"CalendarCode", "SubcontractorCode"} <= set(cols("master-resource"))
    assert {"CustomerCode", "ProjectCode", "MaterialCode"} <= set(cols("transaction-sales-order"))
    assert {"SalesOrderLineCode", "ParentWorkOrderCode", "ProductionVersionCode"} <= set(cols("transaction-work-order"))
    assert {"LendingProjectCode", "BorrowingProjectCode"} <= set(cols("transaction-borrow-payback"))
    assert "UnitOfRow" not in cols("master-routing") and "BaseUom" not in cols("transaction-stock")  # birim yalnız ondalık için


def test_number_format():
    c = cols("master-bom")
    assert c["Quantity"]["decimals_from_unit"] and BY_NAME["master-bom"].unit_field == "UnitOfRow"  # bileşen birimi, boşsa bileşenin temel birimi
    assert (c["ScrapRatio"]["percent"], c["ScrapRatio"]["decimals"]) == (True, 2)
    assert (c["OperationNo"]["type"], c["OperationNo"]["decimals"]) == ("integer", 0)
    assert cols("master-routing")["Consumption"]["decimals_from_unit"] and cols("master-routing")["WaitingTimeHours"]["decimals"] == 2
    c = cols("master-resource")
    assert c["DailyCapacity"]["decimals_from_unit"]
    assert (c["SubconFixedLeadTimeDays"]["decimals"], c["SubconVariableDaysPerUnit"]["decimals"]) == (2, 4)
    c = cols("master-material-supplier")
    assert (c["QuotaRatio"]["percent"], c["FixedLeadTimeDays"]["decimals"], c["VariableLeadTimeDays"]["decimals"]) == (True, 0, 4)
    assert c["MinimumOrderQuantity"]["decimals_from_unit"]
    assert cols("master-uom-conversion")["Factor"]["decimals"] == 4
    for name, field in (("transaction-sales-order", "OpenQuantity"), ("transaction-stock", "Quantity"), ("transaction-work-order", "OrderedQuantity"),
                        ("transaction-purchase-order", "OrderedQuantity"), ("transaction-work-order-component", "RequiredQuantity"),
                        ("transaction-work-order-operation", "RemainingConsumption"), ("transaction-production-confirmation", "ConfirmedQuantity")):
        assert cols(name)[field]["decimals_from_unit"], (name, field)
    assert cols("transaction-work-order-component")["ScrapRatio"]["percent"]
    assert cols("transaction-employee-absence")["HoursPerDay"]["decimals"] == 2
    for d in (*MASTER_LISTS, *TRANSACTION_LISTS):  # her ondalık alan ya sabit ya birimden (K-88)
        for f in columns(d, {}):
            if f["type"] == "number":
                assert f["decimals"] is not None or f["decimals_from_unit"], (d.name, f["field"])


def test_standard_view_shows_all_transferred_fields():
    for name in BY_NAME:
        c = cols(name)
        hidden = {f for f, x in c.items() if not x["default_visible"]}
        expected = {"UpdatedAt"} | ({"IsActive"} if "IsActive" in c and name != "master-location" else set())
        assert hidden == expected & set(c), name
        assert all(x.get("standard_filter") is None for x in c.values())  # süzgeç yok (K-169)
    assert cols("master-location")["IsActive"]["default_visible"]  # versiyonsuz: pasif lokasyon kalır (K-153)


# ------------------------------------------------------------------ API (Smartchain_test, sentetik v0)

@pytest.fixture(scope="module")
def api(db_engine, test_users):
    with db_engine.connect() as conn:
        synthetic = conn.execute(sa.text("SELECT TOP 1 IsSynthetic FROM adm.DataVersion ORDER BY Id DESC")).scalar()
    if not synthetic:
        pytest.skip("Sentetik v0 yüklü değil (python -m app.data.synthetic load)")
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.cookies.set(COOKIE, token(test_users[0]))
    return client


def _current(conn, table: str) -> int:
    has_version = conn.execute(sa.text(
        "SELECT COUNT(*) FROM sys.columns WHERE object_id = OBJECT_ID(:t) AND name = 'VersionTo'"), {"t": f"core.{table}"}).scalar()
    where = (" WHERE VersionFrom <= (SELECT MAX(Id) FROM adm.DataVersion) AND (VersionTo IS NULL OR VersionTo >= (SELECT MAX(Id) FROM adm.DataVersion))"
             if has_version else "")
    return conn.execute(sa.text(f"SELECT COUNT(*) FROM core.[{table}]{where}")).scalar()


@pytest.mark.db
@pytest.mark.parametrize("url, tabs", [("/api/master-data/counts", MASTER_TABS), ("/api/transaction-data/counts", TRANSACTION_TABS)])
def test_counts_match_current_rows(api, db_engine, url, tabs):
    r = api.get(url)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [t["key"] for t in body["tabs"]] == [k for k, _ in tabs]
    tables = {x["list"]: x for t in body["tabs"] for x in t["tables"]}
    with db_engine.connect() as conn:
        for name, x in tables.items():
            assert x["count"] == _current(conn, BY_NAME[name].table_name), name
    if "materials" in tables:
        assert (tables["materials"]["label"], tables["master-resource-group-assignment"]["label"]) == ("Malzeme", "Grup ataması")


@pytest.mark.db
def test_rows_map_codes_and_unit_decimals(api, db_engine):
    r = api.post("/api/master-bom/query", json={"fields": ["MaterialCode", "ComponentMaterialCode", "Quantity", "ComponentUom"], "limit": 100})
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    assert rows and all(row["MaterialCode"] and row["ComponentMaterialCode"] for row in rows)
    with db_engine.connect() as conn:
        base = dict(conn.execute(sa.text("SELECT m.Code, u.Decimals FROM core.Material m JOIN core.UnitOfMeasure u ON u.Code = m.BaseUom "
                                         "WHERE m.VersionTo IS NULL")).all())
    blank = [row for row in rows if not row["ComponentUom"] and row["ComponentMaterialCode"] in base]  # bileşen birimi boşsa temel birimden
    assert blank and all(row["_unit_decimals"] == base[row["ComponentMaterialCode"]] for row in blank)
    r = api.post("/api/transaction-stock/query", json={"fields": ["MaterialCode", "Quantity"], "limit": 100})
    assert r.status_code == 200, r.text
    rows = [row for row in r.json()["rows"] if row["MaterialCode"] in base]
    assert rows and all(row["_unit_decimals"] == base[row["MaterialCode"]] for row in rows)  # stok miktarı malzemenin biriminden
    r = api.post("/api/transaction-work-order/query", json={"fields": ["WorkOrderNo", "SalesOrderLineCode"], "limit": 100})
    assert r.status_code == 200 and all(v is None or " / " in v and not v.startswith(" ") for v in (x["SalesOrderLineCode"] for x in r.json()["rows"]))
    for name in BY_NAME:  # her liste sorgulanır
        assert api.post(f"/api/{name}/query", json={"limit": 5}).status_code == 200, name


@pytest.mark.db
def test_end_user_reads_no_write_endpoint(api, db_engine):
    with db_engine.begin() as conn:
        end, key = ensure_user(conn, "pytest.anaveri.end", END_USER), ensure_user(conn, "pytest.anaveri.key", KEY_USER)
    client = TestClient(create_app(), raise_server_exceptions=False)
    for url in ("/api/master-data/counts", "/api/transaction-data/counts"):
        assert client.get(url, headers=auth(end)).status_code == 200
        assert client.get(url).status_code == 401
    assert client.post("/api/transaction-stock/query", headers=auth(end), json={"fields": ["MaterialCode"]}).status_code == 200
    for path in ("/api/master-bom/save", "/api/transaction-stock/rows", "/api/master-bom"):  # salt okunur: yazma ucu yok
        assert client.post(path, headers=auth(key), json={}).status_code in (404, 405)

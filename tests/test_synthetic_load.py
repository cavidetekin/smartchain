"""Temiz hâlin ana tablolara yüklenmesi, yeniden yükleme ve güvenlik kilidi (K-78, K-79), yerel SQL Server ile.

Test sonunda sentetik veri test veritabanında yüklü kalır (K-103), sonraki testlerin zemini; yeniden yükleme aynı sonucu verir.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.data.synthetic import dataset as d
from app.data.synthetic.dataset import generate
from app.data.synthetic.load import LOAD_ORDER, SyntheticLockError, load, unload
from app.engine.submit import submit_plan_run

pytestmark = pytest.mark.db


def counts(conn, version):
    return {t: conn.execute(text(f"SELECT COUNT(*) FROM core.[{t}] WHERE VersionFrom = :v"), {"v": version}).scalar()
            for t in LOAD_ORDER}


def snapshot(engine):
    with engine.connect() as c:
        return {t: c.execute(text(f"SELECT COUNT(*) FROM core.[{t}]")).scalar() for t in LOAD_ORDER + ["Location"]} | {
            "DataVersion": c.execute(text("SELECT COUNT(*) FROM adm.DataVersion")).scalar(),
            "ParameterSet": c.execute(text("SELECT COUNT(*) FROM param.ParameterSet")).scalar()}


@pytest.fixture(scope="module")
def ds():
    return generate()


@pytest.fixture(scope="module")
def loaded(db_engine, ds):
    return load(db_engine, ds)


def test_load_writes_every_table(db_engine, ds, loaded):
    v = loaded["data_version_id"]
    with db_engine.connect() as c:
        assert counts(c, v) == {t: len(ds.rows(t)) for t in LOAD_ORDER}
        dv = c.execute(text("SELECT LocationId, LoadType, IsSynthetic FROM adm.DataVersion WHERE Id = :v"), {"v": v}).one()
        assert dv.LocationId == loaded["location_id"] and dv.LoadType == "Tam" and dv.IsSynthetic
        flags = c.execute(text("SELECT IsFactory, IsDepot, IsSubcontractor, IsActive FROM core.Location WHERE Id = :l"),
                          {"l": loaded["location_id"]}).one()
        assert tuple(flags) == (True, True, False, True)  # K-111: ORM-01 hem tesis hem depo
        customer, key = c.execute(text("SELECT SUM(CAST(IsCustomerSupplied AS int)), MIN(BusinessKey) FROM core.Material WHERE VersionFrom = :v"), {"v": v}).one()
        assert customer == 1 and key.startswith(f"{d.LOCATION_CODE}|")  # K-113
        pv = c.execute(text("SELECT MIN(LocationId), MAX(LocationId), MIN(BusinessKey), MIN(BOMCode) FROM core.ProductionVersion WHERE VersionFrom = :v"), {"v": v}).one()
        assert (pv[0], pv[1]) == (loaded["location_id"], loaded["location_id"]) and pv[2].startswith(f"{d.LOCATION_CODE}|") and pv[3].startswith("B-")  # K-114
        so = c.execute(text("SELECT MIN(BusinessKey), SUM(OpenQuantity), SUM(OrderedQuantity) FROM core.SalesOrderLine WHERE VersionFrom = :v"), {"v": v}).one()
        assert so[0].startswith(f"{d.LOCATION_CODE}|") and so[1] == so[2]  # K-120
        assert c.execute(text("SELECT COUNT(*) FROM core.SalesOrderLine WHERE VersionFrom = :v AND LineItemNo IS NULL"), {"v": v}).scalar() == 0  # boşsa 0 kuralı
        po = c.execute(text("SELECT MIN(BusinessKey), SUM(OpenQuantity), SUM(OrderedQuantity) FROM core.PurchaseOrderLine WHERE VersionFrom = :v"), {"v": v}).one()
        assert po[0].startswith(f"{d.LOCATION_CODE}|PO-") and po[1] == po[2]  # K-125
        done = c.execute(text("SELECT MIN(BusinessKey), MIN(LocationId), COUNT(*), COUNT(MaterialId) FROM core.ProductionConfirmation WHERE VersionFrom = :v"), {"v": v}).one()
        assert done[0].startswith(f"{d.LOCATION_CODE}|T-WO-") and done[1] == loaded["location_id"] and done[2] == done[3] == 6
        wo = c.execute(text("SELECT MIN(BusinessKey), COUNT(ProductionVersionId), COUNT(*) FROM core.WorkOrder WHERE VersionFrom = :v"), {"v": v}).one()
        assert wo[0].startswith(f"{d.LOCATION_CODE}|WO-") and wo[1] == wo[2]  # K-124
        for table in ("WorkOrderComponent", "WorkOrderOperation"):
            part = c.execute(text(f"SELECT MIN(BusinessKey), MIN(LocationId), MAX(LocationId) FROM core.{table} WHERE VersionFrom = :v"), {"v": v}).one()
            assert part[0].startswith(f"{d.LOCATION_CODE}|WO-") and part[1] == part[2] == loaded["location_id"]
        stock = c.execute(text("SELECT MIN(BusinessKey), SUM(CASE WHEN Status = N'Kalitede' AND IsInQuality = 1 AND ExpectedAcceptanceDate IS NOT NULL THEN 1 ELSE 0 END), "
                               "SUM(CASE WHEN Status = N'Bloke' AND IsBlocked = 1 THEN 1 ELSE 0 END) FROM core.Stock WHERE VersionFrom = :v"), {"v": v}).one()
        assert stock[0].startswith(f"{d.LOCATION_CODE}|") and (stock[1], stock[2]) == (1, 1)  # K-123
        lent = c.execute(text("SELECT LocationId, BusinessKey, BorrowedQuantity FROM core.BorrowPayback WHERE VersionFrom = :v"), {"v": v}).all()
        assert len(lent) == 1 and lent[0][0] == loaded["location_id"] and lent[0][1].startswith(f"{d.LOCATION_CODE}|MAM-006|PRJ-01|PRJ-02|")  # K-119
        ms = c.execute(text("SELECT MIN(LocationId), MIN(BusinessKey), MAX(QuotaRatio) FROM core.MaterialSupplier WHERE VersionFrom = :v"), {"v": v}).one()
        assert ms[0] == loaded["location_id"] and ms[1].startswith(f"{d.LOCATION_CODE}|") and float(ms[2]) == 0.3  # K-118
        people = c.execute(text("SELECT COUNT(*), SUM(CAST(IsEmployee AS int)) FROM core.Resource WHERE VersionFrom = :v"), {"v": v}).one()
        assert tuple(people) == (40, 25)  # K-117: işçiler kaynak
        links = c.execute(text("SELECT COUNT(*) FROM core.ResourceGroupAssignment WHERE VersionFrom = :v"), {"v": v}).scalar()
        assert links >= 25 + 13 and c.execute(text("SELECT COUNT(*) FROM core.EmployeeAbsence WHERE VersionFrom = :v"), {"v": v}).scalar() == 3
        labor = c.execute(text("SELECT COUNT(*), MIN(ResourceNumber) FROM core.Routing WHERE VersionFrom = :v AND ResourceId IS NULL AND ResourceGroupId IS NOT NULL AND ResourceRole = N'Secondary'"), {"v": v}).one()
        assert labor[0] > 0 and labor[1] == 2  # K-116: işçilik ayrı satır
        bom = c.execute(text("SELECT MIN(LocationId), MIN(BusinessKey), COUNT(*) FROM core.BOM b WHERE VersionFrom = :v AND EXISTS "
                             "(SELECT 1 FROM core.ProductionVersion p WHERE p.VersionFrom = :v AND p.MaterialId = b.MaterialId AND p.BOMCode = b.Code)"), {"v": v}).one()
        total = c.execute(text("SELECT COUNT(*) FROM core.BOM WHERE VersionFrom = :v"), {"v": v}).scalar()
        assert bom[0] == loaded["location_id"] and bom[1].startswith(f"{d.LOCATION_CODE}|") and bom[2] == total > 0  # K-115: her satırın versiyonu var
        names = c.execute(text("SELECT DISTINCT FromUomName, ToUomName FROM core.UomConversion WHERE VersionFrom = :v"), {"v": v}).all()
        assert [tuple(n) for n in names] == [("Metre", "Kilogram")]  # K-112
        units = dict(c.execute(text("SELECT Code, Decimals FROM core.UnitOfMeasure")).all())
        assert units == {"ADET": 0, "KG": 3, "M": 2, "SAAT": 2}  # birimler şablondan değil, sentetik veriden
        loc = c.execute(text("SELECT Code, IsSynthetic FROM core.Location WHERE Id = :l"),
                        {"l": loaded["location_id"]}).one()
        assert loc.Code == d.LOCATION_CODE and loc.IsSynthetic
        entities = {r[0] for r in c.execute(text("SELECT EntityName FROM adm.DataVersionEntity WHERE DataVersionId = :v"),
                                            {"v": v})}
        assert entities == set(LOAD_ORDER)
        for t in LOAD_ORDER:  # versiyon alanları (K-63)
            bad = c.execute(text(f"SELECT COUNT(*) FROM core.[{t}] WHERE VersionFrom = :v AND (BusinessKey IS NULL "
                                 "OR VersionTo IS NOT NULL OR ImportBatchId IS NOT NULL)"), {"v": v}).scalar()
            assert bad == 0, t
        ps = c.execute(text("SELECT Name, IsSynthetic FROM param.ParameterSet WHERE Id = :p"),
                       {"p": loaded["parameter_set_id"]}).one()
        assert ps.Name == d.SET_NAME and ps.IsSynthetic
        limit = c.execute(text("SELECT UpperLimit FROM param.SupplierLimit WHERE ParameterSetId = :p"),
                          {"p": loaded["parameter_set_id"]}).scalar()
        assert limit == d.LIMIT_QTY


def test_reload_replaces_previous_version_and_its_plans(db_engine, ds, loaded):
    old = loaded["data_version_id"]
    with Session(db_engine) as s:
        run_id, _ = submit_plan_run(s, data_version_id=old, parameter_set_id=loaded["parameter_set_id"])
    again = load(db_engine, ds)
    assert again["removed_versions"] == [old] and again["data_version_id"] != old
    with db_engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM adm.DataVersion WHERE Id = :v"), {"v": old}).scalar() == 0
        assert c.execute(text("SELECT COUNT(*) FROM planning.PlanRun WHERE Id = :r"), {"r": run_id}).scalar() == 0
        assert counts(c, again["data_version_id"]) == {t: len(ds.rows(t)) for t in LOAD_ORDER}
        dup = c.execute(text("SELECT COUNT(*) FROM (SELECT Code FROM core.Material WHERE VersionTo IS NULL "
                             "GROUP BY Code HAVING COUNT(*) > 1) x")).scalar()
        assert dup == 0
        assert c.execute(text("SELECT COUNT(*) FROM core.Location WHERE Code = :c"), {"c": d.LOCATION_CODE}).scalar() == 1
    loaded.update(again)


LOCK_CASES = {
    "ParameterSet": ("INSERT INTO param.ParameterSet (Name, IsSynthetic) OUTPUT inserted.Id VALUES (N'Gerçek set', 0)",
                     "DELETE FROM param.ParameterSet WHERE Id = :id", "parametre seti 'Gerçek set'"),
    "Location": ("INSERT INTO core.Location (Code, Name, Type, IsSynthetic) OUTPUT inserted.Id "
                 "VALUES (N'GERCEK-01', N'Gerçek fabrika', N'Tesis', 0)",
                 "DELETE FROM core.Location WHERE Id = :id", "lokasyon GERCEK-01"),
    "DataVersion": ("INSERT INTO adm.DataVersion (LocationId, CreatedAt, LoadType) OUTPUT inserted.Id "
                    "VALUES ((SELECT Id FROM core.Location WHERE Code = N'ORM-01'), SYSUTCDATETIME(), N'Tam')",
                    "DELETE FROM adm.DataVersion WHERE Id = :id", "veri versiyonu"),
}


@pytest.mark.parametrize("kind", list(LOCK_CASES))
def test_lock_stops_without_deleting(db_engine, ds, loaded, kind):
    insert, delete, label = LOCK_CASES[kind]
    with db_engine.begin() as c:
        rid = c.execute(text(insert)).scalar_one()
    try:
        before = snapshot(db_engine)
        for action in (lambda: load(db_engine, ds), lambda: unload(db_engine)):
            with pytest.raises(SyntheticLockError) as exc:
                action()
            msg = str(exc.value)
            assert "sentetik olmayan" in msg and "hiçbir şey silinmedi" in msg and label in msg
            if kind == "DataVersion":
                assert f"veri versiyonu {rid}" in msg
            assert snapshot(db_engine) == before
    finally:
        with db_engine.begin() as c:
            c.execute(text(delete), {"id": rid})
    loaded.update(load(db_engine, ds))  # kilit kalkınca yeniden çalışır


def test_health_ok_with_synthetic_data(db_engine, loaded):
    r = TestClient(create_app()).get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"

"""Temiz hâlin ana tablolara yüklenmesi, yeniden yükleme ve güvenlik kilidi (K-78, K-79), yerel SQL Server ile.

Test sonunda sentetik veri yüklü kalır: geliştirmede ekranların zemini; yeniden yükleme aynı sonucu verir.
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

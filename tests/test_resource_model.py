"""Kaynak modeli (K-180, geliştirme 7.5): planlama birimi kaynak grubudur. Sentetik v0'da; kendi değiştirdiğini geri alır.

Kapasitesi tanımsız kaynak kontrolü kritik gruba üyelikten okur; talep zinciri rota → grup → eşleşme → kaynak yolundan geçer; kayıt kartının
İlişkili kayıtları; tüketimin ve günlük kapasitenin ondalığı grubun kapasite biriminden gelir.
"""
from datetime import date, timedelta

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.api.permissions import KEY_USER
from app.data.synthetic import dataset as d
from app.quality import chain

from auth_helpers import auth, ensure_user
from test_quality import _clean, _sql, check, core_id, warning

pytestmark = pytest.mark.db

NO_CAPACITY_GROUP = "TORNA"  # durum 9: T-05'in tek grubu, kritik (docs/11)


@pytest.fixture
def eng(db_engine):
    _clean(db_engine)
    yield db_engine
    _clean(db_engine)


@pytest.fixture(scope="module")
def api(db_engine):
    with db_engine.begin() as c:
        user = ensure_user(c, "pytest.rm.key", KEY_USER)
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.headers.update(auth(user))
    return client


def _members(engine, **match) -> list[tuple[int, int]]:
    where = " AND ".join(f"{k} = :{k}" for k in match)
    return [tuple(r) for r in _sql(engine, f"SELECT ResourceGroupId, ResourceId FROM core.ResourceGroupMember WHERE VersionTo IS NULL AND {where}", **match)]


def test_no_capacity_check_reads_work_patterns_and_the_critical_group(eng):
    """K-185: ne kendisinde ne grubunda geçerli çalışma düzeni olan kaynak; bütün gruplar için çıkar. Önem: Yüksek = aktif kritik gruba üye ve
    talep zincirinde; kritik olmayan (ya da pasif) grupta Normal. Gruba çalışma düzeni girilince uyarı kalkar; bitmiş kayıt sayılmaz."""
    group = core_id(eng, "ResourceGroup", Code=NO_CAPACITY_GROUP)
    resource = core_id(eng, "Resource", Code=d.NO_CAPACITY_RESOURCE)
    fason = core_id(eng, "Resource", Code=d.FASON_NO_CAPACITY)
    assert _members(eng, ResourceId=resource) == [(group, resource)]

    def found() -> dict:
        check(eng)
        return {w["RecordKey"]: w["Importance"] for w in warning(eng, "SC.RES_NO_CAPACITY") if w["EntityName"] == "Resource"}

    assert found() == {str(resource): "Yüksek", str(fason): "Normal"}   # T-05: grubu kritik ve rotada; F-KAPLA: fason, kritik değil
    base = _sql(eng, "SELECT Id FROM param.ScenarioDefinition WHERE IsBase = 1").scalar()
    try:
        _sql(eng, "UPDATE core.ResourceGroup SET IsCritical = 0 WHERE Id = :g AND VersionTo IS NULL", g=group)
        assert found() == {str(resource): "Normal", str(fason): "Normal"}   # kritik olmayan grupta da çıkar, önemi Normal
        _sql(eng, "UPDATE core.ResourceGroup SET IsCritical = 1, IsActive = 0 WHERE Id = :g AND VersionTo IS NULL", g=group)
        assert found()[str(resource)] == "Normal"                           # pasif grup kritik sayılmaz
        _sql(eng, "UPDATE core.ResourceGroup SET IsCritical = 1, IsActive = 1 WHERE Id = :g AND VersionTo IS NULL", g=group)
        insert = ("INSERT INTO param.WorkPattern (ScenarioDefinitionId, IsValid, ResourceGroupId, ValidFrom, ValidTo, DailyCapacity, DayMon, DayTue, DayWed, DayThu, "
                  "DayFri, DaySat, DaySun, UpdatedAt) VALUES (:s, :v, :g, :a, :b, 9.25, 1, 1, 1, 1, 1, 0, 0, SYSUTCDATETIME())")
        _sql(eng, insert, s=base, v=1, g=group, a=date.today() - timedelta(days=30), b=date.today() - timedelta(days=1))   # bitmiş kayıt sayılmaz
        _sql(eng, insert, s=base, v=0, g=group, a=date.today() - timedelta(days=30), b=None)                               # geçersiz kayıt sayılmaz
        assert str(resource) in found()
        _sql(eng, insert, s=base, v=1, g=group, a=date.today() - timedelta(days=30), b=None)                               # gruba geçerli kayıt: uyarı kalkar
        assert found() == {str(fason): "Normal"}
    finally:
        _sql(eng, "UPDATE core.ResourceGroup SET IsCritical = 1, IsActive = 1 WHERE Id = :g AND VersionTo IS NULL", g=group)
        _sql(eng, "DELETE FROM param.WorkPattern WHERE DailyCapacity = 9.25 AND ResourceGroupId = :g", g=group)
    assert len(found()) == 2


def test_demand_chain_reaches_the_resource_through_its_group(eng):
    """Zincir: rota ve iş emri operasyonu → kaynak grubu → grup eşleşmesi → kaynak. Kaynağın malzemeleri gruplarının malzemeleridir."""
    group = core_id(eng, "ResourceGroup", Code=NO_CAPACITY_GROUP)
    resource = core_id(eng, "Resource", Code=d.NO_CAPACITY_RESOURCE)
    with Session(eng) as s:
        counts = chain.rebuild(s, date.today())
        s.commit()
        by_resource, _ = chain.start_materials(s, "Resource", resource)
        by_group, _ = chain.start_materials(s, "ResourceGroup", group)
    assert counts["ResourceGroup"] > 0 and counts["ResourceGroupMember"] >= counts["Resource"] > 0

    def in_chain(entity: str, record: int) -> bool:
        return bool(_sql(eng, "SELECT 1 FROM adm.DemandChain WHERE EntityName = :e AND RecordId = :r", e=entity, r=record).first())

    assert in_chain("ResourceGroup", group) and in_chain("Resource", resource)
    assert by_group and by_resource == by_group
    routed = {r[0] for r in _sql(eng, "SELECT DISTINCT ResourceGroupId FROM core.Routing WHERE VersionTo IS NULL")}
    chained = {r[0] for r in _sql(eng, "SELECT RecordId FROM adm.DemandChain WHERE EntityName = N'ResourceGroup'")}
    assert chained <= routed | {r[0] for r in _sql(eng, "SELECT DISTINCT ResourceGroupId FROM core.WorkOrderOperation WHERE VersionTo IS NULL")}


def test_record_card_relations(api, db_engine):
    """K-173, K-180: Kaynak → Kaynak grup eşleşmesi (rota yok); Kaynak grubu → Kaynak grup eşleşmesi, Rota, İş emri operasyonu; Tedarikçi → Fason kaynak grubu."""
    group = core_id(db_engine, "ResourceGroup", Code=d.BOTTLENECK_GROUP)
    resource = _members(db_engine, ResourceGroupId=group)[0][1]
    card = api.get(f"/api/records/master-resource/{resource}").json()
    assert [(x["key"], x["label"], x["list"]) for x in card["relations"]] == [("group-member", "Kaynak grup eşleşmesi", "master-resource-group-member")]
    assert card["relations"][0]["count"] == len(_members(db_engine, ResourceId=resource))
    card = api.get(f"/api/records/master-resource-group/{group}").json()
    rel = {x["key"]: x for x in card["relations"]}
    assert list(rel) == ["group-member", "routing", "work-order-operation"]
    assert (rel["routing"]["list"], rel["work-order-operation"]["list"]) == ("master-routing", "transaction-work-order-operation")
    assert rel["group-member"]["count"] == len(_members(db_engine, ResourceGroupId=group))
    routes = _sql(db_engine, "SELECT COUNT(*) FROM core.Routing WHERE VersionTo IS NULL AND ResourceGroupId = :g", g=group).scalar()
    assert rel["routing"]["count"] == routes > 0
    q = api.post("/api/master-routing/query", json={"fields": ["ResourceGroupCode"], "filters": rel["routing"]["filters"], "limit": 100}).json()
    assert q["filtered"] == routes and {r["ResourceGroupCode"] for r in q["rows"]} == {d.BOTTLENECK_GROUP}
    supplier = _sql(db_engine, "SELECT TOP 1 SubcontractorId FROM core.ResourceGroup WHERE VersionTo IS NULL AND SubcontractorId IS NOT NULL ORDER BY Code").scalar()
    card = api.get(f"/api/records/master-supplier/{supplier}").json()
    sub = next(x for x in card["relations"] if x["key"] == "subcontract-resource-group")
    assert (sub["label"], sub["list"], sub["count"]) == ("Fason kaynak grubu", "master-resource-group", 1)


def test_consumption_decimals_come_from_the_group_unit(api, db_engine):
    """Rota ve iş emri operasyonunda tüketim grubun kapasite biriminin ondalığıyla; kaynağın günlük kapasitesi gruplarının ortak biriminden,
    grubu olmayan kaynakta varsayılan ondalık (K-168, K-180)."""
    units = dict(_sql(db_engine, "SELECT g.Code, u.Decimals FROM core.ResourceGroup g JOIN core.UnitOfMeasure u ON u.Code = g.CapacityUnit WHERE g.VersionTo IS NULL").all())
    assert units
    for name, field in (("master-routing", "Consumption"), ("transaction-work-order-operation", "PlannedConsumption")):
        r = api.post(f"/api/{name}/query", json={"fields": ["ResourceGroupCode", field], "limit": 100})
        assert r.status_code == 200, r.text
        rows = r.json()["rows"]
        assert rows and all(row["ResourceGroupCode"] and row["_unit_decimals"] == units[row["ResourceGroupCode"]] for row in rows), name
    of_resource = dict(_sql(db_engine, "SELECT r.Code, MIN(u.Decimals) FROM core.Resource r JOIN core.ResourceGroupMember m ON m.ResourceId = r.Id AND m.VersionTo IS NULL "
                                       "JOIN core.ResourceGroup g ON g.Id = m.ResourceGroupId AND g.VersionTo IS NULL JOIN core.UnitOfMeasure u ON u.Code = g.CapacityUnit "
                                       "WHERE r.VersionTo IS NULL GROUP BY r.Code HAVING COUNT(DISTINCT g.CapacityUnit) = 1").all())
    names = {c["field"] for c in api.get("/api/master-resource/columns").json()["columns"]}
    assert of_resource and "Code" in names and not {"DailyCapacity", "CalendarId"} & names   # kaynakta kapasite alanı yok (K-185): birimli sayı da yok
    columns = {c["field"] for c in api.get("/api/master-routing/columns").json()["columns"]}
    assert "ResourceGroupCode" in columns and not {"ResourceCode", "ResourceId"} & columns  # rotada kaynak kolonu yok

"""Dönem tablosu önbelleğinin performans ölçümü (K-184, docs/08): 2.000 kaynak × yaklaşık 400 gün × 10 senaryo.

Ölçülenler: tablo boyutu ve ilk kurulum süresi (hedefsiz; yazdırılır), tek kaynağın yenilenmesi (hedef 100 ms), önbellekten okuma (pivotun
ilk parçası 500 ms, tablonun ilk parçası 300 ms, tek gruba süzülmüş istek 150 ms; ortanca). Veri bir işlem içinde üretilir, ölçülür ve işlem
geri alınır; veritabanında iz kalmaz (önbellek satırları dahil).
"""
import time
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import periods as P
from app.api.lists.period_tables import RESOURCE_GROUP_PERIODS
from app.api.lists.request import PivotRequest, QueryRequest
from app.api.services import lists as service
from app.params import scenarios
from app.periods import cache, capacity_demo

from test_lists_perf import _copy_rows, median_ms

pytestmark = [pytest.mark.db, pytest.mark.perf]

GROUPS, RESOURCES, SCENARIOS = 200, 2_000, 10
HORIZON = (("Hafta", 26, "Hafta"), ("Ay", 8, "Ay"))   # yaklaşık 26 hafta + 8 ay: 400 gün dolayında, 34 dönem
REFRESH_MS, PIVOT_MS, TABLE_MS, FILTERED_MS = 100, 500, 300, 150
CACHE = capacity_demo.CACHE


def generate(conn, groups: int = GROUPS, resources: int = RESOURCES) -> None:
    """Kaynak grupları, kaynaklar (günlük kapasiteli, var olan takvime bağlı) ve her kaynağı bir gruba bağlayan eşleşmeler."""
    v = conn.execute(text("SELECT MAX(Id) FROM adm.DataVersion")).scalar()
    common = {"VersionFrom": str(int(v)), "VersionTo": "NULL"}
    _copy_rows(conn, "ResourceGroup", groups, {**common, "Id": "5000000 + x.n", "Code": "CONCAT('PERF-G-', x.n)", "Name": "CONCAT(N'Perf grubu ', x.n)",
                                               "BusinessKey": "CONCAT('PERF-G-', x.n)"})
    _copy_rows(conn, "Resource", resources, {**common, "Id": "6000000 + x.n", "Code": "CONCAT('PERF-R-', x.n)", "Name": "CONCAT(N'Perf kaynağı ', x.n)",
                                             "BusinessKey": "CONCAT('PERF-R-', x.n)", "DailyCapacity": "8"})
    _copy_rows(conn, "ResourceGroupMember", resources, {**common, "Id": "7000000 + x.n", "ResourceGroupId": f"5000000 + (x.n % {int(groups)}) + 1",
                                                        "ResourceId": "6000000 + x.n", "BusinessKey": "CONCAT('PERF-M-', x.n)"})


def set_horizon(conn, scenario_id: int, rows=HORIZON) -> None:
    conn.execute(text("DELETE FROM param.TimeBucketDefinition WHERE ScenarioDefinitionId = :s AND Axis = N'Plan'"), {"s": scenario_id})
    for seq, (kind, count, unit) in enumerate(rows, 1):
        conn.execute(text("INSERT INTO param.TimeBucketDefinition (ScenarioDefinitionId, Axis, Seq, BucketType, [Count], SpanUnit) VALUES (:s, N'Plan', :q, :k, :c, :u)"),
                     {"s": scenario_id, "q": seq, "k": kind, "c": count, "u": unit})


def build(session: Session, scenario_id: int) -> tuple[float, int]:
    """Senaryonun önbelleğini kurar: (süre sn, gün sayısı)."""
    found = P.read_periods(session, scenario_id, date.today())
    start = time.perf_counter()
    cache.ensure(session, CACHE, scenario_id, found[0].start, found[-1].end)
    return time.perf_counter() - start, (found[-1].end - found[0].start).days + 1


@pytest.fixture
def big(db_engine):
    """Üretilmiş veri ve Baz'ın 400 günlük ufku; işlem sonunda geri alınır."""
    conn = db_engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)   # dış işleme katılır: önbelleğin commit'i dış işlemi kapatmaz, sonunda hepsi geri alınır
    try:
        generate(conn)
        base = cache.base_id(session)
        set_horizon(conn, base)
        cache.drop(session, CACHE)
        yield session, base
    finally:
        session.close()
        trans.rollback()
        conn.close()


def test_build_size_and_refresh(big):
    """İlk kurulum ve tablo boyutu (10 senaryo; biri Baz'ı izler: yalnız farkını tutar); tek kaynağın yenilenmesi."""
    session, base = big
    seconds, days = build(session, base)
    rows = session.execute(text("SELECT COUNT(*) FROM cache.ResourceCapacityDay WHERE ScenarioDefinitionId = :s"), {"s": base}).scalar()
    print(f"\nBaz ilk kurulum: {seconds:.1f} sn · {rows} satır ({days} gün)")
    assert rows >= RESOURCES * days
    built = [seconds]
    for i in range(SCENARIOS - 2):                       # Baz'ı izlemeyen kopyalar: tamamını kendileri tutar
        copy = scenarios.create_copy(session, f"pytest perf {i}", base, follows_base=False)
        built.append(build(session, copy["Id"])[0])
    follower = scenarios.create_copy(session, "pytest perf izleyen", base, follows_base=True)
    session.execute(text("INSERT INTO param.ResourceEfficiency (ScenarioDefinitionId, ResourceId, ValidFrom, ValidTo, EfficiencyPct) "
                         "SELECT :s, 6000000 + n, :a, DATEADD(day, 30, :a), 90 FROM (SELECT TOP 20 ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n FROM sys.all_objects) x"),
                    {"s": follower["Id"], "a": date.today()})
    built.append(build(session, follower["Id"])[0])
    total = session.execute(text("SELECT COUNT(*) FROM cache.ResourceCapacityDay")).scalar()
    own = session.execute(text("SELECT COUNT(*) FROM cache.ResourceCapacityDay WHERE ScenarioDefinitionId = :s"), {"s": follower["Id"]}).scalar()
    size_kb = session.execute(text("SELECT SUM(reserved_page_count) * 8 FROM sys.dm_db_partition_stats WHERE object_id = OBJECT_ID('cache.ResourceCapacityDay')")).scalar()
    print(f"{SCENARIOS} senaryo: {total} satır · {size_kb / 1024:.0f} MB · kurulum ortalaması {sum(built) / len(built):.1f} sn, en uzunu {max(built):.1f} sn "
          f"· Baz'ı izleyen senaryo {own} satır tutuyor")
    assert own == 20 * 31 and total >= (SCENARIOS - 1) * RESOURCES * days
    ms = median_ms(lambda: cache.invalidate(session, CACHE, base, [6000001]))
    print(f"tek kaynağın yenilenmesi (Baz, bütün günler; izleyen senaryo dahil): ortanca {ms:.0f} ms")
    assert ms < REFRESH_MS


READS = {
    "pivotun ilk parçası": (PIVOT_MS, lambda s: service.pivot(s, RESOURCE_GROUP_PERIODS, PivotRequest.model_validate(
        {**{k: v for k, v in RESOURCE_GROUP_PERIODS.standard_pivot.items() if k in ("rows", "columns", "values", "totals", "sort")}, "limit": 100}))),
    "tablonun ilk parçası": (TABLE_MS, lambda s: service.query(s, RESOURCE_GROUP_PERIODS, QueryRequest(limit=100))),
    "tek gruba süzülmüş": (FILTERED_MS, lambda s: service.query(s, RESOURCE_GROUP_PERIODS, QueryRequest.model_validate(
        {"limit": 100, "filters": [{"field": "ResourceGroupCode", "op": "in", "values": ["PERF-G-7"]}]}))),
}


@pytest.mark.parametrize("name", list(READS))
def test_read_from_cache_under_target(big, name):
    """Önbellek kuruluyken okuma: ekran açılırken hesap yapılmaz, günlük sonuç dönemlere ve gruplara toplanır."""
    session, base = big
    build(session, base)
    target, work = READS[name]
    out = work(session)
    assert out["rows"]
    ms = median_ms(lambda: work(session))
    print(f"\ndönem tablosu ({name}): ortanca {ms:.0f} ms")
    assert ms < target

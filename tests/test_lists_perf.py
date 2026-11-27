"""Liste sorgusu performans hedefi (docs/12, K-87): 50.000 satırda ilk parça ve sayılar ortanca 300 ms altında.

Satırlar bir işlem içinde T-SQL ile üretilir, ölçülür ve işlem geri alınır; veritabanında iz kalmaz.
"""
import statistics
import time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.lists import MATERIALS
from app.api.lists.request import (
    ChartRequest, FilterItem, GroupsRequest, PivotRequest, QueryRequest, RuleSpec, SortItem, ValuesRequest,
)
from app.api.services import lists as service

pytestmark = [pytest.mark.db, pytest.mark.perf]

ROWS = 50_000
TARGET_MS = 300
RUNS = 5

GENERATE = text("""
INSERT INTO core.Material (Id, VersionFrom, LocationId, Code, Name, BaseUom, MaterialGroup, MaterialLevel,
                           SafetyStock, AdditionalText1, BusinessKey, UpdatedAt)
SELECT 1000000 + n, :v, :loc, CONCAT('PERF-', RIGHT('00000' + CAST(n AS varchar(6)), 6)),
       CONCAT(CHOOSE(n % 4 + 1, N'Çelik mil ', N'Rulman ', N'Sac levha ', N'İşlenmiş kapak '), n),
       N'ADET', CHOOSE(n % 6 + 1, N'Çubuk', N'Levha', N'Rulman', N'Conta', N'Dövme', N'İşlenmiş parça'),
       CHOOSE(n % 3 + 1, N'Hammadde', N'Yarı mamul', N'Nihai ürün'), n % 500, CHOOSE(n % 3 + 1, 'A', 'B', 'C'),
       CONCAT('PERF-', n), SYSUTCDATETIME()
FROM (SELECT TOP (:rows) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n
      FROM sys.all_objects a CROSS JOIN sys.all_objects b) x
""")


def median_ms(work) -> float:
    times = []
    for _ in range(RUNS):
        start = time.perf_counter()
        work()
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


@pytest.fixture
def big_session(db_engine):
    conn = db_engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    try:
        v, loc = conn.execute(text("SELECT TOP 1 Id, LocationId FROM adm.DataVersion ORDER BY Id DESC")).one()
        conn.execute(GENERATE, {"v": v, "loc": loc, "rows": ROWS})
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


def test_first_chunk_and_counts_under_target(big_session):
    req = QueryRequest(
        filters=[FilterItem(field="Name", op="contains", value="çelik"),
                 FilterItem(field="MaterialLevel", op="in", values=["Hammadde", "Yarı mamul"])],
        sort=[SortItem(field="MaterialGroup"), SortItem(field="SafetyStock", dir="desc")], limit=100)
    body = service.query(big_session, MATERIALS, req)
    assert body["total"] >= ROWS and body["filtered"] > 0 and len(body["rows"]) == 100
    ms = median_ms(lambda: service.query(big_session, MATERIALS, req))
    print(f"\nsorgu (50.000 satır, filtre + 2 sıralama + 100 satır + sayılar): ortanca {ms:.0f} ms")
    assert ms < TARGET_MS


def test_last_chunk_under_target(big_session):
    req = QueryRequest(sort=[SortItem(field="Name", dir="desc")], offset=ROWS - 100, limit=100)
    ms = median_ms(lambda: service.query(big_session, MATERIALS, req))
    print(f"\nson parça (offset {ROWS - 100}): ortanca {ms:.0f} ms")
    assert ms < TARGET_MS


def test_values_under_target(big_session):
    req = ValuesRequest(field="MaterialGroup", search="U", filters=[FilterItem(field="Name", op="contains", value="MİL")])
    assert service.values(big_session, MATERIALS, req)
    ms = median_ms(lambda: service.values(big_session, MATERIALS, req))
    print(f"\ndeğerler: ortanca {ms:.0f} ms")
    assert ms < TARGET_MS


def test_groups_under_target(big_session):
    """K-90: iki alanla gruplama + filtre + ara toplamlar (toplam, ortalama, birim karışıklığı)."""
    req = GroupsRequest(group_by=["MaterialLevel", "MaterialGroup"], fields=list(MATERIALS.default_visible),
                        filters=[FilterItem(field="Name", op="contains", value="e")],
                        sort=[SortItem(field="MaterialLevel", dir="desc")])
    tree = service.groups(big_session, MATERIALS, req)
    assert sum(g["count"] for g in tree["groups"]) > ROWS / 2
    ms = median_ms(lambda: service.groups(big_session, MATERIALS, req))
    print(f"\ngruplama (2 alan, filtre, ara toplamlar): ortanca {ms:.0f} ms")
    assert ms < TARGET_MS


# --- koşullu biçim (K-95): 10 kural, satır başına _rules ve etki sayıları ---

RULES_10 = [
    RuleSpec(field="Name", condition={"op": "contains", "value": "çelik"}),
    RuleSpec(field="Name", condition={"op": "starts_with", "value": "rul"}),
    RuleSpec(field="MaterialGroup", condition={"op": "in", "values": ["Çubuk", "Levha"]}),
    RuleSpec(field="MaterialLevel", condition={"op": "equals", "value": "hammadde"}),
    RuleSpec(field="SafetyStock", condition={"op": "between", "min": 100, "max": 300}),
    RuleSpec(field="SafetyStock", condition={"op": "gt", "value": 400}),
    RuleSpec(field="SafetyStock", condition={"op": "lt", "field_ref": "MaxStock"}),
    RuleSpec(field="UpdatedAt", condition={"op": "relative", "value": "this_week"}),
    RuleSpec(field="AdditionalText1", condition={"op": "empty"}),
    RuleSpec(field="Code", condition={"op": "contains", "value": "99"}),
]


def test_rules_first_chunk_under_target(big_session):
    """İlk sorgu testindeki istek + 10 kural; kuralların getirdiği ek süre de yazılır."""
    base = QueryRequest(
        filters=[FilterItem(field="Name", op="contains", value="çelik"),
                 FilterItem(field="MaterialLevel", op="in", values=["Hammadde", "Yarı mamul"])],
        sort=[SortItem(field="MaterialGroup"), SortItem(field="SafetyStock", dir="desc")], limit=100)
    req = base.model_copy(update={"rules": RULES_10})
    body = service.query(big_session, MATERIALS, req)
    assert len(body["rows"]) == 100 and any(r["_rules"] for r in body["rows"])
    plain = median_ms(lambda: service.query(big_session, MATERIALS, base))
    ms = median_ms(lambda: service.query(big_session, MATERIALS, req))
    print(f"\nkurallı sorgu (50.000 satır, 10 kural, ilk parça + sayılar): ortanca {ms:.0f} ms (kuralsız {plain:.0f} ms)")
    assert ms < TARGET_MS


# --- grafik (K-178): toplama ucu; ölçümler Aşama 7 sonundaki performans işinde koşulur ---

CHARTS = {
    "kategori + kırılım": {"x": {"field": "MaterialGroup"}, "split": "MaterialLevel",
                           "series": [{"id": "a", "field": "SafetyStock", "fn": "sum"}, {"id": "n", "fn": "count"}]},
    "haftalık dönem + iki seri": {"x": {"field": "UpdatedAt", "bucket": "week"},
                                  "series": [{"id": "a", "field": "SafetyStock", "fn": "avg"}, {"id": "b", "field": "SafetyStock", "fn": "max"}]},
    "filtreli, çok kategorili": {"x": {"field": "Name"}, "series": [{"id": "a", "field": "SafetyStock", "fn": "sum"}],
                                 "filters": [{"field": "Name", "op": "contains", "value": "e"}, {"field": "SafetyStock", "op": "between", "min": 50, "max": 450},
                                             {"field": "MaterialGroup", "op": "in", "values": ["Çubuk", "Levha", "Rulman", "Conta"]}]},
}


@pytest.mark.parametrize("name", list(CHARTS))
def test_chart_under_target(big_session, name):
    req = ChartRequest.model_validate(CHARTS[name])
    out = service.chart(big_session, MATERIALS, req)
    assert out["rows"] > ROWS / 10
    ms = median_ms(lambda: service.chart(big_session, MATERIALS, req))
    print(f"\ngrafik ({name}): ortanca {ms:.0f} ms")
    assert ms < TARGET_MS



# --- ilişkili alanlar (K-182): iki seviyeli ilişkili alanla ilk parça, süzme ve sıralama ---

RELATED_WORK_ORDERS = 5_000
RELATED_NAME = "WorkOrderId/MaterialId/Name"


def _copy_rows(conn, table: str, rows: int, overrides: dict[str, str]) -> None:
    """Tablonun güncel ilk satırını şablon alıp `rows` satır üretir; `overrides`: kolon → n'e bağlı SQL ifadesi (Id dahil)."""
    cols = [r[0] for r in conn.execute(text("SELECT name FROM sys.columns WHERE object_id = OBJECT_ID(:t) AND is_computed = 0 AND is_identity = 0 "
                                            "ORDER BY column_id"), {"t": f"core.{table}"})]
    select = ", ".join(overrides.get(c, f"t.[{c}]") for c in cols)
    conn.execute(text(f"INSERT INTO core.[{table}] ({', '.join(f'[{c}]' for c in cols)}) SELECT {select} "
                      f"FROM (SELECT TOP 1 * FROM core.[{table}] WHERE VersionTo IS NULL ORDER BY Id) t "
                      "CROSS JOIN (SELECT TOP (:rows) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n FROM sys.all_objects a CROSS JOIN sys.all_objects b) x"),
                 {"rows": rows})


def generate_related(conn, operations: int = ROWS, work_orders: int = RELATED_WORK_ORDERS) -> None:
    """Malzemeler (bugünkü üretici), her biri bir malzemeye bağlı üretim siparişleri ve her biri bir üretim siparişine bağlı operasyonlar."""
    v, loc = conn.execute(text("SELECT TOP 1 Id, LocationId FROM adm.DataVersion ORDER BY Id DESC")).one()
    conn.execute(GENERATE, {"v": v, "loc": loc, "rows": work_orders})
    _copy_rows(conn, "WorkOrder", work_orders, {
        "Id": "2000000 + x.n", "VersionFrom": str(int(v)), "VersionTo": "NULL", "WorkOrderNo": "CONCAT('PERF-WO-', x.n)",
        "MaterialId": "1000000 + x.n", "BusinessKey": "CONCAT('PERF-WO-', x.n)", "ParentWorkOrderId": "NULL"})
    _copy_rows(conn, "WorkOrderOperation", operations, {
        "Id": "3000000 + x.n", "VersionFrom": str(int(v)), "VersionTo": "NULL", "WorkOrderId": f"2000000 + (x.n % {int(work_orders)}) + 1",
        "OperationNo": "x.n", "BusinessKey": "CONCAT('PERF-WOO-', x.n)"})


@pytest.fixture
def related_session(db_engine):
    conn = db_engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    try:
        generate_related(conn)
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.mark.parametrize("name, req", [
    ("ilk parça", QueryRequest(fields=["WorkOrderCode", "OperationName", RELATED_NAME], limit=100)),
    ("ilişkili alanda süzme", QueryRequest(fields=["WorkOrderCode", "OperationName", RELATED_NAME], limit=100,
                                           filters=[FilterItem(field=RELATED_NAME, op="contains", value="çelik")])),
    ("ilişkili alanda sıralama", QueryRequest(fields=["WorkOrderCode", "OperationName", RELATED_NAME], limit=100,
                                              sort=[SortItem(field=RELATED_NAME, dir="desc")])),
])
def test_related_fields_under_target(related_session, name, req):
    """K-182: Üretim siparişi operasyonu → Üretim siparişi → Malzeme; 50.000 operasyon, 5.000 üretim siparişi. Yazıldı, tam performans ölçümüyle birlikte koşulur."""
    from app.api.lists.master_data import BY_NAME
    defn = BY_NAME["transaction-work-order-operation"]
    body = service.query(related_session, defn, req)
    assert body["total"] >= ROWS and len(body["rows"]) == 100 and all(r[RELATED_NAME] for r in body["rows"])
    ms = median_ms(lambda: service.query(related_session, defn, req))
    print(f"\nilişkili alan, iki seviye ({name}): ortanca {ms:.0f} ms")
    assert ms < TARGET_MS


# --- pivot (K-183): toplama veritabanında; hedef grafiğinkinden gevşek (çapraz ara toplamlar): ortanca 500 ms ---

PIVOT_TARGET_MS = 500
PIVOT_VALUES = [{"id": "a", "field": "SafetyStock", "fn": "sum"}, {"id": "b", "field": "SafetyStock", "fn": "avg"},
                {"id": "c", "kind": "calc", "a": "a", "op": "div", "b": "b", "rules": [{"id": "k1", "enabled": True, "condition": {"op": "gt", "value": 100}, "format": {"fill": "#f7dcd5"}}]}]
PIVOT_TOTALS = {"rows": True, "columns": True, "subtotals": True}
PIVOTS = {
    "iki satır alanı × sütun, bütün toplamlar": {"rows": [{"field": "MaterialGroup"}, {"field": "BaseUom"}], "columns": [{"field": "MaterialLevel"}],
                                                 "values": PIVOT_VALUES, "totals": PIVOT_TOTALS},
    "50.000 yaprak satır, ilk parça": {"rows": [{"field": "MaterialGroup"}, {"field": "Name"}], "columns": [{"field": "MaterialLevel"}],
                                       "values": PIVOT_VALUES, "totals": PIVOT_TOTALS, "limit": 100},
    "50.000 yaprak satır, değere göre sıralı son parça": {"rows": [{"field": "MaterialGroup"}, {"field": "Name"}], "columns": [{"field": "MaterialLevel"}],
                                                          "values": PIVOT_VALUES, "totals": PIVOT_TOTALS, "sort": {"by": "a", "dir": "desc"},
                                                          "offset": ROWS - 100, "limit": 100},
    "filtreli": {"rows": [{"field": "MaterialGroup"}, {"field": "BaseUom"}], "columns": [{"field": "MaterialLevel"}], "values": PIVOT_VALUES,
                 "totals": PIVOT_TOTALS, "filters": [{"field": "Name", "op": "contains", "value": "e"}, {"field": "SafetyStock", "op": "between", "min": 50, "max": 450}]},
}


@pytest.mark.parametrize("name", list(PIVOTS))
def test_pivot_under_target(big_session, name):
    req = PivotRequest.model_validate(PIVOTS[name])
    out = service.pivot(big_session, MATERIALS, req)
    assert out["rows"] and out["row_count"] >= len(out["rows"])
    ms = median_ms(lambda: service.pivot(big_session, MATERIALS, req))
    print(f"\npivot ({name}): ortanca {ms:.0f} ms")
    assert ms < PIVOT_TARGET_MS

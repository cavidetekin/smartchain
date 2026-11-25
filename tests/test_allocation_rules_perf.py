"""Alokasyon kuralı hesabının performans ölçümü (K-199, docs/08): yaklaşık 10.000 malzeme, 16 seviye, 30.000 ağaç satırı, 5.000 açık sipariş
satırı, 30 proje, 200 müşteri, 300 ayrılmış arz (üçte biri sipariş, proje ve müşteri).

Ölçülenler (üç koşunun ortancası): hesabın aşamaları ve toplamı, kaynak malzemeli ve kaynak malzemesiz; ayrıca fark alıp yazma dahil tam çağrı.
Hedef: toplam ortanca ≤ 10 sn (hesap her aktarımın içinde çalışır). Veri bir işlem içinde üretilir, ölçülür ve geri alınır; iz kalmaz.

Ağacın biçimi: 110 ürün ailesi; her ailede bir mamul ve 15 seviyede altışar malzeme. Her malzeme bir alt seviyedeki üç malzemeyi kullanır; her
seviyede bir malzeme komşu ailenin malzemesini de kullanır (ortak parça). Her mamulün ağacı böylece komşu ailelere de uzanır.
"""
import statistics
import time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.allocation import rules

pytestmark = [pytest.mark.db, pytest.mark.perf]

FAMILIES, LEVELS, WIDTH = 110, 15, 6          # 110 × (1 + 15 × 6) = 10.010 malzeme; mamul dahil 16 seviye
PER = 1 + LEVELS * WIDTH
ORDERS, PROJECTS, CUSTOMERS, SUPPLIES = 5_000, 30, 200, 300
BASE = 8_000_000
TARGET_SECONDS = 10.0
RUNS = 3


def node(family: int, level: int, w: int = 0) -> int:
    """Malzemenin kimliği: seviye 0 mamul; seviye 1–15'te altışar malzeme."""
    return BASE + (family % FAMILIES) * 100 + (0 if level == 0 else (level - 1) * WIDTH + w % WIDTH + 1)


def _values(conn, table: str, rows: list[tuple]) -> None:
    for i in range(0, len(rows), 1000):
        conn.execute(text(f"INSERT INTO {table} VALUES " + ", ".join("(" + ", ".join(v if isinstance(v, str) else str(v) for v in row) + ")" for row in rows[i:i + 1000])))


def generate(conn) -> dict:
    v = int(conn.execute(text("SELECT MAX(Id) FROM adm.DataVersion")).scalar())
    loc = conn.execute(text("INSERT INTO core.Location (Code, Name, IsActive, IsSynthetic) OUTPUT inserted.Id VALUES (N'PERF-AR', N'Perf', 1, 0)")).scalar_one()
    materials = [(node(f, lv, w),) for f in range(FAMILIES) for lv, w in [(0, 0), *[(lv, w) for lv in range(1, LEVELS + 1) for w in range(WIDTH)]]]
    edges = []
    for f in range(FAMILIES):
        edges += [(node(f, 0), node(f, 1, w)) for w in range(WIDTH)]
        for lv in range(1, LEVELS):
            edges += [(node(f, lv, w), node(f, lv + 1, w + d)) for w in range(WIDTH) for d in range(3)]
            edges.append((node(f, lv, 0), node(f + 1, lv + 1, 0)))          # ortak parça: komşu ailenin malzemesi
    orders = [(n, node(n, 0), n % CUSTOMERS, n % PROJECTS if n % 3 == 0 else "NULL") for n in range(ORDERS)]
    supplies = []
    for n in range(SUPPLIES):
        kind, lv, w = n % 3, 8 + n % 8, n % WIDTH
        if kind == 0:      # siparişe: siparişin kendi ailesinde, derinde
            order = (n * 37) % ORDERS
            supplies.append((n, node(order, lv, w), "N'Sipariş'", f"N'PSO-{order}|10|0'"))
        elif kind == 1:    # projeye
            supplies.append((n, node(n * 7, lv, w), "N'Proje'", f"N'PERF-P-{n % PROJECTS}'"))
        else:              # müşteriye: müşterinin bir siparişinin ailesinde
            customer = n % CUSTOMERS
            supplies.append((n, node(customer + CUSTOMERS * (n % 5), lv, w), "N'Müşteri'", f"N'PERF-C-{customer}'"))
    for sql in ("CREATE TABLE #pm (Id bigint PRIMARY KEY)", "CREATE TABLE #pe (P bigint, C bigint, PRIMARY KEY (P, C))",
                "CREATE TABLE #po (N int PRIMARY KEY, M bigint, Cu int, Pr int NULL)",
                "CREATE TABLE #ps (N int PRIMARY KEY, M bigint, L nvarchar(10) COLLATE DATABASE_DEFAULT, K nvarchar(60) COLLATE DATABASE_DEFAULT)"):
        conn.execute(text(sql))
    _values(conn, "#pm", materials)
    _values(conn, "#pe", edges)
    _values(conn, "#po", orders)
    _values(conn, "#ps", supplies)
    p = {"v": v, "l": loc}
    conn.execute(text("INSERT INTO core.Material (Id, LocationId, Code, Name, BaseUom, IsActive, IsCustomAllocated, VersionFrom, BusinessKey, UpdatedAt) "
                      "SELECT Id, :l, CONCAT('PERF-AR-', Id), N'Perf', N'ADET', 1, 1, :v, CONCAT('PERF-AR-', Id), SYSUTCDATETIME() FROM #pm"), p)
    conn.execute(text("INSERT INTO core.ProductionVersion (Id, LocationId, MaterialId, Code, IsActive, BOMCode, RouteCode, VersionFrom, BusinessKey, UpdatedAt) "
                      "SELECT DISTINCT P, :l, P, N'V1', 1, CONCAT('B', P), N'R', :v, CONCAT('PERF-PV-', P), SYSUTCDATETIME() FROM #pe"), p)
    conn.execute(text("INSERT INTO core.BOM (Id, LocationId, MaterialId, Code, ComponentMaterialId, OperationNo, SequenceNo, Quantity, VersionFrom, BusinessKey, UpdatedAt) "
                      "SELECT 9000000 + ROW_NUMBER() OVER (ORDER BY P, C), :l, P, CONCAT('B', P), C, 10, 1, 1, :v, CONCAT('PERF-B-', P, '-', C), SYSUTCDATETIME() FROM #pe"), p)
    numbers = "(SELECT TOP ({n}) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS n FROM sys.all_objects a CROSS JOIN sys.all_objects b) x"
    for table, prefix, count in (("Customer", "PERF-C-", CUSTOMERS), ("Project", "PERF-P-", PROJECTS)):
        conn.execute(text(f"INSERT INTO core.[{table}] (Id, Code, Name, IsActive, VersionFrom, BusinessKey, UpdatedAt) "
                          f"SELECT 8000000 + x.n, CONCAT('{prefix}', x.n), N'Perf', 1, :v, CONCAT('{prefix}', x.n), SYSUTCDATETIME() FROM " + numbers.format(n=count)), p)
    conn.execute(text("INSERT INTO core.SalesOrderLine (Id, LocationId, OrderNo, [LineNo], LineItemNo, CustomerId, ProjectId, MaterialId, OpenQuantity, RequestedDate, IsActive, "
                      "VersionFrom, BusinessKey, UpdatedAt) SELECT 8000000 + N, :l, CONCAT('PSO-', N), 10, 0, 8000000 + Cu, 8000000 + Pr, M, 5, '20270101', 1, :v, "
                      "CONCAT('PERF-SO-', N), SYSUTCDATETIME() FROM #po"), p)
    conn.execute(text("INSERT INTO core.Stock (Id, LocationId, MaterialId, Warehouse, LotNo, Status, Quantity, IsActive, IsCustomAllocated, AllocationLevel, AllocationKey, "
                      "VersionFrom, BusinessKey, UpdatedAt) SELECT 8000000 + N, :l, M, N'PERF', CONCAT('P', N), N'Serbest', 10, 1, 1, L, K, :v, CONCAT('PERF-ST-', N), "
                      "SYSUTCDATETIME() FROM #ps"), p)
    return {"version": v, "location": loc, "materials": len(materials), "bom": len(edges), "orders": len(orders), "supplies": len(supplies)}


def measure(conn, sources: bool) -> dict:
    """Hesabın aşama süreleri: RUNS koşunun ortancası (sn); sayılar son koşudan."""
    runs = []
    try:
        for _ in range(RUNS):
            runs.append(rules.compute(conn, sources=sources))
    finally:
        rules._drop(conn)
    seconds = {k: round(statistics.median(r["seconds"][k] for r in runs), 3) for k in runs[0]["seconds"]}
    return {"seconds": seconds, "total": round(statistics.median(sum(r["seconds"].values()) for r in runs), 3),
            **{k: v for k, v in runs[-1].items() if k != "seconds"}}


def test_allocation_rules_at_scale(db_engine, capsys):
    with Session(db_engine) as s:
        try:
            size = generate(s)
            with_sources = measure(s, True)
            without = measure(s, False)
            t0 = time.perf_counter()
            full = rules.rebuild(s, size["version"], s.execute(text("SELECT SYSUTCDATETIME()")).scalar(), history=True)
            rebuild_seconds = round(time.perf_counter() - t0, 3)
            rows = s.execute(text("SELECT COUNT(*), SUM(CASE WHEN Reason = :own THEN 1 ELSE 0 END) FROM core.MaterialAllocationRule WHERE LocationId = :l AND VersionTo IS NULL"),
                             {"own": rules.OWN, "l": size["location"]}).one()
        finally:
            s.rollback()
    with capsys.disabled():
        print(f"\nAlokasyon kuralı · {size['materials']} malzeme, {size['bom']} ağaç satırı, {size['orders']} sipariş satırı, {size['supplies']} ayrılmış arz")
        print(f"  kenar {with_sources['edges']} · arz anahtarı {with_sources['supply']} · talep anahtarı {with_sources['demand']} · "
              f"aşağı {with_sources['levels_down']} seviye · yukarı {with_sources['levels_up']} seviye · kural {with_sources['rules']} (bu lokasyonda {rows[0]}; {rows[1]} kendi arzı)")
        print(f"  kaynak malzemeli  : toplam {with_sources['total']} sn  {with_sources['seconds']}")
        print(f"  kaynak malzemesiz : toplam {without['total']} sn  {without['seconds']}")
        print(f"  fark ve yazma dahil tam çağrı (ilk yazma, Geçmiş dahil): {rebuild_seconds} sn  {full['seconds']}")
    assert rows[0] > 1000 and with_sources["levels_up"] >= 15
    assert with_sources["total"] <= TARGET_SECONDS, f"kaynak malzemeli hesap {with_sources['total']} sn; hedef {TARGET_SECONDS} sn"

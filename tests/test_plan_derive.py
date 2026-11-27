"""Malzeme hareketleri ve kapasite yükleri türetmesi (K-205, `app/planning/derive.py`): her satır türü, elle kurulmuş küçük bir plan hesabıyla.

Sentetik verinin üzerinde (Smartchain_test) bir plan hesabı işlem içinde açılır, karar satırları doğrudan yazılır, türetme çalışır; beklenen değerler
veritabanındaki ağaç, rota ve sipariş satırlarından ayrıca hesaplanır. Test sonunda işlem geri alınır.
"""
from collections import defaultdict
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.data.synthetic import dataset as d
from app.periods import cache
from app.planning import demand, derive, movements as mv

pytestmark = pytest.mark.db
CUR = "VersionTo IS NULL"


def one(session, sql, **p):
    return session.execute(sa.text(sql), p).scalar()


def rows(session, sql, **p):
    return session.execute(sa.text(sql), p).all()


@pytest.fixture
def run(db_engine):
    """Baz senaryoda, sentetik veri versiyonunda bir plan hesabı ve talep kopyası; işlem sonunda geri alınır."""
    with Session(db_engine) as s:
        try:
            version = one(s, "SELECT MAX(v.Id) FROM adm.DataVersion v JOIN core.Location l ON l.Id = v.LocationId AND l.Code = :c WHERE v.IsSynthetic = 1",
                          c=d.LOCATION_CODE)
            assert version, "test veritabanında sentetik veri bekleniyor"
            base = cache.base_id(s)
            rid = one(s, "INSERT INTO planning.PlanRun (DataVersionId, ScenarioDefinitionId, Status) OUTPUT inserted.Id VALUES (:v, :sd, N'Sırada')", v=version, sd=base)
            demand.copy(s, rid)
            periods = derive.plan_periods(s, base)
            yield s, rid, version, periods
        finally:
            s.rollback()


def supply(s, rid, **row):
    cols = {"PlanRunId": rid, "IsManual": 0, "IsFixed": 0, "IsIncluded": 1, "IsSubcontract": 0, "UpdatedAt": sa.func.sysutcdatetime(), **row}
    t = sa.Table("PlannedSupply", sa.MetaData(), autoload_with=s.connection(), schema="planning")
    return s.execute(sa.insert(t).values(**cols).returning(t.c.Id)).scalar_one()


def test_every_movement_type_and_load(run):
    s, rid, version, periods = run
    p2, p3 = periods[1], periods[2]
    mat = dict(rows(s, f"SELECT Code, Id FROM core.Material WHERE {CUR}"))
    loc = one(s, "SELECT Id FROM core.Location WHERE Code = :c", c=d.LOCATION_CODE)
    pv = s.execute(sa.text(f"SELECT Id, BOMCode, RouteCode, BaseQuantity FROM core.ProductionVersion WHERE MaterialId = :m AND Code = N'V1' AND {CUR}"),
                   {"m": mat["MAM-001"]}).one()
    wo = s.execute(sa.text(f"SELECT Id, MaterialId, OpenQuantity FROM core.WorkOrder WHERE WorkOrderNo = N'WO-5012' AND {CUR}")).one()
    # karar satırları: üretim planı, satın alma planı (yuvarlanmış), iki döneme bölünmüş üretim siparişi, alokasyon transferi, karşılama satırı
    production = supply(s, rid, SupplyNo="ÜP-000001", SupplyType=mv.SUPPLY_PRODUCTION, Source=mv.SOURCE_PLAN, MaterialId=mat["MAM-001"], LocationId=loc, Uom="ADET",
                        PeriodStart=p2.start, PeriodEnd=p2.end, ProductionVersionId=pv.Id, BOMCode=pv.BOMCode, RouteCode=pv.RouteCode, Quantity=10, RoundedQuantity=10)
    purchase = supply(s, rid, SupplyNo="SP-000001", SupplyType=mv.SUPPLY_PURCHASE, Source=mv.SOURCE_PLAN, MaterialId=mat["SAT-007"], LocationId=loc, Uom="ADET",
                      PeriodStart=p2.start, PeriodEnd=p2.end, Quantity=12, RoundedQuantity=50)
    halves = [supply(s, rid, SupplyNo="WO-5012", SupplyType=mv.SUPPLY_PRODUCTION, Source=mv.SOURCE_ORDER, WorkOrderId=wo.Id, MaterialId=wo.MaterialId,
                     LocationId=loc, Uom="ADET", PeriodStart=p.start, PeriodEnd=p.end, Quantity=float(wo.OpenQuantity) / 2, RoundedQuantity=float(wo.OpenQuantity) / 2)
              for p in (p2, p3)]
    excluded = supply(s, rid, SupplyNo="ÜP-000002", SupplyType=mv.SUPPLY_PRODUCTION, Source=mv.SOURCE_PLAN, MaterialId=mat["MAM-002"], LocationId=loc, Uom="ADET",
                      PeriodStart=p2.start, PeriodEnd=p2.end, Quantity=5, RoundedQuantity=5, IsIncluded=0)
    s.execute(sa.text("INSERT INTO planning.PlannedAllocationTransfer (PlanRunId, MaterialId, LocationId, PeriodStart, PeriodEnd, AllocationLevel, AllocationKey, "
                      "Quantity, Uom, UpdatedAt) VALUES (:r, :m, :l, :a, :b, N'Müşteri', N'MUS-A', 5, N'ADET', SYSUTCDATETIME())"),
              {"r": rid, "m": mat["SAT-009"], "l": loc, "a": p2.start, "b": p2.end})
    dem = s.execute(sa.text("SELECT TOP 1 * FROM planning.PlannedDemand WHERE PlanRunId = :r AND IsIncluded = 1 AND OrderNo IS NOT NULL ORDER BY Id"), {"r": rid}).mappings().one()
    fid = one(s, "INSERT INTO planning.DemandFulfillment (PlanRunId, PlannedDemandId, DemandType, OrderNo, [LineNo], LineItemNo, CustomerId, ProjectId, MaterialId, "
                 "LocationId, Uom, PeriodStart, PeriodEnd, Quantity, IsTardy, UpdatedAt) OUTPUT inserted.Id VALUES (:r, :d, :t, :o, :ln, :li, :c, :p, :m, :l, :u, :a, :b, :q, 0, "
                 "SYSUTCDATETIME())", r=rid, d=dem["Id"], t=dem["DemandType"], o=dem["OrderNo"], ln=dem["LineNo"], li=dem["LineItemNo"], c=dem["CustomerId"],
              p=dem["ProjectId"], m=dem["MaterialId"], l=loc, u=dem["Uom"], a=p2.start, b=p2.end, q=dem["DemandQuantity"])

    out = derive.derive(s, rid)
    t = s.execute(sa.text("SELECT * FROM planning.MaterialTransaction WHERE PlanRunId = :r"), {"r": rid}).mappings().all()
    by = defaultdict(list)
    for x in t:
        by[x["MovementType"]].append(x)
    first = periods[0].start
    assert all(x["MovementDate"] == x["PeriodStart"] for x in t)                                                  # hareket tarihi dönem başı

    # + Stok, + Kalitedeki stok: aktif, bloke değil; ilk dönem; bloke stok yazılmaz
    stock = rows(s, f"SELECT Id, IsInQuality, Quantity FROM core.Stock WHERE {CUR} AND ISNULL(IsActive, 1) = 1 AND ISNULL(IsBlocked, 0) = 0 AND Quantity > 0")
    blocked = {r[0] for r in rows(s, f"SELECT Id FROM core.Stock WHERE {CUR} AND IsBlocked = 1")}
    assert {x["StockId"] for x in by[mv.STOCK] + by[mv.QUALITY_STOCK]} == {r[0] for r in stock} and blocked and not blocked & {x["StockId"] for x in t}
    assert {x["StockId"] for x in by[mv.QUALITY_STOCK]} == {r[0] for r in stock if r[1]} and all(x["PeriodStart"] == first for x in by[mv.STOCK])

    # + Satın alma siparişi: açık satırlar; üretim siparişine bağlı fason satır yazılmaz; geçmiş tarih ilk döneme
    po = rows(s, f"SELECT Id, IsSubcontract, WorkOrderId, COALESCE(ConfirmedDate, RequestedDate), PurchaseOrderNo FROM core.PurchaseOrderLine WHERE {CUR} "
                 "AND ISNULL(IsActive, 1) = 1 AND OpenQuantity > 0")
    linked = {r[0] for r in po if r[1] and r[2]}
    assert linked and {x["PurchaseOrderLineId"] for x in by[mv.PURCHASE_ORDER]} == {r[0] for r in po} - linked
    assert all(x["DocumentNo"] for x in by[mv.PURCHASE_ORDER]) and all(x["PeriodStart"] <= max(r[3], first) <= x["PeriodEnd"] or r[3] < first
                                                                       for x in by[mv.PURCHASE_ORDER] for r in po if r[0] == x["PurchaseOrderLineId"])

    # + tedarik planı: üretimde Miktar, satın almada Yuvarlanmış miktar; plana dahil olmayan yazılmaz
    plus = {x["PlannedSupplyId"]: x for x in t if x["Direction"] == mv.PLUS and x["PlannedSupplyId"]}
    assert (plus[production]["MovementType"], float(plus[production]["Quantity"]), plus[production]["DocumentNo"]) == (mv.PRODUCTION_PLAN, 10.0, "ÜP-000001")
    assert (plus[purchase]["MovementType"], float(plus[purchase]["Quantity"])) == (mv.PURCHASE_PLAN, 50.0)
    assert {plus[h]["MovementType"] for h in halves} == {mv.PRODUCTION_ORDER} and excluded not in plus
    assert not [x for x in t if x["PlannedSupplyId"] == excluded]

    # − Üretim planı ihtiyacı: miktar × BOM miktarı ÷ temel miktar × (1 + fire); bileşen başına bir satır
    expected = defaultdict(float)
    for comp, qty, scrap, lot in rows(s, f"SELECT ComponentMaterialId, Quantity, ISNULL(ScrapRatio, 0), ISNULL(IsLotBasedUsage, 0) FROM core.BOM WHERE Code = :c "
                                         f"AND {CUR} AND Quantity > 0", c=pv.BOMCode):
        expected[comp] += float(qty if lot else Decimal(10) * qty / pv.BaseQuantity) * (1 + float(scrap))
    got = {x["MaterialId"]: float(x["Quantity"]) for x in by[mv.PRODUCTION_PLAN_NEED] if x["PlannedSupplyId"] == production}
    assert got == pytest.approx(dict(expected)) and all(x["DocumentNo"] == "ÜP-000001" for x in by[mv.PRODUCTION_PLAN_NEED])

    # − Üretim siparişi ihtiyacı: siparişin kendi bileşenleri; bölünmüş siparişte miktarla orantılı (yarı yarıya)
    remaining = defaultdict(float)
    for comp, rem in rows(s, f"SELECT MaterialId, COALESCE(RemainingQuantity, RequiredQuantity - ISNULL(IssuedQuantity, 0)) FROM core.WorkOrderComponent "
                             f"WHERE WorkOrderId = :w AND {CUR}", w=wo.Id):
        if rem and rem > 0:
            remaining[comp] += float(rem)
    for h in halves:
        got = {x["MaterialId"]: float(x["Quantity"]) for x in by[mv.PRODUCTION_ORDER_NEED] if x["PlannedSupplyId"] == h}
        assert got == pytest.approx({k: v / 2 for k, v in remaining.items()})

    # − Talep: karşılama adedi; no satış sipariş no
    [dx] = [x for x in t if x["DemandFulfillmentId"] == fid]
    assert (dx["Direction"], dx["MovementType"], float(dx["Quantity"]), dx["DocumentNo"]) == (mv.MINUS, dem["DemandType"], float(dem["DemandQuantity"]), dem["OrderNo"])

    # ± Alokasyon transferi: genelden −, özele +
    pair = sorted((x["Direction"], x["AllocationKey"], float(x["Quantity"])) for x in by[mv.ALLOCATION_TRANSFER])
    assert pair == [("+", "MUS-A", 5.0), ("-", None, 5.0)]
    assert out["MaterialTransaction"]["Tedarik planı"] == 4

    # Kapasite yükü: üretim planında rotadan (tüketim ÷ temel miktar × miktar, aynı grup toplanır); üretim siparişinde kalan tüketim, tamamlanmış
    # operasyon yazmaz, bölünmüşte yarı yarıya; satın almada yük yok; plana dahil olmayan yazılmaz
    loads = s.execute(sa.text("SELECT PlannedSupplyId, ResourceGroupId, ProductionQuantity, UnitUsage, CapacityUsage FROM planning.CapacityLoad WHERE PlanRunId = :r"),
                      {"r": rid}).all()
    route = defaultdict(float)
    for g, c in rows(s, f"SELECT ResourceGroupId, Consumption FROM core.Routing WHERE RouteCode = :rc AND {CUR} AND ISNULL(IsActive, 1) = 1 "
                        "AND ISNULL(IsLotBasedUsage, 0) = 0 AND Consumption > 0", rc=pv.RouteCode):
        route[g] += float(c)
    assert {g: float(u) for sid, g, q, unit, u in loads if sid == production} == pytest.approx({g: 10 * c / float(pv.BaseQuantity) for g, c in route.items()})
    assert all(abs(float(u) - float(q) * float(unit)) < 0.01 for _, _, q, unit, u in loads)
    ops = defaultdict(float)
    for g, rem in rows(s, f"SELECT ResourceGroupId, COALESCE(RemainingConsumption, PlannedConsumption - ISNULL(ConfirmedConsumption, 0)) FROM core.WorkOrderOperation "
                          f"WHERE WorkOrderId = :w AND {CUR} AND ISNULL(IsActive, 1) = 1 AND ISNULL(IsCompleted, 0) = 0 AND ISNULL(IsLotBasedUsage, 0) = 0", w=wo.Id):
        if rem and rem > 0:
            ops[g] += float(rem)
    for h in halves:
        assert {g: float(u) for sid, g, q, unit, u in loads if sid == h} == pytest.approx({g: v / 2 for g, v in ops.items()})
    assert not [x for x in loads if x[0] in (purchase, excluded)]

    # yeniden türetme aynı sonucu verir (önce siler)
    assert derive.derive(s, rid) == out

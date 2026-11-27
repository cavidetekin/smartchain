"""Malzeme hareketleri ve kapasite yükleri türetmesi (K-202, K-205; geliştirme 8.0): karar tablolarından ve ERP'den gelen arzdan.

Kalıcı ürün kodudur: motor da fikstür de aynı türetmeyi kullanır (yazıcı karar satırlarını yazdıktan sonra, aynı işlemde çağırır). Plan hesabının
veri versiyonu (`PlanRun.DataVersionId`) ve senaryonun plan dönemleri okunur. Elle değişmez; tedarik planı elle değişince yeniden türetme 8.6'dan sonra.

**MaterialTransaction**
- + Stok, + Kalitedeki stok: `Stock` (aktif, bloke değil, miktarı > 0); ilk dönem; stok miktarı. Bloke stok hareket yazmaz.
- + Satın alma siparişi: açık `PurchaseOrderLine` (aktif, açık miktarı > 0); teyit, yoksa istek tarihinin dönemi, geçmişteyse ilk dönem, ufuktan
  sonraysa yazılmaz; açık miktar. Üretim siparişine bağlı fason satın alma satırı yazmaz (malzeme üretim siparişiyle gelir).
- + Üretim siparişi, + Üretim planı, + Satın alma planı: `PlannedSupply` (plana dahil); kaydın dönemi; Miktar (satın almada Yuvarlanmış miktar).
- − Talep (dört tür): `DemandFulfillment`; satırın dönemi; karşılama adedi.
- − Üretim planı ihtiyacı: tedarik planı kaydının ürün ağacı (`BOMCode`); üretimin dönemi; Miktar × BOM miktarı ÷ versiyonun temel miktarı ×
  (1 + fire). Parti bazlı satır kayıt başına bir kez; alternatif grupta yalnız en öncelikli; hayalet satır bileşeninin varsayılan versiyonuyla
  patlatılır; miktarı 0 olan satır yazılmaz.
- − Üretim siparişi ihtiyacı: siparişin kendi bileşenleri (`WorkOrderComponent`); kalan ihtiyaç (boşsa gereken − çekilen); sipariş döneme
  bölündüyse satırın miktarıyla orantılı.
- ± Alokasyon transferi: `PlannedAllocationTransfer`; iki satır (genelden −, özele +).
- Birim dönüşümü yoktur (K-205): satırın birimi malzemenin temel biriminden farklıysa satır atlanır ve sayılır (veri kalitesi uyarısı ayrıca verir).
- Her satır kaynağının alokasyon bilgisini taşır. Talep ve üretim ihtiyacı satırında anahtar, malzemenin alokasyon kuralında (`MaterialAllocationRule`)
  bulunan en detaylı sahiptir (talepte sipariş satırı → proje → müşteri; üretim ihtiyacında üst kaydın anahtarı); kural yoksa geneldir.
- Hareket tarihi şimdilik dönem başıdır. No: plan kaydında tedarik planı no, siparişte sipariş no, talepte satış sipariş no; stokta, tahminde ve
  transferde boş.

**CapacityLoad**
- Üretim planı: kaydın rotası (`RouteCode`); birim kullanım = tüketim ÷ versiyonun temel miktarı; yük = Miktar × birim kullanım; aynı gruba düşen
  satırlar toplanır. Parti bazlı satır (hazırlık) yazılmaz (Faz 1 dışı). Fason operasyon fasoncu kaynak grubuna yazar.
- Üretim siparişi: siparişin kendi operasyonları (`WorkOrderOperation`); kalan tüketim (boşsa planlanan − teyit edilen); tamamlanmış operasyon
  yazmaz; bölündüyse miktarla orantılı.
- Satın alma planı: yük yok.
"""
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.periods import periods as period_list

from . import movements as mv

ORDER, PROJECT, CUSTOMER = "Sipariş", "Proje", "Müşteri"   # app/allocation ile aynı adlar


def _v(alias: str) -> str:
    """Plan hesabının veri versiyonunda geçerli satır."""
    return f"{alias}.VersionFrom <= :v AND ({alias}.VersionTo IS NULL OR {alias}.VersionTo >= :v)"


def _active(alias: str) -> str:
    return f"ISNULL({alias}.IsActive, 1) = 1"


def _run(session: Session, plan_run_id: int) -> dict:
    row = session.execute(sa.text("SELECT DataVersionId, ScenarioDefinitionId FROM planning.PlanRun WHERE Id = :id"), {"id": plan_run_id}).one()
    return {"run": plan_run_id, "v": row.DataVersionId, "sid": row.ScenarioDefinitionId}


def plan_periods(session: Session, scenario_id: int, today: date | None = None) -> list[period_list.Period]:
    return period_list.read(session, scenario_id, today or date.today())


def _periods_table(session: Session, periods: list[period_list.Period]) -> None:
    """Dönemler geçici tabloda (uzun JSON parametresi büyük sorguda sürücüde eski metin tipine bağlanıyor; `demand.copy`'deki gibi)."""
    session.execute(sa.text("IF OBJECT_ID('tempdb..#DerivePeriod') IS NOT NULL DROP TABLE #DerivePeriod"))
    session.execute(sa.text("CREATE TABLE #DerivePeriod ([start] date NOT NULL PRIMARY KEY, [end] date NOT NULL)"))
    if periods:
        session.execute(sa.text("INSERT INTO #DerivePeriod ([start], [end]) VALUES (:a, :b)"), [{"a": p.start, "b": p.end} for p in periods])


FIRST = "(SELECT TOP 1 [start] FROM #DerivePeriod ORDER BY [start])"
FIRST_END = "(SELECT TOP 1 [end] FROM #DerivePeriod ORDER BY [start])"
COLUMNS = ("PlanRunId, MaterialId, LocationId, Uom, Direction, MainMovement, MovementType, DocumentNo, Quantity, PeriodStart, PeriodEnd, MovementDate, "
           "IsCustomAllocated, AllocationLevel, AllocationKey, ExpiryDate, PriorityGroup, OrderNo, [LineNo], LineItemNo, CustomerId, ProjectId, StockId, "
           "PurchaseOrderLineId, PlannedSupplyId, DemandFulfillmentId, UpdatedAt")


def _rule(material: str, key_sql: str, level: str) -> str:
    """Malzemenin alokasyon kuralında bu sahip var mı (veri versiyonunda)."""
    return (f"EXISTS (SELECT 1 FROM core.MaterialAllocationRule ar WHERE ar.MaterialId = {material} AND ar.AllocationLevel = N'{level}' "
            f"AND ar.AllocationKey = {key_sql} AND {_v('ar')})")


def _same_unit(uom: str, material: str) -> str:
    """Birim boşsa temel birimdir; doluysa malzemenin temel birimiyle aynı olmalı (dönüşüm yok, K-205)."""
    return f"({uom} IS NULL OR {uom} = (SELECT TOP 1 m.BaseUom FROM core.Material m WHERE m.Id = {material} AND {_v('m')}))"


def material_transactions(session: Session, plan_run_id: int, today: date | None = None) -> dict[str, int]:
    """Plan hesabının malzeme hareketlerini yeniden kurar. Dönen: hareket türüne göre yazılan satır ve atlanan (farklı birim) satır sayısı."""
    p = _run(session, plan_run_id)
    _periods_table(session, plan_periods(session, p["sid"], today))
    session.execute(sa.text("DELETE FROM planning.MaterialTransaction WHERE PlanRunId = :run"), p)
    out: dict[str, int] = {}

    def insert(name: str, select: str) -> None:
        cte = ""
        if select.lstrip().startswith("WITH"):  # SQL Server: WITH, INSERT'ten önce gelir
            at = select.rindex("SELECT :run")
            cte, select = select[:at], select[at:]
        out[name] = session.execute(sa.text(f"{cte} INSERT INTO planning.MaterialTransaction ({COLUMNS}) {select}"), p).rowcount

    def skipped(name: str, sql: str) -> None:
        n = session.execute(sa.text(sql), p).scalar() or 0
        if n:
            out[f"{name} · farklı birim (atlandı)"] = n

    # + Stok, + Kalitedeki stok
    stock_where = f"{_v('s')} AND {_active('s')} AND ISNULL(s.IsBlocked, 0) = 0 AND s.Quantity > 0"
    insert("Stok", f"""
        SELECT :run, s.MaterialId, s.LocationId, COALESCE(s.Uom, m.BaseUom), N'{mv.PLUS}', N'{mv.MAIN_STOCK}',
               CASE WHEN s.IsInQuality = 1 THEN N'{mv.QUALITY_STOCK}' ELSE N'{mv.STOCK}' END, NULL, s.Quantity, {FIRST}, {FIRST_END}, {FIRST},
               ISNULL(s.IsCustomAllocated, 0), s.AllocationLevel, s.AllocationKey, s.ExpiryDate, NULL, NULL, NULL, NULL, NULL, NULL, s.Id, NULL, NULL, NULL,
               SYSUTCDATETIME()
        FROM core.Stock s JOIN core.Material m ON m.Id = s.MaterialId AND {_v('m')}
        WHERE {stock_where} AND (s.Uom IS NULL OR s.Uom = m.BaseUom) AND EXISTS (SELECT 1 FROM #DerivePeriod)""")
    skipped("Stok", f"SELECT COUNT(*) FROM core.Stock s JOIN core.Material m ON m.Id = s.MaterialId AND {_v('m')} WHERE {stock_where} AND s.Uom <> m.BaseUom")

    # + Satın alma siparişi
    po_where = (f"{_v('o')} AND {_active('o')} AND o.OpenQuantity > 0 AND NOT (ISNULL(o.IsSubcontract, 0) = 1 AND o.WorkOrderId IS NOT NULL)")
    insert("Satın alma siparişi", f"""
        SELECT :run, o.MaterialId, o.LocationId, COALESCE(o.Uom, m.BaseUom), N'{mv.PLUS}', N'{mv.MAIN_PURCHASE}', N'{mv.PURCHASE_ORDER}', o.PurchaseOrderNo,
               o.OpenQuantity, d.[start], d.[end], d.[start], ISNULL(o.IsCustomAllocated, 0), o.AllocationLevel, o.AllocationKey, NULL, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, o.Id, NULL, NULL, SYSUTCDATETIME()
        FROM core.PurchaseOrderLine o JOIN core.Material m ON m.Id = o.MaterialId AND {_v('m')}
        CROSS APPLY (SELECT TOP 1 pp.[start], pp.[end] FROM #DerivePeriod pp WHERE COALESCE(o.ConfirmedDate, o.RequestedDate) <= pp.[end]
                     ORDER BY pp.[start]) d
        WHERE {po_where} AND (o.Uom IS NULL OR o.Uom = m.BaseUom)""")
    skipped("Satın alma siparişi", f"SELECT COUNT(*) FROM core.PurchaseOrderLine o JOIN core.Material m ON m.Id = o.MaterialId AND {_v('m')} "
                                   f"WHERE {po_where} AND o.Uom <> m.BaseUom")

    # + Üretim siparişi, + Üretim planı, + Satın alma planı
    insert("Tedarik planı", f"""
        SELECT :run, s.MaterialId, s.LocationId, s.Uom, N'{mv.PLUS}',
               CASE WHEN s.SupplyType = N'{mv.SUPPLY_PURCHASE}' THEN N'{mv.MAIN_PURCHASE}' ELSE N'{mv.MAIN_PRODUCTION}' END,
               CASE WHEN s.SupplyType = N'{mv.SUPPLY_PURCHASE}' THEN N'{mv.PURCHASE_PLAN}'
                    WHEN s.Source = N'{mv.SOURCE_ORDER}' THEN N'{mv.PRODUCTION_ORDER}' ELSE N'{mv.PRODUCTION_PLAN}' END,
               s.SupplyNo, CASE WHEN s.SupplyType = N'{mv.SUPPLY_PURCHASE}' THEN COALESCE(s.RoundedQuantity, s.Quantity) ELSE s.Quantity END,
               s.PeriodStart, s.PeriodEnd, s.PeriodStart, ISNULL(s.IsCustomAllocated, 0), s.AllocationLevel, s.AllocationKey, NULL, NULL, NULL, NULL, NULL,
               NULL, NULL, NULL, NULL, s.Id, NULL, SYSUTCDATETIME()
        FROM planning.PlannedSupply s WHERE s.PlanRunId = :run AND s.IsIncluded = 1 AND s.Quantity > 0""")

    # − Talep: anahtar, malzemenin kuralında bulunan en detaylı sahip (sipariş satırı → proje → müşteri)
    order_key = "CONCAT(f.OrderNo, N'|', CAST(f.[LineNo] AS nvarchar(12)), N'|', CAST(ISNULL(f.LineItemNo, 0) AS nvarchar(12)))"
    insert("Talep", f"""
        SELECT :run, f.MaterialId, f.LocationId, f.Uom, N'{mv.MINUS}', N'{mv.MAIN_DEMAND}', f.DemandType, f.OrderNo, f.Quantity, f.PeriodStart, f.PeriodEnd,
               f.PeriodStart, CASE WHEN k.lvl IS NULL THEN 0 ELSE 1 END, k.lvl, k.akey, NULL, d.PriorityGroup, f.OrderNo, f.[LineNo], f.LineItemNo,
               f.CustomerId, f.ProjectId, NULL, NULL, NULL, f.Id, SYSUTCDATETIME()
        FROM planning.DemandFulfillment f JOIN planning.PlannedDemand d ON d.Id = f.PlannedDemandId
        LEFT JOIN core.Project pr ON pr.Id = f.ProjectId AND {_v('pr')}
        LEFT JOIN core.Customer cu ON cu.Id = f.CustomerId AND {_v('cu')}
        OUTER APPLY (SELECT TOP 1 x.lvl, x.akey FROM (VALUES
              (1, CASE WHEN f.OrderNo IS NOT NULL AND {_rule('f.MaterialId', order_key, ORDER)} THEN N'{ORDER}' END, {order_key}),
              (2, CASE WHEN pr.Code IS NOT NULL AND {_rule('f.MaterialId', 'pr.Code', PROJECT)} THEN N'{PROJECT}' END, pr.Code),
              (3, CASE WHEN cu.Code IS NOT NULL AND {_rule('f.MaterialId', 'cu.Code', CUSTOMER)} THEN N'{CUSTOMER}' END, cu.Code)
            ) x(rnk, lvl, akey) WHERE x.lvl IS NOT NULL ORDER BY x.rnk) k
        WHERE f.PlanRunId = :run AND f.Quantity > 0 AND {_same_unit('f.Uom', 'f.MaterialId')}""")

    # − Üretim planı ihtiyacı: ağaç (hayalet satırlar varsayılan versiyonla patlatılır; en çok 5 seviye)
    insert("Üretim planı ihtiyacı", f"""
        WITH lines AS (
            SELECT b.Code, b.ComponentMaterialId, b.Quantity, b.ComponentUom, ISNULL(b.ScrapRatio, 0) AS Scrap, ISNULL(b.IsLotBasedUsage, 0) AS Lot,
                   CASE WHEN ISNULL(b.IsPhantom, 0) = 1 OR ISNULL(cm.IsPhantom, 0) = 1 THEN 1 ELSE 0 END AS Phantom, cm.BaseUom
            FROM core.BOM b JOIN core.Material cm ON cm.Id = b.ComponentMaterialId AND {_v('cm')}
            WHERE {_v('b')} AND b.Quantity > 0
              AND (b.AlternativeGroup IS NULL OR b.AlternativePriority = (SELECT MIN(b2.AlternativePriority) FROM core.BOM b2 WHERE b2.Code = b.Code
                   AND b2.AlternativeGroup = b.AlternativeGroup AND {_v('b2')}))),
        defaults AS (
            SELECT v.MaterialId, v.BOMCode, v.BaseQuantity FROM (
                SELECT v.*, ROW_NUMBER() OVER (PARTITION BY v.MaterialId ORDER BY ISNULL(v.Priority, 99), v.Id) AS rn
                FROM core.ProductionVersion v WHERE {_v('v')} AND {_active('v')}) v WHERE v.rn = 1),
        tree AS (
            SELECT s.Id AS SupplyId, l.ComponentMaterialId, l.ComponentUom, l.BaseUom, l.Phantom, 1 AS Depth,
                   CAST(CASE WHEN l.Lot = 1 THEN l.Quantity ELSE s.Quantity * l.Quantity / NULLIF(pv.BaseQuantity, 0) END * (1 + l.Scrap) AS decimal(28, 8)) AS Qty
            FROM planning.PlannedSupply s JOIN core.ProductionVersion pv ON pv.Id = s.ProductionVersionId AND {_v('pv')}
            JOIN lines l ON l.Code = s.BOMCode
            WHERE s.PlanRunId = :run AND s.IsIncluded = 1 AND s.SupplyType = N'{mv.SUPPLY_PRODUCTION}' AND s.Source = N'{mv.SOURCE_PLAN}' AND s.Quantity > 0
            UNION ALL
            SELECT t.SupplyId, l.ComponentMaterialId, l.ComponentUom, l.BaseUom, l.Phantom, t.Depth + 1,
                   CAST(CASE WHEN l.Lot = 1 THEN l.Quantity ELSE t.Qty * l.Quantity / NULLIF(pv.BaseQuantity, 0) END * (1 + l.Scrap) AS decimal(28, 8))
            FROM tree t JOIN defaults pv ON pv.MaterialId = t.ComponentMaterialId
            JOIN lines l ON l.Code = pv.BOMCode
            WHERE t.Phantom = 1 AND t.Depth < 5)
        SELECT :run, t.ComponentMaterialId, s.LocationId, t.BaseUom, N'{mv.MINUS}', N'{mv.MAIN_PRODUCTION_NEED}', N'{mv.PRODUCTION_PLAN_NEED}', s.SupplyNo,
               CAST(SUM(t.Qty) AS decimal(18, 4)), s.PeriodStart, s.PeriodEnd, s.PeriodStart,
               CASE WHEN MAX(a.k) IS NULL THEN 0 ELSE 1 END, MAX(a.lvl), MAX(a.k), NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, s.Id, NULL,
               SYSUTCDATETIME()
        FROM tree t JOIN planning.PlannedSupply s ON s.Id = t.SupplyId
        OUTER APPLY (SELECT s.AllocationLevel AS lvl, s.AllocationKey AS k WHERE s.AllocationKey IS NOT NULL AND EXISTS (SELECT 1 FROM core.MaterialAllocationRule ar
                     WHERE ar.MaterialId = t.ComponentMaterialId AND ar.AllocationLevel = s.AllocationLevel AND ar.AllocationKey = s.AllocationKey AND {_v('ar')})) a
        WHERE t.Phantom = 0 AND (t.ComponentUom IS NULL OR t.ComponentUom = t.BaseUom)
        GROUP BY t.ComponentMaterialId, s.Id, s.LocationId, t.BaseUom, s.SupplyNo, s.PeriodStart, s.PeriodEnd
        HAVING SUM(t.Qty) > 0
        OPTION (MAXRECURSION 10)""")

    # − Üretim siparişi ihtiyacı: siparişin kendi bileşenleri; bölünmüş siparişte satırın payı
    insert("Üretim siparişi ihtiyacı", f"""
        WITH rows AS (
            SELECT s.*, s.Quantity / NULLIF(SUM(s.Quantity) OVER (PARTITION BY s.WorkOrderId), 0) AS Share
            FROM planning.PlannedSupply s
            WHERE s.PlanRunId = :run AND s.IsIncluded = 1 AND s.Source = N'{mv.SOURCE_ORDER}' AND s.WorkOrderId IS NOT NULL AND s.Quantity > 0)
        SELECT :run, c.MaterialId, s.LocationId, m.BaseUom, N'{mv.MINUS}', N'{mv.MAIN_PRODUCTION_NEED}', N'{mv.PRODUCTION_ORDER_NEED}',
               s.SupplyNo, CAST(SUM(r.Remaining) * s.Share AS decimal(18, 4)), s.PeriodStart, s.PeriodEnd, s.PeriodStart,
               CASE WHEN MAX(a.k) IS NULL THEN 0 ELSE 1 END, MAX(a.lvl), MAX(a.k), NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, s.Id, NULL, SYSUTCDATETIME()
        FROM rows s JOIN core.WorkOrderComponent c ON c.WorkOrderId = s.WorkOrderId AND {_v('c')}
        JOIN core.Material m ON m.Id = c.MaterialId AND {_v('m')}
        CROSS APPLY (SELECT COALESCE(c.RemainingQuantity, c.RequiredQuantity - ISNULL(c.IssuedQuantity, 0)) AS Remaining) r
        OUTER APPLY (SELECT s.AllocationLevel AS lvl, s.AllocationKey AS k WHERE s.AllocationKey IS NOT NULL AND EXISTS (SELECT 1 FROM core.MaterialAllocationRule ar
                     WHERE ar.MaterialId = c.MaterialId AND ar.AllocationLevel = s.AllocationLevel AND ar.AllocationKey = s.AllocationKey AND {_v('ar')})) a
        WHERE r.Remaining > 0 AND (c.Uom IS NULL OR c.Uom = m.BaseUom)
        GROUP BY c.MaterialId, s.Id, s.LocationId, m.BaseUom, s.SupplyNo, s.Share, s.PeriodStart, s.PeriodEnd""")

    # ± Alokasyon transferi: genelden −, özele +
    for direction, special in ((mv.MINUS, False), (mv.PLUS, True)):
        alloc = "1, t.AllocationLevel, t.AllocationKey" if special else "0, NULL, NULL"
        insert(f"Alokasyon transferi {direction}", f"""
            SELECT :run, t.MaterialId, t.LocationId, t.Uom, N'{direction}', N'{mv.MAIN_TRANSFER}', N'{mv.ALLOCATION_TRANSFER}', NULL, t.Quantity,
                   t.PeriodStart, t.PeriodEnd, t.PeriodStart, {alloc}, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, SYSUTCDATETIME()
            FROM planning.PlannedAllocationTransfer t WHERE t.PlanRunId = :run AND t.Quantity > 0""")
    session.execute(sa.text("DROP TABLE #DerivePeriod"))
    return out


def capacity_loads(session: Session, plan_run_id: int) -> dict[str, int]:
    """Plan hesabının kapasite yüklerini yeniden kurar. Dönen: kaynağa göre yazılan satır sayısı."""
    p = _run(session, plan_run_id)
    session.execute(sa.text("DELETE FROM planning.CapacityLoad WHERE PlanRunId = :run"), p)
    cols = "PlanRunId, ResourceGroupId, LocationId, PlannedSupplyId, MaterialId, ProductionQuantity, UnitUsage, CapacityUsage, CapacityUnit, PeriodStart, PeriodEnd, UpdatedAt"
    out = {}
    out["Üretim planı"] = session.execute(sa.text(f"""
        INSERT INTO planning.CapacityLoad ({cols})
        SELECT :run, r.ResourceGroupId, s.LocationId, s.Id, s.MaterialId, s.Quantity, SUM(r.Consumption) / NULLIF(pv.BaseQuantity, 0),
               s.Quantity * SUM(r.Consumption) / NULLIF(pv.BaseQuantity, 0), MAX(g.CapacityUnit), s.PeriodStart, s.PeriodEnd, SYSUTCDATETIME()
        FROM planning.PlannedSupply s JOIN core.ProductionVersion pv ON pv.Id = s.ProductionVersionId AND {_v('pv')}
        JOIN core.Routing r ON r.RouteCode = s.RouteCode AND {_v('r')} AND {_active('r')} AND ISNULL(r.IsLotBasedUsage, 0) = 0 AND r.ResourceGroupId IS NOT NULL
             AND r.Consumption > 0
             AND (r.AlternativeGroup IS NULL OR r.AlternativePriority = (SELECT MIN(r2.AlternativePriority) FROM core.Routing r2 WHERE r2.RouteCode = r.RouteCode
                  AND r2.AlternativeGroup = r.AlternativeGroup AND {_v('r2')}))
        LEFT JOIN core.ResourceGroup g ON g.Id = r.ResourceGroupId AND {_v('g')}
        WHERE s.PlanRunId = :run AND s.IsIncluded = 1 AND s.SupplyType = N'{mv.SUPPLY_PRODUCTION}' AND s.Source = N'{mv.SOURCE_PLAN}' AND s.Quantity > 0
        GROUP BY r.ResourceGroupId, s.LocationId, s.Id, s.MaterialId, s.Quantity, pv.BaseQuantity, s.PeriodStart, s.PeriodEnd"""), p).rowcount
    out["Üretim siparişi"] = session.execute(sa.text(f"""
        WITH rows AS (
            SELECT s.*, s.Quantity / NULLIF(SUM(s.Quantity) OVER (PARTITION BY s.WorkOrderId), 0) AS Share
            FROM planning.PlannedSupply s
            WHERE s.PlanRunId = :run AND s.IsIncluded = 1 AND s.Source = N'{mv.SOURCE_ORDER}' AND s.WorkOrderId IS NOT NULL AND s.Quantity > 0)
        INSERT INTO planning.CapacityLoad ({cols})
        SELECT :run, o.ResourceGroupId, s.LocationId, s.Id, s.MaterialId, s.Quantity, SUM(x.Remaining) * MAX(s.Share) / NULLIF(s.Quantity, 0),
               SUM(x.Remaining) * MAX(s.Share), MAX(g.CapacityUnit), s.PeriodStart, s.PeriodEnd, SYSUTCDATETIME()
        FROM rows s JOIN core.WorkOrderOperation o ON o.WorkOrderId = s.WorkOrderId AND {_v('o')} AND {_active('o')} AND ISNULL(o.IsCompleted, 0) = 0
             AND ISNULL(o.IsLotBasedUsage, 0) = 0 AND o.ResourceGroupId IS NOT NULL
        CROSS APPLY (SELECT COALESCE(o.RemainingConsumption, o.PlannedConsumption - ISNULL(o.ConfirmedConsumption, 0)) AS Remaining) x
        LEFT JOIN core.ResourceGroup g ON g.Id = o.ResourceGroupId AND {_v('g')}
        WHERE x.Remaining > 0
        GROUP BY o.ResourceGroupId, s.LocationId, s.Id, s.MaterialId, s.Quantity, s.PeriodStart, s.PeriodEnd"""), p).rowcount
    return out


def derive(session: Session, plan_run_id: int, today: date | None = None) -> dict[str, dict[str, int]]:
    """İkisi birden (yazıcının çağırdığı)."""
    return {"MaterialTransaction": material_transactions(session, plan_run_id, today), "CapacityLoad": capacity_loads(session, plan_run_id)}

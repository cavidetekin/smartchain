"""Talep karşılama (`planning.PlannedDemand`, K-202): plan hesabının talep kopyası ve karşılama özeti. Sistem yazar, motor yazmaz.

- `copy`: plan hesabı başlarken, hesabın veri versiyonundaki açık bütün talepler kopyalanır: açık sipariş satırları (aktif, açık miktarı sıfırdan
  büyük) ve tahmin kayıtları (aktif, miktarı sıfırdan büyük; her kayıt bir satır). Tür `objectives.demand_type` kuralıyla, öncelik grubu Öncelik
  yönetimi'nin geçerli grubuyla (K-195), vade dönemi senaryonun plan dönemleriyle. "Plana dahil: Hayır" yalnız türü parametreyle kapalı talepte.
- `summarize`: hesaptan sonra özet alanları kırılım satırlarından (`planning.DemandFulfillment`) yazılır; plana dahil olmayan talepte boş kalır.

Çağıran işlemi (transaction) yönetir.
"""
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app import priorities
from app.params import catalog as cat, service as params
from app.periods import cache, periods

IDENTITY = ("DemandType", "OrderNo", "LineNo", "LineItemNo", "CustomerId", "ProjectId", "MaterialId", "LocationId", "Uom")  # kırılım satırına kopyalanan alanlar
SUMMARY = ("FulfilledQuantity", "OnTimeQuantity", "LateQuantity", "UnmetQuantity", "FulfillmentPct", "LastFulfillmentPeriodStart")

_VERSION = "{0}.VersionFrom <= :v AND ({0}.VersionTo IS NULL OR {0}.VersionTo >= :v)"
_ACTIVE = "ISNULL({0}.IsActive, 1) = 1"
# sipariş satırının türü: `objectives.demand_type` ile aynı kural (teklif işaretliyse Teklif, değilse beklemedeyse Beklemedeki sipariş)
_ORDER_TYPE = (f"CASE WHEN s.IsQuote = 1 THEN N'{cat.DEMAND_QUOTE}' WHEN s.IsOnHold = 1 THEN N'{cat.DEMAND_ON_HOLD}' ELSE N'{cat.DEMAND_FIRM}' END")


def _included(settings: dict) -> str:
    """Plana dahil: türü parametreyle kapalıysa Hayır (Parametreler › Talep); kesin sipariş her zaman plandadır."""
    closed = [t for t, key in cat.DEMAND_SWITCH.items() if settings.get(key) == cat.NO]
    if not closed:
        return "CAST(1 AS bit)"
    return "CAST(CASE WHEN x.DemandType IN (" + ", ".join(f"N'{t}'" for t in closed) + ") THEN 0 ELSE 1 END AS bit)"


def copy(session: Session, plan_run_id: int, today: date | None = None) -> int:
    """Plan hesabının talep kopyasını yeniden kurar; yazılan satır sayısı döner. Önce hesabın çıktıları silinmiş olmalıdır (kırılım talebe bağlıdır)."""
    run = session.execute(sa.text("SELECT DataVersionId, ScenarioDefinitionId FROM planning.PlanRun WHERE Id = :id"), {"id": plan_run_id}).one()
    sid = run.ScenarioDefinitionId
    scenario = cache.scenario_row(session, sid)
    settings = params.read_settings(session, sid)
    horizon = periods.read(session, sid, today or date.today())
    session.execute(sa.text("DELETE FROM planning.PlannedDemand WHERE PlanRunId = :id"), {"id": plan_run_id})
    orders = (f"SELECT {_ORDER_TYPE} AS DemandType, s.Id AS SalesOrderLineId, CAST(NULL AS bigint) AS ForecastId, s.OrderNo, s.[LineNo], s.LineItemNo, "
              "s.CustomerId, s.ProjectId, s.MaterialId, s.LocationId, COALESCE(s.Uom, m.BaseUom) AS Uom, s.OpenQuantity AS DemandQuantity, "
              f"COALESCE(s.ConfirmedDate, s.RequestedDate) AS DueDate, COALESCE(z.EffectivePriorityGroup, {priorities.LOWEST}) AS PriorityGroup "
              f"FROM core.SalesOrderLine s LEFT JOIN core.Material m ON m.Id = s.MaterialId AND {_VERSION.format('m')} "
              f"LEFT JOIN ({priorities.orders_sql()}) z ON z.SalesOrderLineId = s.Id "
              f"WHERE {_VERSION.format('s')} AND {_ACTIVE.format('s')} AND s.OpenQuantity > 0")
    forecasts = (f"SELECT N'{cat.DEMAND_FORECAST}', CAST(NULL AS bigint), f.Id, CAST(NULL AS nvarchar(30)), CAST(NULL AS int), CAST(NULL AS int), "
                 "f.CustomerId, f.ProjectId, f.MaterialId, f.LocationId, COALESCE(f.Uom, m.BaseUom), f.Quantity, f.Period, "
                 f"COALESCE(z.EffectivePriorityGroup, {priorities.LOWEST}) "
                 f"FROM core.Forecast f LEFT JOIN core.Material m ON m.Id = f.MaterialId AND {_VERSION.format('m')} "
                 f"LEFT JOIN ({priorities.forecasts_sql()}) z ON z.ForecastId = f.Id "
                 f"WHERE {_VERSION.format('f')} AND {_ACTIVE.format('f')} AND f.Quantity > 0")
    # vade dönemi: vadenin düştüğü plan dönemi; vade plan başlangıcından önceyse ilk dönem, ufuktan sonraysa boş. Dönemler geçici tablodan okunur
    # (uzun JSON parametresi bu büyüklükteki sorguda sürücüde eski metin tipine bağlanıyor)
    session.execute(sa.text("IF OBJECT_ID('tempdb..#PlanPeriod') IS NOT NULL DROP TABLE #PlanPeriod"))
    session.execute(sa.text("CREATE TABLE #PlanPeriod ([start] date NOT NULL PRIMARY KEY, [end] date NOT NULL)"))
    if horizon:
        session.execute(sa.text("INSERT INTO #PlanPeriod ([start], [end]) VALUES (:a, :b)"), [{"a": p.start, "b": p.end} for p in horizon])
    due_period = "OUTER APPLY (SELECT TOP 1 pp.[start] FROM #PlanPeriod pp WHERE x.DueDate <= pp.[end] ORDER BY pp.[start]) dp"
    result = session.execute(sa.text(
        "INSERT INTO planning.PlannedDemand (PlanRunId, DemandType, SalesOrderLineId, ForecastId, OrderNo, [LineNo], LineItemNo, CustomerId, ProjectId, "
        "MaterialId, LocationId, Uom, DemandQuantity, DueDate, DuePeriodStart, PriorityGroup, IsIncluded, UpdatedAt) "
        "SELECT :run, x.DemandType, x.SalesOrderLineId, x.ForecastId, x.OrderNo, x.[LineNo], x.LineItemNo, x.CustomerId, x.ProjectId, x.MaterialId, "
        f"x.LocationId, x.Uom, x.DemandQuantity, x.DueDate, dp.[start], x.PriorityGroup, {_included(settings)}, SYSUTCDATETIME() "
        f"FROM ({orders} UNION ALL {forecasts}) x {due_period}"),
        {"run": plan_run_id, "v": run.DataVersionId, "sid": sid, "base": cache.base_of(session, scenario)})
    session.execute(sa.text("DROP TABLE #PlanPeriod"))
    return result.rowcount


def summarize(session: Session, plan_run_id: int) -> None:
    """Özet alanları kırılım satırlarından: karşılanan, zamanında, geciken, karşılanmayan, oran (en çok 100) ve son karşılama dönemi."""
    session.execute(sa.text(
        "UPDATE d SET FulfilledQuantity = COALESCE(a.q, 0), OnTimeQuantity = COALESCE(a.onTime, 0), LateQuantity = COALESCE(a.late, 0), "
        "UnmetQuantity = CASE WHEN d.DemandQuantity > COALESCE(a.q, 0) THEN d.DemandQuantity - COALESCE(a.q, 0) ELSE 0 END, "
        "FulfillmentPct = CASE WHEN d.DemandQuantity <= 0 THEN NULL WHEN COALESCE(a.q, 0) >= d.DemandQuantity THEN 100 "
        "ELSE COALESCE(a.q, 0) * 100.0 / d.DemandQuantity END, LastFulfillmentPeriodStart = a.lastPeriod "
        "FROM planning.PlannedDemand d LEFT JOIN (SELECT f.PlannedDemandId, SUM(f.Quantity) AS q, "
        "SUM(CASE WHEN f.IsTardy = 1 THEN 0 ELSE f.Quantity END) AS onTime, SUM(CASE WHEN f.IsTardy = 1 THEN f.Quantity ELSE 0 END) AS late, "
        "MAX(f.PeriodStart) AS lastPeriod FROM planning.DemandFulfillment f WHERE f.PlanRunId = :run GROUP BY f.PlannedDemandId) a ON a.PlannedDemandId = d.Id "
        "WHERE d.PlanRunId = :run AND d.IsIncluded = 1"), {"run": plan_run_id})


def rows(session: Session, plan_run_id: int, included_only: bool = False) -> list[dict]:
    """Plan hesabının talepleri (motorun okuduğu hâl): vade tarihi ve kimlik sırasıyla."""
    where = " AND IsIncluded = 1" if included_only else ""
    found = session.execute(sa.text(f"SELECT * FROM planning.PlannedDemand WHERE PlanRunId = :run{where} ORDER BY DueDate, Id"), {"run": plan_run_id})
    return [dict(r) for r in found.mappings()]

"""Plan metrikleri kataloğu (K-205): `planning.PlanMetric.MetricCode`'un tek tanımı. Kodda sabittir; Senaryo karşılaştırma raporu (9.7) gerekirse
tabloya çevirir. `compute` plan hesabının çıktılarından değerleri hesaplar (fikstür bugün, motor Aşama 10'da aynı kataloğu yazar)."""
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from . import capacity_view, movements as mv

HIGHER, LOWER = "Yüksek iyi", "Düşük iyi"


@dataclass(frozen=True)
class Metric:
    code: str
    name: str
    unit: str
    better: str


METRICS = (
    Metric("OnTimePct", "Zamanında karşılama oranı", "%", HIGHER),
    Metric("FillRatePct", "Karşılama oranı", "%", HIGHER),
    Metric("LateLines", "Geciken talep satırı", "satır", LOWER),
    Metric("UnmetLines", "Karşılanmayan talep satırı", "satır", LOWER),
    Metric("AvgDelayDays", "Ortalama gecikme", "gün", LOWER),
    Metric("MaxUtilizationPct", "En yüksek doluluk (kritik gruplar)", "%", LOWER),
    Metric("OverloadedGroupPeriods", "Aşırı yüklü grup × dönem", "adet", LOWER),
    Metric("OvertimeHours", "Toplam ek mesai", "saat", LOWER),
    Metric("SubcontractQuantity", "Fason üretim miktarı", "miktar", LOWER),
    Metric("PurchasePlanLines", "Satın alma planı satırı", "satır", LOWER),
)
BY_CODE = {m.code: m for m in METRICS}
assert len(BY_CODE) == len(METRICS) and all(len(m.code) <= 40 for m in METRICS)


def compute(session: Session, plan_run_id: int) -> dict[str, float]:
    """Plan hesabının metrikleri: talep özeti (`PlannedDemand`), karşılama kırılımı, kapasite yükü ve ek mesai, tedarik planı."""
    p = {"run": plan_run_id}
    d = session.execute(sa.text(
        "SELECT SUM(DemandQuantity) AS qty, SUM(FulfilledQuantity) AS ful, SUM(OnTimeQuantity) AS ontime, SUM(CASE WHEN LateQuantity > 0 THEN 1 ELSE 0 END) AS late, "
        "SUM(CASE WHEN UnmetQuantity > 0 THEN 1 ELSE 0 END) AS unmet FROM planning.PlannedDemand WHERE PlanRunId = :run AND IsIncluded = 1"), p).one()
    delay = session.execute(sa.text(
        "SELECT SUM(f.Quantity * DATEDIFF(day, d.DuePeriodStart, f.PeriodStart)) / NULLIF(SUM(f.Quantity), 0) FROM planning.DemandFulfillment f "
        "JOIN planning.PlannedDemand d ON d.Id = f.PlannedDemandId WHERE f.PlanRunId = :run AND f.IsTardy = 1 AND d.DuePeriodStart IS NOT NULL"), p).scalar()
    s = session.execute(sa.text(
        f"SELECT SUM(CASE WHEN IsSubcontract = 1 AND SupplyType = N'{mv.SUPPLY_PRODUCTION}' THEN Quantity ELSE 0 END) AS sub, "
        f"SUM(CASE WHEN SupplyType = N'{mv.SUPPLY_PURCHASE}' AND Source = N'{mv.SOURCE_PLAN}' THEN 1 ELSE 0 END) AS buy "
        "FROM planning.PlannedSupply WHERE PlanRunId = :run AND IsIncluded = 1"), p).one()
    groups = capacity_view.group_periods(session, plan_run_id)
    critical = [g for g in groups if g["IsCritical"] and g["AvailableCapacity"] > 0]
    q = float(d.qty or 0)
    return {
        "OnTimePct": round(100 * float(d.ontime or 0) / q, 2) if q else 0.0,
        "FillRatePct": round(100 * float(d.ful or 0) / q, 2) if q else 0.0,
        "LateLines": float(d.late or 0),
        "UnmetLines": float(d.unmet or 0),
        "AvgDelayDays": round(float(delay or 0), 2),
        "MaxUtilizationPct": round(max((100 * g["Load"] / g["AvailableCapacity"] for g in critical), default=0.0), 2),
        "OverloadedGroupPeriods": float(sum(1 for g in groups if g["Overload"] > capacity_view.EPS)),
        "OvertimeHours": round(sum(g["Overtime"] for g in groups), 2),
        "SubcontractQuantity": float(s.sub or 0),
        "PurchasePlanLines": float(s.buy or 0),
    }


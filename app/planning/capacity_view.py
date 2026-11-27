"""Kaynak grubu × dönem: plan hesabının yükü, kapasitesi ve ek mesaisi (K-205). Metrik, uyarı ve tutarlılık denetimi aynı hesabı okur.

Yük `planning.CapacityLoad`'un grup ve dönem toplamı, ek mesai `planning.PlannedOvertime`. Kapasite saklanmaz (K-202): kapasite hesabının gün bazında
değerlerinden (`app.periods.values`, "resource-capacity-day"; senaryonun girişleri) dönem dönem toplanır. Kullanılabilir kapasite (duruş düşülmüş)
ve ek mesai limiti oradadır. Aşım = yük − (kullanılabilir kapasite + ek mesai).
"""
from collections import defaultdict
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app import periods

EPS = 1e-6
NAME = "resource-capacity-day"


def group_periods(session: Session, plan_run_id: int, today: date | None = None) -> list[dict]:
    """Yükü, ek mesaisi ya da kapasitesi olan her grup × plan dönemi: Load, AvailableCapacity, Overtime, OvertimeLimit, Overload."""
    run = session.execute(sa.text("SELECT DataVersionId, ScenarioDefinitionId FROM planning.PlanRun WHERE Id = :id"), {"id": plan_run_id}).one()
    found = periods.read_periods(session, run.ScenarioDefinitionId, today or date.today())
    if not found:
        return []
    start_of = {}
    for p in found:
        day = p.start
        while day <= p.end:
            start_of[day] = p
            day = date.fromordinal(day.toordinal() + 1)
    cells: dict[tuple[int, date], dict] = defaultdict(lambda: {"Load": 0.0, "AvailableCapacity": 0.0, "Overtime": 0.0, "OvertimeLimit": 0.0})
    for r in periods.values(session, NAME, run.ScenarioDefinitionId, found[0].start, found[-1].end):
        p = start_of.get(r["Date"])
        if p is not None:
            c = cells[(r["ResourceGroupId"], p.start)]
            c["AvailableCapacity"] += float(r["AvailableCapacity"] or 0)
            c["OvertimeLimit"] += float(r["OvertimeLimit"] or 0)
    for gid, start, load in session.execute(sa.text("SELECT ResourceGroupId, PeriodStart, SUM(CapacityUsage) FROM planning.CapacityLoad WHERE PlanRunId = :r "
                                                    "GROUP BY ResourceGroupId, PeriodStart"), {"r": plan_run_id}):
        cells[(gid, start)]["Load"] += float(load or 0)
    for gid, start, hours in session.execute(sa.text("SELECT ResourceGroupId, PeriodStart, SUM(Overtime) FROM planning.PlannedOvertime WHERE PlanRunId = :r "
                                                     "GROUP BY ResourceGroupId, PeriodStart"), {"r": plan_run_id}):
        cells[(gid, start)]["Overtime"] += float(hours or 0)
    groups = {r.Id: r for r in session.execute(sa.text(
        "SELECT Id, Code, ISNULL(IsCritical, 0) AS IsCritical FROM core.ResourceGroup WHERE VersionFrom <= :v AND (VersionTo IS NULL OR VersionTo >= :v)"),
        {"v": run.DataVersionId})}
    ends = {p.start: p.end for p in found}
    out = []
    for (gid, start), c in sorted(cells.items(), key=lambda x: (x[0][1], x[0][0])):
        if start not in ends or not (c["Load"] or c["Overtime"]):
            continue
        g = groups.get(gid)
        out.append({"ResourceGroupId": gid, "Code": g.Code if g else str(gid), "IsCritical": bool(g.IsCritical) if g else False, "PeriodStart": start,
                    "PeriodEnd": ends[start], **c, "Overload": c["Load"] - c["AvailableCapacity"] - c["Overtime"]})
    return out

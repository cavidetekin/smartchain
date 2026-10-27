"""PlanResult'u planning.* tablolarına yazar (K-70).

Çıktılar, PlanRun durumu ve iş kaydının bitişi aynı işlemde (tek commit) yazılır: yarım plan görünmez,
commit'ten sonra süreç çökse de iş Bitti olduğu için yeniden çalışmaz. Yayınlanmış PlanRun'a dokunulmaz.
"""
import logging
from datetime import date

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.jobs import queue
from db.models import (CapacityLoad, DemandFulfillment, Pegging, PlanMetric, PlannedOrder, PlanWarning, SolverLog,
                       SupplyRecommendation)
from .interface import RUN_FAILED, RUN_RUNNING, SUPPLY_PLANNED_ORDER, PlanResult

log = logging.getLogger("smartchain.engine")

# PlanResult alanı → tablo. Silme sırası tersidir.
OUTPUTS = [
    ("planned_orders", PlannedOrder),
    ("supply_recommendations", SupplyRecommendation),
    ("demand_fulfillment", DemandFulfillment),
    ("capacity_loads", CapacityLoad),
    ("pegging", Pegging),
    ("warnings", PlanWarning),
]
SYSTEM_COLUMNS = {"Id", "PlanRunId", "UpdatedAt"}


class PlanRunPublished(Exception):
    """Yayınlanmış PlanRun'un çıktıları değişmez; yeniden hesap yeni PlanRun açar (K-70)."""

    message = "Bu plan yayınlanmış; çıktıları değiştirilemez. Yeniden hesap yeni bir plan hesabı açar."


class JobNoLongerOwned(Exception):
    """İş artık bu denemenin değil (geri alındı ya da sonlandırıldı); hiçbir şey yazılmadı."""


def is_published(session: Session, plan_run_id: int) -> bool:
    return session.execute(text("SELECT CASE WHEN EXISTS (SELECT 1 FROM planning.PlanVersion "
                                "WHERE PlanRunId = :id) THEN 1 ELSE 0 END"), {"id": plan_run_id}).scalar_one() == 1


def mark_running(session: Session, plan_run_id: int) -> None:
    if is_published(session, plan_run_id):
        raise PlanRunPublished()
    session.execute(text("UPDATE planning.PlanRun SET Status = :s, StartedAt = SYSUTCDATETIME(), EndedAt = NULL, "
                         "EngineUsed = NULL, Solver = NULL WHERE Id = :id"), {"s": RUN_RUNNING, "id": plan_run_id})
    session.commit()


def _rows(table: sa.Table, rows: list[dict], plan_run_id: int, now, drop=("ref", "supply_ref")) -> list[dict]:
    allowed = {c.name for c in table.columns} - SYSTEM_COLUMNS
    dates = {c.name for c in table.columns if isinstance(c.type, sa.Date)}
    out = []
    for row in rows:
        values = {k: v for k, v in row.items() if k not in drop}
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"{table.name}: bilinmeyen alan {', '.join(sorted(unknown))}")
        for k in dates & set(values):
            if isinstance(values[k], str):
                values[k] = date.fromisoformat(values[k])
        out.append({**values, "PlanRunId": plan_run_id, "UpdatedAt": now})
    return out


def _delete_outputs(session: Session, plan_run_id: int) -> None:
    for _, table in reversed(OUTPUTS):
        session.execute(sa.delete(table).where(table.c.PlanRunId == plan_run_id))
    session.execute(sa.delete(PlanMetric).where(PlanMetric.c.PlanRunId == plan_run_id))
    session.execute(sa.delete(SolverLog).where(SolverLog.c.PlanRunId == plan_run_id))


def write_result(session: Session, plan_run_id: int, result: PlanResult, job_id: int, attempt: int) -> None:
    """Önceki çıktıları sil → yaz → PlanRun ve iş Bitti; tek commit. İş bu denemenin değilse hiçbir şey yazılmaz."""
    try:
        if is_published(session, plan_run_id):
            raise PlanRunPublished()
        now = queue.db_now(session)
        _delete_outputs(session, plan_run_id)

        # Planlı siparişler tek tek: Id'leri Pegging'deki 'supply_ref' bağları için gerekir.
        refs: dict[str, int] = {}
        for src, row in zip(result.planned_orders, _rows(PlannedOrder, result.planned_orders, plan_run_id, now)):
            new_id = session.execute(sa.insert(PlannedOrder).values(**row).returning(PlannedOrder.c.Id)).scalar_one()
            if "ref" in src:
                refs[src["ref"]] = new_id

        pegging = []
        for row in result.pegging:
            if "supply_ref" in row:
                if row["supply_ref"] not in refs:
                    raise ValueError(f"Pegging: bilinmeyen planlı sipariş bağı {row['supply_ref']}")
                row = {**row, "SupplyType": SUPPLY_PLANNED_ORDER, "SupplyId": refs[row["supply_ref"]]}
            pegging.append(row)

        for attr, table in OUTPUTS[1:]:
            rows = pegging if attr == "pegging" else getattr(result, attr)
            if rows:
                session.execute(sa.insert(table), _rows(table, rows, plan_run_id, now))
        if result.metrics:
            session.execute(sa.insert(PlanMetric), [{"PlanRunId": plan_run_id, "MetricCode": k, "Value": v}
                                                    for k, v in result.metrics.items()])
        if result.solver_log:
            session.execute(sa.insert(SolverLog).values(PlanRunId=plan_run_id, **result.solver_log))

        session.execute(text("UPDATE planning.PlanRun SET Status = :s, EngineUsed = :e, Solver = :sv, "
                             "EndedAt = SYSUTCDATETIME() WHERE Id = :id"),
                        {"s": result.status, "e": result.engine_used, "sv": result.solver, "id": plan_run_id})
        if not queue.finish(session, job_id, attempt, progress="Tamamlandı", commit=False):
            raise JobNoLongerOwned()
        session.commit()
    except Exception:
        session.rollback()
        raise
    log.info("PlanRun %s yazıldı (iş %s, %s planlı sipariş)", plan_run_id, job_id, len(result.planned_orders))


def write_failure(session: Session, plan_run_id: int | None, job_id: int, attempt: int, message: str) -> bool:
    """PlanRun Hata + iş Hata, tek commit. İş bu denemenin değilse hiçbir şey yazılmaz (False)."""
    try:
        if plan_run_id is not None and not is_published(session, plan_run_id):
            session.execute(text("UPDATE planning.PlanRun SET Status = :s, EndedAt = SYSUTCDATETIME() WHERE Id = :id"),
                            {"s": RUN_FAILED, "id": plan_run_id})
        if not queue.fail(session, job_id, attempt, message, commit=False):
            session.rollback()
            return False
        session.commit()
    except Exception:
        session.rollback()
        raise
    log.warning("PlanRun %s hata (iş %s): %s", plan_run_id, job_id, message)
    return True

"""Plan hesabı isteği: PlanRun (Sırada) ve iş kaydı tek commit'te. Yeniden hesap (46) ve gece akışı (40) bunu çağırır."""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.jobs import queue
from app.jobs.constants import CHANNEL_INTERACTIVE, CHANNEL_NIGHT, TYPE_NIGHT_SCENARIO, TYPE_WORKSPACE
from .interface import RUN_QUEUED


def submit_plan_run(session: Session, *, data_version_id: int, parameter_set_id: int,
                    requested_by: int | None = None, channel: str = CHANNEL_INTERACTIVE,
                    scenario_id: int | None = None, workspace_id: int | None = None,
                    priority: int | None = None) -> tuple[int, int]:
    """(plan_run_id, job_id) döndürür."""
    try:
        plan_run_id = session.execute(text(
            "INSERT INTO planning.PlanRun (ScenarioId, WorkspaceId, DataVersionId, ParameterSetId, Status) "
            "OUTPUT inserted.Id VALUES (:sc, :ws, :dv, :ps, :st)"),
            {"sc": scenario_id, "ws": workspace_id, "dv": data_version_id, "ps": parameter_set_id,
             "st": RUN_QUEUED}).scalar_one()
        job_type = TYPE_NIGHT_SCENARIO if channel == CHANNEL_NIGHT else TYPE_WORKSPACE
        job_id = queue.enqueue(session, job_type, channel, requested_by, {"plan_run_id": plan_run_id}, priority)
    except Exception:
        session.rollback()
        raise
    return plan_run_id, job_id

"""İş kuyruğu servisi (fonksiyon 47, 48, 93'ün çekirdeği). Sorgular app.jobs.queue'dadır; motor servisi de onu kullanır."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.jobs import queue
from app.jobs.settings import read_settings
from ..errors import AppError


def _iso(value: datetime | None) -> str | None:
    return value.replace(tzinfo=timezone.utc).isoformat(timespec="seconds") if value else None


def to_public(job: dict) -> dict:
    """API ve WebSocket'te işin görünen hali. Payload (iç parametreler) gösterilmez."""
    return {
        "id": job["Id"],
        "job_type": job["JobType"],
        "channel": job["Channel"],
        "priority": job["Priority"],
        "status": job["Status"],
        "requested_by": job["RequestedBy"],
        "progress": job["Progress"],
        "attempt": job["Attempt"],
        "error_text": job["ErrorText"],
        "queue_position": job["QueuePosition"],
        "duration_seconds": job["DurationSeconds"],
        "is_stale": bool(job["IsStale"]),
        "created_at": _iso(job["CreatedAt"]),
        "started_at": _iso(job["StartedAt"]),
        "ended_at": _iso(job["EndedAt"]),
        "heartbeat_at": _iso(job["HeartbeatAt"]),
        "updated_at": _iso(job["UpdatedAt"]),
    }


def _require(session: Session | None) -> Session:
    if session is None:
        raise AppError("database_unavailable", "Veritabanına bağlanılamıyor; iş kuyruğu okunamadı.", 503)
    return session


def list_jobs(session: Session | None, user_id: int | None) -> dict:
    session = _require(session)
    settings = read_settings(session)
    return {
        "jobs": [to_public(j) for j in queue.list_jobs(session, settings, user_id)],
        "counters": queue.counters(session, settings),
    }


def get_job(session: Session | None, job_id: int) -> dict:
    session = _require(session)
    job = queue.get_job(session, job_id, read_settings(session))
    if job is None:
        raise AppError("job_not_found", "İş bulunamadı.", 404)
    return to_public(job)


def cancel(session: Session | None, job_id: int) -> dict:
    session = _require(session)
    try:
        queue.cancel(session, job_id)
    except queue.JobNotFound:
        raise AppError("job_not_found", "İş bulunamadı.", 404)
    except queue.JobNotCancellable as exc:
        raise AppError("job_not_cancellable",
                       f"Yalnız sıradaki iş iptal edilebilir; bu işin durumu: {exc.status}.", 409)
    return get_job(session, job_id)

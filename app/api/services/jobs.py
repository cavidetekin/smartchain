"""İş kuyruğu servisi (fonksiyon 47, 48, 93'ün çekirdeği). Sorgular app.jobs.queue'dadır; motor servisi de onu kullanır."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.jobs import queue
from app.jobs.settings import read_settings
from ..errors import AppError
from ..permissions import Access
from . import authz
from .auth import CurrentUser


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
        "requested_by_name": job["RequestedByName"],
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


def list_jobs(session: Session | None, user: CurrentUser, scope: str = "own") -> dict:
    """Kendi işleri (48); scope="all" herkesin işleri (93; Admin ve System owner)."""
    session = _require(session)
    if scope == "all":
        authz.ensure(user, 93, Access.READ, own=False, details={"scope": "all"})
    settings = read_settings(session)
    return {
        "jobs": [to_public(j) for j in queue.list_jobs(session, settings, None if scope == "all" else user.id)],
        "counters": queue.counters(session, settings),
    }


def _job(session: Session, job_id: int, user: CurrentUser, access: Access) -> dict:
    """İş ve sahiplik (K-100): kendi işi 48, başkasının işi 93."""
    job = queue.get_job(session, job_id, read_settings(session))
    if job is None:
        raise AppError("job_not_found", "İş bulunamadı.", 404)
    if job["RequestedBy"] != user.id:
        authz.ensure(user, 93, access, own=False, details={"job_id": job_id})
    return job


def get_job(session: Session | None, job_id: int, user: CurrentUser) -> dict:
    return to_public(_job(_require(session), job_id, user, Access.READ))


def cancel(session: Session | None, job_id: int, user: CurrentUser) -> dict:
    session = _require(session)
    _job(session, job_id, user, Access.WRITE)
    try:
        queue.cancel(session, job_id)
    except queue.JobNotFound:
        raise AppError("job_not_found", "İş bulunamadı.", 404)
    except queue.JobNotCancellable as exc:
        raise AppError("job_not_cancellable",
                       f"Yalnız sıradaki iş iptal edilebilir; bu işin durumu: {exc.status}.", 409)
    return get_job(session, job_id, user)

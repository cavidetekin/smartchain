"""İş kuyruğu servisi (fonksiyon 47, 48, 93'ün çekirdeği). Sorgular app.jobs.queue'dadır; motor servisi de onu kullanır."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.jobs import queue
from app.jobs.constants import CHANNEL_NIGHT, TYPE_LOAD
from app.jobs.settings import read_settings
from ..errors import DB_UNAVAILABLE, AppError
from ..permissions import SYSTEM_OWNER, Access, role_message
from ..repositories import audit
from . import authz
from .auth import CurrentUser


REASON_REQUIRED = "İptal nedenini yazın."
CANCEL_ACTION = "İş iptali"
PRIORITIZE_ACTION = "İş öne alma"
OBJECT = "Job"


def _iso(value: datetime | None) -> str | None:
    return value.replace(tzinfo=timezone.utc).isoformat(timespec="seconds") if value else None


def to_public(job: dict) -> dict:
    """API ve WebSocket'te işin görünen hali. Payload (iç parametreler) gösterilmez."""
    return {
        "id": job["Id"],
        "job_type": job["JobType"],
        "summary": job["Summary"],
        "channel": job["Channel"],
        "priority": job["Priority"],
        "status": job["Status"],
        "requested_by": job["RequestedBy"],
        "requested_by_name": job["RequestedByName"],
        "is_protected": job["RequestedByRole"] == SYSTEM_OWNER,  # K-107
        "cancel_reason": job["CancelReason"],
        "cancelled_by_name": job["CancelledByName"],
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
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503)
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


def _not_protected(job: dict, user: CurrentUser, access: Access = Access.WRITE) -> None:
    """System owner'ın işine Admin dokunamaz (K-101, K-107); ret denetim izine yazılır."""
    if job["RequestedByRole"] == SYSTEM_OWNER and user.role != SYSTEM_OWNER:
        authz.record_denial(user, 93, access, {"job_id": job["Id"], "reason": "System owner işi"})
        raise AppError("forbidden", role_message(SYSTEM_OWNER), 403)


def cancel(session: Session | None, job_id: int, user: CurrentUser, reason: str | None = None) -> dict:
    """Başkasının işinde neden zorunlu, sahibine bildirimle gider (K-107). İptal denetim izine yazılır."""
    session = _require(session)
    job = _job(session, job_id, user, Access.WRITE)
    _not_protected(job, user)
    reason = (reason or "").strip() or None
    if job["RequestedBy"] != user.id and reason is None:
        raise AppError("reason_required", REASON_REQUIRED, 422, [{"field": "reason", "problem": REASON_REQUIRED}])
    try:
        queue.cancel(session, job_id, reason, user.id, commit=False)
        audit.write_audit(session, CANCEL_ACTION, user.id, OBJECT, str(job_id), {"status": "İptal", "reason": reason},
                          {"status": job["Status"], "job_type": job["JobType"], "requested_by": job["RequestedBy"]})
        session.commit()
    except queue.JobNotFound:
        raise AppError("job_not_found", "İş bulunamadı.", 404)
    except queue.JobNotCancellable as exc:
        message = "Yükleme işi iptal edilemez." if job["JobType"] == TYPE_LOAD else "Yalnız sıradaki iş iptal edilebilir."
        raise AppError("job_not_cancellable", message, 409) from exc
    return get_job(session, job_id, user)


def prioritize(session: Session | None, job_id: int, user: CurrentUser) -> dict:
    session = _require(session)
    job = _job(session, job_id, user, Access.WRITE)
    _not_protected(job, user)
    try:
        queue.prioritize(session, job_id, commit=False)
        audit.write_audit(session, PRIORITIZE_ACTION, user.id, OBJECT, str(job_id), {"channel": job["Channel"]})
        session.commit()
    except queue.JobNotFound:
        raise AppError("job_not_found", "İş bulunamadı.", 404)
    except queue.JobNotPrioritizable as exc:
        message = "Gece işleri öne alınamaz." if job["Channel"] == CHANNEL_NIGHT else "Yalnız sıradaki iş öne alınabilir."
        raise AppError("job_not_prioritizable", message, 409) from exc
    return get_job(session, job_id, user)

"""Ham veri temizliği (ekran 02, fonksiyon 09; K-156): son temizlik, onay penceresi (önizleme), başlatma.

Yalnız System owner başlatır (09 yazma); Admin ve Key user son temizliğin sonucunu görür (09 okuma). Saklama süresi boşsa başlamaz
(409 cleanup_no_retention). Çekim, ön kontrol, validasyon, aktarım ya da temizlik sıradayken veya sürerken başlamaz (409 cleanup_blocked).
İz "Ham veri temizliği" (K-108).
"""
import json

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.cleanup import raw
from app.jobs import queue
from app.jobs.constants import ACTIVE_STATUSES, CHANNEL_PROCESSING, TYPE_CLEANUP, TYPE_PRECHECK, TYPE_PULL, TYPE_TRANSFER, TYPE_VALIDATION

from ..errors import AppError
from ..repositories import audit, integration as repo
from . import auth, flows
from .auth import CurrentUser

ACTION = "Ham veri temizliği"
BUSY_TEXT = {TYPE_CLEANUP: "Temizlik", TYPE_TRANSFER: "Aktarım", TYPE_PULL: "Veri çekme", TYPE_PRECHECK: "Excel ön kontrolü",
             TYPE_VALIDATION: "Validasyon"}  # öncelik sırası
NO_RETENTION = "Saklama süresi tanımlı değil; temizlik çalışmaz. Sistem ayarları'nda girin."


def busy_reason(session: Session) -> str | None:
    busy = session.execute(sa.select(repo.JOB.c.JobType).where(repo.JOB.c.JobType.in_(BUSY_TEXT), repo.JOB.c.Status.in_(ACTIVE_STATUSES))
                           .distinct()).scalars().all()
    if busy:
        name = next(text for t, text in BUSY_TEXT.items() if t in busy)
        return f"{name} sürüyor. Bitince temizliği başlatabilirsiniz."
    return None


def _last(session: Session) -> dict | None:
    j, u = repo.JOB, repo.USER
    row = session.execute(sa.select(j.c.Id, j.c.Status, j.c.CreatedAt, j.c.EndedAt, j.c.Result, j.c.ErrorText, u.c.FullName, u.c.UserName)
                          .select_from(j.outerjoin(u, u.c.Id == j.c.RequestedBy)).where(j.c.JobType == TYPE_CLEANUP)
                          .order_by(j.c.Id.desc()).limit(1)).first()
    if row is None:
        return None
    return {"job_id": row.Id, "status": row.Status, "requested_at": row.CreatedAt, "ended_at": row.EndedAt, "error": row.ErrorText,
            "requested_by_name": row.FullName or row.UserName, "result": json.loads(row.Result) if row.Result else None}


def state(session: Session | None) -> dict:
    """Çekmecenin üstü: saklama süresi ve son temizlik (Admin ve Key user de görür)."""
    session = auth._require(session)
    return auth._db(lambda: {"retention_days": raw.retention_days(session), "last": _last(session)})


def plan(session: Session | None) -> dict:
    """Onay penceresi: silinecek parti, satır, dosya; başlatılamıyorsa nedeni."""
    session = auth._require(session)

    def work():
        days = raw.retention_days(session)
        return {"retention_days": days, "preview": raw.preview(session, days) if days else None,
                "blocked": NO_RETENTION if days is None else busy_reason(session)}

    return auth._db(work)


def start(session: Session | None, user: CurrentUser) -> dict:
    session = auth._require(session)

    def work():
        flows.ensure_idle(session)  # K-163
        days = raw.retention_days(session)
        if days is None:
            raise AppError("cleanup_no_retention", NO_RETENTION, 409)
        reason = busy_reason(session)
        if reason:
            raise AppError("cleanup_blocked", reason, 409)
        job_id = queue.enqueue(session, TYPE_CLEANUP, CHANNEL_PROCESSING, user.id, {"user_id": user.id}, summary=ACTION, commit=False)
        audit.write_audit(session, ACTION, user.id, "Job", str(job_id), {"retention_days": days})
        session.commit()
        return {"job_id": job_id}

    return auth._db(work)

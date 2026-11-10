"""Tam ve kısmi aktarım (ekran 02, fonksiyon 05, 06 ve 07, K-149…K-153, K-155): onay penceresi, başlatma, sonuç.

İş tipi "Aktarım", kanal "Veri işleme"; aynı anda tek aktarım. Çekim, Excel ön kontrolü, validasyon ya da aktarım sıradayken veya sürerken,
ya da staging'de verisi olup validasyonu bitmemiş tablo varken başlamaz (409 transfer_blocked); kısmide yalnız seçilen grupların tabloları bakılır.
İz "Tam aktarım" / "Kısmi aktarım" (K-108).
"""
import json

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration import contract
from app.jobs import queue
from app.jobs.constants import ACTIVE_STATUSES, CHANNEL_PROCESSING, TYPE_PRECHECK, TYPE_PULL, TYPE_TRANSFER, TYPE_VALIDATION
from app.transfer import engine as transfer
from app.transfer.groups import GROUPS, UnknownGroup, group_tables
from app.validation import engine as validation

from ..errors import AppError
from ..repositories import audit, integration as repo
from . import auth
from .auth import CurrentUser
from .validation import state_of

OBJECT = "DataVersion"
ACTION, PARTIAL_ACTION = "Tam aktarım", "Kısmi aktarım"
PARTIAL = transfer.PARTIAL
BUSY_TYPES = (TYPE_PULL, TYPE_PRECHECK, TYPE_VALIDATION, TYPE_TRANSFER)
READY, SKIP_THRESHOLD, SKIP_EMPTY = "Aktarılır", "Eşik aşıldı", "Veri gelmedi"
BUSY_TEXT = {TYPE_TRANSFER: "Aktarım", TYPE_PULL: "Veri çekme", TYPE_PRECHECK: "Excel ön kontrolü", TYPE_VALIDATION: "Validasyon"}  # öncelik sırası


def busy_reason(session: Session) -> str | None:
    busy = session.execute(sa.select(repo.JOB.c.JobType).where(repo.JOB.c.JobType.in_(BUSY_TYPES), repo.JOB.c.Status.in_(ACTIVE_STATUSES))
                           .distinct()).scalars().all()
    if busy:
        name = next(text for t, text in BUSY_TEXT.items() if t in busy)
        return f"{name} sürüyor. Bitince aktarımı başlatabilirsiniz."
    return None


def _pending(session: Session, tables: set[str] | None = None) -> list:
    """Staging'de verisi olup validasyonu bitmemiş tablolar; tables verilirse yalnız onlar."""
    return [e for e in contract.ENTITIES if (tables is None or e.table in tables) and transfer._has_raw(session, e.table)
            and state_of(session, e.table) != validation.DONE]


def blocked(session: Session, tables: set[str] | None = None) -> dict | None:
    """Aktarım başlayamıyorsa nedeni ve tablolar; başlayabiliyorsa None. Kısmide yalnız seçilen tablolar (K-155)."""
    reason = busy_reason(session)
    if reason:
        return {"reason": reason, "tables": []}
    pending = _pending(session, tables)
    if pending:
        return {"reason": "Validasyonu bitmemiş tablo var; önce valide edin.", "tables": [e.name for e in pending]}
    return None


def _plan_row(session: Session, e) -> dict:
    if not transfer._has_raw(session, e.table):
        return {"entity": e.table, "name": e.name, "current_rows": 0, "error_rows": 0, "status": SKIP_EMPTY, "note": transfer.NOTE_EMPTY}
    c = validation.counts(session, e.table)
    note = transfer.threshold_note(session, e.table)
    return {"entity": e.table, "name": e.name, "current_rows": c["current_rows"], "error_rows": c["error_rows"],
            "status": SKIP_THRESHOLD if note else READY, "note": note}


def plan(session: Session | None) -> dict:
    """Onay penceresi: tablo başına güncel satır, Hatalı, durum ve not."""
    session = auth._require(session)

    def work():
        return {"tables": [_plan_row(session, e) for e in contract.ENTITIES], "blocked": blocked(session)}

    return auth._db(work)


def start(session: Session | None, user: CurrentUser) -> dict:
    """İş kuyruğuna yazar; iz aynı işlemde (K-108)."""
    session = auth._require(session)

    def work():
        reason = blocked(session)
        if reason:
            raise AppError("transfer_blocked", reason["reason"] + (f" Tablolar: {', '.join(reason['tables'])}." if reason["tables"] else ""), 409)
        job_id = queue.enqueue(session, TYPE_TRANSFER, CHANNEL_PROCESSING, user.id, {"user_id": user.id}, summary="Tam aktarım", commit=False)
        audit.write_audit(session, ACTION, user.id, "Job", str(job_id), {"transfer_type": "Tam"})
        session.commit()
        return {"job_id": job_id}

    return auth._db(work)


def partial_plan(session: Session | None) -> dict:
    """Kısmi aktarım penceresi (K-155): gruplar ve tabloları; süren iş; validasyonu bitmemiş tablolar (seçime göre engel arayüzde hesaplanır)."""
    session = auth._require(session)

    def work():
        rows = {e.table: _plan_row(session, e) for e in contract.ENTITIES}
        return {"groups": [{"name": g, "tables": [rows[t] for t in transfer.order() if t in tables]} for g, tables in GROUPS.items()],
                "busy": busy_reason(session), "pending": [e.table for e in _pending(session, group_tables(GROUPS))]}

    return auth._db(work)


def _groups(groups: list[str]) -> list[str]:
    chosen = [g for g in GROUPS if g in set(groups)]   # docs sırasıyla, tekrarsız
    try:
        group_tables(groups)
    except UnknownGroup as exc:
        raise AppError("transfer_groups", f"Bilinmeyen grup: {exc}.", 422) from None
    if not chosen:
        raise AppError("transfer_groups", "En az bir grup seçin.", 422)
    return chosen


def start_partial(session: Session | None, user: CurrentUser, groups: list[str]) -> dict:
    """Kısmi aktarımı iş kuyruğuna yazar; yük {mode: Kısmi, groups} (5.6'daki akış adımı da aynı yükü yazar, K-155)."""
    session = auth._require(session)
    chosen = _groups(groups)

    def work():
        reason = blocked(session, group_tables(chosen))
        if reason:
            raise AppError("transfer_blocked", reason["reason"] + (f" Tablolar: {', '.join(reason['tables'])}." if reason["tables"] else ""), 409)
        job_id = queue.enqueue(session, TYPE_TRANSFER, CHANNEL_PROCESSING, user.id, {"user_id": user.id, "mode": PARTIAL, "groups": chosen},
                               summary=f"{PARTIAL_ACTION} · {', '.join(chosen)}", commit=False)
        audit.write_audit(session, PARTIAL_ACTION, user.id, "Job", str(job_id), {"transfer_type": PARTIAL, "groups": ", ".join(chosen)})
        session.commit()
        return {"job_id": job_id}

    return auth._db(work)


def result(session: Session | None, job_id: int) -> dict:
    """İş durumu ve sonucu (veri versiyonu, tablo başına sayılar). Bulunmayan ya da başka tipte iş 404."""
    session = auth._require(session)

    def work():
        job = repo.job_row(session, job_id)
        if job is None or job["JobType"] != TYPE_TRANSFER:
            raise AppError("transfer_not_found", "Aktarım bulunamadı.", 404)
        res = json.loads(job["Result"] or "{}")
        return {"job_id": job_id, "status": job["Status"], "progress": job["Progress"], "error": job["ErrorText"], "requested_at": job["CreatedAt"],
                "data_version": res.get("data_version"), "tables": res.get("tables", [])}

    return auth._db(work)

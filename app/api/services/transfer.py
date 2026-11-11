"""Tam ve kısmi aktarım (ekran 02, fonksiyon 05, 06 ve 07, K-149…K-153, K-155): onay penceresi, başlatma, sonuç.

İş tipi "Aktarım", kanal "Veri işleme"; aynı anda tek aktarım. Çekim, Excel ön kontrolü, validasyon ya da aktarım sıradayken veya sürerken,
ya da staging'de verisi olup validasyonu bitmemiş tablo varken başlamaz (409 transfer_blocked); kısmide yalnız seçilen grupların tabloları bakılır.
İz "Tam aktarım" / "Kısmi aktarım" (K-108).
"""
import io
import json
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration import contract
from app.jobs import queue
from app.jobs.constants import ACTIVE_STATUSES, CHANNEL_PROCESSING, TYPE_CLEANUP, TYPE_PRECHECK, TYPE_PULL, TYPE_TRANSFER, TYPE_VALIDATION
from app.flows.runner import failed_rules
from app.transfer import engine as transfer
from app.transfer.groups import GROUPS, UnknownGroup, group_tables
from app.validation import engine as validation

from db.models import metadata

from ..errors import AppError
from ..export.writer import XlsxWriter, local_datetime
from ..permissions import SYSTEM_OWNER
from ..repositories import audit, export as export_repo, integration as repo
from . import auth, flows
from .auth import CurrentUser
from .validation import state_of

OBJECT = "DataVersion"
ACTION, PARTIAL_ACTION = "Tam aktarım", "Kısmi aktarım"  # iz (K-108)
FULL_NAME, PARTIAL_NAME = "Tam veri aktarımı", "Kısmi veri aktarımı"  # iş özeti ve bildirim (K-157)
PARTIAL = transfer.PARTIAL
BUSY_TYPES = (TYPE_PULL, TYPE_PRECHECK, TYPE_VALIDATION, TYPE_TRANSFER, TYPE_CLEANUP)
READY, SKIP_THRESHOLD, SKIP_EMPTY = "Aktarılır", "Eşik aşıldı", "Veri gelmedi"
BUSY_TEXT = {TYPE_TRANSFER: "Aktarım", TYPE_CLEANUP: "Temizlik", TYPE_PULL: "Veri çekme", TYPE_PRECHECK: "Excel ön kontrolü", TYPE_VALIDATION: "Validasyon"}  # öncelik sırası


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


def _plan_row(session: Session, e, failed: dict[str, int]) -> dict:
    """failed: çalışmayan veri kuralı sayısı (K-163); onay penceresi uyarır, kullanıcı bilerek devam eder."""
    if not transfer._has_raw(session, e.table):
        return {"entity": e.table, "name": e.name, "current_rows": 0, "error_rows": 0, "status": SKIP_EMPTY, "note": transfer.NOTE_EMPTY,
                "failed_rules": failed.get(e.table, 0)}
    c = validation.counts(session, e.table)
    note = transfer.threshold_note(session, e.table)
    return {"entity": e.table, "name": e.name, "current_rows": c["current_rows"], "error_rows": c["error_rows"],
            "status": SKIP_THRESHOLD if note else READY, "note": note, "failed_rules": failed.get(e.table, 0)}


def plan(session: Session | None) -> dict:
    """Onay penceresi: tablo başına güncel satır, Hatalı, durum ve not."""
    session = auth._require(session)

    def work():
        failed = failed_rules(session)
        return {"tables": [_plan_row(session, e, failed) for e in contract.ENTITIES], "blocked": blocked(session)}

    return auth._db(work)


def start(session: Session | None, user: CurrentUser) -> dict:
    """İş kuyruğuna yazar; iz aynı işlemde (K-108)."""
    session = auth._require(session)

    def work():
        flows.ensure_idle(session)  # K-163
        reason = blocked(session)
        if reason:
            raise AppError("transfer_blocked", reason["reason"] + (f" Tablolar: {', '.join(reason['tables'])}." if reason["tables"] else ""), 409)
        job_id = queue.enqueue(session, TYPE_TRANSFER, CHANNEL_PROCESSING, user.id, {"user_id": user.id}, summary=FULL_NAME, commit=False)
        audit.write_audit(session, ACTION, user.id, "Job", str(job_id), {"transfer_type": "Tam"})
        session.commit()
        return {"job_id": job_id}

    return auth._db(work)


def partial_plan(session: Session | None) -> dict:
    """Kısmi aktarım penceresi (K-155): gruplar ve tabloları; süren iş; validasyonu bitmemiş tablolar (seçime göre engel arayüzde hesaplanır)."""
    session = auth._require(session)

    def work():
        failed = failed_rules(session)
        rows = {e.table: _plan_row(session, e, failed) for e in contract.ENTITIES}
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
    """Kısmi aktarımı iş kuyruğuna yazar; yük {mode: Kısmi, groups} (5.6'daki zamanlanmış iş adımı da aynı yükü yazar, K-155)."""
    session = auth._require(session)
    chosen = _groups(groups)

    def work():
        flows.ensure_idle(session)
        reason = blocked(session, group_tables(chosen))
        if reason:
            raise AppError("transfer_blocked", reason["reason"] + (f" Tablolar: {', '.join(reason['tables'])}." if reason["tables"] else ""), 409)
        job_id = queue.enqueue(session, TYPE_TRANSFER, CHANNEL_PROCESSING, user.id, {"user_id": user.id, "mode": PARTIAL, "groups": chosen},
                               summary=f"{PARTIAL_NAME} · {', '.join(chosen)}", commit=False)
        audit.write_audit(session, PARTIAL_ACTION, user.id, "Job", str(job_id), {"transfer_type": PARTIAL, "groups": ", ".join(chosen)})
        session.commit()
        return {"job_id": job_id}

    return auth._db(work)


VERSION = metadata.tables["adm.DataVersion"]
ENTITY = metadata.tables["adm.DataVersionEntity"]
SUPPORT_NAME = "Smartchain"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
REPORT_TITLE = "Veri aktarım raporu"
REPORT_COLUMNS = [{"field": "name", "label": "Tablo", "type": "text"}, {"field": "new", "label": "Yeni", "type": "integer"},
                  {"field": "changed", "label": "Güncellenen", "type": "integer"}, {"field": "closed", "label": "Silinen", "type": "integer"},
                  {"field": "not_transferred", "label": "Aktarılmayan", "type": "integer"}, {"field": "note", "label": "Not", "type": "text"}]
REPORT_WIDTHS = {"name": 14, "note": 40}


def _version_tables(session: Session, version: int) -> list[dict]:
    """Raporun tablo satırları DataVersionEntity'den (K-156): iş sonucuna bağlı kalmaz; aktarım sırasıyla."""
    rank = {e: i for i, e in enumerate(transfer.order())}
    rows = session.execute(sa.select(ENTITY).where(ENTITY.c.DataVersionId == version)).mappings().all()
    out = []
    for r in sorted(rows, key=lambda r: rank.get(r["EntityName"], len(rank))):
        info = contract.entity(r["EntityName"])
        out.append({"entity": r["EntityName"], "name": info.name if info else r["EntityName"], "new": r["NewCount"], "changed": r["ChangedCount"],
                    "closed": r["ClosedCount"], "not_transferred": r["NotTransferredCount"], "note": r["Note"]})
    return out


def _report(session: Session, job_id: int) -> dict:
    job = repo.job_row(session, job_id)
    if job is None or job["JobType"] != TYPE_TRANSFER:
        raise AppError("transfer_not_found", "Aktarım bulunamadı.", 404)
    payload = json.loads(job["Payload"] or "{}")
    partial = payload.get("mode") == PARTIAL
    version = session.execute(sa.select(VERSION.c.Id).where(VERSION.c.JobId == job_id)).scalar()
    if version is None:   # 0047'den önceki ya da henüz bitmemiş iş: sonuçtaki numara
        version = json.loads(job["Result"] or "{}").get("data_version")
    user = session.execute(sa.select(repo.USER.c.FullName, repo.USER.c.UserName, repo.USER.c.Role)
                           .where(repo.USER.c.Id == job["RequestedBy"])).first() if job["RequestedBy"] else None
    name = None if user is None else SUPPORT_NAME if user.Role == SYSTEM_OWNER else (user.FullName or user.UserName)
    started, ended = job["StartedAt"], job["EndedAt"]
    return {"job_id": job_id, "status": job["Status"], "progress": job["Progress"], "error": job["ErrorText"], "requested_at": job["CreatedAt"],
            "started_at": started, "ended_at": ended, "duration_seconds": int((ended - started).total_seconds()) if started and ended else None,
            "transfer_type": PARTIAL if partial else "Tam", "groups": payload.get("groups") if partial else None, "requested_by_name": name,
            "data_version": version, "tables": _version_tables(session, version) if version else []}


def result(session: Session | None, job_id: int) -> dict:
    """Veri aktarım raporu (K-151, K-156): iş durumu, tür ve gruplar, başlatan, süre, veri versiyonu, tablo başına sayılar. Bulunmayan ya da
    başka tipte iş 404."""
    session = auth._require(session)
    return auth._db(lambda: _report(session, job_id))


def _local(value: datetime | None) -> str:
    return local_datetime(value).strftime("%d.%m.%Y %H:%M") if value else ""


def report_excel(session: Session | None, user: CurrentUser, job_id: int) -> tuple[bytes, str]:
    """Raporun Excel'i: Veri sayfasında tablo satırları, Bilgi sayfasında tür, gruplar, başlatan, zaman, süre, veri versiyonu; iz (K-91)."""
    session = auth._require(session)

    def work():
        r = _report(session, job_id)
        buffer = io.BytesIO()
        w = XlsxWriter(buffer, REPORT_COLUMNS, REPORT_WIDTHS)
        w.header()
        for t in r["tables"]:
            w.data_row(t)
        kind = r["transfer_type"] + (f" · {', '.join(r['groups'])}" if r["groups"] else "")
        w.info_sheet([("Rapor", REPORT_TITLE), ("Tür", kind), ("Başlatan", r["requested_by_name"] or ""), ("Başlama", _local(r["started_at"])),
                      ("Süre (sn)", "" if r["duration_seconds"] is None else str(r["duration_seconds"])),
                      ("Veri versiyonu", f"v{r['data_version']}" if r["data_version"] else ""), ("Durum", r["status"])]
                     + ([("Hata", r["error"])] if r["error"] else []))
        w.save()
        name = f"smartchain_veri-aktarim-raporu_v{r['data_version']}.xlsx" if r["data_version"] else f"smartchain_veri-aktarim-raporu_is-{job_id}.xlsx"
        export_repo.write_audit(session, user.id, "transfer-report", name, {"rows": len(r["tables"]), "data_version": r["data_version"]})
        session.commit()
        return buffer.getvalue(), name

    return auth._db(work)

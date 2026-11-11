"""Veri çekme (fonksiyon 01, K-130): yöntemi SQL olan tablolarda view'ı okuyup stg'ye yazar. Veri versiyonu açmaz.

Tablo başına bir parti. Okuma bitene kadar parti "Ön kontrol": kimse okumaz, yarıda kalırsa satırları silinir. Bir tablonun hatası diğerini durdurmaz;
yenileme sürüyorsa ya da yeni veri yoksa önceki ham veri korunur, bunlar hata değildir. Satırlar Excel'le aynı kontrol kodundan geçer.
"""
import json
import logging
import time
from collections.abc import Callable

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.integration import contract, structural
from app.integration.sql_source import NO_SIGNAL, RUNNING, Signal, SourceError
from app.jobs import queue
from app.jobs.constants import ACTIVE_STATUSES, CHANNEL_PULL, TYPE_PULL
from app.validation import engine as validation

from ..errors import AppError
from ..export.describe import tr_number
from ..repositories import audit, imports as imports_repo, integration as repo, lists as lists_repo
from . import auth, flows, imports, integration
from .auth import CurrentUser

log = logging.getLogger("smartchain.pull")

OBJECT = "Job"
ACTION = "Veri çekme"
MAX_TRIES = 3  # geçici hata (fonksiyon 01)
READ, RECEIVED, FAILED, INCOMPLETE = "Okunacak", imports_repo.RECEIVED, imports_repo.FAILED, imports_repo.INCOMPLETE
NO_NEW, REFRESHING, SKIPPED, ERROR = "Yeni veri yok", "Veri güncellemesi devam ediyor", "Atlandı", "Hata"
SOURCE_LOST = "SQL kaynağına ulaşılamadı."
NO_NEW_REASON = "Son çekimden beri değişiklik yok."
NO_SIGNAL_REASON = "Tamamlanmış veri güncellemesi yok."
REFRESH_REASON = "Veri güncellemesi devam ediyor."
CHANGED_REASON = "Çekim sırasında veri güncellendi."
EMPTY_REASON = "View satır vermedi."


def _skip_reason(row: dict | None) -> str | None:
    if repo.method_of(row) != repo.METHOD_SQL:
        return "Yöntemi Excel"
    if not repo.is_pull_enabled(row):
        return "Çekim kapalı"
    if not (row or {}).get("ViewName"):
        return "View tanımsız"
    return None


def _targets(entities: list[str] | None) -> list[contract.Entity]:
    """Tanımlı sırayla: referans verisinden işlem verisine (docs/03)."""
    if entities:
        for table in entities:
            integration.entity_of(table)
    return [e for e in contract.ENTITIES if not entities or e.table in entities]


def _signal_state(signal: Signal, last: int | None) -> tuple[str, str | None]:
    if signal.state == RUNNING:
        return REFRESHING, REFRESH_REASON
    if signal.state == NO_SIGNAL:
        return NO_NEW, NO_SIGNAL_REASON
    return (NO_NEW, NO_NEW_REASON) if signal.id == last else (READ, None)


def plan(session: Session | None) -> dict:
    """Onay penceresi: tablo, yöntem, kaynak, durum ve neden."""
    session = auth._require(session)

    def work():
        rows = repo.all_entities(session)
        database = repo.read_database(session)
        out = []
        source = None
        source_error = None
        if database and any(_skip_reason(rows.get(e.table)) is None for e in contract.ENTITIES):
            try:
                source = integration.open_source(session, database).__enter__()
            except SourceError as exc:
                source_error = str(exc)
        try:
            for entity in contract.ENTITIES:
                row = rows.get(entity.table)
                method = repo.method_of(row)
                state, reason = SKIPPED, _skip_reason(row)
                if reason is None:
                    if source is None:
                        state, reason = ERROR, source_error or "SQL kaynağı tanımlı değil."
                    else:
                        try:
                            state, reason = _signal_state(source.signal(entity.table), repo.last_signal(session, entity.table))
                        except SourceError as exc:
                            state, reason = ERROR, str(exc)
                        except DBAPIError:
                            state, reason = ERROR, SOURCE_LOST
                out.append({"entity": entity.table, "name": entity.name, "method": method, "source": (row or {}).get("ViewName") if method == repo.METHOD_SQL else None,
                            "state": state, "reason": reason})
        finally:
            if source is not None:
                source.__exit__()
        last = repo.last_pull(session)
        return {"database": database, "tables": out,
                "last": {"at": last["CreatedAt"], "by": last["FullName"] or last["UserName"] or "sistem"} if last else None}

    return auth._db(work)


def start(session: Session | None, user: CurrentUser, entities: list[str] | None, read_anyway: list[str]) -> dict:
    """İş kuyruğuna yazar; iz aynı işlemde (K-108). Aynı anda tek çekim."""
    session = auth._require(session)

    def work():
        flows.ensure_idle(session)  # K-163
        if not repo.read_database(session):
            raise integration.not_configured()
        targets = _targets(entities)
        if queue_active(session):
            raise AppError("pull_running", "Çalışan bir çekim var; bitince yeniden deneyin.", 409)
        tables = [e.table for e in targets] if entities else []
        summary = (f"{targets[0].name}" if entities and len(targets) == 1 else f"{len(targets)} tablo")
        job_id = queue.enqueue(session, TYPE_PULL, CHANNEL_PULL, user.id, {"entities": tables, "read_anyway": list(read_anyway), "user_id": user.id}, summary=f"Veri çekme · {summary}"[:200])
        audit.write_audit(session, ACTION, user.id, OBJECT, str(job_id), {"entities": [e.name for e in targets] if entities else "Bütün tablolar", "read_anyway": [e.name for e in contract.ENTITIES if e.table in read_anyway]})
        session.commit()
        return {"job_id": job_id}

    return auth._db(work)


def queue_active(session: Session) -> bool:
    return session.execute(sa.select(repo.JOB.c.Id).where(repo.JOB.c.JobType == TYPE_PULL, repo.JOB.c.Status.in_(ACTIVE_STATUSES))).first() is not None


def result(session: Session | None, job_id: int) -> dict:
    """İş durumu ve tablo başına sonuç. Bulunmayan ya da başka tipte iş 404."""
    session = auth._require(session)

    def work():
        job = repo.job_row(session, job_id)
        if job is None or job["JobType"] != TYPE_PULL:
            raise AppError("pull_not_found", "Çekim bulunamadı.", 404)
        return {"job_id": job_id, "status": job["Status"], "progress": job["Progress"], "error": job["ErrorText"],
                "requested_at": job["CreatedAt"], "tables": json.loads(job["Result"] or "[]")}

    return auth._db(work)


def _outcome(entity: contract.Entity, row: dict | None, status: str, reason: str | None = None, **extra) -> dict:
    return {"entity": entity.table, "name": entity.name, "method": repo.method_of(row), "source": (row or {}).get("ViewName"), "status": status, "reason": reason,
            "read": None, "valid": None, "errors": None, "batch_id": None, "attempts": [], **extra}


def _read_table(session: Session, entity: contract.Entity, row: dict, job_id: int, user_id: int | None, read_anyway: bool,
                progress: Callable[[str], None] | None, group: int | None = None) -> dict:
    table, view = entity.table, row["ViewName"]
    labels = lists_repo.read_labels(session, table)
    with integration.open_source(session) as source:
        signal = source.signal(table)
        state, reason = _signal_state(signal, repo.last_signal(session, table))
        if state == REFRESHING or (state == NO_NEW and not read_anyway):
            return _outcome(entity, row, state, reason)
        check = integration.inspect_view(session, source, table, view, labels)
        if check.errors:
            session.commit()
            return _outcome(entity, row, ERROR, check.message)
        batch_id = repo.create_batch(session, table, view, signal.id, user_id, job_id)
        imports_repo.insert_findings(session, batch_id, [structural.Finding(structural.WARNING, "view_column", w) for w in check.warnings])
        session.commit()
        try:
            read, _too_many = imports.read_rows(session, batch_id, entity, labels, source.read_rows(view, check.columns), progress, None)
            after = source.signal(table)
        except Exception:
            session.rollback()
            imports.mark_incomplete(session, batch_id)
            raise
    if after.state == RUNNING or after.id != signal.id:
        imports.mark_incomplete(session, batch_id)
        return _outcome(entity, row, INCOMPLETE, CHANGED_REASON, batch_id=batch_id)
    imports.finish_batch(session, batch_id, entity, read, False, {})
    batch = imports_repo.get_batch(session, batch_id)
    if batch["Status"] == imports_repo.PENDING:
        imports_repo.set_batch(session, batch_id, Status=imports_repo.RECEIVED)
        # Güncel hâl ve doğrulama (K-133, K-134); toplu çekimde tablolar arası kurallar grubun sonunda; commit eder
        validation.on_received(session, entity.table, batch_id, validation.current.FULL,
                               validation.TRIGGER_BULK if group else validation.TRIGGER_PULL, user_id, group)
    session.commit()
    errors = batch["ErrorCount"] or 0
    status = imports_repo.status_of(session, batch_id)
    return _outcome(entity, row, status, EMPTY_REASON if read == 0 else None, batch_id=batch_id, read=read, valid=max(read - errors, 0), errors=errors)


def _pull_one(session: Session, entity: contract.Entity, row: dict | None, job_id: int, user_id: int | None, read_anyway: bool, wait_seconds: int,
              progress: Callable[[str], None] | None, group: int | None = None) -> dict:
    skip = _skip_reason(row)
    if skip:
        return _outcome(entity, row, SKIPPED, skip)
    attempts: list[dict] = []
    for attempt in range(1, MAX_TRIES + 1):
        try:
            return {**_read_table(session, entity, row, job_id, user_id, read_anyway, progress, group), "attempts": attempts}
        except SourceError as exc:  # yapı eksik (sinyal tablosu, view): yeniden denemek düzeltmez
            session.rollback()
            return _outcome(entity, row, ERROR, str(exc), attempts=attempts)
        except DBAPIError as exc:
            session.rollback()
            log.warning("%s okunamadı (deneme %s): %s", entity.table, attempt, exc)
            attempts.append({"attempt": attempt, "at": repo.utcnow().isoformat(timespec="seconds"), "message": SOURCE_LOST})
            if attempt < MAX_TRIES and wait_seconds:
                time.sleep(wait_seconds)
    return _outcome(entity, row, ERROR, SOURCE_LOST, attempts=attempts)


def run_job(session: Session, job_id: int, attempt: int, payload: dict, progress: Callable[[str], None]) -> bool:
    """Motor servisinin çekim işi. Yeniden denemede yarıda kalan partiler kapanır, tablolar baştan okunur."""
    fail_job(session, job_id)
    rows = repo.all_entities(session)
    wait = repo.read_pull_settings(session)["PullRetryWaitSeconds"]
    targets = _targets(payload.get("entities") or None)
    group = job_id if len(targets) > 1 else None  # toplu çekim: tablolar arası doğrulama bütün tablolar bitince (K-134)
    results: list[dict] = []
    for index, entity in enumerate(targets, 1):
        row = rows.get(entity.table)

        def step(text: str, name: str = entity.name, i: int = index) -> None:
            progress(f"{i} / {len(targets)} · {name} · {text}")

        outcome = _pull_one(session, entity, row, job_id, payload.get("user_id"), entity.table in (payload.get("read_anyway") or ()), wait, step, group)
        results.append(outcome)
        if outcome["status"] != SKIPPED:
            values = {"LastPullStatus": outcome["status"], "LastPullMessage": (outcome["reason"] or "")[:400] or None}
            if outcome["batch_id"]:
                values["LastPullAt"] = repo.utcnow()
            repo.save_entity(session, entity.table, **values)
        repo.set_job_result(session, job_id, results)
        session.commit()
    read = [r for r in results if r["status"] == RECEIVED]
    failed = [r for r in results if r["status"] in (ERROR, FAILED, INCOMPLETE)]
    text = f"{len(read)} tablo alındı · {tr_number(sum(r['read'] or 0 for r in read), 0)} satır" + (f" · {len(failed)} tablo sorunlu" if failed else "")
    ok = queue.finish(session, job_id, attempt, progress=text[:100])
    if group:
        validation.maybe_start_cross(session, group)
    return ok


def fail_job(session: Session, job_id: int) -> None:
    """Süreç düştüyse ya da yeniden deneniyorsa: açık partiler Tamamlanmadı, satırları silinir."""
    session.rollback()
    for batch_id in repo.open_job_batches(session, job_id):
        imports.mark_incomplete(session, batch_id)

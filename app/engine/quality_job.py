"""Veri kalitesi işi (fonksiyon 20, K-174): motor servisinin başlattığı ayrı süreç (cleanup_job deseni).

Aktarımdan, manuel değerden sonra ve gün dönümünde kuyruğa girer. Çökerse aktarım geçerli kalır; iş Hatalı olur, uyarılar önceki hâlinde kalır.
"""
import json
import logging
from datetime import date

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.jobs import queue
from db.models import metadata
from .job import FORMAT

log = logging.getLogger("smartchain.engine.quality")
ACTION = "Veri kalitesi"


def done_text(result: dict) -> str:
    """İş paneli: "Veri kalitesi bitti · 12 yüksek · 3 yeni"."""
    return f"{ACTION} bitti · {result.get('high', 0)} yüksek · {result.get('new', 0)} yeni"


def run_quality_job(job_id: int, attempt: int) -> None:
    from app.api.db import get_engine
    from app.quality import HIGH, STATE_IGNORED, STATE_NEW, run

    db = get_engine()
    job = metadata.tables["adm.Job"]
    warning = metadata.tables["adm.DataQualityWarning"]
    with Session(db) as session:
        payload = json.loads(session.execute(text("SELECT Payload FROM adm.Job WHERE Id = :id"), {"id": job_id}).scalar() or "{}")
        tables = set(payload["tables"]) if payload.get("tables") is not None else None
        day = date.fromisoformat(payload["today"]) if payload.get("today") else None

        def progress(stage: str) -> None:
            with Session(db) as s:
                queue.set_progress(s, job_id, attempt, stage[:100])

        try:
            stats = run.run(session, tables, day, progress)
            visible = warning.c.State != STATE_IGNORED
            n = lambda cond: sa.func.coalesce(sa.func.sum(sa.case((cond, 1), else_=0)), 0)  # noqa: E731  (SQL Server'da COUNT FILTER yok)
            counts = session.execute(sa.select(n(sa.and_(visible, warning.c.Importance == HIGH)), n(warning.c.State == STATE_NEW))).one()
            result = {**stats, "high": counts[0], "new": counts[1], "tables": payload.get("tables"), "today": payload.get("today")}
            session.execute(sa.update(job).where(job.c.Id == job_id).values(Result=json.dumps(result, ensure_ascii=False, default=str)))
            if not queue.finish(session, job_id, attempt, progress=done_text(result)[:100], commit=False):
                session.rollback()
                log.warning("İş %s (deneme %s) artık bu sürecin değil", job_id, attempt)
                return
            session.commit()
            log.info("Veri kalitesi işi %s bitti · %s", job_id, result)
        except Exception:
            log.exception("Veri kalitesi işi %s hata", job_id)
            session.rollback()
            with Session(db) as s:
                queue.fail(s, job_id, attempt, f"{ACTION} kontrolü tamamlanamadı; uyarılar önceki hâlinde. Destek için iş numarası: {job_id}")


def quality_process_main(job_id: int, attempt: int, _time_budget_seconds: int) -> None:
    """Ayrı sürecin giriş noktası (multiprocessing spawn)."""
    logging.basicConfig(level=logging.INFO, format=FORMAT)
    run_quality_job(job_id, attempt)

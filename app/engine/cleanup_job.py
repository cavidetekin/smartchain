"""Ham veri temizliği işi (fonksiyon 09, K-156): motor servisinin başlattığı ayrı süreç (transfer_job deseni).

Veritabanı değişiklikleri, iş sonucu ve özet iz tek işlemde commit edilir; dosyalar commit'ten sonra silinir ve sonuçtaki dosya sayısı ile boyut
güncellenir. Saklama süresi boşsa hiçbir şey silinmez, iş notuyla biter.
"""
import json
import logging

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.jobs import queue
from db.models import metadata
from .job import FORMAT

log = logging.getLogger("smartchain.engine.cleanup")
ACTION = "Ham veri temizliği"
NO_RETENTION = "Saklama süresi tanımlı değil; temizlik çalışmadı."


def _n(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def done_text(result: dict) -> str:
    """Bildirim (K-157): "Ham veri temizliği bitti · 55 yükleme · 7.185 eski satır · 10 dosya"."""
    if result.get("note"):
        return f"{ACTION} · {result['note']}"
    return f"{ACTION} bitti · {_n(result['batches'])} yükleme · {_n(result['rows'])} eski satır · {_n(result['files'])} dosya"


def run_cleanup_job(job_id: int, attempt: int) -> None:
    from app.api.db import get_engine
    from app.api.repositories import audit
    from app.cleanup import raw

    db = get_engine()
    job = metadata.tables["adm.Job"]
    with Session(db) as session:
        payload = json.loads(session.execute(text("SELECT Payload FROM adm.Job WHERE Id = :id"), {"id": job_id}).scalar() or "{}")

        def progress(stage: str) -> None:
            with Session(db) as s:
                queue.set_progress(s, job_id, attempt, stage[:100])

        try:
            days = raw.retention_days(session)
            paths = []
            if days is None:
                result = {"note": NO_RETENTION}
            else:
                summary, paths = raw.run(session, days, progress)
                result = summary.as_dict()
                audit.write_audit(session, ACTION, payload.get("user_id"), "ImportBatch", str(job_id),
                                  {k: result[k] for k in ("retention_days", "batches", "abandoned", "rows")} | {"files": len(paths)})
            session.execute(sa.update(job).where(job.c.Id == job_id).values(Result=json.dumps(result, ensure_ascii=False)))
            if not queue.finish(session, job_id, attempt, progress=done_text({**result, "files": len(paths)})[:100], commit=False):
                session.rollback()
                log.warning("İş %s (deneme %s) artık bu sürecin değil", job_id, attempt)
                return
            session.commit()
        except Exception:
            log.exception("Temizlik işi %s hata", job_id)
            session.rollback()
            with Session(db) as s:
                queue.fail(s, job_id, attempt, f"{ACTION} tamamlanamadı; hiçbir şey silinmedi. Destek için iş numarası: {job_id}")
            return
        if days is not None:
            raw.delete_files(summary, paths)        # commit'ten sonra; gerçek sayı ve boyut sonuca yazılır
            with Session(db) as s:
                s.execute(sa.update(job).where(job.c.Id == job_id).values(Result=json.dumps(summary.as_dict(), ensure_ascii=False)))
                s.commit()
            log.info("Temizlik işi %s bitti · %s parti, %s satır, %s dosya", job_id, summary.batches, summary.rows, summary.files)


def cleanup_process_main(job_id: int, attempt: int, _time_budget_seconds: int) -> None:
    """Ayrı sürecin giriş noktası (multiprocessing spawn)."""
    logging.basicConfig(level=logging.INFO, format=FORMAT)
    run_cleanup_job(job_id, attempt)

"""Veri çekme işi (K-130): motor servisinin başlattığı ayrı süreç (import_job deseni).

Düşerse iş Hata, açık partiler Tamamlanmadı olur, satırlar silinir; önceki ham veri korunur.
"""
import json
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.jobs import queue
from .job import FORMAT

log = logging.getLogger("smartchain.engine.pull")


def run_pull_job(job_id: int, attempt: int) -> None:
    """Servis bunu ayrı süreçte çağırır; testler doğrudan da çağırabilir."""
    from app.api.db import get_engine
    from app.api.services import pull

    db = get_engine()
    with Session(db) as session:
        payload = json.loads(session.execute(text("SELECT Payload FROM adm.Job WHERE Id = :id"), {"id": job_id}).scalar() or "{}")

        def progress(stage: str) -> None:
            with Session(db) as s:
                queue.set_progress(s, job_id, attempt, stage[:100])

        try:
            if pull.run_job(session, job_id, attempt, payload, progress):
                log.info("Çekim işi %s bitti", job_id)
            else:
                log.warning("İş %s (deneme %s) artık bu sürecin değil", job_id, attempt)
        except Exception:
            log.exception("Çekim işi %s hata", job_id)
            pull.fail_job(session, job_id)
            with Session(db) as s:
                queue.fail(s, job_id, attempt, f"Çekim tamamlanamadı. Destek için iş numarası: {job_id}")
            from app.validation import engine as validation
            with Session(db) as s:  # okunan tabloların tablolar arası doğrulaması yine başlar (K-134)
                validation.maybe_start_cross(s, job_id)


def pull_process_main(job_id: int, attempt: int, _time_budget_seconds: int) -> None:
    """Ayrı sürecin giriş noktası (multiprocessing spawn)."""
    logging.basicConfig(level=logging.INFO, format=FORMAT)
    run_pull_job(job_id, attempt)

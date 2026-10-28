"""Dışa aktarım işi (K-93): motor servisinin "Dışa aktarım" tipindeki işler için başlattığı ayrı süreç.

Dosya EXPORT_DIR/<iş>.xlsx'e yazılır; ilerleme ("120.000 / 142.000 satır") adım adım yazılır, kalp atışını servis yazar
(K-71). İz ve iş bitişi tek işlemde (services/export.run_job); hata olursa dosya silinir, iş Hata.
"""
import json
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.jobs import queue
from .job import FORMAT

log = logging.getLogger("smartchain.engine.export")


def run_export_job(job_id: int, attempt: int) -> None:
    """Servis bunu ayrı süreçte çağırır; testler doğrudan da çağırabilir."""
    from app.api.db import get_engine
    from app.api.services import export

    db = get_engine()
    with Session(db) as session:
        payload = session.execute(text("SELECT Payload FROM adm.Job WHERE Id = :id"), {"id": job_id}).scalar()

        def progress(stage: str) -> None:
            with Session(db) as s:
                queue.set_progress(s, job_id, attempt, stage)

        try:
            result = export.run_job(session, job_id, attempt, json.loads(payload or "{}"), progress)
            if result:
                log.info("Dışa aktarım işi %s bitti: %s", job_id, result)
            else:
                log.warning("İş %s (deneme %s) artık bu sürecin değil; dosya verilmedi", job_id, attempt)
        except Exception:
            log.exception("Dışa aktarım işi %s hata", job_id)
            with Session(db) as s:
                queue.fail(s, job_id, attempt, f"Excel dosyası hazırlanamadı. Destek için iş numarası: {job_id}")


def export_process_main(job_id: int, attempt: int, _time_budget_seconds: int) -> None:
    """Ayrı sürecin giriş noktası (multiprocessing spawn)."""
    logging.basicConfig(level=logging.INFO, format=FORMAT)
    run_export_job(job_id, attempt)

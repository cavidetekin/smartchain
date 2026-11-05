"""Excel ön kontrol işi (K-129): motor servisinin büyük yüklemeler için başlattığı ayrı süreç (export_job deseni).

İlerleme ("120.000 satır") adım adım yazılır, kalp atışını sürdürür. Düşerse iş Hata, parti Tamamlanmadı olur, satırlar silinir.
"""
import json
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.jobs import queue
from .job import FORMAT

log = logging.getLogger("smartchain.engine.import")


def run_import_job(job_id: int, attempt: int) -> None:
    """Servis bunu ayrı süreçte çağırır; testler doğrudan da çağırabilir."""
    from app.api.db import get_engine
    from app.api.services import imports

    db = get_engine()
    with Session(db) as session:
        payload = json.loads(session.execute(text("SELECT Payload FROM adm.Job WHERE Id = :id"), {"id": job_id}).scalar() or "{}")

        def progress(stage: str) -> None:
            with Session(db) as s:
                queue.set_progress(s, job_id, attempt, stage)

        try:
            if imports.run_job(session, job_id, attempt, payload, progress):
                log.info("Ön kontrol işi %s bitti", job_id)
            else:
                log.warning("İş %s (deneme %s) artık bu sürecin değil", job_id, attempt)
        except Exception:
            log.exception("Ön kontrol işi %s hata", job_id)
            imports.fail_job(session, payload)
            with Session(db) as s:
                queue.fail(s, job_id, attempt, f"Ön kontrol tamamlanamadı. Destek için iş numarası: {job_id}")


def import_process_main(job_id: int, attempt: int, _time_budget_seconds: int) -> None:
    """Ayrı sürecin giriş noktası (multiprocessing spawn)."""
    logging.basicConfig(level=logging.INFO, format=FORMAT)
    run_import_job(job_id, attempt)

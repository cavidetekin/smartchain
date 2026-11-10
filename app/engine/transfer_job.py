"""Aktarım işi, tam ya da kısmi (K-149, K-153, K-155): motor servisinin başlattığı ayrı süreç (validation_job deseni).

Aktarım ve iş kaydı tek işlemde commit edilir; düşerse işlem geri alınır, önceki veri versiyonu geçerli kalır, iş Hata olur.
"""
import json
import logging

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.jobs import queue
from db.models import metadata
from .job import FORMAT

log = logging.getLogger("smartchain.engine.transfer")
PARTIAL = "Kısmi"


def action(payload: dict) -> str:
    return "Kısmi aktarım" if payload.get("mode") == PARTIAL else "Tam aktarım"


def summary_lines(tables: list[dict]) -> list[str]:
    """Özet denetim kaydı (K-108): tablo başına tek satır."""
    out = []
    for t in tables:
        if t["new"] is None:  # aktarılmadı (veri gelmedi, eşik)
            out.append(f"{t['name']}: {t['note']}")
        else:
            out.append(f"{t['name']}: {t['new']} yeni, {t['changed']} güncellenen, {t['closed']} silinen, {t['not_transferred']} aktarılmayan"
                       + (f" · {t['note']}" if t["note"] else ""))
    return out


def run_transfer_job(job_id: int, attempt: int) -> None:
    """Servis bunu ayrı süreçte çağırır; testler doğrudan da çağırabilir."""
    from app.api.db import get_engine
    from app.api.repositories import audit
    from app.transfer import engine

    db = get_engine()
    with Session(db) as session:
        payload = json.loads(session.execute(text("SELECT Payload FROM adm.Job WHERE Id = :id"), {"id": job_id}).scalar() or "{}")

        def progress(stage: str) -> None:
            with Session(db) as s:
                queue.set_progress(s, job_id, attempt, stage[:100])

        try:
            groups = payload.get("groups") if payload.get("mode") == PARTIAL else None
            result = engine.run_transfer(session, payload.get("user_id"), progress, groups=groups)
            details = {"data_version": result["data_version"], "transfer_tables": summary_lines(result["tables"])}
            if groups:
                details["groups"] = ", ".join(groups)
            audit.write_audit(session, action(payload), payload.get("user_id"), "DataVersion", str(result["data_version"]), details)
            job = metadata.tables["adm.Job"]  # tipli yazım: 4000 karakterden uzun sonuç nvarchar(max) olarak gider
            session.execute(sa.update(job).where(job.c.Id == job_id).values(Result=json.dumps(result, ensure_ascii=False)))
            if queue.finish(session, job_id, attempt, progress=f"{action(payload)} bitti · v{result['data_version']}", commit=False):
                session.commit()
                log.info("Aktarım işi %s bitti · v%s", job_id, result["data_version"])
            else:
                session.rollback()
                log.warning("İş %s (deneme %s) artık bu sürecin değil", job_id, attempt)
        except Exception:
            log.exception("Aktarım işi %s hata", job_id)
            session.rollback()
            with Session(db) as s:
                queue.fail(s, job_id, attempt, f"{action(payload)} tamamlanamadı; önceki veri versiyonu geçerli. Destek için iş numarası: {job_id}")


def transfer_process_main(job_id: int, attempt: int, _time_budget_seconds: int) -> None:
    """Ayrı sürecin giriş noktası (multiprocessing spawn)."""
    logging.basicConfig(level=logging.INFO, format=FORMAT)
    run_transfer_job(job_id, attempt)

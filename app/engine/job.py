"""İş süreci: motor servisinin her iş için başlattığı ayrı süreçte çalışır (01-mimari · iş yalıtımı).

Kalp atışını bu süreç değil, servis yazar; burası yalnız adım geçişlerinde ilerleme yazar (K-71).
Yakalanan hata PlanRun'u ve işi Hata yapar; süreç beklenmedik biterse servis işi yeniden sıraya alır.
"""
import json
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.jobs import queue
from .fake import build_engine
from .interface import EngineError
from .loader import load_input
from .writer import JobNoLongerOwned, PlanRunPublished, mark_running, write_failure, write_result

log = logging.getLogger("smartchain.engine.job")

FORMAT = "%(asctime)s %(levelname)-7s [iş %(process)d] %(name)s: %(message)s"


def plan_run_id_of(payload: str | None) -> int | None:
    try:
        return int(json.loads(payload or "{}")["plan_run_id"])
    except (ValueError, KeyError, TypeError):
        return None


def run_plan_job(job_id: int, attempt: int, time_budget_seconds: int) -> None:
    """Bir plan hesabı işi. Servis bunu ayrı süreçte çağırır; testler doğrudan da çağırabilir."""
    from app.api.db import get_engine  # süreç kendi bağlantı havuzunu kurar

    db = get_engine()
    with Session(db) as session:
        payload = session.execute(text("SELECT Payload FROM adm.Job WHERE Id = :id"), {"id": job_id}).scalar()
        plan_run_id = plan_run_id_of(payload)

        def progress(stage: str) -> None:
            with Session(db) as s:
                queue.set_progress(s, job_id, attempt, stage)

        try:
            if plan_run_id is None:
                raise EngineError("İş parametresinde plan hesabı (plan_run_id) yok.")
            mark_running(session, plan_run_id)
            inp = load_input(session, plan_run_id, time_budget_seconds)
            result = build_engine().run(inp, progress)
            write_result(session, plan_run_id, result, job_id, attempt)
        except JobNoLongerOwned:
            log.warning("İş %s (deneme %s) artık bu sürecin değil; sonuç yazılmadı", job_id, attempt)
        except (EngineError, PlanRunPublished) as exc:
            write_failure(session, plan_run_id, job_id, attempt, getattr(exc, "message", None) or str(exc))
        except Exception:
            log.exception("İş %s (PlanRun %s) beklenmeyen hata", job_id, plan_run_id)
            write_failure(session, plan_run_id, job_id, attempt,
                          f"Hesap beklenmeyen bir hatayla durdu. Destek için iş numarası: {job_id}")


def process_main(job_id: int, attempt: int, time_budget_seconds: int) -> None:
    """Ayrı sürecin giriş noktası (multiprocessing spawn)."""
    logging.basicConfig(level=logging.INFO, format=FORMAT)
    run_plan_job(job_id, attempt, time_budget_seconds)

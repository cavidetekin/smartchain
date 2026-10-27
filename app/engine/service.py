"""Motor servisi (üst süreç): kuyruktan işi alır, her işi ayrı süreçte çalıştırır (01-mimari · iş yalıtımı).

- Kalp atışını servis yazar: iş süreci yaşadıkça gider; çözücü GIL'i bırakmasa da etkilenmez (K-71).
- Süre bütçesi + pay aşılırsa süreci sonlandırır; iş ve PlanRun Hata.
- İş süreci beklenmedik biterse işi hemen yeniden sıraya alır (deneme hakkı varsa, K-67).
- Takılan işleri (requeue_stale) açılışta ve belli aralıkla kendisi de geri alır; API kapalıyken iş beklemez.

Çalıştırma (geliştirme):  python -m app.engine.service      Windows servisi olarak kurulum 0.6'da.
"""
import logging
import multiprocessing as mp
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.jobs import queue
from app.jobs.constants import CHANNELS
from app.jobs.settings import JobSettings, read_settings
from .job import plan_run_id_of, process_main
from .settings import EngineSettings, read_engine_settings
from .writer import write_failure

log = logging.getLogger("smartchain.engine")

STALE_CHECK_SECONDS = 15


@dataclass
class RunningJob:
    job_id: int
    attempt: int
    plan_run_id: int | None
    budget: float
    process: mp.process.BaseProcess
    deadline: float
    last_heartbeat: float


class EngineService:
    def __init__(self, db=None, job_settings: JobSettings | None = None,
                 engine_settings: EngineSettings | None = None, channels=CHANNELS):
        from app.api.db import get_engine
        self.db = db or get_engine()
        self._fixed_job_settings = job_settings
        self._fixed_engine_settings = engine_settings
        self.channels = channels
        self.running: dict[int, RunningJob] = {}
        self._ctx = mp.get_context("spawn")
        self._last_stale_check = 0.0
        self.job_settings = job_settings or JobSettings()
        self.engine_settings = engine_settings or EngineSettings()

    def _refresh_settings(self, session: Session) -> None:
        if self._fixed_job_settings is None:
            self.job_settings = read_settings(session)
        if self._fixed_engine_settings is None:
            self.engine_settings = read_engine_settings(session)

    def start(self) -> None:
        with Session(self.db) as s:
            self._refresh_settings(s)
            self._requeue_stale(s)
        log.info("Motor servisi başladı (kanallar: %s)", ", ".join(self.channels))

    def _requeue_stale(self, session: Session) -> None:
        ids = queue.requeue_stale(session, self.job_settings)
        if ids:
            log.warning("Yanıt vermeyen işler geri alındı: %s", ids)
        self._last_stale_check = time.monotonic()

    def poll_once(self) -> None:
        with Session(self.db) as s:
            if time.monotonic() - self._last_stale_check >= STALE_CHECK_SECONDS:
                self._refresh_settings(s)
                self._requeue_stale(s)
            for run in list(self.running.values()):
                self._check(s, run)
            for channel in self.channels:
                while (job := queue.claim_next(s, channel, self.job_settings)) is not None:
                    self._spawn(s, job, channel)

    def _spawn(self, session: Session, job: dict, channel: str) -> None:
        plan_run_id = plan_run_id_of(job["Payload"])
        budget = self.engine_settings.time_budget(channel)
        process = self._ctx.Process(target=process_main, args=(job["Id"], job["Attempt"], int(budget)),
                                    name=f"smartchain-job-{job['Id']}", daemon=True)
        process.start()
        now = time.monotonic()
        self.running[job["Id"]] = RunningJob(job["Id"], job["Attempt"], plan_run_id, budget, process,
                                             deadline=now + budget + self.engine_settings.kill_grace,
                                             last_heartbeat=now)
        log.info("İş %s (deneme %s, PlanRun %s) süreç %s'de başladı", job["Id"], job["Attempt"], plan_run_id,
                 process.pid)

    def _stop(self, run: RunningJob) -> None:
        if run.process.is_alive():
            run.process.kill()
        run.process.join(10)
        self.running.pop(run.job_id, None)

    def _check(self, session: Session, run: RunningJob) -> None:
        if not run.process.is_alive():
            run.process.join()
            self.running.pop(run.job_id, None)
            # Süreç iş kaydını bitirmeden kapandıysa (çöküş) iş hâlâ Çalışıyor'dur: hemen geri al.
            status = queue.requeue(session, run.job_id, run.attempt, self.job_settings)
            if status is not None:
                log.warning("İş %s süreci %s koduyla bitti → %s", run.job_id, run.process.exitcode, status)
            return
        now = time.monotonic()
        if now > run.deadline:
            self._stop(run)
            write_failure(session, run.plan_run_id, run.job_id, run.attempt,
                          f"Süre bütçesi aşıldı ({run.budget:g} sn + {self.engine_settings.kill_grace:g} sn pay); "
                          "hesap durduruldu.")
            return
        if now - run.last_heartbeat >= self.engine_settings.heartbeat_seconds:
            if queue.heartbeat(session, run.job_id, run.attempt):
                run.last_heartbeat = now
            else:  # iş geri alındı ya da sonlandırıldı; bu süreç artık sonuç yazamaz
                log.warning("İş %s (deneme %s) artık bu sürecin değil; süreç sonlandırıldı", run.job_id, run.attempt)
                self._stop(run)

    def shutdown(self) -> None:
        """Çalışan süreçler sonlandırılır; işleri kalp atışı kesilince geri alınır (K-67)."""
        for run in list(self.running.values()):
            self._stop(run)

    def run_forever(self, interval: float = 1.0) -> None:
        self.start()
        try:
            while True:
                try:
                    self.poll_once()
                except Exception:
                    log.exception("Motor servisi döngüsünde hata; devam ediliyor")
                time.sleep(interval)
        finally:
            self.shutdown()


def main() -> None:
    from app.api.logging_setup import setup_logging
    from app.api.settings import get_settings
    setup_logging(get_settings(), "engine.log")
    try:
        EngineService().run_forever()
    except KeyboardInterrupt:
        log.info("Motor servisi durduruldu")


if __name__ == "__main__":
    main()

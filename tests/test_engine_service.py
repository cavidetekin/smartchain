"""Motor servisi (K-71): iş ayrı süreçte, kalp atışı servisten, süre bütçesi, çöküş, servis requeue_stale."""
import time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.engine.service import EngineService
from app.engine.settings import EngineSettings
from app.engine.submit import submit_plan_run
from app.jobs import queue
from app.jobs.constants import CHANNEL_INTERACTIVE, STATUS_DONE, STATUS_FAILED, STATUS_QUEUED, TYPE_WORKSPACE
from app.jobs.settings import JobSettings
from conftest import set_fake

pytestmark = pytest.mark.db

JOBS = JobSettings(heartbeat_timeout_seconds=2, max_attempts=2)


def service(db_engine, budget=120, grace=60):
    return EngineService(db_engine, job_settings=JOBS, channels=(CHANNEL_INTERACTIVE,),
                         engine_settings=EngineSettings(time_budget_interactive=budget, kill_grace=grace,
                                                        heartbeat_seconds=0.5))


def submit(session, env):
    return submit_plan_run(session, data_version_id=env["data_version_id"],
                           parameter_set_id=env["parameter_set_id"], requested_by=env["user_id"])


def run_until_done(svc, session, job_id, timeout=60, each=None):
    svc.start()
    end = time.monotonic() + timeout
    try:
        while time.monotonic() < end:
            svc.poll_once()
            if each:
                each()
            session.expire_all()
            job = queue.get_job(session, job_id, JOBS)
            if job["Status"] in (STATUS_DONE, STATUS_FAILED) and not svc.running:
                return job
            time.sleep(0.2)
        pytest.fail(f"İş {timeout} sn içinde bitmedi: {job}")
    finally:
        svc.shutdown()


def plan_run(session, plan_run_id):
    return session.execute(text("SELECT Status FROM planning.PlanRun WHERE Id = :id"), {"id": plan_run_id}).scalar()


def outputs(session, plan_run_id):
    return session.execute(text("SELECT COUNT(*) FROM planning.PlannedOrder WHERE PlanRunId = :id"),
                           {"id": plan_run_id}).scalar()


def test_job_runs_in_own_process(db_engine, db_session, plan_env):
    plan_run_id, job_id = submit(db_session, plan_env)
    job = run_until_done(service(db_engine), db_session, job_id)
    assert job["Status"] == STATUS_DONE and job["Attempt"] == 1
    assert plan_run(db_session, plan_run_id) == "Bitti"
    assert outputs(db_session, plan_run_id) == 3


def test_heartbeat_from_service_keeps_long_job_alive(db_engine, db_session, plan_env):
    """Hesap kalp atışı eşiğinden (2 sn) çok uzun sürer (6 × 1 sn); servis kalp atışı yazdığı için takılmış sayılmaz."""
    set_fake(db_engine, plan_env["parameter_set_id"], step=1)
    plan_run_id, job_id = submit(db_session, plan_env)
    requeued = []
    with Session(db_engine) as watcher:  # API'nin izleyicisi gibi
        job = run_until_done(service(db_engine), db_session, job_id,
                             each=lambda: requeued.extend(queue.requeue_stale(watcher, JOBS)))
    assert requeued == []
    assert job["Status"] == STATUS_DONE and job["Attempt"] == 1 and job["DurationSeconds"] >= 6
    assert plan_run(db_session, plan_run_id) == "Bitti"


def test_time_budget_kills_process(db_engine, db_session, plan_env):
    set_fake(db_engine, plan_env["parameter_set_id"], step=5)
    plan_run_id, job_id = submit(db_session, plan_env)
    started = time.monotonic()
    job = run_until_done(service(db_engine, budget=1, grace=1), db_session, job_id)
    assert time.monotonic() - started < 15
    assert job["Status"] == STATUS_FAILED and "Süre bütçesi aşıldı" in job["ErrorText"]
    assert plan_run(db_session, plan_run_id) == "Hata"
    assert outputs(db_session, plan_run_id) == 0


def test_crash_requeues_then_fails(db_engine, db_session, plan_env):
    set_fake(db_engine, plan_env["parameter_set_id"], mode="crash")
    _, job_id = submit(db_session, plan_env)
    job = run_until_done(service(db_engine), db_session, job_id)
    assert job["Status"] == STATUS_FAILED and job["Attempt"] == JOBS.max_attempts
    assert job["ErrorText"] == queue.CRASH_ERROR


def test_engine_error_fails_job_and_plan_run(db_engine, db_session, plan_env):
    set_fake(db_engine, plan_env["parameter_set_id"], mode="error")
    plan_run_id, job_id = submit(db_session, plan_env)
    job = run_until_done(service(db_engine), db_session, job_id)
    assert job["Status"] == STATUS_FAILED and "Model kurulamadı" in job["ErrorText"]
    assert plan_run(db_session, plan_run_id) == "Hata"


def test_service_requeues_stale_job_on_start(db_engine, db_session, plan_env):
    """API kapalıyken de takılan iş bekletilmez: servis açılışta geri alır."""
    job_id = queue.enqueue(db_session, TYPE_WORKSPACE, CHANNEL_INTERACTIVE, plan_env["user_id"])
    queue.claim_next(db_session, CHANNEL_INTERACTIVE, JOBS)
    db_session.execute(text("UPDATE adm.Job SET HeartbeatAt = DATEADD(second, -10, SYSUTCDATETIME()) WHERE Id = :id"),
                       {"id": job_id})
    db_session.commit()
    service(db_engine).start()
    assert queue.get_job(db_session, job_id, JOBS)["Status"] == STATUS_QUEUED

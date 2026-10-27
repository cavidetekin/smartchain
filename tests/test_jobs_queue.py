"""İş kuyruğu (fonksiyon 47, 93; K-67, K-68), yerel SQL Server ile."""
import threading

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.jobs import queue
from app.jobs.constants import (CHANNEL_INTERACTIVE, CHANNEL_NIGHT, STATUS_CANCELLED, STATUS_DONE, STATUS_FAILED,
                                STATUS_QUEUED, STATUS_RUNNING, TYPE_NIGHT_SCENARIO, TYPE_WORKSPACE)

pytestmark = pytest.mark.db


def add(session, user, n=1, channel=CHANNEL_INTERACTIVE, priority=None):
    job_type = TYPE_WORKSPACE if channel == CHANNEL_INTERACTIVE else TYPE_NIGHT_SCENARIO
    return [queue.enqueue(session, job_type, channel, user, {"workspace_id": i}, priority) for i in range(n)]


def test_enqueue_and_position(db_session, job_settings, test_users):
    ids = add(db_session, test_users[0], 3)
    jobs = [queue.get_job(db_session, i, job_settings) for i in ids]
    assert [j["Status"] for j in jobs] == [STATUS_QUEUED] * 3
    assert [j["QueuePosition"] for j in jobs] == [1, 2, 3]
    assert jobs[0]["Payload"] == '{"workspace_id": 0}'
    assert jobs[0]["CreatedAt"] and jobs[0]["UpdatedAt"] and jobs[0]["Attempt"] == 0


def test_enqueue_rejects_unknown_type(db_session):
    with pytest.raises(ValueError):
        queue.enqueue(db_session, "Bilinmeyen", CHANNEL_INTERACTIVE)
    with pytest.raises(ValueError):
        queue.enqueue(db_session, TYPE_WORKSPACE, "Gündüz")


def test_priority_before_order(db_session, job_settings, test_users):
    low = add(db_session, test_users[0])[0]
    high = add(db_session, test_users[0], priority=5)[0]
    assert queue.get_job(db_session, high, job_settings)["QueuePosition"] == 1
    assert queue.claim_next(db_session, CHANNEL_INTERACTIVE, job_settings)["Id"] == high
    assert queue.get_job(db_session, low, job_settings)["QueuePosition"] == 1


def test_limit_keeps_rest_queued(db_session, job_settings, test_users):
    limit = job_settings.limit_interactive
    ids = add(db_session, test_users[0], limit + 1)
    claimed = [queue.claim_next(db_session, CHANNEL_INTERACTIVE, job_settings) for _ in range(limit + 1)]
    assert [c["Id"] for c in claimed[:limit]] == ids[:limit]
    assert all(c["Status"] == STATUS_RUNNING and c["Attempt"] == 1 and c["StartedAt"] for c in claimed[:limit])
    assert claimed[limit] is None
    last = queue.get_job(db_session, ids[limit], job_settings)
    assert last["Status"] == STATUS_QUEUED and last["QueuePosition"] == 1

    # Slot boşalınca sıradaki başlar.
    assert queue.finish(db_session, ids[0], 1)
    assert queue.claim_next(db_session, CHANNEL_INTERACTIVE, job_settings)["Id"] == ids[limit]
    done = queue.get_job(db_session, ids[0], job_settings)
    assert done["Status"] == STATUS_DONE and done["EndedAt"] and done["DurationSeconds"] is not None


def test_concurrent_claims_respect_limit(db_engine, db_session, job_settings, test_users):
    """Aynı anda gelen isteklerde sınır aşılmaz (uygulama kilidi, K-68)."""
    workers = job_settings.limit_interactive + 5
    add(db_session, test_users[0], workers)
    barrier = threading.Barrier(workers)
    results, errors = [], []

    def worker():
        try:
            with Session(db_engine) as s:
                barrier.wait()
                results.append(queue.claim_next(s, CHANNEL_INTERACTIVE, job_settings))
        except Exception as exc:  # pragma: no cover - teşhis için
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert not errors
    claimed = [r["Id"] for r in results if r]
    assert len(claimed) == job_settings.limit_interactive
    assert len(set(claimed)) == len(claimed)
    running = db_session.execute(text("SELECT COUNT(*) FROM adm.Job WHERE Status = :s"),
                                 {"s": STATUS_RUNNING}).scalar_one()
    assert running == job_settings.limit_interactive


def test_night_channel_has_own_limit(db_session, job_settings, test_users):
    add(db_session, test_users[0], job_settings.limit_interactive)
    add(db_session, None, 1, CHANNEL_NIGHT)
    for _ in range(job_settings.limit_interactive):
        assert queue.claim_next(db_session, CHANNEL_INTERACTIVE, job_settings)
    night = queue.claim_next(db_session, CHANNEL_NIGHT, job_settings)
    assert night and night["Channel"] == CHANNEL_NIGHT
    c = queue.counters(db_session, job_settings)
    assert c[CHANNEL_INTERACTIVE]["running"] == job_settings.limit_interactive
    assert c[CHANNEL_NIGHT] == {"running": 1, "queued": 0, "limit": job_settings.limit_night}


def test_cancel(db_session, job_settings, test_users):
    first, second = add(db_session, test_users[0], 2)
    queue.cancel(db_session, first)
    job = queue.get_job(db_session, first, job_settings)
    assert job["Status"] == STATUS_CANCELLED and job["EndedAt"]
    assert queue.get_job(db_session, second, job_settings)["QueuePosition"] == 1

    running = queue.claim_next(db_session, CHANNEL_INTERACTIVE, job_settings)
    with pytest.raises(queue.JobNotCancellable) as exc:
        queue.cancel(db_session, running["Id"])
    assert exc.value.status == STATUS_RUNNING
    with pytest.raises(queue.JobNotFound):
        queue.cancel(db_session, 999_999_999)


def test_heartbeat_and_stale_job(db_session, job_settings, test_users):
    """Kalp atışı gelmeyen iş yeniden sıraya döner; deneme hakkı bitince Hata (K-67)."""
    job_id = add(db_session, test_users[0])[0]
    job = queue.claim_next(db_session, CHANNEL_INTERACTIVE, job_settings)
    assert queue.heartbeat(db_session, job_id, 1, "Model kuruluyor")
    assert queue.get_job(db_session, job_id, job_settings)["Progress"] == "Model kuruluyor"

    def go_silent():
        db_session.execute(text("UPDATE adm.Job SET HeartbeatAt = DATEADD(second, -1 - :t, SYSUTCDATETIME()) "
                                "WHERE Id = :id"), {"t": job_settings.heartbeat_timeout_seconds, "id": job_id})
        db_session.commit()

    for attempt in range(1, job_settings.max_attempts + 1):
        go_silent()
        assert queue.get_job(db_session, job_id, job_settings)["IsStale"] is True
        assert queue.requeue_stale(db_session, job_settings) == [job_id]
        job = queue.get_job(db_session, job_id, job_settings)
        if attempt < job_settings.max_attempts:
            assert job["Status"] == STATUS_QUEUED and job["Progress"] == queue.STALE_PROGRESS
            # Eski deneme artık işi yazamaz.
            assert not queue.heartbeat(db_session, job_id, attempt)
            assert not queue.finish(db_session, job_id, attempt)
            assert queue.claim_next(db_session, CHANNEL_INTERACTIVE, job_settings)["Attempt"] == attempt + 1
    assert job["Status"] == STATUS_FAILED and job["ErrorText"] == queue.STALE_ERROR and job["EndedAt"]


def test_fail(db_session, job_settings, test_users):
    job_id = add(db_session, test_users[0])[0]
    queue.claim_next(db_session, CHANNEL_INTERACTIVE, job_settings)
    assert queue.fail(db_session, job_id, 1, "Model kurulamadı")
    job = queue.get_job(db_session, job_id, job_settings)
    assert job["Status"] == STATUS_FAILED and job["ErrorText"] == "Model kurulamadı"


def test_list_jobs_filters_by_user(db_session, job_settings, test_users):
    a = add(db_session, test_users[0], 2)
    b = add(db_session, test_users[1], 1)
    queue.claim_next(db_session, CHANNEL_INTERACTIVE, job_settings)
    mine = queue.list_jobs(db_session, job_settings, test_users[0])
    assert [j["Id"] for j in mine] == a  # önce çalışan, sonra sıradaki
    assert [j["Status"] for j in mine] == [STATUS_RUNNING, STATUS_QUEUED]
    assert {j["Id"] for j in queue.list_jobs(db_session, job_settings)} == set(a + b)

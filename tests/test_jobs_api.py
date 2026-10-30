"""İş kuyruğu uç noktaları, yerel SQL Server ile."""
import pytest

from app.jobs import queue
from app.jobs.constants import CHANNEL_INTERACTIVE, STATUS_CANCELLED, TYPE_WORKSPACE

pytestmark = pytest.mark.db


def test_list_and_get(db_client, db_session, job_settings, test_users):
    user = test_users[0]
    job_id = queue.enqueue(db_session, TYPE_WORKSPACE, CHANNEL_INTERACTIVE, user)
    queue.enqueue(db_session, TYPE_WORKSPACE, CHANNEL_INTERACTIVE, test_users[1])

    r = db_client.get("/api/jobs")  # oturumdaki kullanıcının işleri (K-97)
    assert r.status_code == 200
    body = r.json()
    assert [j["id"] for j in body["jobs"]] == [job_id]
    assert body["counters"][CHANNEL_INTERACTIVE] == {"running": 0, "queued": 2,
                                                    "limit": job_settings.limit_interactive}
    assert "payload" not in body["jobs"][0]

    r = db_client.get(f"/api/jobs/{job_id}")
    assert r.status_code == 200
    job = r.json()
    assert job["status"] == "Sırada" and job["queue_position"] == 1
    assert job["created_at"].endswith("+00:00")


def test_get_missing(db_client):
    r = db_client.get("/api/jobs/999999999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "job_not_found"


def test_cancel(db_client, db_session, job_settings, test_users):
    job_id = queue.enqueue(db_session, TYPE_WORKSPACE, CHANNEL_INTERACTIVE, test_users[0])
    r = db_client.post(f"/api/jobs/{job_id}/cancel")
    assert r.status_code == 200
    assert r.json()["status"] == STATUS_CANCELLED

    r = db_client.post(f"/api/jobs/{job_id}/cancel")
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "job_not_cancellable" and "İptal" in err["message"]


def test_database_unavailable(app, client):
    from app.api.db import get_session
    app.dependency_overrides[get_session] = lambda: None
    r = client.get("/api/jobs")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "database_unavailable"

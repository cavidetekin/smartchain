"""WebSocket bildirimi (fonksiyon 48, K-69): iş değişince yalnız sahibine mesaj gider."""
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.jobs import queue
from app.jobs.constants import CHANNEL_INTERACTIVE, STATUS_DONE, STATUS_QUEUED, STATUS_RUNNING, TYPE_WORKSPACE

pytestmark = pytest.mark.db

pool = ThreadPoolExecutor(max_workers=2)


def receive(ws, timeout=10):
    """Zaman aşımlı okuma; mesaj gelmezse test asılı kalmaz, başarısız olur."""
    return pool.submit(ws.receive_json).result(timeout=timeout)


def next_job_message(ws, job_id, status):
    while True:
        msg = receive(ws)
        if msg["type"] == "job" and msg["job"]["id"] == job_id and msg["job"]["status"] == status:
            return msg["job"]


def test_ping_pong_without_db():
    with TestClient(create_app()) as client, client.websocket_connect("/api/ws?user_id=1") as ws:
        assert receive(ws) == {"type": "hello", "user_id": 1}
        ws.send_text("ping")
        assert receive(ws) == {"type": "pong"}


def test_job_status_pushed_to_owner_only(db_session, job_settings, test_users):
    owner, other = test_users
    with TestClient(create_app()) as client, \
            client.websocket_connect(f"/api/ws?user_id={owner}") as ws_owner, \
            client.websocket_connect(f"/api/ws?user_id={other}") as ws_other:
        assert receive(ws_owner)["type"] == "hello"
        assert receive(ws_other)["type"] == "hello"

        job_id = queue.enqueue(db_session, TYPE_WORKSPACE, CHANNEL_INTERACTIVE, owner)
        assert next_job_message(ws_owner, job_id, STATUS_QUEUED)["queue_position"] == 1

        queue.claim_next(db_session, CHANNEL_INTERACTIVE, job_settings)
        next_job_message(ws_owner, job_id, STATUS_RUNNING)
        queue.heartbeat(db_session, job_id, 1, "Çözülüyor")
        queue.finish(db_session, job_id, 1)
        assert next_job_message(ws_owner, job_id, STATUS_DONE)["progress"] == "Çözülüyor"

        # Diğer kullanıcıya iş mesajı gitmedi: sıradaki mesajı pong.
        ws_other.send_text("ping")
        assert receive(ws_other) == {"type": "pong"}

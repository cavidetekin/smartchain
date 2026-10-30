"""WebSocket bildirimi (fonksiyon 48, K-69): iş değişince yalnız sahibine mesaj gider. Bağlantı oturumla (K-97)."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from starlette.websockets import WebSocketDisconnect

from app.api.deps import COOKIE
from app.api.main import create_app
from app.api.notify import SESSION_CLOSED, JobWatcher
from app.api.security import token_hash
from app.jobs import queue
from app.jobs.constants import CHANNEL_INTERACTIVE, STATUS_DONE, STATUS_QUEUED, STATUS_RUNNING, TYPE_WORKSPACE

from auth_helpers import auth

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


def test_connection_requires_session():
    """Oturumsuz (ya da bozuk çerezli) el sıkışma kabul edilmez (K-97)."""
    with TestClient(create_app()) as client:
        for headers in ({}, {"Cookie": f"{COOKIE}=bozuk"}):
            with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect("/api/ws", headers=headers):
                pass
            assert exc.value.code == SESSION_CLOSED


def test_foreign_origin_rejected(test_users):
    with TestClient(create_app()) as client, pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws", headers={**auth(test_users[0]), "Origin": "http://evil.example"}):
            pass


def test_ping_pong_with_session(test_users):
    user = test_users[0]
    with TestClient(create_app()) as client, client.websocket_connect("/api/ws", headers=auth(user)) as ws:
        assert receive(ws) == {"type": "hello", "user_id": user}
        ws.send_text("ping")
        assert receive(ws) == {"type": "pong"}


def test_logout_closes_socket(test_users):
    user = test_users[0]
    headers = auth(user, fresh=True)  # bu testin kendi oturumu
    with TestClient(create_app()) as client, client.websocket_connect("/api/ws", headers=headers) as ws:
        assert receive(ws)["type"] == "hello"
        assert client.post("/api/auth/logout", headers=headers).status_code == 204
        with pytest.raises(WebSocketDisconnect) as exc:
            receive(ws)
        assert exc.value.code == SESSION_CLOSED


def test_idle_session_closed_by_watcher(test_users, db_engine, monkeypatch):
    """İzleyici hareketsizlik sınırını geçen oturumu kapatır, soketi 4401 ile kapatır, iz yazar."""
    monkeypatch.setattr(JobWatcher, "SESSION_CHECK_EVERY", timedelta(0))
    user = test_users[1]
    headers = auth(user, fresh=True)
    with TestClient(create_app()) as client, client.websocket_connect("/api/ws", headers=headers) as ws:
        assert receive(ws)["type"] == "hello"
        with db_engine.begin() as c:
            c.execute(text("UPDATE adm.UserSession SET LastActivityAt = DATEADD(minute, -31, SYSUTCDATETIME()) "
                           "WHERE TokenHash = :h"), {"h": token_hash(headers["Cookie"].split("=", 1)[1])})
        with pytest.raises(WebSocketDisconnect) as exc:
            receive(ws)
        assert exc.value.code == SESSION_CLOSED
    with db_engine.connect() as c:
        reasons = c.execute(text("SELECT EndReason FROM adm.UserSession WHERE UserId = :u"), {"u": user}).scalars().all()
        logged = c.execute(text("SELECT COUNT(*) FROM adm.AuditLog WHERE UserId = :u AND Action = N'Çıkış' "
                                "AND NewValue LIKE N'%Zaman aşımı%'"), {"u": user}).scalar()
    assert "Zaman aşımı" in reasons and logged >= 1


def test_job_status_pushed_to_owner_only(db_session, job_settings, test_users):
    owner, other = test_users
    with TestClient(create_app()) as client, \
            client.websocket_connect("/api/ws", headers=auth(owner)) as ws_owner, \
            client.websocket_connect("/api/ws", headers=auth(other)) as ws_other:
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

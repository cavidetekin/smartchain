"""Dışa aktarımda bağlantı havuzu (K-91, docs/08 "Dışa aktarım"): aktarım ve indirme bağlantıyı tutmaz.

- Arka arkaya 30 aktarımdan (anlık, gruplu, arka plan, indirme) sonra havuzdan alınmış bağlantı sayısı başlangıçtaki gibi.
- Dosya istemciye akarken oturum kapanmıştır (bağlantı havuzda): yavaş ya da kopan istemci bağlantıyı tutamaz.
- İstemci yanıtın ortasında koparsa (gönderme hatası) bağlantı yine havuza döner.
"""
import asyncio
import json
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.api.db import get_engine
from app.api.main import create_app
from app.engine.export_job import run_export_job
from app.jobs import queue
from app.jobs.constants import CHANNEL_EXPORT
from app.jobs.settings import JobSettings

from test_export_api import FIELDS, export, setting, user  # noqa: F401  (fikstür ve yardımcılar)
from test_lists_api import api  # noqa: F401

pytestmark = pytest.mark.db


def checked_out() -> int:
    return get_engine().pool.checkedout()


class ClientGone(Exception):
    """Sunucu (uvicorn) istemci koptuğunda send'de buna benzer bir hata alır."""


def call(app, method: str, path: str, query: dict, body: dict | None = None, drop_after_chunks: int | None = None) -> dict:
    """Uygulamayı ASGI düzeyinde çağırır. Her gövde parçası gönderilirken havuzdaki alınmış bağlantı sayısını kaydeder;
    drop_after_chunks verilirse o kadar parçadan sonra istemci kopar (send hata fırlatır, ardından http.disconnect)."""
    raw = json.dumps(body).encode() if body is not None else b""
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method, "scheme": "http",
             "path": path, "raw_path": path.encode(), "query_string": urlencode(query).encode(), "root_path": "",
             "headers": [(b"host", b"test"), (b"content-type", b"application/json"),
                         (b"content-length", str(len(raw)).encode())],
             "client": ("127.0.0.1", 1), "server": ("test", 80)}
    sent = {"status": None, "chunks": 0, "during_body": [], "size": 0}
    received = False

    async def receive():
        nonlocal received
        if not received:
            received = True
            return {"type": "http.request", "body": raw, "more_body": False}
        await asyncio.sleep(3600) if drop_after_chunks is None else None
        return {"type": "http.disconnect"}

    async def send(message):
        if message["type"] == "http.response.start":
            sent["status"] = message["status"]
        elif message["type"] == "http.response.body":
            sent["during_body"].append(checked_out())
            if drop_after_chunks is not None and sent["chunks"] >= drop_after_chunks:
                raise ClientGone()
            sent["chunks"] += 1
            sent["size"] += len(message.get("body", b""))

    async def run():
        try:
            await app(scope, receive, send)
        except ClientGone:
            pass

    asyncio.run(run())
    return sent


@pytest.fixture
def app():
    return create_app()


def background_file(api, user, db_engine, db_session) -> int:  # noqa: F811
    """Arka plan aktarımı: iş kuyruğa girer, aynı süreçte üretilir; iş numarası döner."""
    setting(db_engine, "ExportSyncMaxRows", 10)
    r = export(api, user)
    assert r.status_code == 202, r.status_code
    setting(db_engine, "ExportSyncMaxRows", 10000)
    job = queue.claim_next(db_session, CHANNEL_EXPORT, JobSettings())
    run_export_job(job["Id"], job["Attempt"])
    db_session.commit()  # testin oturumu bağlantıyı bırakır
    return r.json()["job_id"]


def test_thirty_exports_leave_pool_as_found(api, user, db_engine, db_session):  # noqa: F811
    job_id = background_file(api, user, db_engine, db_session)
    db_session.close()
    start = checked_out()
    grouped = {"group_by": ["MaterialLevel", "MaterialGroup"], "aggregates": {"SafetyStock": {"fn": "sum"}}}
    for i in range(30):
        kind = i % 5
        if kind == 3:  # arka plan eşiği aşıldı: kuyruğa girer (202)
            setting(db_engine, "ExportSyncMaxRows", 10)
            assert export(api, user).status_code == 202
            setting(db_engine, "ExportSyncMaxRows", 10000)
        elif kind == 4:
            assert api.get(f"/api/exports/{job_id}/file?user_id={user}").status_code == 200
        else:
            assert export(api, user, **(grouped if kind == 1 else {})).status_code == 200
        assert checked_out() == start, f"{i + 1}. aktarımdan sonra havuzda {checked_out() - start} bağlantı kaldı"
    assert export(api, 987654).status_code == 404  # hata yolu da bırakır
    assert export(api, user, fields=["Secret"]).status_code == 422
    assert checked_out() == start


def test_download_releases_connection_before_streaming(app, api, user, db_engine, db_session):  # noqa: F811
    job_id = background_file(api, user, db_engine, db_session)
    db_session.close()
    start = checked_out()
    sent = call(app, "GET", f"/api/exports/{job_id}/file", {"user_id": user})
    assert sent["status"] == 200 and sent["size"] > 0
    assert sent["during_body"] and all(n == start for n in sent["during_body"]), sent["during_body"]
    assert checked_out() == start


def test_client_disconnect_returns_connection(app, api, user, db_engine, db_session):  # noqa: F811
    job_id = background_file(api, user, db_engine, db_session)
    db_session.close()
    start = checked_out()
    for _ in range(5):
        call(app, "GET", f"/api/exports/{job_id}/file", {"user_id": user}, drop_after_chunks=0)
        call(app, "POST", "/api/materials/export", {"user_id": user}, {"fields": FIELDS}, drop_after_chunks=0)
    assert checked_out() == start
    # kopmalardan sonra API çalışmaya devam eder
    assert TestClient(app).get("/api/materials/columns").status_code == 200
    assert checked_out() == start

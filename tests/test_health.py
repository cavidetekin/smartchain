from app.api.repositories import health as repo
from app.api.services.health import expected_schema_version


def test_expected_schema_version_is_head():
    assert expected_schema_version() == "0010"


def test_health_ok(client, monkeypatch):
    monkeypatch.setattr(repo, "read_schema_version", lambda s: "0010")
    monkeypatch.setattr(repo, "read_server_version", lambda s: "17.0.1000.7")
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"]["connected"] is True
    assert body["database"]["schema_version"] == "0010"
    assert r.headers["X-Trace-Id"]


def test_health_schema_mismatch(client, monkeypatch):
    monkeypatch.setattr(repo, "read_schema_version", lambda s: None)
    monkeypatch.setattr(repo, "read_server_version", lambda s: "17.0")
    r = client.get("/api/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert "Güncelleme gerekiyor" in body["database"]["message"]


def test_health_db_down(client, monkeypatch):
    def boom(s):
        raise RuntimeError("bağlantı yok")

    monkeypatch.setattr(repo, "read_schema_version", boom)
    r = client.get("/api/health")
    assert r.status_code == 503
    db = r.json()["database"]
    assert db["connected"] is False
    assert "bağlanılamadı" in db["message"]


def test_health_driver_missing(app, client):
    from app.api.db import get_session
    app.dependency_overrides[get_session] = lambda: None
    r = client.get("/api/health")
    assert r.status_code == 503
    assert "ODBC Driver 18" in r.json()["database"]["message"]

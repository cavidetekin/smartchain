"""GET /api/data-versions/current (bağlam çubuğu, docs/12)."""
from datetime import datetime

import pytest
from sqlalchemy import text

from app.api.repositories import data_versions as repo


def test_current_from_repository(client, monkeypatch):
    monkeypatch.setattr(repo, "read_current", lambda s: {
        "Id": 35, "CreatedAt": datetime(2026, 10, 27, 9, 20), "LoadType": "Tam", "IsSynthetic": True,
        "LocationCode": "ORM-01"})
    r = client.get("/api/data-versions/current")
    assert r.status_code == 200
    assert r.json() == {"id": 35, "location_code": "ORM-01", "created_at": "2026-10-27T09:20:00+00:00",
                        "load_type": "Tam", "is_synthetic": True}


def test_no_data_version(client, monkeypatch):
    monkeypatch.setattr(repo, "read_current", lambda s: None)
    r = client.get("/api/data-versions/current")
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_data_version"


@pytest.mark.db
def test_current_is_latest_in_database(db_client, db_engine):
    with db_engine.connect() as c:
        latest = c.execute(text("SELECT MAX(Id) FROM adm.DataVersion")).scalar()
    r = db_client.get("/api/data-versions/current")
    if latest is None:
        assert r.status_code == 404
    else:
        assert r.status_code == 200 and r.json()["id"] == latest

"""Denetim izi yazma kuralı (K-108): aynı işlemde; yazılamazsa işlem geri alınır, sistem olayı düşer."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.api.main import create_app
from app.api.permissions import ADMIN, KEY_USER, SYSTEM_OWNER
from app.api.repositories import audit
from app.jobs import queue
from app.jobs.constants import CHANNEL_INTERACTIVE, TYPE_WORKSPACE

from auth_helpers import auth, delete_users, ensure_user

pytestmark = pytest.mark.db

PREFIX = "pytest.izkurali."
TRIGGER = "adm.TR_AuditLog_Test"


def clean(engine):
    with engine.begin() as c:
        c.execute(text(f"DROP TRIGGER IF EXISTS {TRIGGER}"))
        c.execute(text("DELETE FROM adm.SystemEvent"))
        c.execute(text("DELETE FROM adm.Job"))
        c.execute(text("DELETE FROM adm.SystemSetting WHERE SettingKey = N'DiskWarnPercent'"))
        delete_users(c, [r[0] for r in c.execute(text("SELECT Id FROM adm.AppUser WHERE UserName LIKE :p"), {"p": PREFIX + "%"})])


@pytest.fixture
def people(db_engine):
    clean(db_engine)
    with db_engine.begin() as c:
        out = {r: ensure_user(c, PREFIX + r.replace(" ", "-").lower(), r, f"Ad {r}") for r in (SYSTEM_OWNER, ADMIN, KEY_USER)}
    yield out
    clean(db_engine)


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def broken_audit(engine):
    """Gerçek yazma hatası: adm.AuditLog'a her ekleme reddedilir."""
    with engine.begin() as c:
        c.execute(text(f"CREATE TRIGGER {TRIGGER} ON adm.AuditLog INSTEAD OF INSERT AS THROW 50001, 'iz yazılamıyor', 1;"))


def events(engine):
    with engine.connect() as c:
        return [tuple(r) for r in c.execute(text("SELECT Component, Message, Resolution, IsResolved FROM adm.SystemEvent ORDER BY Id"))]


def assert_failed(r):
    assert r.status_code == 503, r.text
    assert r.json()["error"]["code"] == "audit_failed"
    assert r.json()["error"]["message"] == "İşlem yapılamadı: denetim kaydı yazılamadı."


def test_setting_rolled_back_and_event_written(db_engine, client, people):
    broken_audit(db_engine)
    assert_failed(client.put("/api/settings/health", headers=auth(people[SYSTEM_OWNER]), json={"DiskWarnPercent": 40}))
    with db_engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM adm.SystemSetting WHERE SettingKey = N'DiskWarnPercent'")).scalar_one() == 0
    assert events(db_engine) == [("Denetim izi", "Denetim kaydı yazılamadı · Ayar değişikliği", "İşlem geri alındı", False)]


def test_user_change_rolled_back(db_engine, client, people):
    broken_audit(db_engine)
    key = people[KEY_USER]
    assert_failed(client.put(f"/api/users/{key}/name", headers=auth(people[ADMIN]), json={"full_name": "Yeni Ad"}))
    with db_engine.connect() as c:
        assert c.execute(text("SELECT FullName FROM adm.AppUser WHERE Id = :i"), {"i": key}).scalar_one() == f"Ad {KEY_USER}"


def test_job_cancel_rolled_back(db_engine, db_session, client, people, job_settings):
    job = queue.enqueue(db_session, TYPE_WORKSPACE, CHANNEL_INTERACTIVE, people[KEY_USER])
    broken_audit(db_engine)
    assert_failed(client.post(f"/api/jobs/{job}/cancel", headers=auth(people[ADMIN]), json={"reason": "x"}))
    db_session.rollback()
    assert queue.get_job(db_session, job, job_settings)["Status"] == "Sırada"


def test_excel_not_given_when_trace_fails(db_engine, client, people):
    broken_audit(db_engine)
    r = client.post("/api/users/export", headers=auth(people[ADMIN]), json={"fields": ["UserName"]})
    assert_failed(r)
    assert "content-disposition" not in r.headers


def test_denial_is_still_denied_when_trace_fails(db_engine, client, people):
    broken_audit(db_engine)
    r = client.get("/api/system-health", headers=auth(people[KEY_USER]))
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
    assert events(db_engine)[0][1] == "Denetim kaydı yazılamadı · Yetkisiz istek"


def test_same_failure_not_repeated_within_a_minute(db_engine, client, people):
    broken_audit(db_engine)
    for value in (40, 41):
        assert_failed(client.put("/api/settings/health", headers=auth(people[SYSTEM_OWNER]), json={"DiskWarnPercent": value}))
    assert len(events(db_engine)) == 1


def test_answer_survives_when_event_cannot_be_written(db_engine, client, people, monkeypatch):
    def boom(*a, **k):
        raise DBAPIError("INSERT", {}, Exception("yazılamadı"))
    monkeypatch.setattr(audit, "_insert", boom)
    monkeypatch.setattr(audit.events, "record", boom)
    assert_failed(client.put("/api/settings/health", headers=auth(people[SYSTEM_OWNER]), json={"DiskWarnPercent": 40}))

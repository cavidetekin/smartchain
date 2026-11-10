"""Sistem sağlığı (ekran 24; K-106), iş kuyruğu yönetimi (fonksiyon 93; K-107) ve anlık yenileme mesajı."""
import asyncio
import io
import json

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.api.notify import ConnectionManager, JobWatcher
from app.api.permissions import ADMIN, END_USER, KEY_USER, SYSTEM_OWNER
from app.api.repositories import system_health as repo
from app.api.services.system_health import NOT_RESPONDING, RUNNING, SLOW, STOPPED, engine_state
from app.jobs import events, queue
from app.jobs.constants import (CHANNEL_INTERACTIVE, CHANNEL_NIGHT, STATUS_CANCELLED, TYPE_TRANSFER, TYPE_NIGHT_SCENARIO, TYPE_WORKSPACE)
from app.jobs.settings import JobSettings

from auth_helpers import auth, delete_users, ensure_user

pytestmark = pytest.mark.db

PREFIX = "pytest.saglik."
SETTINGS = "/api/settings/health"
ROLES = (SYSTEM_OWNER, ADMIN, KEY_USER, END_USER)
KEYS = ("DiskWarnPercent", "QueueWaitWarnMinutes", "SystemEventRetentionDays", "ImportSyncMaxMb", "ImportMaxMb", "ImportMaxRows")


def clean(engine):
    with engine.begin() as c:
        c.execute(text("DELETE FROM adm.Job"))
        c.execute(text("DELETE FROM adm.SystemEvent"))
        c.execute(text("DELETE FROM adm.ServiceStatus"))
        c.execute(text("DELETE FROM adm.SystemSetting WHERE SettingKey IN :keys").bindparams(bindparam("keys", expanding=True)),
                  {"keys": list(KEYS)})
        c.execute(text("DELETE FROM adm.AuditLog WHERE ObjectType = N'Job' OR ObjectKey IN :keys").bindparams(bindparam("keys", expanding=True)), {"keys": list(KEYS)})
        delete_users(c, [r[0] for r in c.execute(text("SELECT Id FROM adm.AppUser WHERE UserName LIKE :p"), {"p": PREFIX + "%"})])


@pytest.fixture
def people(db_engine):
    clean(db_engine)
    with db_engine.begin() as c:
        out = {r: ensure_user(c, PREFIX + r.replace(" ", "-").lower(), r, f"Ad {r}") for r in ROLES}
    yield out
    clean(db_engine)


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def session(db_engine):
    with Session(db_engine) as s:
        yield s


def enqueue(session, user, job_type=TYPE_WORKSPACE, channel=CHANNEL_INTERACTIVE):
    return queue.enqueue(session, job_type, channel, user)


def execute(engine, sql, **params):
    with engine.begin() as c:
        c.execute(text(sql), params)


def beat(engine, seconds_ago=0, stopped=False):
    execute(engine, "DELETE FROM adm.ServiceStatus")
    execute(engine, "INSERT INTO adm.ServiceStatus (ServiceName, HeartbeatAt, StartedAt, StoppedAt, AppVersion) VALUES "
                    "(N'Motor', DATEADD(second, -1 * :s, SYSUTCDATETIME()), SYSUTCDATETIME(), "
                    f"{'SYSUTCDATETIME()' if stopped else 'NULL'}, N'0.19.0')", s=seconds_ago)


def summary(client, people, role=ADMIN):
    r = client.get("/api/system-health", headers=auth(people[role]))
    assert r.status_code == 200, r.text
    return r.json()


# --- servis durumu ---

@pytest.mark.parametrize("row, expected", [
    (None, STOPPED),
    ({"StoppedAt": "dolu", "AgeSeconds": 1}, STOPPED),
    ({"StoppedAt": None, "AgeSeconds": 30}, RUNNING),
    ({"StoppedAt": None, "AgeSeconds": 31}, SLOW),
    ({"StoppedAt": None, "AgeSeconds": 120}, SLOW),
    ({"StoppedAt": None, "AgeSeconds": 121}, NOT_RESPONDING),
])
def test_engine_state(row, expected):
    assert engine_state(row, 15, 120) == expected


def test_summary_services_and_cards(db_engine, client, people, session):
    beat(db_engine)
    body = summary(client, people)
    services = {s["key"]: s for s in body["services"]}
    assert list(services) == ["app", "engine", "database", "notifications"]
    assert services["engine"]["status"] == "Çalışıyor" and services["engine"]["version"] == "0.19.0"
    assert services["database"]["ms"] >= 0 and services["database"]["pool_size"] > 0
    assert services["notifications"]["connections"] == 0
    cards = body["cards"]
    assert cards["queue"] == {"queued": 0, "oldest_wait_minutes": None, "threshold": 10, "warn": False}
    assert cards["interactive"]["limit"] == JobSettings().limit_interactive
    assert cards["errors"] == {"last_7_days": 0, "resolved": 0}
    assert 0 <= cards["disk"]["percent"] <= 100 and cards["disk"]["threshold"] == 85 and cards["disk"]["database_bytes"] > 0


def test_engine_down_warns_queue(db_engine, client, people):
    assert {s["key"]: s["status"] for s in summary(client, people)["services"]}["engine"] == "Kapalı"  # hiç çalışmadı
    assert summary(client, people)["cards"]["queue"]["warn"] is True
    beat(db_engine, stopped=True)
    assert summary(client, people)["cards"]["queue"]["warn"] is True
    beat(db_engine, seconds_ago=300)
    body = summary(client, people)
    assert {s["key"]: s["status"] for s in body["services"]}["engine"] == "Yanıt vermiyor" and body["cards"]["queue"]["warn"] is True
    beat(db_engine, seconds_ago=60)
    body = summary(client, people)
    assert {s["key"]: s["status"] for s in body["services"]}["engine"] == "Yavaş" and body["cards"]["queue"]["warn"] is False


def test_thresholds_take_effect(db_engine, client, people, session):
    beat(db_engine)
    owner = auth(people[SYSTEM_OWNER])
    job = enqueue(session, people[ADMIN])
    execute(db_engine, "UPDATE adm.Job SET CreatedAt = DATEADD(minute, -15, SYSUTCDATETIME()) WHERE Id = :i", i=job)
    queue_card = summary(client, people)["cards"]["queue"]
    assert (queue_card["queued"], queue_card["oldest_wait_minutes"], queue_card["warn"]) == (1, 15, True)
    assert client.put(SETTINGS, headers=owner, json={"QueueWaitWarnMinutes": 20}).status_code == 200
    assert summary(client, people)["cards"]["queue"]["warn"] is False

    assert client.put(SETTINGS, headers=owner, json={"DiskWarnPercent": 1}).status_code == 200
    assert summary(client, people)["cards"]["disk"]["warn"] is True


def test_disk_works_without_volume_permission(db_engine, client, people, monkeypatch):
    monkeypatch.setattr(repo, "database_volume", lambda s: None)
    assert summary(client, people)["cards"]["disk"]["free_bytes"] > 0


def test_error_counts(db_engine, client, people, session):
    events.record(session, "Motor", "Çözülen", resolved=True)
    events.record(session, "Motor", "Açık")
    session.execute(text("INSERT INTO adm.SystemEvent (OccurredAt, Component, Message, IsResolved) VALUES "
                         "(DATEADD(day, -8, SYSUTCDATETIME()), N'Motor', N'Eski', 0)"))
    session.commit()
    assert summary(client, people)["cards"]["errors"] == {"last_7_days": 2, "resolved": 1}


# --- yetki ---

@pytest.mark.parametrize("url", ["/api/system-health", "/api/system-events/1", "/api/job-queue/columns", "/api/job-runs/columns",
                                 "/api/system-events/columns"])
@pytest.mark.parametrize("role", [KEY_USER, END_USER])
def test_closed_to_key_and_end_user(client, people, url, role):
    assert client.get(url, headers=auth(people[role])).status_code == 403


@pytest.mark.parametrize("role", [SYSTEM_OWNER, ADMIN])
def test_open_to_admin_and_owner(client, people, role):
    h = auth(people[role])
    assert client.get("/api/system-health", headers=h).status_code == 200
    for name in ("job-queue", "job-runs", "system-events"):
        assert client.get(f"/api/{name}/columns", headers=h).status_code == 200


@pytest.mark.parametrize("role", [ADMIN, KEY_USER, END_USER])
def test_settings_only_system_owner(client, people, role):
    h = auth(people[role])
    assert client.get(SETTINGS, headers=h).status_code == 403
    assert client.put(SETTINGS, headers=h, json={"DiskWarnPercent": 50}).status_code == 403


# --- ayarlar ---

def test_settings_defaults_limits_and_audit(db_engine, client, people):
    owner = people[SYSTEM_OWNER]
    body = client.get(SETTINGS, headers=auth(owner)).json()
    assert body["values"] == body["defaults"] == {"DiskWarnPercent": 85, "QueueWaitWarnMinutes": 10, "SystemEventRetentionDays": 90, "ImportSyncMaxMb": 5, "ImportMaxMb": 100, "ImportMaxRows": 200000,
                                                  "RawDataRetentionDays": None}  # K-156: varsayılanı yok
    assert body["limits"]["ImportMaxRows"] == {"min": 1000, "max": 1000000}
    assert body["limits"]["SystemEventRetentionDays"] == {"min": 7, "max": 3650}
    for bad in ({"DiskWarnPercent": 0}, {"DiskWarnPercent": 100}, {"QueueWaitWarnMinutes": 0}, {"SystemEventRetentionDays": 6}):
        r = client.put(SETTINGS, headers=auth(owner), json=bad)
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation", bad
    assert client.put(SETTINGS, headers=auth(owner), json={"Baska": 1}).status_code == 422

    r = client.put(SETTINGS, headers=auth(owner), json={"DiskWarnPercent": 70, "QueueWaitWarnMinutes": 10})
    assert r.status_code == 200 and r.json()["values"]["DiskWarnPercent"] == 70
    with db_engine.connect() as c:
        rows = c.execute(text("SELECT Action, ObjectKey, OldValue, NewValue FROM adm.AuditLog WHERE ObjectType = N'SystemSetting' "
                              "AND ObjectKey IN (N'DiskWarnPercent', N'QueueWaitWarnMinutes') AND UserId = :u"), {"u": owner}).all()
    assert [(r[0], r[1]) for r in rows] == [("Ayar değişikliği", "DiskWarnPercent")]  # değişmeyen yazılmaz
    assert json.loads(rows[0][2]) == {"Value": 85} and json.loads(rows[0][3]) == {"Value": 70}


def test_import_settings_are_saved(db_engine, client, people):
    """Excel yükleme ayarları (K-129) aynı formdan kaydedilir; sınır dışı 422 (K-157: önceden kaydetme isteği bu alanları kabul etmiyordu)."""
    owner = people[SYSTEM_OWNER]
    r = client.put(SETTINGS, headers=auth(owner), json={"ImportSyncMaxMb": 10, "ImportMaxMb": 50, "ImportMaxRows": 300000})
    assert r.status_code == 200, r.text
    assert {k: r.json()["values"][k] for k in ("ImportSyncMaxMb", "ImportMaxMb", "ImportMaxRows")} == {"ImportSyncMaxMb": 10, "ImportMaxMb": 50, "ImportMaxRows": 300000}
    assert client.put(SETTINGS, headers=auth(owner), json={"ImportMaxRows": 10}).status_code == 422
    with db_engine.connect() as c:
        keys = {r[0] for r in c.execute(text("SELECT ObjectKey FROM adm.AuditLog WHERE ObjectType = N'SystemSetting' AND UserId = :u"), {"u": owner})}
    assert {"ImportSyncMaxMb", "ImportMaxMb", "ImportMaxRows"} <= keys


# --- listeler ---

def query(client, people, name, role=ADMIN, **body):
    r = client.post(f"/api/{name}/query", headers=auth(people[role]), json=body)
    assert r.status_code == 200, r.text
    return r.json()["rows"]


def test_job_queue_list(db_engine, client, people, session):
    key = people[KEY_USER]
    first, second = enqueue(session, key), enqueue(session, key)
    queue.prioritize(session, second)
    old = enqueue(session, key)
    queue.cancel(session, old)
    execute(db_engine, "UPDATE adm.Job SET EndedAt = DATEADD(hour, -30, SYSUTCDATETIME()) WHERE Id = :i", i=old)
    rows = {r["Id"]: r for r in query(client, people, "job-queue", fields=["Id", "RequesterName", "QueuePosition"])}
    assert set(rows) == {first, second}  # 24 saatten eski biten yok
    assert (rows[second]["QueuePosition"], rows[first]["QueuePosition"]) == (1, 2)
    assert rows[first]["RequesterName"] == f"Ad {KEY_USER}"
    # görünmeyen kolonda da satır işlemi alanları döner
    assert rows[first]["Status"] == "Sırada" and rows[first]["JobType"] == TYPE_WORKSPACE and rows[first]["RequestedBy"] == key
    assert rows[first]["IsProtected"] is False and rows[first]["Summary"] is None


def test_job_runs_list(db_engine, client, people, session):
    key = people[KEY_USER]
    enqueue(session, key)  # bitmemiş iş listede yok
    recent, old = enqueue(session, key), enqueue(session, key)
    queue.cancel(session, recent, "Neden", people[ADMIN])
    queue.cancel(session, old)
    execute(db_engine, "UPDATE adm.Job SET EndedAt = DATEADD(day, -8, SYSUTCDATETIME()) WHERE Id = :i", i=old)
    rows = query(client, people, "job-runs", fields=["Id", "Status", "CancelReason"])
    assert [r["Id"] for r in rows] == [recent] and rows[0]["CancelReason"] == "Neden"


def test_events_list_excel_and_detail(db_engine, client, people, session):
    events.record(session, "Motor", "Olay", "Devam etti", trace_id="abc123", detail="Teknik")
    session.commit()
    columns = client.get("/api/system-events/columns", headers=auth(people[ADMIN])).json()["columns"]
    assert [c["field"] for c in columns] == ["OccurredAt", "Component", "Message", "Resolution", "IsResolved", "JobId", "TraceId"]
    assert client.post("/api/system-events/query", headers=auth(people[ADMIN]), json={"fields": ["Detail"]}).status_code == 422
    row = query(client, people, "system-events", fields=["Message"])[0]
    assert row["Message"] == "Olay"

    r = client.post("/api/system-events/export", headers=auth(people[ADMIN]), json={"fields": ["Component", "Message"], "scope": {"columns": "all"}})
    assert r.status_code == 200, r.text
    assert "smartchain_sistem-hatalari_" in r.headers["content-disposition"]
    head = [c.value for c in next(load_workbook(io.BytesIO(r.content)).worksheets[0].iter_rows())]
    assert "Teknik özet" not in head and "Hata" in head and "Sistem aksiyonu" in head

    url = f"/api/system-events/{row['Id']}"
    admin_view = client.get(url, headers=auth(people[ADMIN])).json()
    assert admin_view["message"] == "Olay" and admin_view["trace_id"] == "abc123" and admin_view["detail"] is None
    assert client.get(url, headers=auth(people[SYSTEM_OWNER])).json()["detail"] == "Teknik"
    missing = client.get("/api/system-events/999999999", headers=auth(people[ADMIN]))
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "event_not_found"


# --- iptal ve öne alma ---

def audit_rows(engine, action):
    with engine.connect() as c:
        return c.execute(text("SELECT UserId, ObjectKey, NewValue FROM adm.AuditLog WHERE Action = :a AND ObjectType = N'Job'"), {"a": action}).all()


def test_cancel_other_needs_reason(db_engine, client, people, session):
    admin = people[ADMIN]
    job = enqueue(session, people[KEY_USER])
    for body in ({}, {"reason": "   "}):
        r = client.post(f"/api/jobs/{job}/cancel", headers=auth(admin), json=body)
        assert r.status_code == 422 and r.json()["error"]["code"] == "reason_required"
    assert client.post(f"/api/jobs/{job}/cancel", headers=auth(admin), json={"reason": "x" * 201}).status_code == 422

    r = client.post(f"/api/jobs/{job}/cancel", headers=auth(admin), json={"reason": " Gece akışı "})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == STATUS_CANCELLED and body["cancel_reason"] == "Gece akışı" and body["cancelled_by_name"] == f"Ad {ADMIN}"
    row = audit_rows(db_engine, "İş iptali")[0]
    assert (row[0], row[1]) == (admin, str(job)) and json.loads(row[2])["cancel_reason"] == "Gece akışı"


def test_summary_in_lists_and_job(db_engine, client, people, session):
    key = people[KEY_USER]
    job = queue.enqueue(session, TYPE_WORKSPACE, CHANNEL_INTERACTIVE, key, summary="Plan A · yeniden hesap")
    assert CHANNEL_INTERACTIVE == "Hesaplama"
    columns = client.get("/api/job-queue/columns", headers=auth(people[ADMIN])).json()["columns"]
    assert [c["field"] for c in columns][:3] == ["Id", "JobType", "Summary"] and columns[2]["label"] == "İş"
    assert query(client, people, "job-queue", fields=["Status"])[0]["Summary"] == "Plan A · yeniden hesap"
    public = client.get(f"/api/jobs/{job}", headers=auth(key)).json()
    assert public["summary"] == "Plan A · yeniden hesap" and public["channel"] == "Hesaplama"
    labels = {c["field"]: c["label"] for c in client.get("/api/job-runs/columns", headers=auth(people[ADMIN])).json()["columns"]}
    assert labels["Summary"] == "İş" and labels["Status"] == "Sonuç"
    labels = {c["field"]: c["label"] for c in client.get("/api/system-events/columns", headers=auth(people[ADMIN])).json()["columns"]}
    assert labels["Resolution"] == "Sistem aksiyonu"


def test_cancel_own_without_reason(db_engine, client, people, session):
    key = people[KEY_USER]
    job = enqueue(session, key)
    r = client.post(f"/api/jobs/{job}/cancel", headers=auth(key))
    assert r.status_code == 200 and r.json()["cancel_reason"] is None
    assert audit_rows(db_engine, "İş iptali")[0][0] == key


def test_key_user_cannot_cancel_other(client, people, session):
    job = enqueue(session, people[ADMIN])
    assert client.post(f"/api/jobs/{job}/cancel", headers=auth(people[KEY_USER]), json={"reason": "x"}).status_code == 403


def test_load_job_cannot_be_cancelled(db_engine, client, people, session):
    admin = people[ADMIN]
    job = enqueue(session, admin, TYPE_TRANSFER)
    r = client.post(f"/api/jobs/{job}/cancel", headers=auth(admin))
    assert r.status_code == 409 and r.json()["error"]["message"] == "Aktarım işi iptal edilemez."
    assert audit_rows(db_engine, "İş iptali") == []


def test_prioritize(db_engine, client, people, session):
    admin, key = people[ADMIN], people[KEY_USER]
    first, second, third = enqueue(session, key), enqueue(session, key), enqueue(session, key)
    r = client.post(f"/api/jobs/{third}/prioritize", headers=auth(admin))
    assert r.status_code == 200 and r.json()["queue_position"] == 1
    r = client.post(f"/api/jobs/{second}/prioritize", headers=auth(admin))
    assert r.json()["queue_position"] == 1
    settings = JobSettings()
    session.rollback()
    assert queue.get_job(session, first, settings)["QueuePosition"] == 3
    assert [r[1] for r in audit_rows(db_engine, "İş öne alma")] == [str(third), str(second)]
    # çalışmaya alma da bu sırayla
    assert queue.claim_next(session, CHANNEL_INTERACTIVE, settings)["Id"] == second

    running = client.post(f"/api/jobs/{second}/prioritize", headers=auth(admin))
    assert running.status_code == 409 and running.json()["error"]["code"] == "job_not_prioritizable"


def test_prioritize_rules(client, people, session):
    admin = people[ADMIN]
    night = enqueue(session, admin, TYPE_NIGHT_SCENARIO, CHANNEL_NIGHT)
    r = client.post(f"/api/jobs/{night}/prioritize", headers=auth(admin))
    assert r.status_code == 409 and r.json()["error"]["message"] == "Gece işleri öne alınamaz."
    job = enqueue(session, people[KEY_USER])
    assert client.post(f"/api/jobs/{job}/prioritize", headers=auth(people[KEY_USER])).status_code == 403
    assert client.post("/api/jobs/999999999/prioritize", headers=auth(admin)).status_code == 404


def test_system_owner_job_protected_from_admin(db_engine, client, people, session):
    owner, admin = people[SYSTEM_OWNER], people[ADMIN]
    job = enqueue(session, owner)
    public = client.get(f"/api/jobs/{job}", headers=auth(admin)).json()
    assert public["requested_by_name"] == "Smartchain" and public["is_protected"] is True
    everyone = client.get("/api/jobs?scope=all", headers=auth(admin)).json()["jobs"]
    assert [j["requested_by_name"] for j in everyone] == ["Smartchain"]
    row = query(client, people, "job-queue", fields=["RequesterName"])[0]
    assert row["RequesterName"] == "Smartchain" and row["IsProtected"] is True

    for url, body in ((f"/api/jobs/{job}/cancel", {"reason": "x"}), (f"/api/jobs/{job}/prioritize", {})):
        r = client.post(url, headers=auth(admin), json=body)
        assert r.status_code == 403 and "System owner" in r.json()["error"]["message"], url
    with db_engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM adm.AuditLog WHERE Action = N'Yetkisiz istek' AND UserId = :u"), {"u": admin}).scalar_one() == 2
    assert client.post(f"/api/jobs/{job}/prioritize", headers=auth(owner)).status_code == 200
    assert client.post(f"/api/jobs/{job}/cancel", headers=auth(owner)).status_code == 200


# --- anlık yenileme ---

class FakeSocket:
    def __init__(self):
        self.sent = []

    async def send_json(self, message):
        self.sent.append(message)


def test_health_message_only_to_watchers():
    manager = ConnectionManager()
    watcher, other = FakeSocket(), FakeSocket()
    manager.add(1, watcher, watching=True)
    manager.add(2, other)
    assert manager.connection_count() == 2
    asyncio.run(manager.send_health())
    assert watcher.sent == [{"type": "health"}] and other.sent == []
    manager.remove(1, watcher)
    asyncio.run(manager.send_health())
    assert len(watcher.sent) == 1 and manager.connection_count() == 1


def test_watcher_marks_health_changes(db_engine, people, session):
    watcher = JobWatcher(ConnectionManager(), 1)
    watcher.poll()  # başlangıç
    watcher._health_due = False
    watcher.poll()
    assert watcher._health_due is False  # değişiklik yok

    enqueue(session, people[KEY_USER])
    watcher.poll()
    assert watcher._health_due is True
    watcher._health_due = False

    events.record(session, "Motor", "Yeni olay")
    session.commit()
    watcher.poll()
    assert watcher._health_due is True
    watcher._health_due = False

    beat(db_engine, stopped=True)
    watcher.poll()
    assert watcher._health_due is True

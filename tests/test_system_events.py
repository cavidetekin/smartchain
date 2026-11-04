"""Sistem olayları (K-106): yazan yerler, aynı işlem, tekrar kuralı, temizlik, beklenmeyen API hatası."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.deps import COOKIE
from app.api.main import create_app
from app.jobs import events, queue
from app.jobs.constants import CHANNEL_EXPORT, CHANNEL_INTERACTIVE, STATUS_FAILED, STATUS_QUEUED, TYPE_EXPORT, TYPE_WORKSPACE

from auth_helpers import token

pytestmark = pytest.mark.db


def rows(session):
    session.expire_all()
    session.rollback()
    return [dict(r) for r in session.execute(text("SELECT * FROM adm.SystemEvent ORDER BY Id")).mappings()]


def running(session, settings, user, job_type=TYPE_WORKSPACE, channel=CHANNEL_INTERACTIVE):
    job_id = queue.enqueue(session, job_type, channel, user)
    job = queue.claim_next(session, channel, settings)
    assert job["Id"] == job_id
    return job


def age(session, job_id):
    session.execute(text("UPDATE adm.Job SET HeartbeatAt = DATEADD(minute, -10, SYSUTCDATETIME()) WHERE Id = :i"), {"i": job_id})
    session.commit()


def test_record_fields_and_limits(db_session):
    assert events.record(db_session, events.COMPONENT_APP, "x" * 600, "y" * 300, resolved=True, trace_id="abc", detail="z" * 2000)
    db_session.commit()
    row = rows(db_session)[0]
    assert row["Component"] == "Uygulama" and len(row["Message"]) == 500 and len(row["Resolution"]) == 200
    assert row["IsResolved"] is True and row["TraceId"] == "abc" and len(row["Detail"]) == 1000


def test_same_event_not_repeated_unless_job(db_session):
    assert events.record(db_session, events.COMPONENT_ENGINE, "Aynı")
    assert not events.record(db_session, events.COMPONENT_ENGINE, "Aynı")
    assert events.record(db_session, events.COMPONENT_APP, "Aynı")  # başka bileşen
    assert events.record(db_session, events.COMPONENT_ENGINE, "İş", job_id=1)
    assert events.record(db_session, events.COMPONENT_ENGINE, "İş", job_id=1)  # işe bağlı olay düşmez
    db_session.commit()
    assert len(rows(db_session)) == 4


def test_failed_write_does_not_break_the_caller(db_session, job_settings, test_users, monkeypatch):
    def boom(*a):
        raise RuntimeError("yazılamadı")
    monkeypatch.setattr(events, "_repeated", boom)
    assert events.record(db_session, events.COMPONENT_ENGINE, "Olay") is False
    job = running(db_session, job_settings, test_users[0])  # oturum kullanılabilir
    monkeypatch.undo()
    assert job["Status"] == "Çalışıyor"


def test_job_failure_writes_event_in_same_transaction(db_session, job_settings, test_users):
    job = running(db_session, job_settings, test_users[0])
    assert queue.fail(db_session, job["Id"], job["Attempt"], "Hesap bozuk", commit=False)
    db_session.rollback()
    assert rows(db_session) == []  # iş geri alındı, olay da yok
    assert queue.get_job(db_session, job["Id"], job_settings)["Status"] == "Çalışıyor"

    assert queue.fail(db_session, job["Id"], job["Attempt"], "Hesap bozuk")
    row = rows(db_session)[0]
    assert (row["Component"], row["JobId"], row["IsResolved"]) == ("Motor", job["Id"], False)
    assert "Hesap bozuk" in row["Message"] and row["Resolution"] == "İş hata ile bitti"
    assert not queue.fail(db_session, job["Id"], job["Attempt"], "Yine")  # artık çalışmıyor: olay da yok
    assert len(rows(db_session)) == 1


def test_export_failure_component(db_session, job_settings, test_users):
    job = running(db_session, job_settings, test_users[0], TYPE_EXPORT, CHANNEL_EXPORT)
    queue.fail(db_session, job["Id"], job["Attempt"], "Dosya yok")
    assert rows(db_session)[0]["Component"] == "Dışa aktarım"


def test_stale_job_events(db_session, job_settings, test_users):
    job = running(db_session, job_settings, test_users[0])
    age(db_session, job["Id"])
    assert queue.requeue_stale(db_session, job_settings) == [job["Id"]]
    assert queue.requeue_stale(db_session, job_settings) == []  # ikinci çağrı satırı bulamaz, olay çift yazılmaz
    first = rows(db_session)
    assert len(first) == 1 and first[0]["Component"] == "İş kuyruğu" and first[0]["IsResolved"] is True
    assert first[0]["Resolution"] == f"Yeniden sıraya alındı (deneme 1 / {job_settings.max_attempts})"
    assert first[0]["Detail"] == f"{TYPE_WORKSPACE} · deneme 1"
    assert queue.get_job(db_session, job["Id"], job_settings)["Status"] == STATUS_QUEUED

    again = queue.claim_next(db_session, CHANNEL_INTERACTIVE, job_settings)
    age(db_session, again["Id"])
    queue.requeue_stale(db_session, job_settings)
    last = rows(db_session)[-1]
    assert last["IsResolved"] is False and last["Resolution"] == "Deneme hakkı bitti" and "yanıt vermedi" in last["Message"]
    assert queue.get_job(db_session, job["Id"], job_settings)["Status"] == STATUS_FAILED


def test_crashed_process_event(db_session, job_settings, test_users):
    job = running(db_session, job_settings, test_users[0])
    assert queue.requeue(db_session, job["Id"], job["Attempt"], job_settings) == STATUS_QUEUED
    row = rows(db_session)[0]
    assert "süreci beklenmedik bitti" in row["Message"] and row["IsResolved"] is True
    assert row["Detail"] == f"{TYPE_WORKSPACE} · deneme 1"


def test_purge_removes_only_old(db_session):
    db_session.execute(text("INSERT INTO adm.SystemEvent (OccurredAt, Component, Message, IsResolved) VALUES "
                            "(DATEADD(day, -100, SYSUTCDATETIME()), N'Motor', N'Eski', 0), "
                            "(DATEADD(day, -10, SYSUTCDATETIME()), N'Motor', N'Yeni', 0)"))
    db_session.commit()
    assert events.purge(db_session, 90) == 1
    assert [r["Message"] for r in rows(db_session)] == ["Yeni"]
    assert events.purge(db_session, 90) == 0


def test_unexpected_api_error_is_recorded(db_engine, clean_jobs, test_users, db_session, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("gizli parametre")
    monkeypatch.setattr("app.api.services.jobs.list_jobs", boom)
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.cookies.set(COOKIE, token(test_users[0]))
    r = client.get("/api/jobs")
    assert r.status_code == 500
    row = rows(db_session)[0]
    assert row["Component"] == "Uygulama" and row["Message"] == "Beklenmeyen hata · GET /api/jobs"
    assert row["TraceId"] == r.headers["X-Trace-Id"] and row["Detail"] == "RuntimeError"  # istisna metni yazılmaz
    assert client.get("/api/jobs").status_code == 500
    assert len(rows(db_session)) == 1  # hata seli yok


def test_unexpected_error_answer_survives_when_event_fails(db_engine, clean_jobs, test_users, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr("app.api.services.jobs.list_jobs", boom)
    monkeypatch.setattr("app.api.services.system_health.get_engine", boom)
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.cookies.set(COOKIE, token(test_users[0]))
    r = client.get("/api/jobs")
    assert r.status_code == 500 and r.json()["error"]["code"] == "unexpected"

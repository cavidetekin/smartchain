"""Uygulama hesabının yetkisi (K-109): denetim izinde yalnız ekleme ve okuma; uygulama db_owner olmadan çalışır.

Geliştirme bağlantısı sysadmin olduğu için DENY ona işlemez. Bu yüzden test, Smartchain_test içinde girişsiz bir kullanıcı açar ve
EXECUTE AS ile onun kimliğine geçer. Sunucu düzeyinde değişiklik yoktur; kullanıcı ve rol test sonunda silinir.
"""
import importlib.util
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.lists import MATERIALS
from app.api.lists.request import QueryRequest
from app.api.repositories import audit, settings as settings_repo
from app.api.services import lists as list_service, system_health
from app.jobs import events, queue
from app.jobs.constants import CHANNEL_INTERACTIVE, TYPE_WORKSPACE
from app.jobs.settings import JobSettings

pytestmark = pytest.mark.db

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("setup_db_permissions", ROOT / "installer" / "setup_db.py")
setup_db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup_db)

USER = "pytest_app_user"
MARK = "pytest.yetki"


@pytest.fixture
def app_connection(db_engine, clean_jobs):
    """Uygulama rolünde kısıtlı kullanıcının kimliğiyle bağlantı."""
    admin = db_engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    for sql in setup_db.app_role_statements():
        admin.execute(text(sql))
    admin.execute(text(f"DROP USER IF EXISTS {USER}"))
    admin.execute(text(f"CREATE USER {USER} WITHOUT LOGIN"))
    admin.execute(text(f"ALTER ROLE {setup_db.APP_ROLE} ADD MEMBER {USER}"))
    conn = db_engine.connect()
    conn.execute(text(f"EXECUTE AS USER = '{USER}'"))
    conn.commit()
    try:
        yield conn
    finally:
        conn.rollback()
        conn.execute(text("REVERT"))
        conn.commit()
        conn.close()
        admin.execute(text(f"DELETE FROM adm.AuditLog WHERE Action = N'{MARK}'"))
        admin.execute(text("DELETE FROM adm.SystemSetting WHERE SettingKey = N'DiskWarnPercent'"))
        admin.execute(text("DELETE FROM adm.SystemEvent"))
        admin.execute(text(f"DROP USER IF EXISTS {USER}"))
        for sql in setup_db.app_role_drop_statements():
            admin.execute(text(sql))
        admin.close()


@pytest.mark.parametrize("sql", [
    "UPDATE adm.AuditLog SET Action = Action WHERE Id = 0",
    "DELETE FROM adm.AuditLog WHERE Id = 0",
    "TRUNCATE TABLE adm.AuditLog",
    "ALTER TABLE adm.AuditLog ADD Deneme int NULL",
    "DROP TABLE adm.AuditLog",
])
def test_audit_log_cannot_be_changed(app_connection, sql):
    with pytest.raises(DBAPIError) as exc:
        app_connection.execute(text(sql))
    assert "permission" in str(exc.value).lower()
    app_connection.rollback()


def test_audit_log_can_be_read_and_added(app_connection):
    with Session(bind=app_connection) as s:
        audit.write_audit(s, MARK, None, "Test", "1", {"Value": 1})
        assert s.execute(text("SELECT COUNT(*) FROM adm.AuditLog WHERE Action = :a"), {"a": MARK}).scalar_one() == 1
        s.commit()


def test_application_works_without_db_owner(app_connection):
    """Çalışma anındaki işler: kuyruk kilidi, olay, ayar, liste, sağlık özeti. DDL yok."""
    with Session(bind=app_connection) as s:
        job_id = queue.enqueue(s, TYPE_WORKSPACE, CHANNEL_INTERACTIVE)
        job = queue.claim_next(s, CHANNEL_INTERACTIVE, JobSettings())
        assert job["Id"] == job_id
        assert queue.heartbeat(s, job_id, job["Attempt"])
        assert queue.fail(s, job_id, job["Attempt"], "deneme")
        settings_repo.set_setting(s, "DiskWarnPercent", "70")
        s.commit()
        events.service_started(s, "test")
        events.service_beat(s)
        events.service_stopped(s)
        assert events.purge(s, 90) >= 0
        assert list_service.query(s, MATERIALS, QueryRequest(limit=5))["rows"]
        assert system_health.summary(s, datetime.now(), 0)["cards"]["disk"]["database_bytes"] > 0


def _odbc_connection(db_engine):
    raw = db_engine.raw_connection()
    return raw, raw.driver_connection


def test_verify_finds_nothing_when_rights_are_right(db_engine, app_connection):
    raw, conn = _odbc_connection(db_engine)
    try:
        assert setup_db.audit_permission_problems(conn) == []
    finally:
        raw.rollback()
        raw.close()


def test_verify_reports_db_owner_and_missing_deny(db_engine, app_connection):
    admin = db_engine.connect().execution_options(isolation_level="AUTOCOMMIT")
    raw, conn = _odbc_connection(db_engine)
    role = setup_db.APP_ROLE
    try:
        admin.execute(text(f"REVOKE UPDATE, DELETE ON adm.AuditLog FROM {role}"))
        admin.execute(text(f"ALTER ROLE db_owner ADD MEMBER {USER}"))
        problems = setup_db.audit_permission_problems(conn)
        assert f"{USER}: db_owner" in problems
        assert f"{setup_db.APP_ROLE}: UPDATE engeli yok" in problems and f"{setup_db.APP_ROLE}: DELETE engeli yok" in problems
    finally:
        admin.execute(text(f"ALTER ROLE db_owner DROP MEMBER {USER}"))
        admin.execute(text(f"DENY UPDATE, DELETE ON adm.AuditLog TO {role}"))
        raw.rollback()
        raw.close()
        admin.close()

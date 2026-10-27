import os
import tempfile

os.environ.setdefault("SMARTCHAIN_LOG_DIR", tempfile.mkdtemp(prefix="smartchain-logs-"))
os.environ.setdefault("SMARTCHAIN_JOB_WATCH_SECONDS", "0.2")

import pytest
from fastapi.testclient import TestClient

from app.api.db import get_session
from app.api.main import create_app


class FakeSession:
    """Veritabanı olmadan testler için yer tutucu; sorgular repository'de taklit edilir."""


@pytest.fixture
def app():
    application = create_app()
    application.dependency_overrides[get_session] = lambda: FakeSession()
    return application


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


# --- Yerel SQL Server (Smartchain) gerektiren testler (işaret: db) ---
# Bu testler adm.Job tablosunu her testten önce ve sonra boşaltır; yalnız geliştirme veritabanında çalıştırın.

@pytest.fixture(scope="session")
def db_engine():
    from sqlalchemy import text
    from app.api.db import get_engine
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT TOP 0 CreatedAt, UpdatedAt FROM adm.Job"))  # şema 0002 kurulu mu
    except Exception as exc:
        pytest.skip(f"SQL Server'a bağlanılamadı ya da şema eski: {exc}")
    return engine


def _clear_jobs(engine):
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM adm.Job"))


@pytest.fixture(scope="session")
def test_users(db_engine):
    """İki deneme kullanıcısı (Job.RequestedBy adm.AppUser'a bağlı). Oturum sonunda silinir."""
    from sqlalchemy import text
    names = ["test.job.1", "test.job.2"]
    with db_engine.begin() as conn:
        for n in names:
            conn.execute(text("IF NOT EXISTS (SELECT 1 FROM adm.AppUser WHERE UserName = :n) "
                              "INSERT INTO adm.AppUser (UserName, Role, PasswordHash) VALUES (:n, N'Key user', 0x00)"),
                         {"n": n})
        ids = [conn.execute(text("SELECT Id FROM adm.AppUser WHERE UserName = :n"), {"n": n}).scalar_one()
               for n in names]
    yield ids
    _clear_jobs(db_engine)
    with db_engine.begin() as conn:
        for n in names:
            conn.execute(text("DELETE FROM adm.AppUser WHERE UserName = :n"), {"n": n})


@pytest.fixture
def clean_jobs(db_engine, test_users):
    _clear_jobs(db_engine)
    yield
    _clear_jobs(db_engine)


@pytest.fixture
def db_session(db_engine, clean_jobs):
    from sqlalchemy.orm import Session
    with Session(db_engine) as session:
        yield session


@pytest.fixture
def job_settings(db_session):
    from app.jobs.settings import read_settings
    return read_settings(db_session)


@pytest.fixture
def db_client(db_engine, clean_jobs):
    """Gerçek veritabanıyla API istemcisi (izleyici kapalı; lifespan çalışmaz)."""
    return TestClient(create_app(), raise_server_exceptions=False)

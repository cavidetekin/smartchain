import os
import tempfile

os.environ.setdefault("SMARTCHAIN_LOG_DIR", tempfile.mkdtemp(prefix="smartchain-logs-"))
os.environ.setdefault("SMARTCHAIN_JOB_WATCH_SECONDS", "0.2")
os.environ.setdefault("SMARTCHAIN_EXPORT_DIR", tempfile.mkdtemp(prefix="smartchain-exports-"))  # iş süreçleri de görür

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


# --- Motor testleri (0.5): referans satırları ve PlanRun temizliği ---

@pytest.fixture(scope="session")
def engine_refs(db_engine, test_users):
    """Test lokasyonu, veri versiyonu ve parametre seti; oturum sonunda silinir."""
    from sqlalchemy import text
    from app.engine.fake import ensure_fixture_warning_definitions
    from sqlalchemy.orm import Session
    with Session(db_engine) as s:
        ensure_fixture_warning_definitions(s)
        s.execute(text("IF NOT EXISTS (SELECT 1 FROM core.Location WHERE Code = N'TEST-ENG') "
                       "INSERT INTO core.Location (Code, Name, Type, IsSynthetic) VALUES (N'TEST-ENG', N'Motor testi', N'Tesis', 1)"))
        loc = s.execute(text("SELECT Id FROM core.Location WHERE Code = N'TEST-ENG'")).scalar_one()
        dv = s.execute(text("INSERT INTO adm.DataVersion (LocationId, CreatedAt, LoadType, IsSynthetic) "
                            "OUTPUT inserted.Id VALUES (:l, SYSUTCDATETIME(), N'Tam', 1)"), {"l": loc}).scalar_one()
        ps = s.execute(text("INSERT INTO param.ParameterSet (Name, IsSynthetic) OUTPUT inserted.Id "
                            "VALUES (N'Motor testi', 1)")).scalar_one()
        s.commit()
    yield {"location_id": loc, "data_version_id": dv, "parameter_set_id": ps, "user_id": test_users[0]}
    _clear_plan_runs(db_engine, dv)
    with db_engine.begin() as c:
        c.execute(text("DELETE FROM param.PlanningSetting WHERE ParameterSetId = :p"), {"p": ps})
        c.execute(text("DELETE FROM param.ParameterSet WHERE Id = :p"), {"p": ps})
        c.execute(text("DELETE FROM adm.DataVersion WHERE Id = :d"), {"d": dv})
        c.execute(text("DELETE FROM core.Location WHERE Id = :l"), {"l": loc})


def _clear_plan_runs(engine, data_version_id):
    from sqlalchemy import text
    from app.data.cleanup import delete_plan_data
    with engine.begin() as c:
        delete_plan_data(c, [data_version_id])
        c.execute(text("DELETE FROM param.ScenarioDefinition WHERE Name = N'Motor testi'"))


@pytest.fixture
def plan_env(db_engine, engine_refs, clean_jobs):
    """Her motor testi temiz PlanRun ve iş tablosuyla başlar; sahte motor ayarları sıfırlanır."""
    _clear_plan_runs(db_engine, engine_refs["data_version_id"])
    set_fake(db_engine, engine_refs["parameter_set_id"])
    yield engine_refs
    _clear_plan_runs(db_engine, engine_refs["data_version_id"])


def set_fake(engine, parameter_set_id, step=0, mode="normal"):
    """Sahte motorun PlanningSetting ayarları (docs/09)."""
    from sqlalchemy import text
    with engine.begin() as c:
        c.execute(text("DELETE FROM param.PlanningSetting WHERE ParameterSetId = :p"), {"p": parameter_set_id})
        for k, v in {"ModelType": "LP", "FakeEngineStepSeconds": str(step), "FakeEngineMode": mode}.items():
            c.execute(text("INSERT INTO param.PlanningSetting (ParameterSetId, SettingKey, Value) VALUES (:p, :k, :v)"),
                      {"p": parameter_set_id, "k": k, "v": v})

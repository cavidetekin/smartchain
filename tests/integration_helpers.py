"""SQL çekimi testlerinin ortak kaynağı (K-130): kirli hâl SmartchainIntegration_test'te. Veritabanı yalnız _test ile biter (K-103)."""
import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

from app.data.synthetic.dataset import generate
from app.data.synthetic.sql import write_sql

import testdb

DATABASE = "SmartchainIntegration_test"
KEY = "IntegrationDatabase"


def base_url():
    from app.api.settings import get_settings
    return make_url(testdb.resolve(get_settings().db_url))


def run_sql(statement: str, params: dict | None = None):
    engine = sa.create_engine(base_url().set(database=DATABASE), poolclass=NullPool)
    try:
        with engine.begin() as c:
            result = c.execute(sa.text(statement), params or {})
            return result.fetchall() if result.returns_rows else None
    finally:
        engine.dispose()


def clean_settings(engine) -> None:
    with engine.begin() as c:
        c.execute(sa.text("DELETE FROM adm.IntegrationViewVersion"))
        c.execute(sa.text("DELETE FROM adm.IntegrationEntity"))
        c.execute(sa.text(f"DELETE FROM adm.SystemSetting WHERE SettingKey IN (N'{KEY}', N'PullRetryWaitSeconds')"))


@pytest.fixture(scope="session")
def _written(db_engine):
    write_sql(generate(), base_url(), DATABASE)


@pytest.fixture
def integration_db(db_engine, _written):
    """Kaynak hazır, ayar yazılı, bitti sinyali tek ve bitmiş; test sonunda ayarlar temizlenir."""
    clean_settings(db_engine)
    run_sql("DELETE FROM dbo.ERP_LoadLog")
    run_sql("INSERT INTO dbo.ERP_LoadLog (EntityName, StartedAt, FinishedAt) VALUES (NULL, SYSUTCDATETIME(), SYSUTCDATETIME())")
    with db_engine.begin() as c:
        c.execute(sa.text(f"INSERT INTO adm.SystemSetting (SettingKey, Value) VALUES (N'{KEY}', N'{DATABASE}')"))
        c.execute(sa.text("INSERT INTO adm.SystemSetting (SettingKey, Value) VALUES (N'PullRetryWaitSeconds', N'0')"))
    yield db_engine
    clean_settings(db_engine)

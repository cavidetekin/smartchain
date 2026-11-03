"""Testlerin veritabanı (K-103): bütün veritabanı testleri adı _test ile biten ayrı veritabanında koşar.

Bağlantı SMARTCHAIN_TEST_DB_URL'den gelir; yoksa geliştirme bağlantısından türetilir (aynı sunucu, ad + _test).
Oturum başında veritabanı yoksa açılır, şemaya getirilir, önceki koşunun artıkları silinir, sentetik veri yoksa yüklenir.
conftest.py bunu uygulamayı import etmeden önce çağırır; bu yüzden burada üst düzeyde uygulama import edilmez.
"""
import importlib.util
import os
from collections.abc import Mapping
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError

ROOT = Path(__file__).resolve().parents[1]
OVERRIDE = "SMARTCHAIN_TEST_DB_URL"
SUFFIX = "_test"
# Ad yanlışsa uygulama buna bağlanır: koşu zaten başlamaz, geliştirme bağlantısına düşülmez.
NOWHERE = "mssql+pyodbc://@127.0.0.1,1/Reddedildi_test?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes"
SYNTHETIC_MATERIALS = 200


class WrongTestDatabase(Exception):
    """Test veritabanının adı _test ile bitmiyor ya da adı çıkarılamıyor."""


def _name(url: str) -> str | None:
    try:
        return make_url(url).database
    except ArgumentError:
        return None


def is_test_name(name: str | None) -> bool:
    return bool(name) and name.lower().endswith(SUFFIX)


def _wrong(name: str) -> WrongTestDatabase:
    return WrongTestDatabase(f"Testler durdu: veritabanı adı {SUFFIX} ile bitmeli, '{name}' reddedildi. "
                             f"{OVERRIDE} ile test veritabanını verin (K-103).")


def resolve(dev_url: str, environ: Mapping[str, str] = os.environ) -> str:
    """Test bağlantısı: önce SMARTCHAIN_TEST_DB_URL, yoksa geliştirme bağlantısından türetilir."""
    explicit = environ.get(OVERRIDE)
    if explicit:
        name = _name(explicit)
        if not is_test_name(name):
            raise _wrong(name or explicit.split("?")[0])
        return explicit
    name = _name(dev_url)
    if not name:
        raise WrongTestDatabase(f"Testler durdu: geliştirme bağlantısından veritabanı adı çıkarılamadı. {OVERRIDE} verin (K-103).")
    if is_test_name(name):
        return dev_url
    return make_url(dev_url).set(database=f"{name}{SUFFIX}").render_as_string(hide_password=False)


def _setup_db():
    spec = importlib.util.spec_from_file_location("setup_db_for_tests", ROOT / "installer" / "setup_db.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_database(url: str, timeout: int) -> bool:
    """Veritabanı yoksa ürünün collation'ıyla açar. Açtıysa True."""
    setup_db = _setup_db()
    name = make_url(url).database
    setup_db.refuse_in_tests(name)
    master = sa.create_engine(make_url(url).set(database="master"), isolation_level="AUTOCOMMIT", connect_args={"timeout": timeout})
    try:
        with master.connect() as conn:
            if conn.execute(sa.text("SELECT DB_ID(:n)"), {"n": name}).scalar() is not None:
                return False
            conn.execute(sa.text(f"CREATE DATABASE {setup_db.quote_name(name)} COLLATE {setup_db.COLLATION}"))
            return True
    finally:
        master.dispose()


def verify_connected(engine: Engine) -> str:
    """Bağlanılan veritabanı gerçekten test veritabanı mı (ayar ne derse desin)."""
    with engine.connect() as conn:
        name = conn.execute(sa.text("SELECT DB_NAME()")).scalar_one()
    if not is_test_name(name):
        raise _wrong(name)
    return name


def upgrade_schema() -> None:
    """alembic upgrade head; bağlantı SMARTCHAIN_DB_URL'den (conftest koyar). Güncelse işlem yapmaz."""
    from alembic import command
    from alembic.config import Config
    command.upgrade(Config(str(ROOT / "db" / "alembic.ini")), "head")


def clear_leftovers(engine: Engine) -> None:
    """Yarıda kesilen koşunun artıkları: işler, ayarlar, motor testi satırları, deneme hesapları."""
    from app.data.cleanup import delete_plan_data
    from auth_helpers import delete_users
    with engine.begin() as c:
        versions = [r[0] for r in c.execute(sa.text(
            "SELECT Id FROM adm.DataVersion WHERE LocationId IN (SELECT Id FROM core.Location WHERE Code = N'TEST-ENG')"))]
        if versions:
            delete_plan_data(c, versions)
        c.execute(sa.text("DELETE FROM param.ScenarioDefinition WHERE Name = N'Motor testi'"))
        c.execute(sa.text("DELETE s FROM param.PlanningSetting s JOIN param.ParameterSet p ON p.Id = s.ParameterSetId "
                          "WHERE p.Name = N'Motor testi'"))
        c.execute(sa.text("DELETE FROM param.ParameterSet WHERE Name = N'Motor testi'"))
        for version in versions:
            c.execute(sa.text("DELETE FROM adm.DataVersion WHERE Id = :v"), {"v": version})
        c.execute(sa.text("DELETE FROM core.Location WHERE Code = N'TEST-ENG'"))
        c.execute(sa.text("DELETE FROM adm.Job"))
        c.execute(sa.text("DELETE FROM adm.SystemSetting"))
        c.execute(sa.text("UPDATE adm.FieldDefinition SET Label = NULL WHERE Label LIKE N'pytest%'"))
        delete_users(c, [r[0] for r in c.execute(sa.text(
            "SELECT Id FROM adm.AppUser WHERE UserName LIKE N'pytest.%' OR UserName LIKE N'test.job.%'"))])


def ensure_synthetic(engine: Engine) -> bool:
    """Sentetik veri yoksa yükler (docs/11); varsa dokunmaz. Yüklediyse True."""
    with engine.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT TOP 1 v.IsSynthetic, (SELECT COUNT(*) FROM core.Material m WHERE m.VersionFrom <= v.Id "
            "AND (m.VersionTo IS NULL OR m.VersionTo >= v.Id)) FROM adm.DataVersion v ORDER BY v.Id DESC")).first()
    if row and row[0] and row[1] == SYNTHETIC_MATERIALS:
        return False
    from app.data.synthetic.dataset import generate
    from app.data.synthetic.load import load
    load(engine, generate())
    return True

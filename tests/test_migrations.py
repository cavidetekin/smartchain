"""Son geçişin ileri – geri – ileri denemesi (K-186): boş bir deneme veritabanında (`Smartchain_migration_test`; adı `_test` ile biter, K-103)
bütün geçişler uygulanır, son geçiş geri alınır ve yeniden uygulanır; sonunda şema modellerle aynıdır (`alembic check`). Veritabanı test sonunda
düşürülür. Ortak test veritabanına (`Smartchain_test`) dokunmaz: orada geri alış sentetik veriyi silerdi.

Geçişi her zaman "son geçiş" olarak bulur: yeni geçiş eklendiğinde aynı test onu dener.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

import testdb

pytestmark = pytest.mark.db

ROOT = Path(__file__).resolve().parents[1]
NAME = "Smartchain_migration_test"


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "SMARTCHAIN_DB_URL": url, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-m", "alembic", "-c", "db/alembic.ini", *args], cwd=ROOT, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=900)


def _drop(url: str) -> None:
    assert testdb.is_test_name(NAME)
    master = sa.create_engine(make_url(url).set(database="master"), isolation_level="AUTOCOMMIT")
    try:
        with master.connect() as conn:
            if conn.execute(sa.text("SELECT DB_ID(:n)"), {"n": NAME}).scalar() is not None:
                conn.execute(sa.text(f"ALTER DATABASE [{NAME}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE"))
                conn.execute(sa.text(f"DROP DATABASE [{NAME}]"))
    finally:
        master.dispose()


@pytest.fixture
def scratch(db_engine):
    """Boş deneme veritabanı; test sonunda düşürülür (önceki koşudan kaldıysa baştan açılır)."""
    url = make_url(os.environ["SMARTCHAIN_DB_URL"]).set(database=NAME).render_as_string(hide_password=False)
    _drop(url)
    assert testdb.ensure_database(url, timeout=30)
    try:
        yield url
    finally:
        _drop(url)


def _tables(url: str) -> set[str]:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as c:
            return {f"{s}.{t}" for s, t in c.execute(sa.text("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'"))}
    finally:
        engine.dispose()


def _version(url: str) -> str:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as c:
            return c.execute(sa.text("SELECT version_num FROM dbo.alembic_version")).scalar_one()
    finally:
        engine.dispose()


def test_latest_migration_goes_forward_back_and_forward(scratch):
    script = ScriptDirectory.from_config(Config(str(ROOT / "db" / "alembic.ini")))
    head = script.get_current_head()
    previous = script.get_revision(head).down_revision
    assert head and isinstance(previous, str)

    up = _alembic(scratch, "upgrade", "head")
    assert up.returncode == 0, up.stdout + up.stderr
    assert _version(scratch) == head
    after_first = _tables(scratch)

    down = _alembic(scratch, "downgrade", previous)
    assert down.returncode == 0, down.stdout + down.stderr
    assert _version(scratch) == previous
    before = _tables(scratch)
    if head == "0067":   # K-185: yeni giriş tabloları geri alınınca kalkar, kalkan tablolar geri gelir
        assert {"param.WorkPattern", "param.OvertimeLimit", "param.FactoryCalendar"} <= after_first - before
        assert {"core.Calendar", "core.CalendarDay", "core.ResourceCapacityProfile", "core.ResourceDowntime", "param.ResourcePeriodLimit"} <= before - after_first

    again = _alembic(scratch, "upgrade", "head")
    assert again.returncode == 0, again.stdout + again.stderr
    assert _version(scratch) == head and _tables(scratch) == after_first

    check = _alembic(scratch, "check")   # şema modellerle aynı: yeni geçiş gerekmiyor
    assert check.returncode == 0, check.stdout + check.stderr


def test_migrations_do_not_read_the_live_model_or_catalog():
    """K-197: geçiş güncel modelden (`metadata.tables`) ve uygulama kodundan (`app.*`) okumaz; yazdığı değerleri sabit taşır (`db/frozen.py`).
    İstisnalar: veri sözlüğü eşitlemesi (`sync(bind, metadata)`) ve 0055'in yalnız verili veritabanında çalışan geçmiş doldurması."""
    import re
    allowed = {"0055_alan_degisikligi_k_173.py": ("from app.history.backfill import backfill",)}
    problems = []
    for path in sorted((ROOT / "db" / "migrations" / "versions").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            code = line.split("#")[0]
            if "metadata.tables" in code or re.search(r"^\s*(from|import)\s+app(\.|\s|$)", code) or re.search(r"metadata\.(sorted_tables|schema)", code):
                if code.strip() not in allowed.get(path.name, ()):
                    problems.append(f"{path.name}: {code.strip()[:100]}")
    assert not problems, problems

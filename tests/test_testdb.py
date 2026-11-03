"""Testler ayrı veritabanında (K-103): bağlantı türetmesi, yanlış adda durma, alt süreçlerin aynı veritabanını görmesi."""
import os
import subprocess
import sys

import pytest
from sqlalchemy import text

from app.api.settings import get_settings

import testdb

DRIVER = "?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes&TrustServerCertificate=yes"
DEV = f"mssql+pyodbc://@localhost/Smartchain{DRIVER}"


def url(name: str) -> str:
    return f"mssql+pyodbc://@localhost/{name}{DRIVER}"


def test_derived_from_development_connection():
    out = testdb.resolve(DEV, {})
    assert "/Smartchain_test?" in out and out.startswith("mssql+pyodbc://@localhost/")
    assert "ODBC+Driver+18" in out and "TrustServerCertificate=yes" in out


def test_derived_name_already_test_stays():
    assert testdb.resolve(url("Smartchain_test"), {}) == url("Smartchain_test")


def test_override_wins():
    assert testdb.resolve(DEV, {testdb.OVERRIDE: url("Baska_test")}) == url("Baska_test")


@pytest.mark.parametrize("name", ["Smartchain", "smartchain", "SMARTCHAIN", "master", "Smartchain_test_yedek", "test_Smartchain", "Smartchain_install"])
def test_wrong_name_refused(name):
    with pytest.raises(testdb.WrongTestDatabase, match=f"'{name}' reddedildi"):
        testdb.resolve(DEV, {testdb.OVERRIDE: url(name)})


def test_case_of_suffix_does_not_matter():
    assert testdb.resolve(DEV, {testdb.OVERRIDE: url("Smartchain_TEST")}) == url("Smartchain_TEST")


def test_name_cannot_be_derived_from_connection_string_form():
    with pytest.raises(testdb.WrongTestDatabase, match="adı çıkarılamadı"):
        testdb.resolve("mssql+pyodbc:///?odbc_connect=DRIVER%3Dx", {})
    with pytest.raises(testdb.WrongTestDatabase):
        testdb.resolve(DEV, {testdb.OVERRIDE: "mssql+pyodbc:///?odbc_connect=DATABASE%3DSmartchain"})


def test_application_settings_point_to_test_database():
    assert testdb.is_test_name(testdb._name(os.environ["SMARTCHAIN_DB_URL"]))
    assert get_settings().db_url == os.environ["SMARTCHAIN_DB_URL"]


@pytest.mark.db
def test_connected_database_is_test_database(db_engine):
    with db_engine.connect() as conn:
        name = conn.execute(text("SELECT DB_NAME()")).scalar_one()
    assert testdb.is_test_name(name)
    assert testdb.verify_connected(db_engine) == name


def test_verify_connected_refuses_other_database():
    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, *_):
            return self

        def scalar_one(self):
            return "Smartchain"

    class Engine:
        def connect(self):
            return Conn()

    with pytest.raises(testdb.WrongTestDatabase, match="'Smartchain' reddedildi"):
        testdb.verify_connected(Engine())


@pytest.mark.db
def test_child_process_sees_test_database(db_engine):
    """Motorun iş süreçleri gibi alt süreçler ortamı miras alır: geliştirme motoru test işlerini görmez."""
    code = "from sqlalchemy import text; from app.api.db import get_engine; import sys\n" \
           "c = get_engine().connect(); sys.stdout.write(c.execute(text('SELECT DB_NAME()')).scalar_one()); c.close()"
    r = subprocess.run([sys.executable, "-c", code], cwd=testdb.ROOT, capture_output=True, timeout=120)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    with db_engine.connect() as conn:
        assert r.stdout.decode().strip() == conn.execute(text("SELECT DB_NAME()")).scalar_one()


def run_pytest(override: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, testdb.OVERRIDE: override, "PYTHONIOENCODING": "utf-8"}
    env.pop("PYTEST_CURRENT_TEST", None)
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", *args],
                          cwd=testdb.ROOT, env=env, capture_output=True, timeout=300)


@pytest.mark.parametrize("name", ["Smartchain", "master"])
def test_wrong_database_stops_before_any_test(name):
    r = run_pytest(url(name), "tests/test_health.py", "tests/test_users_api.py::test_unknown_user")
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    assert r.returncode == 2, out
    assert f"'{name}' reddedildi" in out
    assert " passed" not in out and " skipped" not in out and " failed" not in out


def test_wrong_database_stops_without_database_tests_too():
    r = run_pytest(url("Smartchain"), "tests/test_health.py", "-m", "not db")
    assert r.returncode == 2, (r.stdout + r.stderr).decode("utf-8", "replace")

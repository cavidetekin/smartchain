"""Testlerin veritabanı güvenliği (plans/2.3.md, 03.11 olayı).

- Test sırasında veritabanını silen, açan ya da geçiş çalıştıran kod adı _test ile bitmeyen veritabanını reddeder.
- Veritabanı testleri atlanırsa koşu başarısız olur; zincir yanlışlıkla "geçmiş" görünmez.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_installer import ROOT, setup_db

MASTER = setup_db.odbc_string("localhost", "master", encrypt="yes", trust_server_certificate=True)
DEV_NAMES = ["Smartchain", "smartchain", "SMARTCHAIN", "Smartchain_install", "test_Smartchain", "Smartchain_test_yedek", "master"]


class FakeConnection:
    """Bağlanılırsa kaydeder; gerçek sunucuya gidilmez."""

    def __init__(self):
        self.sql: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, *_):
        self.sql.append(sql)
        return self

    def fetchone(self):
        return [1]


@pytest.fixture
def connections(monkeypatch):
    fake = FakeConnection()
    monkeypatch.setattr(setup_db, "_connect", lambda odbc: fake)
    return fake


@pytest.mark.parametrize("name", DEV_NAMES)
@pytest.mark.parametrize("work", [setup_db.drop_database, setup_db.ensure_database])
def test_refuses_non_test_database_before_connecting(connections, work, name):
    with pytest.raises(RuntimeError, match="adı _test ile bitmeli"):
        work(MASTER, name)
    assert connections.sql == []


def test_incident_drop_with_user_name_is_refused(connections):
    """03.11: değişken kullanıcı adıyla ezildi, drop_database "smartchain" ile çağrıldı ve geliştirme veritabanı silindi."""
    with pytest.raises(RuntimeError):
        setup_db.drop_database(MASTER, "smartchain")
    assert connections.sql == []


@pytest.mark.parametrize("name", ["Smartchain_install_test", "x_TEST"])
def test_allows_test_database(connections, name):
    setup_db.drop_database(MASTER, name)
    assert any("DROP DATABASE" in s and name in s for s in connections.sql)


@pytest.mark.parametrize("work", [
    lambda db: setup_db.migrate(ROOT, db),
    lambda db: setup_db.first_account(ROOT, db, reset=True),
    lambda db: setup_db.ensure_service_logins(MASTER, db, []),
])
def test_refuses_dev_database_in_connection_string(connections, work):
    for name in ("Smartchain", "smartchain"):
        with pytest.raises(RuntimeError, match="adı _test ile bitmeli"):
            work(setup_db.odbc_string("localhost", name, encrypt="yes", trust_server_certificate=True))
    assert connections.sql == []


def test_command_line_is_guarded_too(connections):
    with pytest.raises(RuntimeError):  # varsayılan --database Smartchain
        setup_db.main(["drop", "--instance", "localhost"])
    assert connections.sql == []


def test_guard_only_applies_in_tests(connections, monkeypatch):
    """Kaldırma (uninstall.ps1 -RemoveData) müşterinin veritabanını silebilmeli: koruma test dışında işlemez."""
    monkeypatch.delenv("PYTEST_CURRENT_TEST")
    setup_db.drop_database(MASTER, "Smartchain")
    assert any("DROP DATABASE [Smartchain]" in s for s in connections.sql)


# --- Atlanan veritabanı testleri ---

UNREACHABLE = ("mssql+pyodbc://@localhost/Smartchain_olmayan_test?driver=ODBC+Driver+18+for+SQL+Server"
               "&trusted_connection=yes&TrustServerCertificate=yes")


def run_pytest(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "SMARTCHAIN_DB_URL": UNREACHABLE, "PYTHONIOENCODING": "utf-8"}
    env.pop("PYTEST_CURRENT_TEST", None)
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", *args],
                          cwd=Path(ROOT), env=env, capture_output=True, timeout=300)


def test_skipped_database_tests_fail_the_run():
    r = run_pytest("tests/test_users_api.py::test_unknown_user")
    out = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 1, out
    assert "1 skipped" in out and "Veritabanı testleri atlandı" in out


def test_running_without_database_is_explicit():
    r = run_pytest("tests/test_health.py", "-m", "not db")
    assert r.returncode == 0, r.stdout.decode("utf-8", "replace")

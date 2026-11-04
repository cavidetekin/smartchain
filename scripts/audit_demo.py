"""Denetim izi demosu (adım 2.6; K-108, K-109). Geliştirme aracı; kurulum paketine girmez.

    python scripts/audit_demo.py break    adm.AuditLog'a yazmayı geçici tetikleyiciyle bozar (geliştirme veritabanı)
    python scripts/audit_demo.py fix      tetikleyiciyi kaldırır
    python scripts/audit_demo.py prove    test veritabanında kısıtlı kullanıcıyla silmeyi dener (yetki güvencesi)
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests"), str(ROOT / "installer")]

import sqlalchemy as sa  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402

import setup_db  # noqa: E402
import testdb  # noqa: E402
from app.api.db import get_engine  # noqa: E402
from app.api.settings import Settings, config_files  # noqa: E402

TRIGGER = "adm.TR_AuditLog_Demo"
DEMO_USER = "smartchain_demo_user"


def break_audit() -> None:
    with get_engine().begin() as c:
        print("Veritabanı:", c.execute(sa.text("SELECT DB_NAME()")).scalar_one())
        c.execute(sa.text(f"CREATE TRIGGER {TRIGGER} ON adm.AuditLog INSTEAD OF INSERT AS "
                          "THROW 50001, 'Demo: denetim izi yazılamıyor', 1;"))
    print("İz yazma bozuldu; 'fix' ile geri alın")


def fix_audit() -> None:
    with get_engine().begin() as c:
        c.execute(sa.text(f"DROP TRIGGER IF EXISTS {TRIGGER}"))
    print("Tetikleyici kaldırıldı")


def prove() -> None:
    url = testdb.resolve(Settings(_env_file=config_files()).db_url)
    assert testdb.is_test_name(testdb._name(url)), "test veritabanı değil"
    engine = sa.create_engine(url)
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        print("Veritabanı:", c.execute(sa.text("SELECT DB_NAME()")).scalar_one())
        for sql in setup_db.app_role_statements():
            c.execute(sa.text(sql))
        c.execute(sa.text(f"CREATE USER {DEMO_USER} WITHOUT LOGIN"))
        c.execute(sa.text(f"ALTER ROLE {setup_db.APP_ROLE} ADD MEMBER {DEMO_USER}"))
        try:
            c.execute(sa.text(f"EXECUTE AS USER = '{DEMO_USER}'"))
            for name, sql in (("SELECT", "SELECT TOP 1 Id FROM adm.AuditLog"),
                              ("UPDATE", "UPDATE adm.AuditLog SET Action = Action WHERE Id = 0"),
                              ("DELETE", "DELETE FROM adm.AuditLog WHERE Id = 0"),
                              ("TRUNCATE", "TRUNCATE TABLE adm.AuditLog"),
                              ("INSERT", "INSERT INTO adm.AuditLog (At, Action) SELECT SYSUTCDATETIME(), N'demo' WHERE 1 = 0")):
                try:
                    c.execute(sa.text(sql))
                    print(f"{name:9} geçti")
                except DBAPIError:
                    print(f"{name:9} reddedildi")
            c.execute(sa.text("REVERT"))
        finally:
            c.execute(sa.text(f"DROP USER IF EXISTS {DEMO_USER}"))
            for sql in setup_db.app_role_drop_statements():
                c.execute(sa.text(sql))
    engine.dispose()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["break", "fix", "prove"])
    {"break": break_audit, "fix": fix_audit, "prove": prove}[p.parse_args().command]()


if __name__ == "__main__":
    main()

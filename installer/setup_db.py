"""Kurulumun veritabanı adımı (K-75, docs/10-kurulum.md). install.ps1 paketteki Python ile çağırır.

  setup_db.py url   --instance .\\SMARTCHAIN [--database Smartchain] [--encrypt yes] [--trust-server-certificate] [--sql-user u]
  setup_db.py setup ... --service-sid S-1-5-80-... --service-sid S-1-5-80-...
  setup_db.py drop  ...

SQL şifresi komut satırında değil, SMARTCHAIN_INSTALL_SQL_PASSWORD ortam değişkeninde gelir.
"""
import argparse
import os
import re
import struct
import sys
from pathlib import Path
from urllib.parse import quote_plus

DRIVER = "ODBC Driver 18 for SQL Server"
COLLATION = "Latin1_General_100_CI_AS_SC"
ENCRYPT_VALUES = ("yes", "no", "strict")


def odbc_string(instance: str, database: str, encrypt: str = "yes", trust_server_certificate: bool = False,
                sql_user: str | None = None, sql_password: str | None = None) -> str:
    """ODBC Driver 18 bağlantı cümlesi. Encrypt varsayılan açık; güvenilir sertifika yoksa TrustServerCertificate."""
    if encrypt not in ENCRYPT_VALUES:
        raise ValueError(f"Encrypt değeri {ENCRYPT_VALUES} olmalı: {encrypt}")
    parts = [f"DRIVER={{{DRIVER}}}", f"SERVER={instance}", f"DATABASE={database}",
             f"Encrypt={encrypt}", f"TrustServerCertificate={'yes' if trust_server_certificate else 'no'}"]
    if sql_user:
        # Süslü parantez içinde: şifrede ; ya da = olabilir; } iki kez yazılır.
        parts += [f"UID={{{sql_user.replace('}', '}}')}}}", f"PWD={{{(sql_password or '').replace('}', '}}')}}}"]
    else:
        parts.append("Trusted_Connection=yes")
    return ";".join(parts)


def sqlalchemy_url(odbc: str) -> str:
    return "mssql+pyodbc:///?odbc_connect=" + quote_plus(odbc)


def sid_to_bytes(sid: str) -> bytes:
    """'S-1-5-80-…' → SQL Server'ın SUSER_SNAME'e verilecek ikili SID."""
    parts = sid.split("-")
    if parts[0] != "S" or len(parts) < 3:
        raise ValueError(f"Geçersiz SID: {sid}")
    revision, authority, subs = int(parts[1]), int(parts[2]), [int(p) for p in parts[3:]]
    return (struct.pack("BB", revision, len(subs)) + authority.to_bytes(6, "big")
            + b"".join(struct.pack("<I", s) for s in subs))


def quote_name(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


def _connect(odbc: str):
    import pyodbc
    return pyodbc.connect(odbc, autocommit=True, timeout=15)


def refuse_in_tests(database: str) -> None:
    """Testler geliştirme veritabanına yıkıcı işlem yapamaz (CLAUDE.md): test sırasında adı _test ile bitmeyen veritabanı
    bağlanmadan reddedilir. Kurulum ve kaldırma etkilenmez; PYTEST_CURRENT_TEST'i yalnız pytest koyar."""
    if "PYTEST_CURRENT_TEST" in os.environ and not database.lower().endswith("_test"):
        raise RuntimeError(f"Test sırasında veritabanının adı _test ile bitmeli; '{database}' reddedildi.")


def _database_of(odbc: str) -> str:
    found = re.search(r"(?:^|;)DATABASE=([^;]*)", odbc)
    return found.group(1) if found else ""


def ensure_database(master_odbc: str, database: str) -> bool:
    """Veritabanı yoksa bizim collation'la açar. Açtıysa True."""
    refuse_in_tests(database)
    with _connect(master_odbc) as conn:
        if conn.execute("SELECT DB_ID(?)", database).fetchone()[0] is not None:
            return False
        conn.execute(f"CREATE DATABASE {quote_name(database)} COLLATE {COLLATION}")
        return True


def ensure_service_logins(master_odbc: str, db_odbc: str, sids: list[str]) -> list[str]:
    """Servis hesaplarına login ve veritabanı kullanıcısı (şimdilik db_owner). Ad, SID'den sunucunun dilinde çözülür."""
    refuse_in_tests(_database_of(db_odbc))
    names = []
    with _connect(master_odbc) as master:
        for sid in sids:
            name = master.execute("SELECT SUSER_SNAME(?)", sid_to_bytes(sid)).fetchone()[0]
            if not name:
                raise RuntimeError(
                    f"Servis hesabı ({sid}) SQL Server'da çözülemedi. SQL Server başka sunucudaysa "
                    "SQL kimliğiyle kurun (-SqlUser, -SqlPassword).")
            if master.execute("SELECT 1 FROM sys.server_principals WHERE sid = ?", sid_to_bytes(sid)).fetchone() is None:
                master.execute(f"CREATE LOGIN {quote_name(name)} FROM WINDOWS")
            names.append(name)
    with _connect(db_odbc) as db:
        for sid, name in zip(sids, names):
            row = db.execute("SELECT name FROM sys.database_principals WHERE sid = ?", sid_to_bytes(sid)).fetchone()
            user = row[0] if row else name
            if row is None:
                db.execute(f"CREATE USER {quote_name(user)} FOR LOGIN {quote_name(name)}")
            db.execute(f"ALTER ROLE db_owner ADD MEMBER {quote_name(user)}")
    return names


def migrate(root: Path, db_odbc: str) -> None:
    """alembic upgrade head (db/migrations); env.py bağlantıyı SMARTCHAIN_DB_URL'den alır."""
    refuse_in_tests(_database_of(db_odbc))
    from alembic import command
    from alembic.config import Config
    os.environ["SMARTCHAIN_DB_URL"] = sqlalchemy_url(db_odbc)
    cfg = Config(str(root / "db" / "alembic.ini"))
    command.upgrade(cfg, "head")


def drop_database(master_odbc: str, database: str) -> None:
    refuse_in_tests(database)
    with _connect(master_odbc) as conn:
        if conn.execute("SELECT DB_ID(?)", database).fetchone()[0] is not None:
            conn.execute(f"ALTER DATABASE {quote_name(database)} SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
            conn.execute(f"DROP DATABASE {quote_name(database)}")


def first_account(root: Path, db_odbc: str, reset: bool) -> tuple[str, str] | None:
    """İlk hesap (K-102): System owner yoksa açar; varsa dokunmaz (reset: yeni geçici şifre). Commit'ten sonra döner."""
    refuse_in_tests(_database_of(db_odbc))
    sys.path.insert(0, str(root))
    import sqlalchemy as sa
    from sqlalchemy.orm import Session

    from app.api.services.users import first_account as create

    engine = sa.create_engine(sqlalchemy_url(db_odbc))
    try:
        with Session(engine) as session:
            return create(session, reset=reset)
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Smartchain kurulum: veritabanı adımı")
    p.add_argument("command", choices=["url", "setup", "drop", "first-account"])
    p.add_argument("--reset", action="store_true", help="first-account: System owner hesabına yeni geçici şifre (K-102)")
    p.add_argument("--instance", required=True)
    p.add_argument("--database", default="Smartchain")
    p.add_argument("--encrypt", default="yes", choices=ENCRYPT_VALUES)
    p.add_argument("--trust-server-certificate", action="store_true")
    p.add_argument("--sql-user", default="")
    p.add_argument("--service-sid", action="append", default=[])
    p.add_argument("--root", default=str(Path(__file__).resolve().parent), help="app ve db klasörlerinin olduğu yer")
    a = p.parse_args(argv)
    password = os.environ.get("SMARTCHAIN_INSTALL_SQL_PASSWORD") if a.sql_user else None
    conn = dict(encrypt=a.encrypt, trust_server_certificate=a.trust_server_certificate,
                sql_user=a.sql_user or None, sql_password=password)
    db_odbc = odbc_string(a.instance, a.database, **conn)
    master_odbc = odbc_string(a.instance, "master", **conn)

    if a.command == "url":
        print(sqlalchemy_url(db_odbc))
    elif a.command == "setup":
        created = ensure_database(master_odbc, a.database)
        print(f"Veritabanı {a.database}: {'açıldı' if created else 'zaten var'}")
        if not a.sql_user:
            for name in ensure_service_logins(master_odbc, db_odbc, a.service_sid):
                print(f"Yetki verildi: {name}")
        sys.path.insert(0, a.root)
        migrate(Path(a.root), db_odbc)
        print("Geçişler tamam (alembic upgrade head)")
    elif a.command == "first-account":
        created = first_account(Path(a.root), db_odbc, a.reset)
        # Şifre yalnız bu satırda, commit'ten sonra; install.ps1 loga yazmadan gösterir.
        print(f"FIRST_ACCOUNT {created[0]} {created[1]}" if created else "FIRST_ACCOUNT_EXISTS")
    elif a.command == "drop":
        drop_database(master_odbc, a.database)
        print(f"Veritabanı {a.database} silindi")
    return 0


if __name__ == "__main__":
    sys.exit(main())

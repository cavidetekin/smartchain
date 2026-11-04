"""Kurulumun veritabanı adımı (K-75, docs/10-kurulum.md). install.ps1 paketteki Python ile çağırır.

  setup_db.py url   --instance .\\SMARTCHAIN [--database Smartchain] [--encrypt yes] [--trust-server-certificate] [--sql-user u]
  setup_db.py setup ... --service-sid S-1-5-80-... --service-sid S-1-5-80-...
  setup_db.py drop  ...

SQL şifresi komut satırında değil, SMARTCHAIN_INSTALL_SQL_PASSWORD ortam değişkeninde gelir.
"""
import argparse
import os
import re
import secrets
import struct
import sys
from pathlib import Path
from urllib.parse import quote_plus

DRIVER = "ODBC Driver 18 for SQL Server"
COLLATION = "Latin1_General_100_CI_AS_SC"
APP_ROLE = "smartchain_app"  # K-109
SQL_APP_LOGIN = "smartchain_app"
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
    """Servis hesaplarına login ve veritabanı kullanıcısı; yetkiyi apply_app_permissions verir (K-109). Ad, SID'den sunucunun dilinde çözülür."""
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
    return names


def app_role_statements() -> list[str]:
    """Uygulama rolü (K-109): okur ve yazar; denetim izinde güncelleme ve silme yok. TRUNCATE ve DDL zaten yok."""
    role = quote_name(APP_ROLE)
    return [f"IF DATABASE_PRINCIPAL_ID(N'{APP_ROLE}') IS NULL CREATE ROLE {role}",
            f"ALTER ROLE db_datareader ADD MEMBER {role}",
            f"ALTER ROLE db_datawriter ADD MEMBER {role}",
            f"DENY UPDATE, DELETE ON adm.AuditLog TO {role}"]


def app_role_drop_statements() -> list[str]:
    role = quote_name(APP_ROLE)
    return [f"IF DATABASE_PRINCIPAL_ID(N'{APP_ROLE}') IS NOT NULL ALTER ROLE db_datareader DROP MEMBER {role}",
            f"IF DATABASE_PRINCIPAL_ID(N'{APP_ROLE}') IS NOT NULL ALTER ROLE db_datawriter DROP MEMBER {role}",
            f"DROP ROLE IF EXISTS {role}"]


def apply_app_permissions(db_odbc: str, sids: list[str] = (), users: list[str] = ()) -> list[str]:
    """Geçişlerden sonra: rol kurulur, servis hesapları role girer, db_owner'dan çıkar (yükseltmede de) (K-109)."""
    refuse_in_tests(_database_of(db_odbc))
    members = list(users)
    with _connect(db_odbc) as db:
        for statement in app_role_statements():
            db.execute(statement)
        for sid in sids:
            row = db.execute("SELECT name FROM sys.database_principals WHERE sid = ?", sid_to_bytes(sid)).fetchone()
            if row is None:
                raise RuntimeError(f"Servis hesabının ({sid}) veritabanı kullanıcısı yok.")
            members.append(row[0])
        for user in members:
            db.execute(f"ALTER ROLE {quote_name(APP_ROLE)} ADD MEMBER {quote_name(user)}")
            if user in _role_members(db, "db_owner"):
                db.execute(f"ALTER ROLE db_owner DROP MEMBER {quote_name(user)}")
    return members


def new_app_password() -> str:
    """SQL Server parola kuralına uyar; tırnak yok, komuta güvenle girer."""
    return "Sc1!" + secrets.token_hex(16)


def ensure_sql_app_login(master_odbc: str, db_odbc: str) -> str:
    """SQL kimliğiyle kurulumda ayrı uygulama hesabı (K-109): kurulum hesabı yönetici yetkili kalır. Şifreyi döndürür, yazdırmaz."""
    refuse_in_tests(_database_of(db_odbc))
    password = new_app_password()
    name = quote_name(SQL_APP_LOGIN)
    with _connect(master_odbc) as master:
        verb = "ALTER" if master.execute("SELECT 1 FROM sys.server_principals WHERE name = ?", SQL_APP_LOGIN).fetchone() else "CREATE"
        master.execute(f"{verb} LOGIN {name} WITH PASSWORD = N'{password}'")
    with _connect(db_odbc) as db:
        if db.execute("SELECT 1 FROM sys.database_principals WHERE name = ?", SQL_APP_LOGIN).fetchone() is None:
            db.execute(f"CREATE USER {name} FOR LOGIN {name}")
    return password


def write_env_db_url(env_file: Path, url: str) -> None:
    """smartchain.env'deki bağlantıyı değiştirir; başka satıra ve dosyanın yetkilerine dokunmaz. URL yazdırılmaz."""
    raw = env_file.read_bytes().decode("utf-8")
    new, n = re.subn(r"(?m)^SMARTCHAIN_DB_URL=[^\r\n]*", lambda _: f"SMARTCHAIN_DB_URL={url}", raw)
    if n != 1:
        raise RuntimeError(f"{env_file}: SMARTCHAIN_DB_URL satırı bulunamadı.")
    env_file.write_bytes(new.encode("utf-8"))


def _role_members(conn, role: str) -> list[str]:
    """Rolün üyeleri, veritabanı kayıtlarından: Windows hesabını sormaz (sanal servis hesabında IS_ROLEMEMBER ve EXECUTE AS hata verir)."""
    return [r[0] for r in conn.execute(
        "SELECT u.name FROM sys.database_role_members m JOIN sys.database_principals r ON r.principal_id = m.role_principal_id "
        "JOIN sys.database_principals u ON u.principal_id = m.member_principal_id WHERE r.name = ?", role).fetchall()]


def audit_permission_problems(conn) -> list[str]:
    """Duman testi (K-109): uygulama hesabında denetim izi için UPDATE ve DELETE yok, db_owner değil. conn: pyodbc bağlantısı.

    Yönetici bağlantısında yetki kayıtları okunur; uygulama hesabıyla bağlıysa (SQL kimliği) kendi yetkisine bakılır.
    """
    admin = conn.execute("SELECT CASE WHEN IS_SRVROLEMEMBER('sysadmin') = 1 OR IS_MEMBER('db_owner') = 1 THEN 1 ELSE 0 END").fetchone()[0]
    if not admin:
        who = conn.execute("SELECT USER_NAME()").fetchone()[0]
        have = {r[0] for r in conn.execute(
            "SELECT permission_name FROM fn_my_permissions('adm.AuditLog', 'OBJECT') WHERE subentity_name = ''").fetchall()}
        return [f"{who}: {p} yetkisi var" for p in ("UPDATE", "DELETE") if p in have] + \
               [f"{who}: {p} yetkisi yok" for p in ("SELECT", "INSERT") if p not in have]
    members = _role_members(conn, APP_ROLE)
    if not members:
        return [f"{APP_ROLE} rolünde hesap yok"]
    denied = {r[0] for r in conn.execute(
        "SELECT permission_name FROM sys.database_permissions WHERE state = 'D' AND major_id = OBJECT_ID('adm.AuditLog') "
        "AND grantee_principal_id = DATABASE_PRINCIPAL_ID(?)", APP_ROLE).fetchall()}
    owners = set(_role_members(conn, "db_owner"))
    return [f"{APP_ROLE}: {p} engeli yok" for p in ("UPDATE", "DELETE") if p not in denied] + \
           [f"{user}: db_owner" for user in members if user in owners]


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
    p.add_argument("--env-file", default="", help="setup, SQL kimliği: uygulama hesabının bağlantısının yazılacağı smartchain.env")
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
        if a.sql_user:  # K-109: servisler kurulum hesabıyla değil, ayrı uygulama hesabıyla bağlanır
            app_password = ensure_sql_app_login(master_odbc, db_odbc)
            apply_app_permissions(db_odbc, users=[SQL_APP_LOGIN])
            if a.env_file:
                write_env_db_url(Path(a.env_file), sqlalchemy_url(odbc_string(
                    a.instance, a.database, encrypt=a.encrypt, trust_server_certificate=a.trust_server_certificate,
                    sql_user=SQL_APP_LOGIN, sql_password=app_password)))
            print(f"Uygulama hesabı hazır: {SQL_APP_LOGIN}")
        else:
            apply_app_permissions(db_odbc, sids=a.service_sid)
            print(f"Uygulama rolü hazır: {APP_ROLE}")
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

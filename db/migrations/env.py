"""Alembic ortamı. Bağlantı: SMARTCHAIN_DB_URL.

Geri alma (downgrade) adı _test ile bitmeyen veritabanında onay ister (K-165, `db/guard.py`): mevcut geçiş gösterilir, yalnız etkileşimli
terminalde veritabanının adı yazılınca çalışır; komut zincirinde durur. Bağlantısız --sql çıktısı etkilenmez.
"""
import os
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool, text
from sqlalchemy.engine import make_url

from models import metadata, SCHEMAS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # db/guard.py
import guard  # noqa: E402

URL = os.environ.get(
    "SMARTCHAIN_DB_URL",
    "mssql+pyodbc://@localhost/Smartchain?driver=ODBC+Driver+18+for+SQL+Server"
    "&trusted_connection=yes&TrustServerCertificate=yes",
)


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name in SCHEMAS
    return True


def run_offline():
    context.configure(url=URL, target_metadata=metadata, literal_binds=True,
                      include_schemas=True, include_name=include_name,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


ACTION = "Geçişi geri alma (alembic downgrade)"


def is_downgrade() -> bool:
    """Komut downgrade mı: alembic komutu EnvironmentContext'e fn ile verir (programla çağrıda da), komut satırında cmd_opts."""
    fn = getattr(getattr(context, "_proxy", None), "context_opts", {}).get("fn")
    cmd = getattr(context.config.cmd_opts, "cmd", None)
    return getattr(fn, "__name__", "") == "downgrade" or bool(cmd and getattr(cmd[0], "__name__", "") == "downgrade")


def current_revision(conn) -> str:
    try:
        return conn.execute(text("SELECT version_num FROM dbo.alembic_version")).scalar() or "yok"
    except Exception:  # tablo yoksa
        return "yok"


def run_online():
    database = make_url(URL).database
    downgrade = is_downgrade()
    try:
        if downgrade:
            guard.require_terminal(database, ACTION)  # terminal yoksa bağlanmadan durur
        engine = create_engine(URL, poolclass=pool.NullPool)
        with engine.connect() as conn:
            if downgrade:
                guard.confirm(database, ACTION, f"geçiş {current_revision(conn)}")
            _migrate(conn)
    except guard.Refused as exc:
        print(exc, file=sys.stderr)
        raise


def _migrate(conn):
    context.configure(connection=conn, target_metadata=metadata, include_schemas=True,
                      include_name=include_name,
                      compare_type=True, compare_server_default=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()

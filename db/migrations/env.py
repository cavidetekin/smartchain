"""Alembic ortamı. Bağlantı: SMARTCHAIN_DB_URL."""
import os

from alembic import context
from sqlalchemy import create_engine, pool

from models import metadata, SCHEMAS

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


def run_online():
    engine = create_engine(URL, poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=metadata, include_schemas=True,
                          include_name=include_name,
                          compare_type=True, compare_server_default=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()

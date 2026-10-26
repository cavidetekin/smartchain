"""Sağlık kontrolü için veritabanı sorguları."""
from sqlalchemy import text
from sqlalchemy.orm import Session


def read_schema_version(session: Session) -> str | None:
    row = session.execute(text("SELECT TOP 1 version_num FROM dbo.alembic_version")).first()
    return row[0] if row else None


def read_server_version(session: Session) -> str:
    return session.execute(text("SELECT CAST(SERVERPROPERTY('ProductVersion') AS nvarchar(50))")).scalar_one()

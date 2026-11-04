"""Sistem sağlığı sorguları (ekran 24, fonksiyon 94; K-106)."""
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.jobs.constants import STATUS_QUEUED
from app.jobs.events import ENGINE_SERVICE
from db.models import metadata

EVENT = metadata.tables["adm.SystemEvent"]


def engine_status(session: Session) -> dict | None:
    """Motorun kalp atışı ve kaç saniye önce atıldığı (veritabanı saatiyle)."""
    row = session.execute(text(
        "SELECT HeartbeatAt, StartedAt, StoppedAt, AppVersion, "
        "DATEDIFF(second, HeartbeatAt, SYSUTCDATETIME()) AS AgeSeconds FROM adm.ServiceStatus WHERE ServiceName = :n"),
        {"n": ENGINE_SERVICE}).mappings().first()
    return dict(row) if row else None


def oldest_wait_minutes(session: Session) -> int | None:
    return session.execute(text(
        "SELECT DATEDIFF(minute, MIN(CreatedAt), SYSUTCDATETIME()) FROM adm.Job WHERE Status = :queued"),
        {"queued": STATUS_QUEUED}).scalar()


def error_counts(session: Session, days: int = 7) -> tuple[int, int]:
    """(olay, sistemin çözdüğü) son `days` günde."""
    row = session.execute(text(
        "SELECT COUNT(*), ISNULL(SUM(CASE WHEN IsResolved = 1 THEN 1 ELSE 0 END), 0) FROM adm.SystemEvent "
        "WHERE OccurredAt >= DATEADD(day, -1 * :d, SYSUTCDATETIME())"), {"d": days}).one()
    return int(row[0]), int(row[1])


def database_bytes(session: Session) -> int:
    return int(session.execute(text("SELECT SUM(CAST(size AS bigint)) * 8192 FROM sys.database_files")).scalar_one())


def data_version_count(session: Session) -> int:
    return session.execute(text("SELECT COUNT(*) FROM adm.DataVersion")).scalar_one()


def database_volume(session: Session) -> tuple[int, int] | None:
    """(toplam, boş) bayt; VIEW SERVER STATE yetkisi yoksa None (K-106: kurulum paketi bu yetkiyi vermez)."""
    if not session.execute(text("SELECT HAS_PERMS_BY_NAME(NULL, NULL, 'VIEW SERVER STATE')")).scalar():
        return None
    row = session.execute(text(
        "SELECT TOP 1 vs.total_bytes, vs.available_bytes FROM sys.database_files f "
        "CROSS APPLY sys.dm_os_volume_stats(DB_ID(), f.file_id) vs ORDER BY vs.available_bytes")).first()
    return (int(row[0]), int(row[1])) if row else None


def get_event(session: Session, event_id: int) -> dict | None:
    row = session.execute(sa.select(EVENT).where(EVENT.c.Id == event_id)).mappings().first()
    return dict(row) if row else None

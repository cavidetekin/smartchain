"""Sistem sağlığı (ekran 24, fonksiyon 94; K-106): kartlar, servis durumu, olay detayı ve sistem olayı yazma."""
import logging
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app import __version__
from app.jobs import events, queue
from app.jobs.constants import CHANNEL_INTERACTIVE
from app.jobs.settings import HEALTH_DEFAULTS, read_int_settings, read_settings

from ..db import get_engine
from ..errors import AppError
from ..permissions import Access, allows
from ..repositories import system_health as repo
from ..settings import get_settings
from . import auth
from .auth import CurrentUser

log = logging.getLogger("smartchain.health")

RUNNING, SLOW, NOT_RESPONDING, STOPPED = "Çalışıyor", "Yavaş", "Yanıt vermiyor", "Kapalı"


def iso(value: datetime | None) -> str | None:
    return value.replace(tzinfo=timezone.utc).isoformat(timespec="seconds") if value else None


def engine_state(row: dict | None, heartbeat_seconds: float, timeout_seconds: float) -> str:
    """Durum saklanmaz, okurken hesaplanır (K-106)."""
    if row is None or row["StoppedAt"] is not None:
        return STOPPED
    age = row["AgeSeconds"]
    if age <= 2 * heartbeat_seconds:
        return RUNNING
    return SLOW if age <= timeout_seconds else NOT_RESPONDING


def _disk(session: Session, threshold: int) -> dict:
    """API'nin diski; veritabanının diski okunabiliyorsa ikisinden daha dolu olanı."""
    total, _, free = shutil.disk_usage(Path(get_settings().log_dir).resolve().anchor)
    volume = repo.database_volume(session)
    if volume and volume[0] and (volume[0] - volume[1]) / volume[0] > (total - free) / total:
        total, free = volume
    percent = round((total - free) * 100 / total)
    return {"percent": percent, "free_bytes": free, "threshold": threshold, "warn": percent >= threshold,
            "database_bytes": repo.database_bytes(session), "data_versions": repo.data_version_count(session)}


def _ping(session: Session) -> int:
    start = time.perf_counter()
    session.execute(text("SELECT 1")).scalar_one()
    return round((time.perf_counter() - start) * 1000)


def summary(session: Session | None, started_at: datetime, connections: int) -> dict:
    session = auth._require(session)

    def work():
        from app.engine.settings import read_engine_settings
        settings = read_settings(session)
        engine_settings = read_engine_settings(session)
        thresholds = read_int_settings(session, HEALTH_DEFAULTS)
        counters = queue.counters(session, settings)
        row = repo.engine_status(session)
        state = engine_state(row, engine_settings.heartbeat_seconds, settings.heartbeat_timeout_seconds)
        queued = sum(c["queued"] for c in counters.values())
        wait = repo.oldest_wait_minutes(session)
        events_total, resolved = repo.error_counts(session)
        pool = get_engine().pool
        return {
            "server_time": iso(queue.db_now(session)),
            "cards": {
                "queue": {"queued": queued, "oldest_wait_minutes": wait, "threshold": thresholds["QueueWaitWarnMinutes"],
                          "warn": state in (STOPPED, NOT_RESPONDING)
                          or (wait is not None and wait >= thresholds["QueueWaitWarnMinutes"])},
                "interactive": {"running": counters[CHANNEL_INTERACTIVE]["running"], "limit": counters[CHANNEL_INTERACTIVE]["limit"]},
                "errors": {"last_7_days": events_total, "resolved": resolved},
                "disk": _disk(session, thresholds["DiskWarnPercent"]),
            },
            "services": [
                {"key": "app", "status": RUNNING, "started_at": iso(started_at.replace(tzinfo=None)), "version": __version__},
                {"key": "engine", "status": state, "heartbeat_at": iso(row["HeartbeatAt"]) if row else None,
                 "version": row["AppVersion"] if row else None, "busy": sum(c["running"] for c in counters.values())},
                {"key": "database", "status": RUNNING, "ms": _ping(session),
                 "pool_in_use": pool.checkedout(), "pool_size": pool.size()},
                {"key": "notifications", "status": RUNNING, "connections": connections},
            ],
        }

    return auth._db(work)


def event_detail(session: Session | None, event_id: int, user: CurrentUser) -> dict:
    """Teknik özet yalnız System owner'a (K-106; 96 okuma)."""
    session = auth._require(session)

    def work():
        row = repo.get_event(session, event_id)
        if row is None:
            raise AppError("event_not_found", "Kayıt bulunamadı.", 404)
        return {"id": row["Id"], "occurred_at": iso(row["OccurredAt"]), "component": row["Component"], "message": row["Message"],
                "resolution": row["Resolution"], "is_resolved": row["IsResolved"], "job_id": row["JobId"],
                "trace_id": row["TraceId"], "detail": row["Detail"] if allows(user.role, 96, Access.READ) else None}

    return auth._db(work)


def record_unexpected(method: str, path: str, exc: Exception, trace_id: str) -> None:
    """Beklenmeyen API hatası (500). Kendi oturumunda; yazılamazsa cevap yine verilir. İstisna metni yazılmaz (parametre taşıyabilir)."""
    try:
        with sessionmaker(bind=get_engine())() as session:
            events.record(session, events.COMPONENT_APP, f"Beklenmeyen hata · {method} {path}", "Takip numarası verildi",
                          trace_id=trace_id, detail=type(exc).__name__)
            session.commit()
    except Exception as err:
        log.warning("Beklenmeyen hata sistem olayına yazılamadı: %s", err)

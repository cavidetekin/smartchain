"""Sistem sağlığı eşikleri ve hataların saklanma süresi (fonksiyon 96, K-106). Form ve kurallar Giriş ve oturum ile aynıdır."""
from sqlalchemy.orm import Session

from app.jobs.settings import HEALTH_DEFAULTS, IMPORT_DEFAULTS, read_int_settings

from . import auth, login_policy
from .auth import CurrentUser

LIMITS = {"DiskWarnPercent": (1, 99), "QueueWaitWarnMinutes": (1, 1440), "SystemEventRetentionDays": (7, 3650),
          "ImportSyncMaxMb": (1, 100), "ImportMaxMb": (1, 100), "ImportMaxRows": (1000, 1000000)}  # K-129: Excel yükleme


DEFAULTS = {**HEALTH_DEFAULTS, **IMPORT_DEFAULTS}


def _current(session: Session) -> dict[str, int]:
    return read_int_settings(session, DEFAULTS)


def read(session: Session | None) -> dict:
    session = auth._require(session)

    def work():
        return {"values": _current(session), "defaults": dict(DEFAULTS),
                "limits": {k: {"min": lo, "max": hi} for k, (lo, hi) in LIMITS.items()}}

    return auth._db(work)


def update(session: Session | None, actor: CurrentUser, changes: dict[str, int]) -> dict:
    session = auth._require(session)

    def work():
        login_policy.apply_changes(session, actor, _current(session), changes, LIMITS)

    auth._db(work)
    return read(session)

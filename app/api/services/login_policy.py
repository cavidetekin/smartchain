"""Şifre ve oturum ayarları (fonksiyon 96, K-105): 2.1'in SystemSetting anahtarları. Değişiklik denetim izine yazılır.

Şifre kuralları bir sonraki şifre değişiminde (K-98), giriş ve oturum ayarları hemen geçerli olur: her istekte okunur.
"""
from sqlalchemy.orm import Session

from app.jobs.settings import read_int_settings

from ..errors import AppError
from ..repositories import audit, auth as auth_repo, settings as repo
from . import auth
from .auth import CurrentUser

ACTION = "Ayar değişikliği"
OBJECT = "SystemSetting"
FLAG = "PasswordRequireLetterAndDigit"
IDLE, WARNING = "SessionIdleMinutes", "SessionWarningMinutes"

# (en az, en çok). read_policy 1'in altını varsayılana çevirdiği için alt sınır en az 1.
LIMITS = {
    "PasswordMinLength": (8, 128), FLAG: (0, 1), "PasswordHistoryCount": (1, 24), "PasswordMaxAgeDays": (1, 3650),
    "LoginMaxFailedAttempts": (1, 20), "LoginLockMinutes": (1, 1440), IDLE: (1, 1440), WARNING: (1, 1439),
}


def _public(values: dict[str, int]) -> dict:
    return {k: bool(v) if k == FLAG else v for k, v in values.items()}


def _current(session: Session) -> dict[str, int]:
    return read_int_settings(session, auth_repo._DEFAULTS, minimum=0)


def read(session: Session | None) -> dict:
    session = auth._require(session)

    def work():
        return {"values": _public(_current(session)), "defaults": _public(auth_repo._DEFAULTS),
                "limits": {k: {"min": lo, "max": hi} for k, (lo, hi) in LIMITS.items() if k != FLAG}}

    return auth._db(work)


def apply_changes(session: Session, actor: CurrentUser, current: dict[str, int], changes: dict[str, int],
                  limits: dict[str, tuple[int, int]], problems: list[dict] | None = None) -> None:
    """Yalnız değişen anahtarlar yazılır; her biri için ayrı iz. Sınır dışı değerde hiçbiri yazılmaz."""
    problems = [{"field": k, "problem": f"En az {limits[k][0]}, en çok {limits[k][1]}."}
                for k, v in changes.items() if not limits[k][0] <= v <= limits[k][1]] + (problems or [])
    if problems:
        raise AppError("validation", "Girilen bilgiler geçersiz.", 422, problems)
    for key, value in changes.items():
        if value != current[key]:
            repo.set_setting(session, key, str(value))
            audit.write_audit(session, ACTION, actor.id, OBJECT, key, {"Value": value}, {"Value": current[key]})
    session.commit()


def update(session: Session | None, actor: CurrentUser, changes: dict[str, int]) -> dict:
    session = auth._require(session)

    def work():
        current = _current(session)
        merged = {**current, **changes}
        cross = [{"field": WARNING, "problem": "Uyarı süresi oturumun kapandığı süreden kısa olmalı."}] if merged[WARNING] >= merged[IDLE] else []
        apply_changes(session, actor, current, changes, LIMITS, cross)

    auth._db(work)
    return read(session)

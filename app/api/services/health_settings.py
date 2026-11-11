"""Sistem sağlığı eşikleri, hataların saklanma süresi, ham verinin saklama süresi (fonksiyon 96, K-106, K-156). Form ve kurallar Giriş ve oturum
ile aynıdır; ham verinin saklama süresinin varsayılanı yoktur, boş bırakılabilir (boşsa temizlik çalışmaz, K-138).
"""
from sqlalchemy.orm import Session

from app.cleanup import raw

from app.jobs.settings import HEALTH_DEFAULTS, IMPORT_DEFAULTS, read_int_settings

from ..errors import AppError
from ..repositories import audit, settings as repo
from . import auth, login_policy
from .auth import CurrentUser

LIMITS = {"DiskWarnPercent": (1, 99), "QueueWaitWarnMinutes": (1, 1440), "SystemEventRetentionDays": (7, 3650),
          "ImportSyncMaxMb": (1, 100), "ImportMaxMb": (1, 100), "ImportMaxRows": (1000, 1000000),  # K-129: Excel yükleme
          raw.SETTING_KEY: raw.LIMITS}  # K-156: ham veri temizliği
OPTIONAL = (raw.SETTING_KEY,)  # varsayılanı yok; boş = ayar satırı yok


DEFAULTS = {**HEALTH_DEFAULTS, **IMPORT_DEFAULTS}  # zamanlanmış işlerin bekleme süreleri kendi sekmesinde (K-164)


def _current(session: Session) -> dict[str, int | None]:
    return {**read_int_settings(session, DEFAULTS), raw.SETTING_KEY: raw.retention_days(session)}


def read(session: Session | None) -> dict:
    session = auth._require(session)

    def work():
        return {"values": _current(session), "defaults": {**DEFAULTS, raw.SETTING_KEY: None}, "optional": list(OPTIONAL),
                "limits": {k: {"min": lo, "max": hi} for k, (lo, hi) in LIMITS.items()}}

    return auth._db(work)


def update(session: Session | None, actor: CurrentUser, changes: dict[str, int | None]) -> dict:
    """Boş değer yalnız isteğe bağlı ayarda (ayar satırı silinir, izi yazılır); öteki ayarlarda 422."""
    session = auth._require(session)

    def work():
        missing = [{"field": k, "problem": "Boş bırakılamaz."} for k, v in changes.items() if v is None and k not in OPTIONAL]
        if missing:
            raise AppError("validation", "Girilen bilgiler geçersiz.", 422, missing)
        current = _current(session)
        for key in [k for k, v in changes.items() if v is None]:
            if current[key] is not None:
                repo.delete_setting(session, key)
                audit.write_audit(session, login_policy.ACTION, actor.id, login_policy.OBJECT, key, {"Value": None}, {"Value": current[key]})
        login_policy.apply_changes(session, actor, current, {k: v for k, v in changes.items() if v is not None}, LIMITS)

    auth._db(work)
    return read(session)

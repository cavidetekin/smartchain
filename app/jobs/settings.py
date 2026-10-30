"""İş kuyruğu ayarları: adm.SystemSetting'den okunur, satır yoksa ya da değer bozuksa varsayılan geçerlidir (K-68)."""
import logging
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from .constants import CHANNEL_EXPORT, CHANNEL_INTERACTIVE, CHANNEL_NIGHT

log = logging.getLogger("smartchain.jobs")

DEFAULTS = {
    "JobLimitInteractive": 3,
    "JobLimitNight": 2,
    "JobLimitExport": 2,
    "JobHeartbeatTimeoutSeconds": 120,
    "JobMaxAttempts": 2,
}


@dataclass(frozen=True)
class JobSettings:
    limit_interactive: int = DEFAULTS["JobLimitInteractive"]
    limit_night: int = DEFAULTS["JobLimitNight"]
    limit_export: int = DEFAULTS["JobLimitExport"]
    heartbeat_timeout_seconds: int = DEFAULTS["JobHeartbeatTimeoutSeconds"]
    max_attempts: int = DEFAULTS["JobMaxAttempts"]

    def limit(self, channel: str) -> int:
        return {CHANNEL_INTERACTIVE: self.limit_interactive, CHANNEL_NIGHT: self.limit_night,
                CHANNEL_EXPORT: self.limit_export}[channel]


def read_int_settings(session: Session, defaults: dict[str, int], minimum: int = 1) -> dict[str, int]:
    """SystemSetting'den tamsayı ayarları (en az `minimum`; 1/0 bayrakları için 0); satır yoksa ya da bozuksa varsayılan."""
    rows = session.execute(
        text("SELECT SettingKey, Value FROM adm.SystemSetting WHERE SettingKey IN :keys")
        .bindparams(bindparam("keys", expanding=True)),
        {"keys": list(defaults)},
    ).all()
    values = dict(defaults)
    for key, raw in rows:
        try:
            value = int(raw)
            if value < minimum:
                raise ValueError
            values[key] = value
        except (TypeError, ValueError):
            log.warning("SystemSetting %s geçersiz (%r); varsayılan %s kullanılıyor", key, raw, defaults[key])
    return values


def read_settings(session: Session) -> JobSettings:
    values = read_int_settings(session, DEFAULTS)
    return JobSettings(
        limit_interactive=values["JobLimitInteractive"],
        limit_night=values["JobLimitNight"],
        limit_export=values["JobLimitExport"],
        heartbeat_timeout_seconds=values["JobHeartbeatTimeoutSeconds"],
        max_attempts=values["JobMaxAttempts"],
    )

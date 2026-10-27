"""İş kuyruğu ayarları: adm.SystemSetting'den okunur, satır yoksa ya da değer bozuksa varsayılan geçerlidir (K-68)."""
import logging
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from .constants import CHANNEL_INTERACTIVE, CHANNEL_NIGHT

log = logging.getLogger("smartchain.jobs")

DEFAULTS = {
    "JobLimitInteractive": 3,
    "JobLimitNight": 2,
    "JobHeartbeatTimeoutSeconds": 120,
    "JobMaxAttempts": 2,
}


@dataclass(frozen=True)
class JobSettings:
    limit_interactive: int = DEFAULTS["JobLimitInteractive"]
    limit_night: int = DEFAULTS["JobLimitNight"]
    heartbeat_timeout_seconds: int = DEFAULTS["JobHeartbeatTimeoutSeconds"]
    max_attempts: int = DEFAULTS["JobMaxAttempts"]

    def limit(self, channel: str) -> int:
        return {CHANNEL_INTERACTIVE: self.limit_interactive, CHANNEL_NIGHT: self.limit_night}[channel]


def read_settings(session: Session) -> JobSettings:
    rows = session.execute(
        text("SELECT SettingKey, Value FROM adm.SystemSetting WHERE SettingKey IN :keys")
        .bindparams(bindparam("keys", expanding=True)),
        {"keys": list(DEFAULTS)},
    ).all()
    values = dict(DEFAULTS)
    for key, raw in rows:
        try:
            value = int(raw)
            if value < 1:
                raise ValueError
            values[key] = value
        except (TypeError, ValueError):
            log.warning("SystemSetting %s geçersiz (%r); varsayılan %s kullanılıyor", key, raw, DEFAULTS[key])
    return JobSettings(
        limit_interactive=values["JobLimitInteractive"],
        limit_night=values["JobLimitNight"],
        heartbeat_timeout_seconds=values["JobHeartbeatTimeoutSeconds"],
        max_attempts=values["JobMaxAttempts"],
    )

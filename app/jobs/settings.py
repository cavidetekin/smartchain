"""İş kuyruğu ayarları: adm.SystemSetting'den okunur, satır yoksa ya da değer bozuksa varsayılan geçerlidir (K-68)."""
import logging
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from .constants import CHANNEL_EXCEL, CHANNEL_INTERACTIVE, CHANNEL_NIGHT, CHANNEL_PROCESSING, CHANNEL_PULL

log = logging.getLogger("smartchain.jobs")

DEFAULTS = {
    "JobLimitInteractive": 3,
    "JobLimitNight": 2,
    "JobLimitExport": 2,
    "JobLimitPull": 1,
    "JobLimitProcessing": 4,  # K-134: ölçüm docs/08 (1: 70,2 · 2: 60,5 · 4: 58,3 · 8: 55,5 sn)
    "JobHeartbeatTimeoutSeconds": 120,
    "JobMaxAttempts": 2,
}


# Sistem sağlığı (K-106): eşikler ve hataların saklanma süresi (gün)
HEALTH_DEFAULTS = {"DiskWarnPercent": 85, "QueueWaitWarnMinutes": 10, "SystemEventRetentionDays": 90}
# Excel yükleme (K-129): ölçüme göre 5 MB'a kadar istek içinde (docs/08)
IMPORT_DEFAULTS = {"ImportSyncMaxMb": 5, "ImportMaxMb": 100, "ImportMaxRows": 200000}


@dataclass(frozen=True)
class JobSettings:
    limit_interactive: int = DEFAULTS["JobLimitInteractive"]
    limit_night: int = DEFAULTS["JobLimitNight"]
    limit_export: int = DEFAULTS["JobLimitExport"]
    limit_pull: int = DEFAULTS["JobLimitPull"]
    limit_processing: int = DEFAULTS["JobLimitProcessing"]
    heartbeat_timeout_seconds: int = DEFAULTS["JobHeartbeatTimeoutSeconds"]
    max_attempts: int = DEFAULTS["JobMaxAttempts"]

    def limit(self, channel: str) -> int:
        return {CHANNEL_INTERACTIVE: self.limit_interactive, CHANNEL_NIGHT: self.limit_night,
                CHANNEL_EXCEL: self.limit_export, CHANNEL_PULL: self.limit_pull,
                CHANNEL_PROCESSING: self.limit_processing}[channel]


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
        limit_pull=values["JobLimitPull"],
        limit_processing=values["JobLimitProcessing"],
        heartbeat_timeout_seconds=values["JobHeartbeatTimeoutSeconds"],
        max_attempts=values["JobMaxAttempts"],
    )

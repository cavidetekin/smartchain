"""Motor servisi ayarları: adm.SystemSetting, satır yoksa varsayılan (K-71, fonksiyon 34)."""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.jobs.constants import CHANNEL_INTERACTIVE, CHANNEL_NIGHT
from app.jobs.settings import read_int_settings

DEFAULTS = {
    "EngineTimeBudgetInteractiveSeconds": 180,
    "EngineTimeBudgetNightSeconds": 1800,
    "EngineKillGraceSeconds": 60,
    "EngineHeartbeatSeconds": 15,
}


@dataclass(frozen=True)
class EngineSettings:
    time_budget_interactive: float = DEFAULTS["EngineTimeBudgetInteractiveSeconds"]
    time_budget_night: float = DEFAULTS["EngineTimeBudgetNightSeconds"]
    kill_grace: float = DEFAULTS["EngineKillGraceSeconds"]
    heartbeat_seconds: float = DEFAULTS["EngineHeartbeatSeconds"]

    def time_budget(self, channel: str) -> float:
        return {CHANNEL_INTERACTIVE: self.time_budget_interactive, CHANNEL_NIGHT: self.time_budget_night}[channel]


def read_engine_settings(session: Session) -> EngineSettings:
    v = read_int_settings(session, DEFAULTS)
    return EngineSettings(
        time_budget_interactive=v["EngineTimeBudgetInteractiveSeconds"],
        time_budget_night=v["EngineTimeBudgetNightSeconds"],
        kill_grace=v["EngineKillGraceSeconds"],
        heartbeat_seconds=v["EngineHeartbeatSeconds"],
    )

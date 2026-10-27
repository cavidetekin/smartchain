"""Uygulama ayarları. Ortam değişkenlerinden (SMARTCHAIN_*) ya da kök klasördeki .env dosyasından okunur."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DB_URL = (
    "mssql+pyodbc://@localhost/Smartchain?driver=ODBC+Driver+18+for+SQL+Server"
    "&trusted_connection=yes&TrustServerCertificate=yes"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SMARTCHAIN_", env_file=ROOT / ".env", extra="ignore")

    db_url: str = DEFAULT_DB_URL
    log_dir: Path = ROOT / "logs"
    log_level: str = "INFO"
    log_retention_days: int = 30
    db_connect_timeout: int = 5
    # API belgesi (/api/docs) dışarıdan JS yükler; kapalı ağ kuralı gereği yalnız geliştirmede açılır.
    enable_docs: bool = False
    # İş kuyruğunu izleme aralığı (sn); değişen iş sahibine WebSocket'le iletilir (K-69). 0: izleme kapalı.
    job_watch_seconds: float = 1.0


@lru_cache
def get_settings() -> Settings:
    return Settings()

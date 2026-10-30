"""Uygulama ayarları. Sıra (sonraki ezer): kök klasördeki .env → SMARTCHAIN_CONFIG dosyası → ortam değişkenleri (SMARTCHAIN_*).

Kurulumda servisler SMARTCHAIN_CONFIG ile ProgramData altındaki smartchain.env'i okur (docs/10-kurulum.md).
"""
import os
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
    # Arka planda hazırlanan Excel dosyaları (K-93); motor servisi yazar, API okur, süresi geçince servis siler.
    export_dir: Path = ROOT / "exports"
    # Oturum çerezi (K-97) yalnız HTTPS'te gider. HTTPS'siz test kurulumunda ve testlerde false.
    session_cookie_secure: bool = True
    # Durum değiştiren isteklerde izin verilen Origin'ler, virgülle (ör. http://localhost:5173). Boşsa Origin'in
    # host'u isteğin Host'u olmalı (K-97).
    allowed_origins: str = ""

    def origins(self) -> set[str]:
        return {o.strip().rstrip("/").lower() for o in self.allowed_origins.split(",") if o.strip()}


def config_files() -> tuple[Path, ...]:
    extra = os.environ.get("SMARTCHAIN_CONFIG")
    return (ROOT / ".env", Path(extra)) if extra else (ROOT / ".env",)


@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=config_files())

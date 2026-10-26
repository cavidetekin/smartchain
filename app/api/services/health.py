"""Sağlık kontrolü: uygulama ayakta mı, veritabanına bağlanılıyor mu, şema sürümü kodla uyumlu mu."""
import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.orm import Session

from app import __version__
from ..repositories import health as repo
from ..settings import ROOT

log = logging.getLogger("smartchain.health")


@lru_cache
def expected_schema_version() -> str | None:
    """Koddaki en son geçiş (Alembic head)."""
    cfg = Config(str(ROOT / "db" / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(ROOT / "db" / "migrations")))
    return ScriptDirectory.from_config(cfg).get_current_head()


def check(session: Session | None) -> dict:
    expected = expected_schema_version()
    db = {"connected": False, "schema_version": None, "expected_schema_version": expected,
          "server_version": None, "message": None}
    if session is None:
        db["message"] = ("Veritabanı sürücüsü yüklenemedi. 'ODBC Driver 18 for SQL Server' kurulu mu, "
                         "bağlantı ayarı (SMARTCHAIN_DB_URL) doğru mu?")
    else:
        try:
            db["schema_version"] = repo.read_schema_version(session)
            db["server_version"] = repo.read_server_version(session)
            db["connected"] = True
        except Exception as exc:  # bağlantı hatası sağlık cevabında anlatılır, 500 dönmez
            log.warning("Veritabanına bağlanılamadı: %s", exc)
            db["message"] = "Veritabanına bağlanılamadı. Bağlantı ayarını ve SQL Server servisini kontrol edin."
    if db["connected"] and db["schema_version"] != expected:
        db["message"] = (f"Veritabanı şeması {db['schema_version']}, uygulama {expected} bekliyor. "
                         "Güncelleme gerekiyor: alembic -c db/alembic.ini upgrade head")
    ok = db["connected"] and db["schema_version"] == expected
    return {
        "status": "ok" if ok else "degraded",
        "app_version": __version__,
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "database": db,
    }

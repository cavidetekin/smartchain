"""Dışa aktarım sorguları (K-91): ayarlar, dışa aktaran kullanıcı, iz (adm.AuditLog)."""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.jobs.settings import read_int_settings
from db.models import metadata
from . import audit

USER = metadata.tables["adm.AppUser"]
ACTION = "Dışa aktarım"

DEFAULTS = {"ExportSyncMaxRows": 10000, "ExportMaxRows": 500000, "ExportFileHours": 24}


def read_settings(session: Session) -> dict[str, int]:
    """SystemSetting: anlık eşik, üst sınır, dosya saklama süresi (docs/02)."""
    return read_int_settings(session, DEFAULTS)


def user_name(session: Session, user_id: int) -> str | None:
    row = session.execute(sa.select(sa.func.coalesce(USER.c.FullName, USER.c.UserName)).where(USER.c.Id == user_id)).first()
    return row[0] if row else None


def write_audit(session: Session, user_id: int, list_name: str, file_name: str, details: dict) -> None:
    """İz (fonksiyon 87): commit çağırana bırakılır; dosya ancak iz yazılınca verilir."""
    audit.write_audit(session, ACTION, user_id, list_name, file_name, details)

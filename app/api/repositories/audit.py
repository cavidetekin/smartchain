"""Denetim izi (adm.AuditLog; fonksiyon 98'in çekirdeği): kim, ne zaman, neyi. Yalnız eklenir; commit çağırana bırakılır."""
import json
import logging

import sqlalchemy as sa
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.jobs import events
from db.models import metadata

from ..errors import AppError

log = logging.getLogger("smartchain.audit")

AUDIT = metadata.tables["adm.AuditLog"]
ROLLED_BACK = "İşlem geri alındı"


def _insert(session: Session, values: dict) -> None:
    session.execute(sa.insert(AUDIT).values(**values))


def _record_failure(session: Session, action: str, exc: Exception) -> None:
    """İz yazılamadı: asıl işlem geri alınır, kendi oturumunda sistem olayı (K-108). Veritabanı kapalıysa yalnız log."""
    session.rollback()
    log.error("Denetim kaydı yazılamadı (%s): %s", action, exc)
    try:
        with Session(session.get_bind()) as s:
            events.record(s, events.COMPONENT_AUDIT, f"Denetim kaydı yazılamadı · {action}", ROLLED_BACK, detail=type(exc).__name__)
            s.commit()
    except Exception as err:
        log.warning("Sistem olayı da yazılamadı: %s", err)


def write_audit(session: Session, action: str, user_id: int | None, object_type: str | None = None,
                object_key: str | None = None, new_value: dict | None = None, old_value: dict | None = None) -> None:
    """Asıl işlemle aynı veritabanı işleminde yazılır (K-108); yazılamazsa işlem geri alınır, 503 audit_failed."""
    try:
        _insert(session, dict(
            UserId=user_id, At=sa.func.sysutcdatetime(), Action=action, ObjectType=object_type,
            ObjectKey=object_key[:200] if object_key else object_key,
            OldValue=json.dumps(old_value, ensure_ascii=False, default=str) if old_value is not None else None,
            NewValue=json.dumps(new_value, ensure_ascii=False, default=str) if new_value is not None else None))
    except DBAPIError as exc:
        _record_failure(session, action, exc)
        raise AppError("audit_failed", "İşlem yapılamadı: denetim kaydı yazılamadı.", 503) from exc

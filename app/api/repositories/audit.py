"""Denetim izi (adm.AuditLog; fonksiyon 98'in çekirdeği): kim, ne zaman, neyi. Yalnız eklenir; commit çağırana bırakılır."""
import json

import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata

AUDIT = metadata.tables["adm.AuditLog"]


def write_audit(session: Session, action: str, user_id: int | None, object_type: str | None = None,
                object_key: str | None = None, new_value: dict | None = None) -> None:
    session.execute(sa.insert(AUDIT).values(
        UserId=user_id, At=sa.func.sysutcdatetime(), Action=action, ObjectType=object_type,
        ObjectKey=object_key[:200] if object_key else object_key,
        NewValue=json.dumps(new_value, ensure_ascii=False, default=str) if new_value is not None else None))

"""Yok say ve Yok saymayı kaldır (fonksiyon 21, K-174): gerekçe zorunlu, toplu; kayıt değişene kadar geçerli; denetim izine."""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata

from . import STATE_IGNORED, STATE_NEW, STATE_OPEN
from .run import reopen_changed

W = metadata.tables["adm.DataQualityWarning"]
ACTION_IGNORE, ACTION_UNIGNORE = "Veri kalitesi: uyarı yok sayıldı", "Veri kalitesi: yok sayma kaldırıldı"  # AuditLog.Action en çok 40
OBJECT = "Veri kalitesi uyarısı"
MAX_LISTED = 20


def _labels(session: Session, ids: list[int]) -> list[str]:
    rows = session.execute(sa.select(W.c.RuleName, W.c.RecordLabel).where(W.c.Id.in_(ids)).order_by(W.c.Id).limit(MAX_LISTED)).all()
    return [f"{r.RuleName} · {r.RecordLabel}" for r in rows]


def ignore(session: Session, user_id: int, ids: list[int], reason: str) -> int:
    """Seçilen uyarılar Yok sayıldı; tek gerekçe hepsine. Değişen sayısı. Commit etmez."""
    from app.api.repositories import audit
    now = sa.func.sysutcdatetime()
    n = session.execute(sa.update(W).where(W.c.Id.in_(ids), W.c.State.in_((STATE_NEW, STATE_OPEN)))
                        .values(State=STATE_IGNORED, IgnoreReason=reason[:400], IgnoredBy=user_id, IgnoredAt=now)).rowcount
    if n:
        audit.write_audit(session, ACTION_IGNORE, user_id, OBJECT, f"{n} uyarı", {"reason": reason, "warnings": _labels(session, ids), "count": n})
    return n


def unignore(session: Session, user_id: int, ids: list[int]) -> int:
    from app.api.repositories import audit
    labels = _labels(session, ids)
    n = session.execute(sa.update(W).where(W.c.Id.in_(ids), W.c.State == STATE_IGNORED)
                        .values(State=STATE_OPEN, IgnoreReason=None, IgnoredBy=None, IgnoredAt=None)).rowcount
    if n:
        audit.write_audit(session, ACTION_UNIGNORE, user_id, OBJECT, f"{n} uyarı", {"warnings": labels, "count": n})
    return n


def reopen_record(session: Session, entity: str, record_key: str) -> int:
    """Manuel değer kaydında: kaydın yok sayılmış uyarıları hemen Açık (değişiklik FieldChange'e yazıldıktan sonra çağrılır). Commit etmez."""
    return reopen_changed(session, entity, str(record_key))

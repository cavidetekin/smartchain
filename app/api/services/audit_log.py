"""Denetim izi detayı ve nesne geçmişi (ekran 26, fonksiyon 98; K-108). Görüntüleme iz bırakmaz."""
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..audit_format import changes
from ..errors import AppError
from ..lists.audit_log import SOURCE, SUPPORT_ACCOUNT, visible_to
from ..permissions import SYSTEM_OWNER
from . import auth
from .auth import CurrentUser

HISTORY_LIMIT = 200


def _iso(value: datetime) -> str:
    return value.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")


def _visible(user: CurrentUser) -> sa.ColumnElement:
    scope = visible_to(user.role, user.id)
    return sa.true() if scope is None else scope


def _row(session: Session, user: CurrentUser, audit_id: int) -> dict:
    row = session.execute(sa.select(SOURCE).where(SOURCE.c.Id == audit_id, _visible(user))).mappings().first()
    if row is None:
        raise AppError("audit_not_found", "Kayıt bulunamadı.", 404)
    return dict(row)


def _actor(row: dict, real: bool) -> str:
    return row["RealActor"] if real and row["RealActor"] else row["ActorName"]


def detail(session: Session | None, audit_id: int, user: CurrentUser) -> dict:
    """Gerçek ad, nesne ve değerler yalnız System owner'a; ötekilere listedeki maskeli hâli."""
    session = auth._require(session)
    real = user.role == SYSTEM_OWNER

    def work():
        row = _row(session, user, audit_id)
        old, new = (row["RawOld"], row["RawNew"]) if real else (row["OldValue"], row["NewValue"])
        return {"id": row["Id"], "at": _iso(row["At"]), "actor": _actor(row, real), "action": row["Action"],
                "object_type": row["ObjectTypeLabel"], "object": row["RawKey"] if real and row["ObjectShown"] == SUPPORT_ACCOUNT else row["ObjectShown"],
                "has_object": row["RawKey"] is not None, "changes": changes(old, new)}

    return auth._db(work)


def history(session: Session | None, audit_id: int, user: CurrentUser) -> dict:
    """Aynı nesnenin kayıtları zaman sırasıyla; en çok HISTORY_LIMIT, en yeniler. Kapsam listeyle aynı."""
    session = auth._require(session)
    real = user.role == SYSTEM_OWNER

    def work():
        row = _row(session, user, audit_id)
        if row["RawKey"] is None:
            return {"rows": [], "truncated": False}
        q = (sa.select(SOURCE).where(SOURCE.c.RawKey == row["RawKey"], _visible(user),
                                     SOURCE.c.RawType == row["RawType"] if row["RawType"] is not None else SOURCE.c.RawType.is_(None))
             .order_by(SOURCE.c.At.desc(), SOURCE.c.Id.desc()).limit(HISTORY_LIMIT + 1))
        rows = [dict(r) for r in session.execute(q).mappings()]
        return {"truncated": len(rows) > HISTORY_LIMIT,
                "rows": [{"id": r["Id"], "at": _iso(r["At"]), "actor": _actor(r, real), "action": r["Action"]}
                         for r in reversed(rows[:HISTORY_LIMIT])]}

    return auth._db(work)

"""Denetim izi detayı ve nesne geçmişi (ekran 26, fonksiyon 98; K-108). Görüntüleme iz bırakmaz."""
from datetime import datetime, timezone

import json

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
        out = {"id": row["Id"], "at": _iso(row["At"]), "actor": _actor(row, real), "action": row["Action"],
               "object_type": row["ObjectTypeLabel"], "object": row["RawKey"] if real and row["ObjectShown"] == SUPPORT_ACCOUNT else row["ObjectShown"],
               "has_object": row["RawKey"] is not None, "changes": changes(old, new)}
        out.update(record_target(session, row["RawType"], row["RawKey"], row["RawNew"]))
        return out

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


# ------------------------------------------------------------------ "Kayda git" (K-173)

TARGET_NOT_FOUND = "Kayıt bulunamadı."
TARGET_AMBIGUOUS = "Kod birden çok kayıtta (lokasyon); kayıt seçilemedi."


def record_target(session: Session, raw_type: str | None, raw_key: str | None, raw_new: str | None) -> dict:
    """Nesnesi veri kaydı olan satırın hedefi: liste ve kayıt. Yeni kayıtta JSON'daki kimlik; eski kayıtta nesnedeki koddan tek eşleşme."""
    from app.api.services.manual_values import OBJECT as MANUAL_OBJECT
    from app.manual import core_table

    from ..lists.master_data import BY_NAME
    if raw_type != MANUAL_OBJECT:
        return {}
    try:
        new = json.loads(raw_new or "{}")
    except ValueError:
        new = {}
    title, _, code = (raw_key or "").partition(" · ")
    list_name = new.get("list") if new.get("list") in BY_NAME else next((n for n, d in BY_NAME.items() if d.title == title), None)
    if list_name is None:
        return {"target": None, "target_reason": TARGET_NOT_FOUND}
    if new.get("record") is not None:
        return {"target": {"list": list_name, "id": str(new["record"])}}
    t = core_table(BY_NAME[list_name].table_name)
    if not code or "Code" not in t.c:
        return {"target": None, "target_reason": TARGET_NOT_FOUND}
    key = t.c.Id if "Id" in t.c else t.c.Code
    ids = session.execute(sa.select(key).where(t.c.Code == code).distinct()).scalars().all()
    if len(ids) != 1:
        return {"target": None, "target_reason": TARGET_AMBIGUOUS if ids else TARGET_NOT_FOUND}
    return {"target": {"list": list_name, "id": str(ids[0])}}


"""Veri kalitesi işlemleri (fonksiyon 20, 21; K-174): Yok say, Yok saymayı kaldır, kartın Talep zinciri, Ana sayfa özeti."""
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.quality import HIGH, STATE_IGNORED, STATE_NEW, chain, ignore as ignore_mod
from db.models import metadata

from ..errors import AppError
from ..permissions import Access
from . import auth, authz
from .auth import CurrentUser

W = metadata.tables["adm.DataQualityWarning"]
MAX_IDS = 10_000
NO_REASON = "Gerekçe boş olamaz."


def _ids(ids: list) -> list[int]:
    try:
        out = sorted({int(i) for i in ids})
    except (TypeError, ValueError):
        raise AppError("validation", "Girilen bilgiler geçersiz.", 422, [{"field": "body.ids", "problem": "Kimlik sayı olmalı"}]) from None
    if not out or len(out) > MAX_IDS:
        raise AppError("validation", "Girilen bilgiler geçersiz.", 422, [{"field": "body.ids", "problem": f"1 ile {MAX_IDS} arasında uyarı seçilmeli"}])
    return out


def ignore(session: Session | None, user: CurrentUser, ids: list, reason: str | None) -> dict:
    session = auth._require(session)
    authz.ensure(user, 21, Access.WRITE)
    text = (reason or "").strip()
    if not text:
        raise AppError("validation", "Girilen bilgiler geçersiz.", 422, [{"field": "body.reason", "problem": NO_REASON}])
    wanted = _ids(ids)

    def work():
        n = ignore_mod.ignore(session, user.id, wanted, text)
        session.commit()
        return {"ignored": n}
    return auth._db(work)


def unignore(session: Session | None, user: CurrentUser, ids: list) -> dict:
    session = auth._require(session)
    authz.ensure(user, 21, Access.WRITE)
    wanted = _ids(ids)

    def work():
        n = ignore_mod.unignore(session, user.id, wanted)
        session.commit()
        return {"unignored": n}
    return auth._db(work)


def demand_chain(session: Session | None, user: CurrentUser, warning_id: int) -> dict:
    """Kartın Talep zinciri: önbellekte yoksa hesaplanır (en çok 1.000 yol)."""
    session = auth._require(session)
    authz.ensure(user, 20, Access.READ)

    def work():
        row = session.execute(sa.select(W.c.EntityName, W.c.RecordKey).where(W.c.Id == warning_id)).first()
        if row is None:
            raise AppError("data_quality_warning_not_found", "Uyarı bulunamadı.", 404)
        return chain.write_paths(session, warning_id, row.EntityName, row.RecordKey, date.today())
    return auth._db(work)


def summary(session: Session | None, user: CurrentUser) -> dict:
    """Ana sayfa özeti (9.1): yüksek önemde uyarı ve bunlardan yeni olanlar (yok sayılan hariç)."""
    session = auth._require(session)
    authz.ensure(user, 20, Access.READ)

    def work():
        high = sa.and_(W.c.State != STATE_IGNORED, W.c.Importance == HIGH)
        n = lambda cond: sa.func.coalesce(sa.func.sum(sa.case((cond, 1), else_=0)), 0)  # noqa: E731  (SQL Server'da COUNT FILTER yok)
        a, b = session.execute(sa.select(n(high), n(sa.and_(high, W.c.State == STATE_NEW)))).one()
        return {"high": int(a or 0), "high_new": int(b or 0)}
    return auth._db(work)

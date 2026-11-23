"""Malzeme blokajı (ekran 31 üçüncü sekme, fonksiyon 99; K-193): yeni kayıt, hücre değişikliği, silme, geçersiz yapma, senaryo farkını kaldırma,
pencerenin seçenekleri. İş kuralları `app/materialholds` ve ortak giriş altyapısında (`app/capacity/entries.py`); burada senaryo, işlem, denetim izi
ve hata cevabı (Kapasite yönetimi servisiyle aynı kalıp).

Her işlem tek veritabanı işlemidir: kayıt, alan geçmişi ve denetim izi birlikte yazılır ya da hiçbiri yazılmaz.
"""
from sqlalchemy.orm import Session

from app import materialholds as rules
from app.capacity import entries

from ..repositories import audit
from . import auth
from .auth import CurrentUser
from .capacity import _run, today

A_CREATED, A_CHANGED, A_DELETED = "Malzeme blokajı eklendi", "Malzeme blokajı değişti", "Malzeme blokajı silindi"
A_INVALID, A_VALID, A_RESTORED = "Malzeme blokajı geçersiz yapıldı", "Malzeme blokajı geçerli yapıldı", "Senaryo farkı kaldırıldı"
KIND = rules.HOLD_KIND


def options(session: Session | None, user: CurrentUser) -> dict:
    session = auth._require(session)
    return auth._db(lambda: {"materials": rules.options(session), "types": list(rules.TYPES)})


def _audit(session: Session, user: CurrentUser, scope: entries.Scope, action: str, label: str, new: dict | None = None, old: dict | None = None) -> None:
    audit.write_audit(session, action, user.id, KIND.title, label, new_value=new, old_value=old, scenario=scope.scenario_name)


def create(session: Session | None, user: CurrentUser, scenario_id: int | None, values: dict) -> dict:
    def work(s: Session, scope: entries.Scope) -> dict:
        out = entries.create(s, KIND, scope, user.id, values, today())
        _audit(s, user, scope, A_CREATED, out["label"], new={k: v for k, v in out["values"].items() if v is not None})
        return {"id": out["id"], "warnings": out["warnings"]}

    return _run(session, user, scenario_id, work)


def change(session: Session | None, user: CurrentUser, scenario_id: int | None, changes: list[dict]) -> dict:
    def work(s: Session, scope: entries.Scope) -> dict:
        out = entries.change(s, KIND, scope, user.id, changes, today())
        for event in out["events"]:
            _audit(s, user, scope, A_CHANGED, event["label"], new=event["new"], old=event["old"])
        return {"saved": out["saved"], "warnings": out["warnings"]}

    return _run(session, user, scenario_id, work)


def remove(session: Session | None, user: CurrentUser, scenario_id: int | None, row_id: int) -> dict:
    def work(s: Session, scope: entries.Scope) -> dict:
        out = entries.remove(s, KIND, scope, user.id, row_id)
        _audit(s, user, scope, A_DELETED, out["label"], old={k: v for k, v in out["values"].items() if v is not None})
        return {"deleted": True}

    return _run(session, user, scenario_id, work)


def set_valid(session: Session | None, user: CurrentUser, scenario_id: int | None, row_id: int, valid: bool) -> dict:
    def work(s: Session, scope: entries.Scope) -> dict:
        out = entries.set_valid(s, KIND, scope, user.id, row_id, valid)
        if out["changed"]:
            _audit(s, user, scope, A_VALID if valid else A_INVALID, out["label"], new={"IsValid": valid}, old={"IsValid": not valid})
        return {"valid": valid}

    return _run(session, user, scenario_id, work)


def restore(session: Session | None, user: CurrentUser, scenario_id: int | None, row_id: int) -> dict:
    def work(s: Session, scope: entries.Scope) -> dict:
        out = entries.restore(s, KIND, scope, user.id, row_id)
        _audit(s, user, scope, A_RESTORED, out["label"], new=out["new"] or None, old=out["old"] or None)
        return {"restored": True}

    return _run(session, user, scenario_id, work)

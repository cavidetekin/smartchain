"""Kapasite yönetimi girişleri (ekran 30, fonksiyon 24; K-185, 7.9b): yeni kayıt, hücre değişikliği, silme, geçersiz yapma, senaryo farkını
kaldırma. İş kuralları `app/capacity/entries.py`'de; burada senaryo, işlem, denetim izi (senaryo kolonuyla) ve hata cevabı.

Her işlem tek veritabanı işlemidir: giriş, alan geçmişi, önbelleğin yenilenmesi ve denetim izi birlikte yazılır ya da hiçbiri yazılmaz.
"""
from datetime import date

from sqlalchemy.orm import Session

from app import periods
from app.capacity import entries
from app.params import scenarios

from ..errors import AppError
from ..repositories import audit
from . import auth
from .auth import CurrentUser

A_CREATED, A_CHANGED, A_DELETED = "Kapasite girişi eklendi", "Kapasite girişi değişti", "Kapasite girişi silindi"
A_INVALID, A_VALID, A_RESTORED = "Kapasite girişi geçersiz yapıldı", "Kapasite girişi geçerli yapıldı", "Senaryo farkı kaldırıldı"


def today() -> date:
    return date.today()


def _kind(name: str) -> entries.Kind:
    kind = entries.KINDS.get(name)
    if kind is None:
        raise AppError("not_found", "Bilinmeyen kapasite girişi.", 404)
    return kind


def _error(err: entries.EntryError) -> AppError:
    return AppError(err.code, err.message, err.status, err.problems or None)


def _run(session: Session | None, user: CurrentUser, scenario_id: int | None, work):
    """Senaryoyu bulur, işi işlem içinde çalıştırır; iş kuralı hatasında geri alır."""
    session = auth._require(session)

    def inner():
        try:
            scenario = scenarios.resolve(session, user.id, scenario_id)
        except scenarios.ScenarioError as err:
            raise AppError(err.code, err.message, err.status) from None
        scope = entries.scope_of(session, scenario)
        try:
            result = work(session, scope)
        except entries.EntryError as err:
            session.rollback()
            raise _error(err) from None
        session.commit()
        return result

    return auth._db(inner)


def horizon(session: Session | None, user: CurrentUser, scenario_id: int | None) -> dict:
    """Senaryonun planlama ufku (ilk dönemin başı, son dönemin sonu): Geçerlilik zaman çubuğu (K-188)."""
    session = auth._require(session)

    def inner():
        try:
            scenario = scenarios.resolve(session, user.id, scenario_id)
        except scenarios.ScenarioError as err:
            raise AppError(err.code, err.message, err.status) from None
        found = periods.read_periods(session, scenario["Id"], today())
        return {"start": found[0].start.isoformat() if found else None, "end": found[-1].end.isoformat() if found else None}

    return auth._db(inner)


def _audit(session: Session, user: CurrentUser, scope: entries.Scope, action: str, kind: entries.Kind, label: str, new: dict | None = None,
           old: dict | None = None) -> None:
    audit.write_audit(session, action, user.id, kind.title, label, new_value=new, old_value=old, scenario=scope.scenario_name)


def create(session: Session | None, user: CurrentUser, kind_name: str, scenario_id: int | None, values: dict) -> dict:
    kind = _kind(kind_name)

    def work(s: Session, scope: entries.Scope) -> dict:
        out = entries.create(s, kind, scope, user.id, values, today())
        _audit(s, user, scope, A_CREATED, kind, out["label"], new={k: v for k, v in out["values"].items() if v is not None})
        return {"id": out["id"], "warnings": out["warnings"]}

    return _run(session, user, scenario_id, work)


def change(session: Session | None, user: CurrentUser, kind_name: str, scenario_id: int | None, changes: list[dict]) -> dict:
    kind = _kind(kind_name)

    def work(s: Session, scope: entries.Scope) -> dict:
        out = entries.change(s, kind, scope, user.id, changes, today())
        for event in out["events"]:
            _audit(s, user, scope, A_CHANGED, kind, event["label"], new=event["new"], old=event["old"])
        return {"saved": out["saved"], "warnings": out["warnings"]}

    return _run(session, user, scenario_id, work)


def remove(session: Session | None, user: CurrentUser, kind_name: str, scenario_id: int | None, row_id: int) -> dict:
    kind = _kind(kind_name)

    def work(s: Session, scope: entries.Scope) -> dict:
        out = entries.remove(s, kind, scope, user.id, row_id)
        _audit(s, user, scope, A_DELETED, kind, out["label"], old={k: v for k, v in out["values"].items() if v is not None})
        return {"deleted": True}

    return _run(session, user, scenario_id, work)


def set_valid(session: Session | None, user: CurrentUser, kind_name: str, scenario_id: int | None, row_id: int, valid: bool) -> dict:
    kind = _kind(kind_name)

    def work(s: Session, scope: entries.Scope) -> dict:
        out = entries.set_valid(s, kind, scope, user.id, row_id, valid)
        if out["changed"]:
            _audit(s, user, scope, A_VALID if valid else A_INVALID, kind, out["label"], new={"IsValid": valid}, old={"IsValid": not valid})
        return {"valid": valid}

    return _run(session, user, scenario_id, work)


def restore(session: Session | None, user: CurrentUser, kind_name: str, scenario_id: int | None, row_id: int) -> dict:
    kind = _kind(kind_name)

    def work(s: Session, scope: entries.Scope) -> dict:
        out = entries.restore(s, kind, scope, user.id, row_id)
        _audit(s, user, scope, A_RESTORED, kind, out["label"], new=out["new"] or None, old=out["old"] or None)
        return {"restored": True}

    return _run(session, user, scenario_id, work)

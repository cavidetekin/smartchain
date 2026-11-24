"""Öncelik yönetimi (ekran 32, fonksiyon 25; K-195; docs/08 "Öncelik yönetimi"): hücre değişiklikleri ve senaryo farkını kaldırma. Okuma ortak liste
uçlarındandır (`priority-*`). İş kuralları `app/priorities`'te; burada senaryo, işlem ve denetim izi (Model kısıtları servisiyle aynı kalıp)."""
from sqlalchemy.orm import Session

from app import priorities as rules
from app.params import scenarios

from ..errors import AppError
from ..repositories import audit
from . import auth
from .auth import CurrentUser

OBJECT = "Öncelik yönetimi"
A_CHANGED, A_RESTORED = "Öncelik grubu değişti", "Senaryo farkı kaldırıldı"


def _run(session: Session | None, user: CurrentUser, scenario_id: int | None, level: str, work):
    """Senaryoyu ve düzeyi bulur, işi işlem içinde çalıştırır; iş kuralı hatasında geri alır."""
    session = auth._require(session)
    found = rules.LEVELS.get(level)
    if found is None:
        raise AppError("not_found", "Bilinmeyen düzey.", 404)

    def inner():
        try:
            scenario = scenarios.resolve(session, user.id, scenario_id)
        except scenarios.ScenarioError as err:
            raise AppError(err.code, err.message, err.status) from None
        scope = rules.scope_of(session, scenario)
        try:
            result = work(session, scope, found)
        except rules.PriorityError as err:
            session.rollback()
            raise AppError(err.code, err.message, err.status, err.problems or None) from None
        session.commit()
        return result

    return auth._db(inner)


def change(session: Session | None, user: CurrentUser, scenario_id: int | None, level: str, changes: list[dict]) -> dict:
    def work(s: Session, scope: rules.Scope, found: rules.Level) -> dict:
        out = rules.change(s, scope, found, user.id, changes)
        for event in out["events"]:
            audit.write_audit(s, A_CHANGED, user.id, OBJECT, event["label"], new_value=event["new"], old_value=event["old"], scenario=scope.scenario_name)
        return {"saved": out["saved"]}

    return _run(session, user, scenario_id, level, work)


def restore(session: Session | None, user: CurrentUser, scenario_id: int | None, level: str, record_id: int) -> dict:
    def work(s: Session, scope: rules.Scope, found: rules.Level) -> dict:
        out = rules.restore(s, scope, found, user.id, record_id)
        audit.write_audit(s, A_RESTORED, user.id, OBJECT, out["label"], new_value=out["new"], old_value=out["old"], scenario=scope.scenario_name)
        return {"restored": True}

    return _run(session, user, scenario_id, level, work)

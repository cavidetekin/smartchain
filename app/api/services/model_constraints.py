"""Model kısıtları (ekran 31, fonksiyon 103; K-189; docs/08 "Model kısıtları"): hücre değişiklikleri ve senaryo farkını kaldırma. Okuma ortak liste
uçlarındandır (`model-constraints-resource-groups`). İş kuralları `app/modelconstraints`'te; burada senaryo, işlem ve denetim izi."""
from sqlalchemy.orm import Session

from app import modelconstraints as rules
from app.params import scenarios

from ..errors import AppError
from ..repositories import audit
from . import auth
from .auth import CurrentUser

OBJECT = "Model kısıtları"
A_CHANGED, A_RESTORED = "Model kısıtı değişti", "Senaryo farkı kaldırıldı"


def _run(session: Session | None, user: CurrentUser, scenario_id: int | None, work):
    """Senaryoyu bulur, işi işlem içinde çalıştırır; iş kuralı hatasında geri alır."""
    session = auth._require(session)

    def inner():
        try:
            scenario = scenarios.resolve(session, user.id, scenario_id)
        except scenarios.ScenarioError as err:
            raise AppError(err.code, err.message, err.status) from None
        scope = rules.scope_of(session, scenario)
        try:
            result = work(session, scope)
        except rules.ConstraintError as err:
            session.rollback()
            raise AppError(err.code, err.message, err.status, err.problems or None) from None
        session.commit()
        return result

    return auth._db(inner)


def change(session: Session | None, user: CurrentUser, scenario_id: int | None, changes: list[dict]) -> dict:
    def work(s: Session, scope: rules.Scope) -> dict:
        out = rules.change(s, scope, user.id, changes)
        for event in out["events"]:
            audit.write_audit(s, A_CHANGED, user.id, OBJECT, event["label"], new_value=event["new"], old_value=event["old"], scenario=scope.scenario_name)
        return {"saved": out["saved"]}

    return _run(session, user, scenario_id, work)


def restore(session: Session | None, user: CurrentUser, scenario_id: int | None, group_id: int) -> dict:
    def work(s: Session, scope: rules.Scope) -> dict:
        out = rules.restore(s, scope, user.id, group_id)
        audit.write_audit(s, A_RESTORED, user.id, OBJECT, out["label"], new_value=out["new"], old_value=out["old"], scenario=scope.scenario_name)
        return {"restored": True}

    return _run(session, user, scenario_id, work)

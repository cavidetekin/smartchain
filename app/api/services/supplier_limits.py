"""Tedarikçi limiti (ekran 31 ikinci sekme, fonksiyon 103; K-191): yeni kayıt (iki tür; kapanışta birden çok malzeme), hücre değişikliği, silme,
geçersiz yapma, senaryo farkını kaldırma, pencerenin seçenekleri. İş kuralları `app/supplierlimits` ve ortak giriş altyapısında
(`app/capacity/entries.py`); burada senaryo, işlem, denetim izi ve hata cevabı (Kapasite yönetimi servisiyle aynı kalıp).

Her işlem tek veritabanı işlemidir: kayıtlar, alan geçmişi ve denetim izi birlikte yazılır ya da hiçbiri yazılmaz.
"""
from sqlalchemy.orm import Session

from app import supplierlimits as rules
from app.capacity import entries

from ..errors import AppError
from ..repositories import audit
from . import auth
from .auth import CurrentUser
from .capacity import _run, today

A_CREATED, A_CHANGED, A_DELETED = "Tedarikçi limiti eklendi", "Tedarikçi limiti değişti", "Tedarikçi limiti silindi"
A_INVALID, A_VALID, A_RESTORED = "Tedarikçi limiti geçersiz yapıldı", "Tedarikçi limiti geçerli yapıldı", "Senaryo farkı kaldırıldı"
INVALID = "Girilen bilgiler geçersiz."


def options(session: Session | None, user: CurrentUser) -> dict:
    session = auth._require(session)
    return auth._db(lambda: {"suppliers": rules.options(session), "types": [rules.UPPER, rules.CLOSURE], "periods": list(rules.PERIODS)})


def _audit(session: Session, user: CurrentUser, scope: entries.Scope, action: str, kind: entries.Kind, label: str, new: dict | None = None,
           old: dict | None = None) -> None:
    audit.write_audit(session, action, user.id, kind.title, label, new_value=new, old_value=old, scenario=scope.scenario_name)


def _kind_of(session: Session, scope: entries.Scope, row_id: int) -> entries.Kind:
    """Satırın türü (iki tür aynı tabloda): kaydın `LimitType` değeri."""
    row = entries._get(session, rules.ANY, scope, row_id)
    return rules.KINDS[row["LimitType"]]


def create(session: Session | None, user: CurrentUser, scenario_id: int | None, values: dict) -> dict:
    """Yeni kayıt. Kapanışta `MaterialIds` ile birden çok malzeme: her biri ayrı kayıt, hepsi ya da hiçbiri."""
    values = dict(values)
    kind = rules.KINDS.get(values.pop("LimitType", None))
    if kind is None:
        raise AppError("validation", INVALID, 422, [{"field": "LimitType", "problem": "Tür seçilmeli."}])
    many = values.pop("MaterialIds", None)
    if many is not None and (not isinstance(many, list) or kind is not rules.CLOSURE_KIND):
        raise AppError("validation", INVALID, 422, [{"field": "MaterialId", "problem": "Birden çok malzeme yalnız kapanışta seçilir."}])
    materials = list(dict.fromkeys(many)) if many else [values.get("MaterialId")]

    def work(s: Session, scope: entries.Scope) -> dict:
        ids, warnings = [], []
        for material in materials:
            out = entries.create(s, kind, scope, user.id, {**values, "MaterialId": material}, today())
            _audit(s, user, scope, A_CREATED, kind, out["label"], new={k: v for k, v in out["values"].items() if v is not None})
            ids.append(out["id"])
            warnings += out["warnings"]
        return {"ids": ids, "warnings": list(dict.fromkeys(warnings))}

    return _run(session, user, scenario_id, work)


def change(session: Session | None, user: CurrentUser, scenario_id: int | None, changes: list[dict]) -> dict:
    def work(s: Session, scope: entries.Scope) -> dict:
        by_kind: dict[str, list[dict]] = {}
        for c in changes:
            by_kind.setdefault(_kind_of(s, scope, int(c["id"])).key, []).append(c)
        saved, warnings, problems = 0, [], []
        for kind in (rules.UPPER_KIND, rules.CLOSURE_KIND):      # iki türün sorunları birlikte bildirilir
            if kind.key not in by_kind:
                continue
            try:
                out = entries.change(s, kind, scope, user.id, by_kind[kind.key], today())
            except entries.EntryError as err:
                if err.code != "validation":
                    raise
                problems += err.problems
                continue
            for event in out["events"]:
                _audit(s, user, scope, A_CHANGED, kind, event["label"], new=event["new"], old=event["old"])
            saved += out["saved"]
            warnings += out["warnings"]
        if problems:
            raise entries.EntryError(problems, message="Kaydedilmedi.")
        return {"saved": saved, "warnings": warnings}

    return _run(session, user, scenario_id, work)


def remove(session: Session | None, user: CurrentUser, scenario_id: int | None, row_id: int) -> dict:
    def work(s: Session, scope: entries.Scope) -> dict:
        kind = _kind_of(s, scope, row_id)
        out = entries.remove(s, kind, scope, user.id, row_id)
        _audit(s, user, scope, A_DELETED, kind, out["label"], old={k: v for k, v in out["values"].items() if v is not None})
        return {"deleted": True}

    return _run(session, user, scenario_id, work)


def set_valid(session: Session | None, user: CurrentUser, scenario_id: int | None, row_id: int, valid: bool) -> dict:
    def work(s: Session, scope: entries.Scope) -> dict:
        kind = _kind_of(s, scope, row_id)
        out = entries.set_valid(s, kind, scope, user.id, row_id, valid)
        if out["changed"]:
            _audit(s, user, scope, A_VALID if valid else A_INVALID, kind, out["label"], new={"IsValid": valid}, old={"IsValid": not valid})
        return {"valid": valid}

    return _run(session, user, scenario_id, work)


def restore(session: Session | None, user: CurrentUser, scenario_id: int | None, row_id: int) -> dict:
    def work(s: Session, scope: entries.Scope) -> dict:
        kind = _kind_of(s, scope, row_id)
        out = entries.restore(s, kind, scope, user.id, row_id)
        _audit(s, user, scope, A_RESTORED, kind, out["label"], new=out["new"] or None, old=out["old"] or None)
        return {"restored": True}

    return _run(session, user, scenario_id, work)

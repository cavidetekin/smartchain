"""Parametreler (ekran 06; fonksiyon 22, 23; K-175): Baz senaryonun parametreleri, hedefleri ve dönem dizisi. Okuma ve yazma `app/params/service.py`
üzerinden; her değişiklik denetim izine (eski → yeni). 7.1'de tek senaryo Baz'dır; senaryo seçimi senaryo yönetimi adımında gelir.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.params import catalog as cat, horizon, service as params

from ..errors import AppError
from ..repositories import audit
from . import auth
from .auth import CurrentUser

ACTION_SETTING = "Parametre değişikliği"
ACTION_OBJECTIVE = "Hedef değişikliği"
ACTION_BUCKETS = "Dönem dizisi değişikliği"
OBJECT = "Senaryo"
INVALID = "Girilen bilgiler geçersiz."
AXES = {"plan": cat.AXIS_PLAN, "rapor": cat.AXIS_REPORT}


def today() -> date:
    return date.today()


def _base(session: Session) -> tuple[int, str]:
    base = params.base_scenario(session)
    if base is None:
        raise AppError("scenario_not_found", "Baz senaryo bulunamadı.", 404)
    return base


def _invalid(err: params.ParamError) -> AppError:
    return AppError("validation", INVALID, 422, err.problems)


def _key(name: str, item: str) -> str:
    return f"{name} · {item}"


def current_scenario(session: Session | None) -> dict:
    """Bağlam çubuğundaki senaryo; 7.1'de her zaman Baz."""
    session = auth._require(session)

    def work():
        scenario_id, name = _base(session)
        return {"id": scenario_id, "name": name}

    return auth._db(work)


def _param(p: cat.Param) -> dict:
    out = {"key": p.key, "label": p.label, "kind": p.kind}
    if p.options:
        out["options"] = list(p.options)
    if p.minimum is not None:
        out["min"] = p.minimum
    if p.maximum is not None:
        out["max"] = p.maximum
    if p.nullable:
        out["nullable"] = True
    if p.enabled_when:
        out["enabled_when"] = {"key": p.enabled_when[0], "value": p.enabled_when[1]}
    if p.hint:
        out["hint"] = p.hint
    if p.unit_key:
        out["unit_key"] = p.unit_key
    return out


def read(session: Session | None) -> dict:
    """Başlıklar, alt başlıklar, parametreler ve değerleri."""
    session = auth._require(session)

    def work():
        scenario_id, name = _base(session)
        sections = [{"key": s.key, "title": s.title, "table": s.table,
                     "subs": [{"key": sub.key, "title": sub.title, "table": sub.table, "params": [_param(p) for p in sub.params]} for sub in s.subs]}
                    for s in cat.SECTIONS]
        fix_end = params.fix_period_end(session, scenario_id, today())
        return {"scenario": {"id": scenario_id, "name": name}, "sections": sections, "values": params.read_settings(session, scenario_id),
                "computed": {"fix_period_end": fix_end.isoformat() if fix_end else None}}

    return auth._db(work)


def update(session: Session | None, actor: CurrentUser, changes: dict) -> dict:
    session = auth._require(session)

    def work():
        scenario_id, name = _base(session)
        try:
            params.save_settings(session, scenario_id, changes, lambda key, old, new: audit.write_audit(
                session, ACTION_SETTING, actor.id, OBJECT, _key(name, key), {"Value": new}, {"Value": old}))
        except params.ParamError as err:
            session.rollback()
            raise _invalid(err) from None
        session.commit()

    auth._db(work)
    return read(session)


def objectives(session: Session | None) -> dict:
    session = auth._require(session)

    def work():
        scenario_id, _ = _base(session)
        return {"rows": params.read_objectives(session, scenario_id), "total_seconds": params.time_budget(session, scenario_id)}

    return auth._db(work)


def update_objectives(session: Session | None, actor: CurrentUser, rows: list[dict]) -> dict:
    session = auth._require(session)

    def work():
        scenario_id, name = _base(session)
        try:
            params.save_objectives(session, scenario_id, rows, lambda label, old, new: audit.write_audit(
                session, ACTION_OBJECTIVE, actor.id, OBJECT, _key(name, label), new, old))
        except params.ParamError as err:
            session.rollback()
            raise _invalid(err) from None
        session.commit()

    auth._db(work)
    return objectives(session)


def _axis(axis: str) -> str:
    if axis not in AXES:
        raise AppError("validation", INVALID, 422, [{"field": "axis", "problem": "plan ya da rapor olmalı."}])
    return AXES[axis]


def _parts(found: list[horizon.Part]) -> dict:
    rows = [{"bucket_type": p.bucket_type, "count": p.count, "span_unit": p.span_unit, "start": p.start.isoformat(), "end": p.end.isoformat(),
             "buckets": len(p.buckets), "days": (p.end - p.start).days + 1} for p in found]
    periods = [{"no": i, "start": b.start.isoformat(), "end": b.end.isoformat(), "bucket_type": b.kind, "days": (b.end - b.start).days + 1}
               for i, b in enumerate((b for p in found for b in p.buckets), start=1)]
    return {"rows": rows, "start": rows[0]["start"] if rows else None, "end": rows[-1]["end"] if rows else None,
            "buckets": len(periods), "periods": periods}


def _rows(rows: list[dict]) -> list[tuple]:
    return [(r.get("bucket_type"), r.get("count"), r.get("span_unit")) for r in rows]


def _kinds(axis: str) -> tuple[str, ...]:
    return cat.PLAN_BUCKETS if axis == cat.AXIS_PLAN else cat.REPORT_BUCKETS


def time_buckets(session: Session | None, axis: str) -> dict:
    """Eksenin saklı dizisi, hesaplanmış başlangıç ve bitişleriyle (raporlama ekseninde kendi satırları)."""
    session = auth._require(session)
    wanted = _axis(axis)

    def work():
        scenario_id, _ = _base(session)
        settings = params.read_settings(session, scenario_id)
        rows = params.bucket_rows(session, scenario_id, wanted)
        found = horizon.parts(params.plan_start(session, settings, today()), rows, horizon.week_start_index(settings.get("WeekStart")))
        return {**_parts(found), "bucket_types": list(_kinds(wanted)), "span_units": list(cat.SPAN_UNITS)}

    return auth._db(work)


def preview_time_buckets(session: Session | None, axis: str, rows: list[dict], week_start: str | None, plan_start: str | None) -> dict:
    """Kaydedilmemiş dizinin hesabı (ekranda taslak değişirken tarihler ve şerit); geçersiz dizide 422."""
    session = auth._require(session)
    wanted = _axis(axis)

    def work():
        scenario_id, _ = _base(session)
        found = horizon.problems(_rows(rows), _kinds(wanted))
        if found:
            raise AppError("validation", INVALID, 422, found)
        return _parts(params.preview_parts(session, scenario_id, today(), [(b, int(c), u) for b, c, u in _rows(rows)], week_start, plan_start))

    return auth._db(work)


def update_time_buckets(session: Session | None, actor: CurrentUser, axis: str, rows: list[dict]) -> dict:
    session = auth._require(session)
    wanted = _axis(axis)

    def work():
        scenario_id, name = _base(session)
        try:
            params.save_buckets(session, scenario_id, wanted, _rows(rows), lambda ax, old, new: audit.write_audit(
                session, ACTION_BUCKETS, actor.id, OBJECT, _key(name, f"{ax} ekseni"), {"Value": new}, {"Value": old}))
        except params.ParamError as err:
            session.rollback()
            raise _invalid(err) from None
        session.commit()

    auth._db(work)
    return time_buckets(session, axis)

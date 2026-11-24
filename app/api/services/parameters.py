"""Parametreler (ekran 06; fonksiyon 22, 23; K-175): Baz senaryonun parametreleri, hedefleri ve dönem dizisi. Okuma ve yazma `app/params/service.py`
üzerinden; her değişiklik denetim izine (eski → yeni). Senaryo istekle gelir (`scenario_id`); verilmezse kullanıcının hatırlanan senaryosu, o da
geçersizse Baz (K-177). Pasif senaryonun parametreleri de açılır ve düzenlenir.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.params import catalog as cat, horizon, objectives as objective_rows, scenarios, service as params

from ..errors import AppError
from ..repositories import audit
from . import auth
from .auth import CurrentUser

ACTION_SETTING = "Parametre değişikliği"
ACTION_OBJECTIVE = "Hedef değişikliği"
ACTION_BUCKETS = "Dönem dizisi değişikliği"
ACTION_WARNING = "Uyarı eşiği değişikliği"
OBJECT = "Senaryo"
INVALID = "Girilen bilgiler geçersiz."
AXES = {"plan": cat.AXIS_PLAN, "rapor": cat.AXIS_REPORT}


def today() -> date:
    return date.today()


def _scenario(session: Session, user: CurrentUser, scenario_id: int | None) -> tuple[int, str]:
    try:
        row = scenarios.resolve(session, user.id, scenario_id)
    except scenarios.ScenarioError as err:
        raise AppError(err.code, err.message, err.status) from None
    return row["Id"], row["Name"]


def _invalid(err: params.ParamError) -> AppError:
    return AppError("validation", INVALID, 422, err.problems)


def _key(name: str, item: str) -> str:
    return f"{name} · {item}"


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


def read(session: Session | None, user: CurrentUser, scenario_id: int | None = None) -> dict:
    """Başlıklar, alt başlıklar, parametreler ve değerleri."""
    session = auth._require(session)

    def work():
        sid, name = _scenario(session, user, scenario_id)
        sections = [{"key": s.key, "title": s.title, "table": s.table,
                     "subs": [{"key": sub.key, "title": sub.title, "table": sub.table, "params": [_param(p) for p in sub.params]} for sub in s.subs]}
                    for s in cat.SECTIONS]
        fix_end = params.fix_period_end(session, sid, today())
        return {"scenario": {"id": sid, "name": name}, "sections": sections, "values": params.read_settings(session, sid),
                "computed": {"fix_period_end": fix_end.isoformat() if fix_end else None}}

    return auth._db(work)


def update(session: Session | None, actor: CurrentUser, changes: dict, scenario_id: int | None = None) -> dict:
    session = auth._require(session)

    def work():
        sid, name = _scenario(session, actor, scenario_id)
        try:
            params.save_settings(session, sid, changes, lambda key, old, new: audit.write_audit(
                session, ACTION_SETTING, actor.id, OBJECT, _key(name, key), {"Value": new}, {"Value": old}, scenario=name))
        except params.ParamError as err:
            session.rollback()
            raise _invalid(err) from None
        session.commit()

    auth._db(work)
    return read(session, actor, scenario_id)


def objectives(session: Session | None, user: CurrentUser, scenario_id: int | None = None) -> dict:
    session = auth._require(session)

    def work():
        sid, _ = _scenario(session, user, scenario_id)
        return {"rows": objective_rows.read_objectives(session, sid), "total_seconds": params.time_budget(session, sid),
                "catalog": objective_rows.catalog(session)}

    return auth._db(work)


def _objective_work(session: Session | None, actor: CurrentUser, scenario_id: int | None, action) -> None:
    """Hedef satırı işlemi (K-196): senaryo çözülür, işlem denetim iziyle çalışır; sorun 422."""
    session = auth._require(session)

    def work():
        sid, name = _scenario(session, actor, scenario_id)
        try:
            out = action(sid, lambda label, old, new: audit.write_audit(session, ACTION_OBJECTIVE, actor.id, OBJECT, _key(name, label), new, old, scenario=name))
        except params.ParamError as err:
            session.rollback()
            raise _invalid(err) from None
        session.commit()
        return out

    return auth._db(work)


def create_objective(session: Session | None, actor: CurrentUser, body: dict, scenario_id: int | None = None) -> dict:
    """"Yeni hedef tanımla": satır listenin sonuna, aktif olarak eklenir."""
    _objective_work(session, actor, scenario_id, lambda sid, log: objective_rows.create(
        session, sid, body["code"], body.get("scope"), body.get("description"), body.get("seconds"), body.get("tolerance"), log))
    return objectives(session, actor, scenario_id)


def update_objective(session: Session | None, actor: CurrentUser, row_id: int, body: dict, scenario_id: int | None = None) -> dict:
    """"Düzenle": hedef, kapsam, açıklama; aktif satırda süre ve ödün payı."""
    _objective_work(session, actor, scenario_id, lambda sid, log: objective_rows.update(
        session, sid, row_id, body["code"], body.get("scope"), body.get("description"), body.get("seconds"), body.get("tolerance"), log))
    return objectives(session, actor, scenario_id)


def delete_objective(session: Session | None, actor: CurrentUser, row_id: int, scenario_id: int | None = None) -> dict:
    _objective_work(session, actor, scenario_id, lambda sid, log: objective_rows.delete(session, sid, row_id, log))
    return objectives(session, actor, scenario_id)


def reset_objectives(session: Session | None, actor: CurrentUser, scenario_id: int | None = None) -> dict:
    _objective_work(session, actor, scenario_id, lambda sid, log: objective_rows.reset(session, sid, log))
    return objectives(session, actor, scenario_id)


def update_objectives(session: Session | None, actor: CurrentUser, rows: list[dict], scenario_id: int | None = None) -> dict:
    session = auth._require(session)

    def work():
        sid, name = _scenario(session, actor, scenario_id)
        try:
            objective_rows.save_objectives(session, sid, rows, lambda label, old, new: audit.write_audit(
                session, ACTION_OBJECTIVE, actor.id, OBJECT, _key(name, label), new, old, scenario=name))
        except params.ParamError as err:
            session.rollback()
            raise _invalid(err) from None
        session.commit()

    auth._db(work)
    return objectives(session, actor, scenario_id)


def warning_thresholds(session: Session | None, user: CurrentUser, scenario_id: int | None = None) -> dict:
    """Uyarı eşikleri (fonksiyon 26; K-190): senaryonun eşikleri katalog sırasıyla. Eksik satır başlangıç değerleriyle tamamlanır."""
    session = auth._require(session)

    def work():
        sid, _ = _scenario(session, user, scenario_id)
        added = params.ensure_warning_thresholds(session, sid)
        rows = params.read_warning_thresholds(session, sid)
        if added:
            session.commit()
        return {"rows": rows, "categories": list(cat.WARNING_CATEGORIES), "severities": list(cat.SEVERITIES)}

    return auth._db(work)


def update_warning_thresholds(session: Session | None, actor: CurrentUser, rows: list[dict], scenario_id: int | None = None) -> dict:
    session = auth._require(session)

    def work():
        sid, name = _scenario(session, actor, scenario_id)
        try:
            saved = params.save_warning_thresholds(session, sid, rows, lambda label, old, new: audit.write_audit(
                session, ACTION_WARNING, actor.id, OBJECT, _key(name, label), new, old, scenario=name))
        except params.ParamError as err:
            session.rollback()
            raise _invalid(err) from None
        session.commit()
        return saved

    saved = auth._db(work)
    return {**warning_thresholds(session, actor, scenario_id), "saved": saved}


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


def time_buckets(session: Session | None, user: CurrentUser, axis: str, scenario_id: int | None = None) -> dict:
    """Eksenin saklı dizisi, hesaplanmış başlangıç ve bitişleriyle (raporlama ekseninde kendi satırları)."""
    session = auth._require(session)
    wanted = _axis(axis)

    def work():
        sid, _ = _scenario(session, user, scenario_id)
        settings = params.read_settings(session, sid)
        rows = params.bucket_rows(session, sid, wanted)
        found = horizon.parts(params.plan_start(session, settings, today()), rows, horizon.week_start_index(settings.get("WeekStart")))
        return {**_parts(found), "bucket_types": list(_kinds(wanted)), "span_units": list(cat.SPAN_UNITS)}

    return auth._db(work)


def preview_time_buckets(session: Session | None, user: CurrentUser, axis: str, rows: list[dict], week_start: str | None, plan_start: str | None,
                         scenario_id: int | None = None) -> dict:
    """Kaydedilmemiş dizinin hesabı (ekranda taslak değişirken tarihler ve şerit); geçersiz dizide 422."""
    session = auth._require(session)
    wanted = _axis(axis)

    def work():
        sid, _ = _scenario(session, user, scenario_id)
        found = horizon.problems(_rows(rows), _kinds(wanted))
        if found:
            raise AppError("validation", INVALID, 422, found)
        return _parts(params.preview_parts(session, sid, today(), [(b, int(c), u) for b, c, u in _rows(rows)], week_start, plan_start))

    return auth._db(work)


def update_time_buckets(session: Session | None, actor: CurrentUser, axis: str, rows: list[dict], scenario_id: int | None = None) -> dict:
    session = auth._require(session)
    wanted = _axis(axis)

    def work():
        sid, name = _scenario(session, actor, scenario_id)
        try:
            params.save_buckets(session, sid, wanted, _rows(rows), lambda ax, old, new: audit.write_audit(
                session, ACTION_BUCKETS, actor.id, OBJECT, _key(name, f"{ax} ekseni"), {"Value": new}, {"Value": old}, scenario=name))
        except params.ParamError as err:
            session.rollback()
            raise _invalid(err) from None
        session.commit()

    auth._db(work)
    return time_buckets(session, actor, axis, scenario_id)

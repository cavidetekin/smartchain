"""Manuel değer (fonksiyon 11, 12, 13; K-170): kaydetme, kaldırma, hücre kaynağı ve veri sözlüğünde Manuel.

Kaydetme mevcut veride yerinde güncellenir, yeni veri versiyonu açılmaz (K-167): core'un güncel satırında hücre manuel değere döner, alttaki değer
(ERP ya da kural sonucu) `ManualValue`'da saklanır. Kaldırınca hücreye son alttaki değer döner. Her değişiklik denetim izine yazılır (K-108).
Zamanlanmış iş ya da aktarım sürerken kaydedilmez (409).
"""
from collections.abc import Iterable
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration.structural import BadValue, convert
from app.jobs.constants import ACTIVE_STATUSES, TYPE_TRANSFER
from app.manual import (ERP, FIELDS, MANUAL, RULE, RULE_SOURCE, SOURCE, UNVERSIONED, as_text, core_table, kind, manual_fields, not_manual_reason,
                        typed)

from ..errors import AppError
from ..lists.master_data import BY_NAME
from ..repositories import audit, integration as integration_repo
from . import auth, flows
from .auth import CurrentUser

SAVE_ACTION, REMOVE_ACTION, MANUAL_ACTION = "Manuel değer girildi", "Manuel değer kaldırıldı", "Manuel değişikliği"
OBJECT = "Manuel değer"
TRANSFER_RUNNING = "Aktarım sürüyor. Bitince kaydedin."


@dataclass(frozen=True)
class Target:
    list_name: str
    table: str
    title: str


def target(list_name: str) -> Target:
    defn = BY_NAME.get(list_name)
    if defn is None:
        raise AppError("not_found", "Liste bulunamadı.", 404)
    return Target(list_name, defn.table_name, defn.title)


def _ensure_idle(session: Session) -> None:
    flows.ensure_idle(session)  # K-163
    job = integration_repo.JOB
    if session.execute(sa.select(job.c.Id).where(job.c.JobType == TYPE_TRANSFER, job.c.Status.in_(ACTIVE_STATUSES)).limit(1)).first():
        raise AppError("transfer_running", TRANSFER_RUNNING, 409)


def _current(table: str, t: sa.Table, key) -> list:
    """Kaydın güncel satırı (versiyonlu tabloda VersionTo boş; birimde kod)."""
    if table == "UnitOfMeasure":
        return [t.c.Code == str(key)]
    conds = [t.c.Id == int(key)]
    if table not in UNVERSIONED:
        conds.append(t.c.VersionTo.is_(None))
    return conds


def _record_text(session: Session, table: str, t: sa.Table, key) -> str:
    """Denetim izinde kaydın okunur adı: kod, yoksa iş anahtarı."""
    col = t.c.Code if "Code" in t.c else t.c.BusinessKey if "BusinessKey" in t.c else None
    value = session.execute(sa.select(col).where(*_current(table, t, key))).scalar() if col is not None else None
    return str(value).replace("|", " · ") if value else str(key)


# Hücre ipucundaki kalıp (K-172): "Sayı girilmeli."; özet "Kaydedilmedi. ALT-006 · Güvenlik stoğu: sayı girilmeli." ön yüzde kurulur
TYPE_PROBLEM = {"number": "Sayı girilmeli.", "integer": "Tam sayı girilmeli.", "date": "Tarih girilmeli.", "datetime": "Tarih girilmeli.",
                "bool": "Evet ya da Hayır girilmeli.", "text": "Metin girilmeli."}
LIST_PROBLEM = "Listedeki değerlerden biri girilmeli."
REQUIRED_PROBLEM = "Değer girilmeli (zorunlu alan)."
NOT_CURRENT = "Kayıt güncel veride yok."
NOT_MANUAL = "Manuel değer girilemez."


def _parse(table: str, col: sa.Column, value, required: bool):
    """Gelen değer alanın tipine; tip, uzunluk, ondalık sayısı, değer listesi ve zorunluluk denetlenir. Uymazsa neden (str)."""
    k = kind(col)
    if k == "bool" and isinstance(value, str) and value.strip().casefold() in ("evet", "hayır", "hayir"):
        value = value.strip().casefold() == "evet"
    try:
        length = getattr(col.type, "length", None) if k == "text" else None
        digits = col.type.precision - col.type.scale if k == "number" and col.type.precision else None
        parsed = convert(k, value, length, digits)
    except BadValue as exc:
        if exc.check == "length":
            return None, f"En çok {length} karakter."
        if exc.check == "range":
            return None, "Sayı alana sığmıyor."
        return None, TYPE_PROBLEM[k]
    if k == "number" and parsed is not None and col.type.scale is not None:
        from decimal import Decimal
        if -Decimal(str(parsed)).normalize().as_tuple().exponent > col.type.scale:
            return None, f"En çok {col.type.scale} ondalık."
    if k == "bool" and parsed is not None:
        parsed = bool(parsed)
    if k == "date" and parsed is not None:
        parsed = parsed.date()
    if parsed is None and required:
        return None, REQUIRED_PROBLEM
    values = (col.info or {}).get("values")
    if values and parsed is not None and parsed not in values:
        return None, LIST_PROBLEM
    return parsed, None


def _required(session: Session, table: str, field: str, col: sa.Column) -> bool:
    flag = session.execute(sa.select(FIELDS.c.IsRequired).where(FIELDS.c.TableName == table, FIELDS.c.FieldName == field)).scalar()
    return bool(flag) or not col.nullable


def save(session: Session | None, actor: CurrentUser, list_name: str, changes: list[dict]) -> dict:
    """changes: [{id, field, value}]. Hepsi geçerliyse tek işlemde yazılır; değilse 422 ve sorunlu hücreler, hiçbiri yazılmaz."""
    session = auth._require(session)
    tg = target(list_name)
    t = core_table(tg.table)

    def work():
        _ensure_idle(session)
        allowed = manual_fields(session, tg.table)
        problems, parsed = [], []

        def problem(key, field, text):  # hücre ve kaydın okunur adı (özet mesaj için, K-172)
            problems.append({"id": str(key), "field": field, "problem": text, "record": _record_text(session, tg.table, t, key)})

        for ch in changes:
            field, key = ch["field"], ch["id"]
            if field not in allowed:
                problem(key, field, not_manual_reason(tg.table, field) or NOT_MANUAL)
                continue
            col = t.c[field]
            value, text = _parse(tg.table, col, ch.get("value"), _required(session, tg.table, field, col))
            if text:
                problem(key, field, text)
                continue
            if not session.execute(sa.select(sa.literal(1)).where(*_current(tg.table, t, key))).first():
                problem(key, field, NOT_CURRENT)
                continue
            parsed.append((str(key), field, value))
        if problems:
            raise AppError("validation", "Kaydedilmedi.", 422, problems)  # ya hep ya hiç (K-170)
        for key, field, value in parsed:
            _write(session, actor, tg, t, key, field, value)
        session.commit()
        return {"saved": len(parsed)}

    return auth._db(work)


def _write(session: Session, actor: CurrentUser, tg: Target, t: sa.Table, key: str, field: str, value) -> None:
    col = t.c[field]
    where = _current(tg.table, t, key)
    old = session.execute(sa.select(col).where(*where)).scalar()
    mv = session.execute(sa.select(MANUAL.c.Id).where(MANUAL.c.TableName == tg.table, MANUAL.c.RecordKey == key, MANUAL.c.FieldName == field)).scalar()
    if mv is None:  # ilk giriş: alttaki değer ve kaynağı saklanır
        base = session.execute(sa.select(as_text(col, col)).where(*where)).scalar()
        rule = session.execute(sa.select(SOURCE.c.DataRuleId).where(SOURCE.c.TableName == tg.table, SOURCE.c.RecordId == (None if tg.table == "UnitOfMeasure" else int(key)),
                                                                    SOURCE.c.FieldName == field, SOURCE.c.Source == RULE_SOURCE)).scalar()
        session.execute(sa.insert(MANUAL).values(
            TableName=tg.table, RecordKey=key, FieldName=field, BaseValue=base, UnderlyingValue=base, UnderlyingSource=RULE_SOURCE if rule else ERP,
            UnderlyingRuleId=rule, IsBaseChanged=False, CreatedBy=actor.id, CreatedAt=sa.func.sysutcdatetime(), UpdatedBy=actor.id, UpdatedAt=sa.func.sysutcdatetime()))
    session.execute(sa.update(t).where(*where).values({field: value}))
    text = session.execute(sa.select(as_text(col, col)).where(*where)).scalar()
    session.execute(sa.update(MANUAL).where(MANUAL.c.TableName == tg.table, MANUAL.c.RecordKey == key, MANUAL.c.FieldName == field)
                    .values(Value=text, UpdatedBy=actor.id, UpdatedAt=sa.func.sysutcdatetime()))
    audit.write_audit(session, SAVE_ACTION, actor.id, OBJECT, f"{tg.title} · {_record_text(session, tg.table, t, key)}",
                      {"list": tg.list_name, "field": field, "Value": value}, {"list": tg.list_name, "field": field, "Value": old})


def _restore(session: Session, actor: CurrentUser | None, tg: Target, t: sa.Table, rows: Iterable) -> int:
    """Manuel değerler kalkar, hücreye son alttaki değer döner (kural ya da ERP)."""
    n = 0
    for mv in rows:
        col = t.c[mv.FieldName]
        where = _current(tg.table, t, mv.RecordKey)
        old = session.execute(sa.select(col).where(*where)).scalar()
        session.execute(sa.update(t).where(*where).values({mv.FieldName: sa.select(sa.cast(sa.literal(mv.UnderlyingValue, sa.Unicode(200)), col.type)
                                                                                     if kind(col) != "text" else sa.literal(mv.UnderlyingValue, sa.Unicode(200))).scalar_subquery()}))
        session.execute(sa.delete(MANUAL).where(MANUAL.c.Id == mv.Id))
        audit.write_audit(session, REMOVE_ACTION, actor.id if actor else None, OBJECT, f"{tg.title} · {_record_text(session, tg.table, t, mv.RecordKey)}",
                          {"list": tg.list_name, "field": mv.FieldName, "Value": typed(mv.UnderlyingValue, col)},
                          {"list": tg.list_name, "field": mv.FieldName, "Value": old})
        n += 1
    return n


def remove(session: Session | None, actor: CurrentUser, list_name: str, items: list[dict]) -> dict:
    """items: [{id, field}] ya da [{id}] (kaydın bütün manuel değerleri)."""
    session = auth._require(session)
    tg = target(list_name)
    t = core_table(tg.table)

    def work():
        _ensure_idle(session)
        conds = [sa.and_(MANUAL.c.RecordKey == str(i["id"]), MANUAL.c.FieldName == i["field"]) if i.get("field") else MANUAL.c.RecordKey == str(i["id"])
                 for i in items]
        rows = session.execute(sa.select(MANUAL).where(MANUAL.c.TableName == tg.table, sa.or_(*conds))).all() if conds else []
        n = _restore(session, actor, tg, t, rows)
        session.commit()
        return {"removed": n}

    return auth._db(work)


# ------------------------------------------------------------------ liste: hücre kaynağı

def annotate(session: Session, table: str, rows: list[dict]) -> None:
    """Satırlara `_sources`: manuel değerli ve kuralla gelen hücrelerin kaynağı (ipucu, köşe işareti). ERP olan hücre yazılmaz."""
    if not rows:
        return
    keys = [str(r["Id"]) for r in rows]
    t = core_table(table)
    users = metadata_users()
    out: dict[str, dict] = {k: {} for k in keys}
    rule_ids = set()
    manual = session.execute(sa.select(MANUAL, sa.func.coalesce(users.c.FullName, users.c.UserName).label("FullName"))
                             .select_from(MANUAL).outerjoin(users, users.c.Id == MANUAL.c.UpdatedBy)
                             .where(MANUAL.c.TableName == table, MANUAL.c.RecordKey.in_(keys))).all()
    for m in manual:
        col = t.c[m.FieldName]
        out[m.RecordKey][m.FieldName] = {"source": "Manuel", "by": m.FullName, "at": m.UpdatedAt.isoformat(timespec="seconds") + "+00:00",
                                         "changed": bool(m.IsBaseChanged), "base": typed(m.BaseValue, col), "underlying": typed(m.UnderlyingValue, col),
                                         "underlying_source": m.UnderlyingSource, "rule_id": m.UnderlyingRuleId}
        if m.UnderlyingRuleId:
            rule_ids.add(m.UnderlyingRuleId)
    if table != "UnitOfMeasure":
        for s in session.execute(sa.select(SOURCE.c.RecordId, SOURCE.c.FieldName, SOURCE.c.DataRuleId).where(
                SOURCE.c.TableName == table, SOURCE.c.Source == RULE_SOURCE, SOURCE.c.RecordId.in_([int(k) for k in keys]))).all():
            cell = out[str(s.RecordId)]
            if s.FieldName not in cell:
                cell[s.FieldName] = {"source": "Kural", "rule_id": s.DataRuleId}
                rule_ids.add(s.DataRuleId)
    names = dict(session.execute(sa.select(RULE.c.Id, RULE.c.Name).where(RULE.c.Id.in_(rule_ids))).all()) if rule_ids else {}
    for r in rows:
        cells = out[str(r["Id"])]
        for c in cells.values():
            if c.get("rule_id"):
                c["rule_name"] = names.get(c["rule_id"])
        r["_sources"] = cells


def metadata_users() -> sa.Table:
    from db.models import metadata
    return metadata.tables["adm.AppUser"]


# ------------------------------------------------------------------ veri sözlüğü: Manuel

def manual_info(session: Session, table: str, field: str) -> dict:
    return {"manual_reason": not_manual_reason(table, field),
            "manual_count": session.execute(sa.select(sa.func.count()).select_from(MANUAL).where(MANUAL.c.TableName == table, MANUAL.c.FieldName == field)).scalar()}


def set_manual(session: Session, actor: CurrentUser, table: str, field: str, on: bool, confirm: bool) -> dict | None:
    """Manuel açılır ya da kapanır. Kapanırken manuel değer varsa onay istenir (409 `manual_values`, sayıyla); onayla manuel değerler kalkar."""
    reason = not_manual_reason(table, field)
    if on and reason:
        raise AppError("not_manual", reason, 422, [{"field": "manual_overrides", "problem": reason}])
    current = session.execute(sa.select(FIELDS.c.ManualOverrides).where(FIELDS.c.TableName == table, FIELDS.c.FieldName == field)).scalar()
    if bool(current) == on:
        return None
    if not on:
        rows = session.execute(sa.select(MANUAL).where(MANUAL.c.TableName == table, MANUAL.c.FieldName == field)).all()
        if rows and not confirm:
            raise AppError("manual_values", f"{len(rows)} kayıtta manuel değer kaldırılacak.", 409, [{"field": "manual_overrides", "count": len(rows)}])
        if rows:
            _ensure_idle(session)
            list_name = next(d.name for d in BY_NAME.values() if d.table_name == table)
            _restore(session, actor, target(list_name), core_table(table), rows)
    session.execute(sa.update(FIELDS).where(FIELDS.c.TableName == table, FIELDS.c.FieldName == field).values(ManualOverrides=on))
    audit.write_audit(session, MANUAL_ACTION, actor.id, "FieldDefinition", f"{table}.{field}", {"ManualOverrides": on}, {"ManualOverrides": bool(current)})
    return None

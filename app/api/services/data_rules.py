"""Veri kuralları (ekran 04, fonksiyon 16, 18, 19; K-140…K-142).

Tanımlama (16) ve sıra / aç-kapa (18): System owner ve Admin yazar, Key user okur, End user görmez. Kayıt toplu ve tek işlemdir
(K-132): biri geçersizse hiçbiri yazılmaz. Kayıt kendiliğinden uygulanmaz; "Kuralları yeniden uygula" (19) zinciri başlatır.
"""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration import contract
from app.validation import conditions, data_rule, engine, texts
from app.validation.current import current_rows
from app.validation.data_rule import Result, RuleError
from app.validation.rules_step import CONDITION, EFFECT, RULE, groups_of
from app.validation.sqlkit import label

from ..errors import AppError
from ..permissions import Access
from ..repositories import audit
from . import auth, authz, flows
from .auth import CurrentUser
from .validation import _groups_payload, entity_of, state_of

OBJECT_RULE, OBJECT_ENTITY = "DataRule", "IntegrationEntity"
ACTION_RULE, ACTION_ORDER, ACTION_APPLY = "Veri kuralı", "Kural sırası", "Kuralları yeniden uygula"
MAX_NAME = 200


def _bad(code: str, message: str, problem: str, field: str = "rules") -> AppError:
    return AppError(code, message, 422, [{"field": field, "problem": problem}])


def fields(session: Session | None, table: str) -> list[dict]:
    """Kural penceresinin alanları ve hedef olup olamayacakları (anahtar alan hedef olamaz, K-141); güncel etiketle, etiketsiz ek alan yok (K-143)."""
    session = auth._require(session)
    entity = entity_of(table)

    def work():
        targets, names, cols = data_rule.targets(entity.table), texts.field_labels(session, entity.table), conditions.columns(entity.table)
        return [{"name": n, "label": names[n], "kind": conditions.kind_of(cols[n]), "values": list(cols[n].info.get("values") or []),
                 "target": targets[n] is None, "reason": targets[n]} for n in texts.editor_fields(session, entity.table)]

    return auth._db(work)


def _result_payload(rule: dict) -> dict:
    return {"kind": rule["ResultKind"], "value": rule["Value"], "source_field": rule["SourceField"], "operator": rule["FormulaOperator"],
            "operand_value": rule["OperandValue"], "operand_field": rule["OperandField"]}


def rule_detail(session: Session | None, rule_id: int) -> dict:
    session = auth._require(session)

    def work():
        row = session.execute(sa.select(RULE).where(RULE.c.Id == rule_id)).mappings().first()
        if row is None:
            raise AppError("data_rule_not_found", "Kural bulunamadı.", 404)
        rule = dict(row)
        return {"id": rule["Id"], "entity": rule["EntityName"], "name": rule["Name"], "target": rule["TargetField"], "result": _result_payload(rule),
                "mode": rule["ApplyMode"], "active": bool(rule["IsActive"]), "seq": rule["Seq"],
                "groups": _groups_payload(groups_of(session, rule["Id"])), "condition": rule["ConditionText"] or "", "result_text": rule["ResultText"] or ""}

    return auth._db(work)


def _parse_groups(entity: str, raw) -> list[list[conditions.Condition]]:
    """Koşulsuz kural bütün satırlara uygulanır (K-141); boş grup kabul edilmez."""
    if raw in (None, []):
        return []
    if not isinstance(raw, list):
        raise _bad("data_rule_bad_condition", "Koşul geçersiz.", "Koşul listesi bekleniyor.")
    groups = []
    for g in raw:
        if not isinstance(g, list) or not g:
            raise _bad("data_rule_bad_condition", "Koşul geçersiz.", "Boş koşul grubu.")
        group = []
        for c in g:
            cond = conditions.Condition(str(c.get("field") or ""), str(c.get("operator") or ""),
                                        None if c.get("value") in (None, "") else str(c.get("value")), c.get("compare_field") or None)
            try:
                conditions.validate(entity, cond)
            except conditions.ConditionError as exc:
                raise _bad("data_rule_bad_condition", "Koşul geçersiz.", str(exc)) from None
            group.append(cond)
        groups.append(group)
    return groups


def _parse_result(raw) -> Result:
    raw = raw or {}
    blank = lambda v: None if v in (None, "") else str(v)  # noqa: E731
    return Result(str(raw.get("kind") or ""), blank(raw.get("value")), raw.get("source_field") or None, raw.get("operator") or None,
                  blank(raw.get("operand_value")), raw.get("operand_field") or None)


def _checked(entity: str, target: str, result: Result, mode: str) -> Result:
    try:
        return data_rule.validate(entity, target, result, mode)
    except RuleError as exc:
        code = "data_rule_bad_target" if "hedef" in str(exc).lower() or "anahtar" in str(exc).lower() else "data_rule_bad_result"
        raise _bad(code, "Kural geçersiz.", str(exc)) from None


def _write_conditions(session: Session, rule_id: int, groups: list[list[conditions.Condition]]) -> None:
    session.execute(sa.delete(CONDITION).where(CONDITION.c.DataRuleId == rule_id))
    for no, group in enumerate(groups, 1):
        for c in group:
            session.execute(sa.insert(CONDITION).values(DataRuleId=rule_id, GroupNo=no, FieldName=c.field, Operator=c.operator,
                                                        Value=c.value, CompareField=c.compare_field))


def _name_taken(session: Session, entity: str, name: str, rule_id: int | None = None) -> bool:
    q = sa.select(RULE.c.Id).where(RULE.c.EntityName == entity, RULE.c.Name == name)
    if rule_id is not None:
        q = q.where(RULE.c.Id != rule_id)
    return session.execute(q).first() is not None


def _shown(entity: str, name: str) -> str:
    return f"{entity_of(entity).name} · {name}"


def _renumber(session: Session, entity: str) -> None:
    ids = session.execute(sa.select(RULE.c.Id).where(RULE.c.EntityName == entity).order_by(RULE.c.Seq, RULE.c.Id)).scalars().all()
    for seq, rid in enumerate(ids, 1):
        session.execute(sa.update(RULE).where(RULE.c.Id == rid, RULE.c.Seq != seq).values(Seq=seq))


def _definition(session: Session, entity: str, change: dict, base: dict | None) -> dict:
    """Yeni ya da değişen kuralın hedef, sonuç, seçenek ve koşulu; denetlenmiş ve saklanacak biçimde."""
    target = change["target"] if "target" in change else (base or {}).get("TargetField")
    mode = change["mode"] if "mode" in change else (base or {}).get("ApplyMode")
    result = _parse_result(change["result"]) if "result" in change else (Result(base["ResultKind"], base["Value"], base["SourceField"], base["FormulaOperator"],
                                                                                  base["OperandValue"], base["OperandField"]) if base else _parse_result(None))
    if result.kind == data_rule.CLEAR:
        mode = data_rule.ALWAYS
    if not target:
        raise _bad("data_rule_bad_target", "Kural geçersiz.", "Hedef alan seçin.")
    result = _checked(entity, str(target), result, str(mode or ""))
    groups = _parse_groups(entity, change["groups"]) if "groups" in change else (groups_of(session, base["Id"]) if base else [])
    names = texts.field_labels(session, entity)  # metin güncel etiketle (K-143); etiket değişince texts.refresh yeniden yazar
    return {"target": str(target), "mode": mode, "result": result, "groups": groups,
            "condition": conditions.sentence(entity, groups, names) if groups else "", "result_text": data_rule.text(entity, str(target), result, names)}


def _values(d: dict) -> dict:
    r: Result = d["result"]
    return {"TargetField": d["target"], "ApplyMode": d["mode"], "ResultKind": r.kind, "Value": r.value, "SourceField": r.source_field,
            "FormulaOperator": r.operator, "OperandValue": r.operand_value, "OperandField": r.operand_field,
            "ConditionText": d["condition"][:400] or None, "ResultText": d["result_text"][:400]}


def _audit_values(entity: str, rule: dict) -> dict:
    return {"rule_name": rule["Name"], "target_field": label(entity, rule["TargetField"]), "result": rule["ResultText"] or "",
            "condition": rule["ConditionText"] or "", "apply_mode": rule["ApplyMode"], "active": bool(rule["IsActive"])}


def save_rules(session: Session | None, user: CurrentUser, changes: list[dict], orders: list[dict]) -> dict:
    """Toplu kayıt (K-132): kurallar, koşullar ve sıra tek işlemde. Değişen tablolar "Kurallar yeniden uygulansın mı?" içindir."""
    session = auth._require(session)
    authz.ensure(user, 16, Access.WRITE)
    if orders:
        authz.ensure(user, 18, Access.WRITE)

    def work():
        flows.ensure_idle(session)  # K-163: akış sürerken kural kaydedilmez
        changed: set[str] = set()
        now = engine.utcnow()
        for change in changes:
            rule_id = change.get("id")
            if rule_id is None:  # yeni kural: tablonun sonuna
                entity = entity_of(str(change.get("entity") or "")).table
                name = (change.get("name") or "").strip()
                if not name:
                    raise _bad("validation", "Girilen bilgiler geçersiz.", "Kural adı boş olamaz.")
                if _name_taken(session, entity, name[:MAX_NAME]):
                    raise _bad("data_rule_name_taken", "Bu adla kural var.", f"{name}: bu tabloda aynı adla kural var.")
                d = _definition(session, entity, change, None)
                seq = (session.execute(sa.select(sa.func.max(RULE.c.Seq)).where(RULE.c.EntityName == entity)).scalar() or 0) + 1
                row = dict(EntityName=entity, Name=name[:MAX_NAME], Seq=seq, IsActive=bool(change.get("active", True)),
                           UpdatedBy=user.id, UpdatedAt=now, **_values(d))
                new_id = session.execute(sa.insert(RULE).values(**row).returning(RULE.c.Id)).scalar_one()
                _write_conditions(session, new_id, d["groups"])
                _renumber(session, entity)  # sıra her zaman 1, 2, 3… (K-143)
                audit.write_audit(session, ACTION_RULE, user.id, OBJECT_RULE, _shown(entity, name),
                                  {"entity_name": entity_of(entity).name, **_audit_values(entity, row)})
                changed.add(entity)
                continue
            row = session.execute(sa.select(RULE).where(RULE.c.Id == int(rule_id))).mappings().first()
            if row is None:
                raise AppError("data_rule_not_found", "Kural bulunamadı.", 404)
            rule = dict(row)
            entity = rule["EntityName"]
            shown = _shown(entity, rule["Name"])
            if change.get("delete"):
                session.execute(sa.delete(EFFECT).where(EFFECT.c.DataRuleId == rule["Id"]))
                session.execute(sa.delete(CONDITION).where(CONDITION.c.DataRuleId == rule["Id"]))
                session.execute(sa.delete(RULE).where(RULE.c.Id == rule["Id"]))
                audit.write_audit(session, ACTION_RULE, user.id, OBJECT_RULE, shown, {"entity_name": entity_of(entity).name, "rule_name": rule["Name"], "deleted": True},
                                  _audit_values(entity, rule))
                _renumber(session, entity)
                changed.add(entity)
                continue
            values = {}
            if "name" in change and (change["name"] or "").strip() != rule["Name"]:
                name = (change["name"] or "").strip()
                if not name:
                    raise _bad("validation", "Girilen bilgiler geçersiz.", "Kural adı boş olamaz.")
                if _name_taken(session, entity, name[:MAX_NAME], rule["Id"]):
                    raise _bad("data_rule_name_taken", "Bu adla kural var.", f"{name}: bu tabloda aynı adla kural var.")
                values["Name"] = name[:MAX_NAME]
            if "active" in change and bool(change["active"]) != bool(rule["IsActive"]):
                values["IsActive"] = bool(change["active"])
            if any(k in change for k in ("target", "result", "mode", "groups")):
                d = _definition(session, entity, change, rule)
                values.update({k: v for k, v in _values(d).items() if v != rule[k]})
                if "groups" in change:
                    _write_conditions(session, rule["Id"], d["groups"])
            if values:
                session.execute(sa.update(RULE).where(RULE.c.Id == rule["Id"]).values(UpdatedBy=user.id, UpdatedAt=now, **values))
                after = {**rule, **values}
                old, new = _audit_values(entity, rule), _audit_values(entity, after)
                diff_old = {k: v for k, v in old.items() if new[k] != v}
                audit.write_audit(session, ACTION_RULE, user.id, OBJECT_RULE, shown,
                                  {"entity_name": entity_of(entity).name, "rule_name": after["Name"], **{k: new[k] for k in diff_old}}, diff_old)
                changed.add(entity)
        for item in orders:
            entity = entity_of(str(item.get("entity") or "")).table
            ids = [int(i) for i in item.get("ids") or []]
            rows = session.execute(sa.select(RULE.c.Id, RULE.c.Name, RULE.c.Seq).where(RULE.c.EntityName == entity).order_by(RULE.c.Seq, RULE.c.Id)).all()
            if sorted(ids) != sorted(r.Id for r in rows) or len(ids) != len(set(ids)):
                raise AppError("data_rule_order_stale", "Kural listesi değişti; liste yenilendi, sırayı yeniden kaydedin.", 409)
            before = [r.Name for r in rows]
            names = {r.Id: r.Name for r in rows}
            for seq, rid in enumerate(ids, 1):
                session.execute(sa.update(RULE).where(RULE.c.Id == rid, RULE.c.Seq != seq).values(Seq=seq, UpdatedBy=user.id, UpdatedAt=now))
            after = [names[i] for i in ids]
            if after != before:
                audit.write_audit(session, ACTION_ORDER, user.id, OBJECT_ENTITY, entity_of(entity).name,
                                  {"entity_name": entity_of(entity).name, "order": " → ".join(after)}, {"order": " → ".join(before)})
                changed.add(entity)
        session.commit()
        return {"saved": len(changes) + len(orders), "changed_entities": sorted(changed)}

    return auth._db(work)


def apply(session: Session | None, user: CurrentUser, table: str | None) -> dict:
    """Kuralları yeniden uygula (19, K-142): tablo seçiliyse o tablonun zinciri; değilse kuralı olan bütün tablolar, tablolar arası sonda."""
    session = auth._require(session)
    authz.ensure(user, 19, Access.WRITE)

    def work():
        flows.ensure_idle(session)
        if table:
            entities = [entity_of(table).table]
        else:
            entities = sorted(session.execute(sa.select(RULE.c.EntityName).distinct()).scalars().all())
            if not entities:
                raise AppError("data_rule_none", "Uygulanacak kural yok.", 409)
        entities = [e for e in entities if current_rows(session, e)]
        if not entities:
            raise AppError("validation_no_data", "Bu tabloda valide edilecek veri yok.", 409)
        running = [e for e in entities if state_of(session, e) in (engine.QUEUED, engine.RULES, engine.VALIDATING)]
        if running:
            raise AppError("validation_running", f"Validasyonu süren tablo var: {', '.join(entity_of(e).name for e in running)}.", 409)
        audit.write_audit(session, ACTION_APPLY, user.id, OBJECT_ENTITY, ", ".join(entity_of(e).name for e in entities)[:200],
                          {"entities": ", ".join(entity_of(e).name for e in entities)})
        if len(entities) == 1:
            return {"job_ids": [engine.enqueue(session, entities[0], engine.SCOPE_TABLE, engine.TRIGGER_RULES, None, user.id)]}
        group = engine.enqueue_group(session, entities, engine.TRIGGER_RULES, user.id)
        return {"job_ids": group}

    return auth._db(work)

"""Zincirin ilk adımı: veri kuralları (fonksiyon 19; K-134, K-140, K-141).

İşlenmiş katman ham katmanın güncel hâlinden kurulur; tablonun aktif kuralları Seq sırasıyla, her biri kendi savepoint'inde çalışır.
Sonraki kural öncekinin sonucunu görür; aynı alana yazan kurallarda sonuncu kazanır. Değer, Alan ya da Formül boş çıkarsa hücre
değişmez; değişmeyen hücre yazılmaz. Değişen hücre kural izine (DataRuleEffect) yazılır: son kural ve ham değer.
Kuralın tamamını etkileyen hata (tanımsız alan, bütün kuralda başarısız olan dönüşüm) kuralı geri alır: "Çalışmadı" ve nedeni.
Kopya, kurallar ve durumlar tek işlemdedir; iş düşerse işlenmiş katman önceki hâlinde kalır.
"""
import logging
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata

from . import conditions, data_rule, processed
from .conditions import Condition, ConditionError
from .data_rule import RuleError
from .sqlkit import raw_table, shown, table

log = logging.getLogger("smartchain.rules")

RULE = metadata.tables["adm.DataRule"]
CONDITION = metadata.tables["adm.DataRuleCondition"]
EFFECT = metadata.tables["adm.DataRuleEffect"]
HIT = sa.table("#hit", sa.column("Id", sa.BigInteger))


def rules_of(session: Session, entity: str, active: bool | None = None) -> list[dict]:
    q = sa.select(RULE).where(RULE.c.EntityName == entity).order_by(RULE.c.Seq, RULE.c.Id)
    if active is not None:
        q = q.where(RULE.c.IsActive == active)
    return [dict(r) for r in session.execute(q).mappings()]


def groups_of(session: Session, rule_id: int) -> list[list[Condition]]:
    rows = session.execute(sa.select(CONDITION).where(CONDITION.c.DataRuleId == rule_id).order_by(CONDITION.c.GroupNo, CONDITION.c.Id)).mappings()
    groups: dict[int, list[Condition]] = {}
    for r in rows:
        groups.setdefault(r["GroupNo"], []).append(Condition(r["FieldName"], r["Operator"], r["Value"], r["CompareField"]))
    return [groups[k] for k in sorted(groups)]


def result_of(rule: dict) -> data_rule.Result:
    return data_rule.Result(rule["ResultKind"], rule["Value"], rule["SourceField"], rule["FormulaOperator"], rule["OperandValue"], rule["OperandField"])


def _changed(target, expr, clear: bool) -> sa.ColumnElement:
    if clear:
        return target.is_not(None)
    return sa.and_(expr.is_not(None), sa.or_(target.is_(None), target != expr))


def _apply(session: Session, entity: str, rule: dict) -> int:
    """Kuralı uygular; değişen hücre sayısı. Geçersiz kural RuleError ya da ConditionError."""
    t, raw = table(entity), raw_table(entity)
    field = rule["TargetField"]
    result = data_rule.validate(entity, field, result_of(rule), rule["ApplyMode"])
    groups = groups_of(session, rule["Id"])
    wheres = [conditions.where(entity, groups)(t)] if groups else []
    target = t.c[field]
    expr = data_rule.expression(t, entity, field, result)
    if rule["ApplyMode"] == data_rule.ONLY_EMPTY:
        wheres.append(target.is_(None))
    wheres.append(_changed(target, expr, result.kind == data_rule.CLEAR))
    session.execute(sa.text("DELETE FROM #hit"))
    session.execute(sa.insert(HIT).from_select(["Id"], sa.select(t.c.StagingRowId).where(*wheres)))
    hits = sa.select(HIT.c.Id)
    changed = session.execute(sa.update(t).where(t.c.StagingRowId.in_(hits)).values({field: expr})).rowcount
    if changed:
        session.execute(sa.delete(EFFECT).where(EFFECT.c.EntityName == entity, EFFECT.c.FieldName == field, EFFECT.c.StagingRowId.in_(hits)))
        session.execute(sa.insert(EFFECT).from_select(
            ["EntityName", "StagingRowId", "FieldName", "DataRuleId", "RawValue"],
            sa.select(sa.literal(entity, sa.Unicode(60)), HIT.c.Id, sa.literal(field, sa.Unicode(60)), sa.literal(rule["Id"], sa.BigInteger),
                      sa.func.left(shown(raw.c[field]), 200))
            .select_from(HIT.join(raw, raw.c.StagingRowId == HIT.c.Id))))
    return changed


def _db_message(exc: Exception) -> str:
    text = str(getattr(exc, "orig", exc))
    if "overflow" in text.lower():
        return "Sonuç alana sığmıyor (taşma)."
    if "conversion failed" in text.lower() or "converting" in text.lower():
        return "Tip dönüşümü başarısız."
    return "Kural çalıştırılamadı."


def run(session: Session, entity: str) -> int:
    """İşlenmiş katmanı kurar, aktif kuralları sırayla uygular; commit eder. Çalışan kural sayısı."""
    processed.rebuild(session, entity)
    rules = rules_of(session, entity, active=True)
    ran = 0
    if rules:
        session.execute(sa.text("CREATE TABLE #hit (Id bigint PRIMARY KEY)"))
        try:
            for rule in rules:
                status, message = data_rule.RAN, None
                savepoint = session.begin_nested()
                try:
                    _apply(session, entity, rule)
                    savepoint.commit()
                    ran += 1
                except (RuleError, ConditionError, KeyError) as exc:
                    savepoint.rollback()
                    status, message = data_rule.FAILED, str(exc) or "Kural geçersiz."
                except sa.exc.DBAPIError as exc:
                    savepoint.rollback()
                    status, message = data_rule.FAILED, _db_message(exc)
                    log.warning("Veri kuralı %s (%s) çalışmadı: %s", rule["Id"], entity, exc)
                session.execute(sa.update(RULE).where(RULE.c.Id == rule["Id"]).values(
                    LastRunStatus=status, LastRunMessage=message[:400] if message else None, LastRunAt=datetime.now(timezone.utc).replace(tzinfo=None)))
        finally:
            session.execute(sa.text("DROP TABLE #hit"))
    session.commit()
    return ran

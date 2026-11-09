"""Alan etiketleri ve kural metinleri (K-88, K-143).

Etiket: veri sözlüğünde (FieldDefinition.Label) etiket varsa o, yoksa sözleşmenin standart etiketi; ek alanda standart ad
("Ek sayı alanı 1"). Kural editörlerinde yalnız etiketi tanımlı ek alanlar listelenir. Kuralların okunur Koşul ve Sonuç
metinleri güncel etiketlerden üretilir: kayıtta ve veri sözlüğünde bir etiket değişince o tablonun kural metinleri yeniden
yazılır; liste her zaman güncel etiketi gösterir, süzme ve sıralama da aynı metinde çalışır.
"""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.dictionary import ADDITIONAL
from db.models import metadata

from . import conditions
from .sqlkit import labels as standard_labels

FIELD_DEFINITION = metadata.tables["adm.FieldDefinition"]
DATA_RULE = metadata.tables["adm.DataRule"]
VALIDATION_RULE = metadata.tables["adm.ValidationRule"]


def dictionary_labels(session: Session, entity: str) -> dict[str, str]:
    """Veri sözlüğündeki etiketler (boş olanlar atlanır)."""
    rows = session.execute(sa.select(FIELD_DEFINITION.c.FieldName, FIELD_DEFINITION.c.Label)
                           .where(FIELD_DEFINITION.c.TableName == entity, FIELD_DEFINITION.c.Label.is_not(None)))
    return {name: label.strip() for name, label in rows if label and label.strip()}


def field_labels(session: Session, entity: str) -> dict[str, str]:
    """Alan → güncel etiket: veri sözlüğü, yoksa standart etiket (ek alanda standart ad)."""
    return {**standard_labels(entity), **dictionary_labels(session, entity)}


def editor_fields(session: Session, entity: str) -> list[str]:
    """Kural editörlerinde listelenen alanlar: etiketsiz ek alan çıkar (K-143)."""
    labelled = dictionary_labels(session, entity)
    return [name for name in conditions.columns(entity) if not ADDITIONAL.match(name) or name in labelled]


def refresh(session: Session, entity: str | None = None) -> int:
    """Kural metinlerini güncel etiketlerle yeniden yazar (veri kuralları; kullanıcı ve düzenlenmiş hazır validasyon kuralları).
    commit çağıranındır. Yeniden yazılan kural sayısı."""
    from . import data_rule
    from .rules_step import groups_of, result_of
    from .engine import user_groups

    written = 0
    q = sa.select(DATA_RULE.c.Id, DATA_RULE.c.EntityName, DATA_RULE.c.TargetField, DATA_RULE.c.ResultKind, DATA_RULE.c.Value, DATA_RULE.c.SourceField,
                  DATA_RULE.c.FormulaOperator, DATA_RULE.c.OperandValue, DATA_RULE.c.OperandField, DATA_RULE.c.ConditionText, DATA_RULE.c.ResultText)
    if entity:
        q = q.where(DATA_RULE.c.EntityName == entity)
    cache: dict[str, dict[str, str]] = {}
    for r in session.execute(q).mappings().all():
        names = cache.setdefault(r["EntityName"], field_labels(session, r["EntityName"]))
        groups = groups_of(session, r["Id"])
        try:
            condition = conditions.sentence(r["EntityName"], groups, names) if groups else ""
            result = data_rule.text(r["EntityName"], r["TargetField"], result_of(dict(r)), names)
        except (KeyError, ValueError):  # alan sözleşmeden kalkmış: metin olduğu gibi kalır, kural "Çalışmadı" olur
            continue
        if (condition or None) != r["ConditionText"] or result != r["ResultText"]:
            session.execute(sa.update(DATA_RULE).where(DATA_RULE.c.Id == r["Id"]).values(ConditionText=condition[:400] or None, ResultText=result[:400]))
            written += 1
    q = sa.select(VALIDATION_RULE.c.Id, VALIDATION_RULE.c.EntityName, VALIDATION_RULE.c.ConditionText).where(
        sa.or_(VALIDATION_RULE.c.Kind == "Kullanıcı", VALIDATION_RULE.c.IsCustomized == sa.true()))
    if entity:
        q = q.where(VALIDATION_RULE.c.EntityName == entity)
    for r in session.execute(q).mappings().all():
        groups = user_groups(session, r["Id"])
        if not groups:
            continue
        names = cache.setdefault(r["EntityName"], field_labels(session, r["EntityName"]))
        try:
            text = conditions.sentence(r["EntityName"], groups, names)[:400]
        except (KeyError, ValueError):
            continue
        if text != r["ConditionText"]:
            session.execute(sa.update(VALIDATION_RULE).where(VALIDATION_RULE.c.Id == r["Id"]).values(ConditionText=text))
            written += 1
    return written

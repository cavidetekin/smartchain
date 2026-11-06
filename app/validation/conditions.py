"""Koşullar (K-136, K-139): kullanıcı kuralı ve editörle ifade edilen hazır kural; SQL'e çeviri ve okunur cümle. Veri kuralları da kullanır (4.2).

Koşullar VE gruplarıdır, gruplar arası VEYA. Alan adı sözleşmeden doğrulanır, değer her zaman parametreyle gider.
Boş değer: ≠ boşu da kapsar (boş bayrak "1 değil", K-138); öteki karşılaştırmalar boş alanda tutmaz (SQL).
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

import sqlalchemy as sa

from app.integration.contract import stg_columns

from .sqlkit import label

EQ, NE, GT, LT, GE, LE = "=", "≠", ">", "<", "≥", "≤"
CONTAINS, STARTS, IN_LIST, EMPTY, FILLED = "İçerir", "İle başlar", "Listede", "Boş", "Boş değil"
OPERATORS = (EQ, NE, GT, LT, GE, LE, CONTAINS, STARTS, IN_LIST, EMPTY, FILLED)  # veri kurallarıyla aynı (K-139)
NO_VALUE = (EMPTY, FILLED)
TEXT_ONLY = (CONTAINS, STARTS)
SYMBOL = {EMPTY: "boş", FILLED: "boş değil", CONTAINS: "içerir", STARTS: "ile başlar", IN_LIST: "listede"}
EXCLUDED = ("StagingRowId", "ImportBatchId", "RowStatus", "ErrorText", "SourceRowNo", "IsCurrent")


class ConditionError(ValueError):
    """Koşul geçersiz: alan yok, operatör yok, değer tipe uymuyor."""


@dataclass(frozen=True)
class Condition:
    field: str
    operator: str
    value: str | None = None
    compare_field: str | None = None


def kind_of(col: sa.Column) -> str:
    t = col.type
    if isinstance(t, sa.Boolean):
        return "bool"
    if isinstance(t, (sa.Date, sa.DateTime)):
        return "date"
    if isinstance(t, sa.Integer):
        return "integer"
    if isinstance(t, sa.Numeric):
        return "number"
    return "text"


def columns(entity: str) -> dict[str, sa.Column]:
    return {c.name: c for c in stg_columns(entity) if c.name not in EXCLUDED}


def _parse(kind: str, raw: str):
    text = raw.strip()
    try:
        if kind == "bool":
            if text.casefold() in ("1", "evet", "true"):
                return True
            if text.casefold() in ("0", "hayır", "false"):
                return False
            raise ValueError
        if kind == "date":
            if "." in text:
                d, m, y = text.split(".")
                return date(int(y), int(m), int(d))
            return date.fromisoformat(text)
        if kind in ("integer", "number"):
            normal = text.replace(" ", "")
            if "," in normal:
                normal = normal.replace(".", "").replace(",", ".")
            value = Decimal(normal)
            if kind == "integer" and value != value.to_integral_value():
                raise ValueError
            return int(value) if kind == "integer" else value
    except (ValueError, InvalidOperation):
        raise ConditionError(f"Değer alanın tipine uymuyor: {raw}") from None
    return text


def _escape_like(text: str) -> str:
    return text.replace("[", "[[]").replace("%", "[%]").replace("_", "[_]")


def validate(entity: str, condition: Condition) -> None:
    cols = columns(entity)
    if condition.field not in cols:
        raise ConditionError(f"Alan yok: {condition.field}")
    if condition.operator not in OPERATORS:
        raise ConditionError(f"Operatör yok: {condition.operator}")
    kind = kind_of(cols[condition.field])
    if condition.operator in NO_VALUE:
        return
    if condition.operator in TEXT_ONLY and kind != "text":
        raise ConditionError(f"{condition.operator} yalnız metin alanında kullanılır.")
    if condition.compare_field:
        if condition.compare_field not in cols:
            raise ConditionError(f"Alan yok: {condition.compare_field}")
        if condition.operator in (IN_LIST, *TEXT_ONLY):
            raise ConditionError(f"{condition.operator} alan–alan karşılaştırmasında kullanılmaz.")
        other = kind_of(cols[condition.compare_field])
        if {kind, other} - {"integer", "number"} and kind != other:
            raise ConditionError("Karşılaştırılan iki alanın tipi uyumlu olmalı.")
        return
    if condition.value is None or not str(condition.value).strip():
        raise ConditionError("Değer boş olamaz.")
    if condition.operator == IN_LIST:
        for part in str(condition.value).split(","):
            if part.strip():
                _parse(kind, part)
    else:
        _parse(kind, str(condition.value))


def _clause(t, entity: str, c: Condition) -> sa.ColumnElement:
    cols = columns(entity)
    col = t.c[c.field]
    kind = kind_of(cols[c.field])
    if c.operator == EMPTY:
        return col.is_(None)
    if c.operator == FILLED:
        return col.is_not(None)
    if c.compare_field:
        right = t.c[c.compare_field]
    elif c.operator == IN_LIST:
        values = [_parse(kind, p) for p in str(c.value).split(",") if p.strip()]
        return col.in_(values)
    elif c.operator == CONTAINS:
        return col.like("%" + _escape_like(str(c.value).strip()) + "%")
    elif c.operator == STARTS:
        return col.like(_escape_like(str(c.value).strip()) + "%")
    else:
        right = sa.literal(_parse(kind, str(c.value)), col.type)
    if c.operator == NE:  # boş da "eşit değil" sayılır (K-139)
        return sa.or_(col.is_(None), col != right)
    return {EQ: col == right, GT: col > right, GE: col >= right, LT: col < right, LE: col <= right}[c.operator]


def check(entity: str, groups) -> list[list[Condition]]:
    groups = [list(g) for g in groups if g]
    if not groups:
        raise ConditionError("Kuralın koşulu yok.")
    for group in groups:
        for c in group:
            validate(entity, c)
    return groups


def group_where(t, entity: str, group) -> sa.ColumnElement:
    return sa.and_(*[_clause(t, entity, c) for c in group])


def where(entity: str, groups: list[list[Condition]]):
    """Kural koşulunun SQL'i: tablo takma adı → koşul."""
    groups = check(entity, groups)
    return lambda t: sa.or_(*[group_where(t, entity, g) for g in groups])


def first_field(groups: list[list[Condition]]) -> str | None:
    return next((c.field for g in groups for c in g), None)


def sentence(entity: str, groups: list[list[Condition]]) -> str:
    """Okunur cümle: "Minimum lot boş değil ve Maksimum lot boş veya Lot katı > Maksimum lot"."""
    def one(c: Condition) -> str:
        name = label(entity, c.field)
        if c.operator in NO_VALUE:
            return f"{name} {SYMBOL[c.operator]}"
        right = label(entity, c.compare_field) if c.compare_field else str(c.value).strip()
        if c.operator in TEXT_ONLY:
            return f"{name} {right} {SYMBOL[c.operator]}"
        if c.operator == IN_LIST:
            return f"{name} şunlardan biri: {right}"
        if (kind_of(columns(entity)[c.field]) == "bool") and not c.compare_field:
            right = {"1": "Evet", "0": "Hayır"}.get(right, right)
        return f"{name} {c.operator} {right}"
    return " veya ".join(" ve ".join(one(c) for c in g) for g in groups if g)

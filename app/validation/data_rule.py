"""Veri kuralının sonucu (K-141): Değer, Alan, Formül, Boşalt; hedef alan, seçenek, tip denetimi, SQL ifadesi ve okunur cümle.

Kural tek tablo içindedir; koşulu validasyon kurallarıyla ortak koşul derleyicisidir (`conditions`). Anahtar alanlar ve sistem
alanları hedef olamaz. Değer, Alan ya da Formül boş çıkarsa hücre değişmez; bölen sıfırsa o satırda sonuç boş sayılır.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import sqlalchemy as sa

from app.integration.structural import key_fields

from . import conditions
from .conditions import ConditionError, columns, kind_of
from .sqlkit import label

VALUE, FIELD, FORMULA, CLEAR = "Değer", "Alan", "Formül", "Boşalt"
KINDS = (VALUE, FIELD, FORMULA, CLEAR)
ONLY_EMPTY, ALWAYS = "Yalnız boşsa", "Her zaman"
MODES = (ONLY_EMPTY, ALWAYS)
PLUS, MINUS, TIMES, DIVIDE = "+", "−", "×", "÷"
NUMBER_OPERATORS = (PLUS, MINUS, TIMES, DIVIDE)
DATE_OPERATORS = (PLUS, MINUS)  # gün
RAN, FAILED = "Çalıştı", "Çalışmadı"
NUMERIC = ("integer", "number")


class RuleError(ValueError):
    """Kural geçersiz: hedef, sonuç ya da seçenek tipe uymuyor."""


@dataclass(frozen=True)
class Result:
    kind: str
    value: str | None = None
    source_field: str | None = None
    operator: str | None = None
    operand_value: str | None = None
    operand_field: str | None = None


def targets(entity: str) -> dict[str, str | None]:
    """Hedef olabilecek alanlar: alan → None; olamayan → nedeni."""
    keys = set(key_fields(entity))
    return {name: ("Anahtar alan hedef olamaz." if name in keys else None) for name in columns(entity)}


def _kind(entity: str, field: str) -> str:
    return kind_of(columns(entity)[field])


def _values(entity: str, field: str) -> list[str]:
    return list(columns(entity)[field].info.get("values") or [])


def normalize(entity: str, field: str, raw: str | None) -> str:
    """Sabit değer hedef tipine göre çözülür ve saklanacak biçime çevrilir (bayrak 1 / 0, tarih yyyy-aa-gg, sayı noktalı)."""
    if raw is None or not str(raw).strip():
        raise RuleError("Değer boş olamaz.")
    kind = _kind(entity, field)
    try:
        value = conditions.parse(kind, str(raw))
    except ConditionError as exc:
        raise RuleError(str(exc)) from None
    allowed = _values(entity, field)
    if kind == "text" and allowed and value not in allowed:
        raise RuleError(f"Değer listede yok: {value}. Seçenekler: {', '.join(allowed)}.")
    if kind == "bool":
        return "1" if value else "0"
    if kind == "date":
        return value.isoformat()
    if kind in NUMERIC:
        return format(value, "f") if isinstance(value, Decimal) else str(value)
    width = getattr(columns(entity)[field].type, "length", None)
    if width and len(value) > width:
        raise RuleError(f"Değer en çok {width} karakter olabilir.")
    return value


def validate(entity: str, target: str, result: Result, mode: str) -> Result:
    """Kaydı denetler; saklanacak biçimdeki sonucu döner. Hata RuleError."""
    cols = columns(entity)
    if target not in cols:
        raise RuleError(f"Hedef alan yok: {target}")
    reason = targets(entity)[target]
    if reason:
        raise RuleError(reason)
    if mode not in MODES:
        raise RuleError(f"Seçenek yok: {mode}")
    kind = _kind(entity, target)
    if result.kind == VALUE:
        return Result(VALUE, value=normalize(entity, target, result.value))
    if result.kind == CLEAR:
        if mode != ALWAYS:
            raise RuleError("Boşalt yalnız \"Her zaman\" ile kullanılır.")
        return Result(CLEAR)
    source = result.source_field
    if not source or source not in cols:
        raise RuleError(f"Kaynak alan yok: {source or '—'}")
    skind = _kind(entity, source)
    if result.kind == FIELD:
        if source == target:
            raise RuleError("Kaynak alan hedefle aynı olamaz.")
        if kind != "text" and skind != kind and not (kind in NUMERIC and skind in NUMERIC):
            raise RuleError("Kaynak alanın tipi hedefe uymuyor.")
        return Result(FIELD, source_field=source)
    if result.kind != FORMULA:
        raise RuleError(f"Sonuç türü yok: {result.kind}")
    if kind in NUMERIC:
        if skind not in NUMERIC:
            raise RuleError("Formülde kaynak alan sayı olmalı.")
        operators, want = NUMBER_OPERATORS, "number"
    elif kind == "date":
        if skind != "date":
            raise RuleError("Tarih formülünde kaynak alan tarih olmalı.")
        operators, want = DATE_OPERATORS, "integer"
    else:
        raise RuleError("Formül yalnız sayı ve tarih alanında kullanılır.")
    if result.operator not in operators:
        raise RuleError(f"Operatör bu alanda kullanılmaz: {result.operator or '—'}")
    if bool(result.operand_field) == bool(result.operand_value not in (None, "")):
        raise RuleError("Formülde bir değer ya da bir alan seçilmeli.")
    if result.operand_field:
        if result.operand_field not in cols or _kind(entity, result.operand_field) not in NUMERIC:
            raise RuleError("Formülde ikinci alan sayı olmalı.")
        return Result(FORMULA, source_field=source, operator=result.operator, operand_field=result.operand_field)
    try:
        operand = conditions.parse(want, str(result.operand_value))
    except ConditionError:
        raise RuleError("Gün sayısı tam sayı olmalı." if want == "integer" else f"Değer sayı olmalı: {result.operand_value}") from None
    text = format(operand, "f") if isinstance(operand, Decimal) else str(operand)
    return Result(FORMULA, source_field=source, operator=result.operator, operand_value=text)


def expression(t, entity: str, target: str, result: Result) -> sa.ColumnElement:
    """Sonucun SQL ifadesi (t: işlenmiş katmanın takma adı). Bölen sıfırsa sonuç boş (NULLIF)."""
    col = t.c[target]
    kind = _kind(entity, target)
    if result.kind == CLEAR:
        return sa.null()
    if result.kind == VALUE:
        return sa.literal(conditions.parse(kind, result.value), col.type)
    source = t.c[result.source_field]
    if result.kind == FIELD:
        if kind == "text" and _kind(entity, result.source_field) != "text":
            return sa.cast(source, col.type)
        return source
    if result.operand_field:
        operand = t.c[result.operand_field]
    elif kind == "date":
        operand = sa.literal(int(result.operand_value), sa.Integer)
    else:
        operand = sa.literal(Decimal(result.operand_value), sa.Numeric(28, 10))
    if kind == "date":
        days = operand if result.operator == PLUS else -operand
        return sa.func.dateadd(sa.literal_column("day"), days, source)
    if result.operator == PLUS:
        return source + operand
    if result.operator == MINUS:
        return source - operand
    if result.operator == TIMES:
        return source * operand
    return source / sa.func.nullif(operand, 0)


def _shown(entity: str, field: str, raw: str) -> str:
    kind = _kind(entity, field)
    if kind == "bool":
        return "Evet" if raw in ("1", "True", "true") else "Hayır"
    if kind == "date":
        d = date.fromisoformat(raw)
        return d.strftime("%d.%m.%Y")
    if kind in NUMERIC:
        return _number(raw)
    return raw


def text(entity: str, target: str, result: Result, labels: dict[str, str] | None = None) -> str:
    """Okunur sonuç: "Tesis = Evet", "Teyit tarihi = İstenen tarih + 3 gün", "Tesis boşaltılır". labels: güncel etiketler (texts.field_labels)."""
    label_of = (lambda f: labels.get(f, label(entity, f))) if labels else (lambda f: label(entity, f))
    name = label_of(target)
    if result.kind == CLEAR:
        return f"{name} boşaltılır"
    if result.kind == VALUE:
        return f"{name} = {_shown(entity, target, result.value)}"
    source = label_of(result.source_field)
    if result.kind == FIELD:
        return f"{name} = {source}"
    operand = label_of(result.operand_field) if result.operand_field else _number(result.operand_value)
    unit = " gün" if _kind(entity, target) == "date" else ""
    return f"{name} = {source} {result.operator} {operand}{unit}"


def _number(raw: str) -> str:
    whole, _, frac = raw.partition(".")
    frac = frac.rstrip("0")
    sign = "-" if whole.startswith("-") else ""
    digits = whole.lstrip("-") or "0"
    return sign + f"{int(digits):,}".replace(",", ".") + (f",{frac}" if frac else "")

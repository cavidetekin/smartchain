"""Veri sözlüğü (fonksiyon 96, K-104, K-170): alan okuma, etiket ve Manuel. Öteki alanlar salt okunur (Değer önceliği sabit, Senaryo Aşama 8).

Görünüm ve kurallar alan adını saklar, etiketi değil: etiket değişince yalnız başlık değişir. Ek alanın etiketi silinince
alan listeden kalkar, görünüm açılırken ayıklanır (views._clean); kayıt değişmediği için etiket dönünce görünüm de döner.
"""
import json

from sqlalchemy.orm import Session

from app.validation import texts
from db.dictionary import is_additional

from ..errors import AppError
from ..lists import FIELD_DEFINITIONS, LISTS
from ..repositories import audit, field_definitions as repo
from . import auth, manual_values
from .auth import CurrentUser

LABEL_MAX = 40  # K-88
ACTION = "Alan etiketi değişikliği"
OBJECT = "FieldDefinition"


def _row(session: Session, table: str, field: str) -> dict:
    row = repo.get_field(session, table, field)
    if row is None:
        raise AppError("field_not_found", "Alan bulunamadı.", 404)
    return row


def _usage(session: Session, table: str, field: str) -> tuple[int, int]:
    """(kullanan görünüm, kullanan kural): yalnız o tabloya bağlı listelerde."""
    names = [d.name for d in LISTS if d.table_name == table]
    views = rules = 0
    for raw in repo.view_definitions(session, names):
        data = json.loads(raw)
        used = (any(c.get("field") == field for c in data.get("columns", []))
                or any(s.get("field") == field for s in data.get("sort", []))
                or any(f.get("field") == field for f in data.get("filters", []))
                or field in data.get("group_by", []) or field in (data.get("aggregates") or {}))
        hits = sum(1 for r in data.get("rules") or []
                   if r.get("field") == field or (r.get("condition") or {}).get("field_ref") == field)
        views += 1 if used or hits else 0
        rules += hits
    return views, rules


def detail(session: Session | None, table: str, field: str) -> dict:
    session = auth._require(session)

    def work():
        row = _row(session, table, field)
        views, rules = _usage(session, table, field)
        return {"table": row["TableName"], "field": row["FieldName"], "label": row["Label"],
                "standard_label": row["StandardLabel"], "description": row["Description"], "is_additional": is_additional(field),
                "field_class": row["FieldClass"],
                "manual_overrides": row["ManualOverrides"], "editable_in_workspace": row["EditableInWorkspace"],
                "is_required": row["IsRequired"], "if_empty": row["IfEmpty"],
                "options": {"field_class": FIELD_DEFINITIONS.values["FieldClass"]},
                "used_in_views": views, "used_in_rules": rules, **manual_values.manual_info(session, table, field)}

    return auth._db(work)


def set_label(session: Session | None, actor: CurrentUser, table: str, field: str, label: str) -> dict:
    """Boş etiket: standart etikete döner; ek alanda alan listelerden kalkar (K-88)."""
    session = auth._require(session)
    value = label.strip() or None

    def work():
        row = _row(session, table, field)
        if value == row["Label"]:
            return None
        if value and repo.label_taken(session, table, field, value):
            raise AppError("label_taken", "Bu tabloda aynı etiketli bir alan var.", 409, [{"field": "label", "problem": "Bu tabloda aynı etiketli bir alan var."}])
        repo.set_label(session, table, field, value)
        texts.refresh(session, table)  # kural metinleri güncel etiketle (K-143)
        audit.write_audit(session, ACTION, actor.id, OBJECT, f"{table}.{field}", {"Label": value}, {"Label": row["Label"]})
        session.commit()
        return None

    auth._db(work)
    return detail(session, table, field)


def set_manual(session: Session | None, actor: CurrentUser, table: str, field: str, on: bool, confirm: bool) -> dict:
    """Manuel aç / kapa (K-170); kapanırken manuel değer varsa onay istenir (409 manual_values), onayla manuel değerler kalkar."""
    session = auth._require(session)

    def work():
        _row(session, table, field)
        manual_values.set_manual(session, actor, table, field, on, confirm)
        session.commit()

    auth._db(work)
    return detail(session, table, field)

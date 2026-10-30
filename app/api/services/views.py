"""Kayıtlı görünümler (K-89, docs/08 "Görünümler").

İçerik kaydederken liste tanımına göre doğrulanır; açılırken artık olmayan alanlar atılır ve uyarı döner.
Yalnız sahibi değiştirir ya da siler; paylaşılanı şimdilik herkes görür (rol kuralı 2.2). Kullanıcı A-36 gereği
şimdilik user_id ile gelir.
"""
import json
from datetime import date, timezone

from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from ..errors import AppError
from ..lists.definition import ListDefinition
from ..lists.query import Builder, ListQueryError
from ..lists.request import (
    AggSpec, DefaultViewRequest, FilterItem, FormatRule, ViewCreate, ViewDefinition, ViewUpdate,
)
from ..repositories import lists as list_repo, views as repo

DB_DOWN = "Veritabanına bağlanılamıyor; görünümler okunamadı."


def _builder(session: Session, defn: ListDefinition) -> Builder:
    """Yalnız alan ve filtre doğrulaması için (veri okunmaz; versiyon ve tarih önemsiz)."""
    return Builder(defn, list_repo.read_labels(session, defn.table_name), version=0, today=date.today())


def _problems(b: Builder, d: ViewDefinition) -> list[dict]:
    problems: list[dict] = []
    seen = set()
    for i, c in enumerate(d.columns):
        if c.field not in b.columns:
            problems.append({"field": f"definition.columns.{i}.field", "problem": f"Bilinmeyen alan: {c.field}"})
        elif c.field in seen:
            problems.append({"field": f"definition.columns.{i}.field", "problem": f"Alan iki kez: {c.field}"})
        seen.add(c.field)
    if d.pinned > len(d.columns):
        problems.append({"field": "definition.pinned", "problem": "Sabit kolon sayısı kolon sayısını aşamaz"})
    for name, check in (("sort", lambda: b.order_by(d.sort)), ("filters", lambda: b.where(d.filters))):
        try:
            if getattr(d, name):
                check()
        except ListQueryError as exc:
            problems += [{**p, "field": f"definition.{p['field']}"} for p in exc.details]
    for i, f in enumerate(d.group_by):
        if f not in b.columns or d.group_by.index(f) != i:
            problems.append({"field": f"definition.group_by.{i}", "problem": f"Geçersiz gruplama alanı: {f}"})
    try:
        b.aggregate_specs(None, d.aggregates, "definition.aggregates")
    except ListQueryError as exc:
        problems += exc.details
    try:
        b.rule_columns(d.rules, "definition.rules")  # koşullu biçim (K-95)
    except ListQueryError as exc:
        problems += exc.details
    if len({r.id for r in d.rules}) != len(d.rules):
        problems.append({"field": "definition.rules", "problem": "Kural kimlikleri tekil olmalı"})
    return problems


def _clean(b: Builder, raw: str) -> tuple[dict, list[str]]:
    """Kayıtlı içerik bugünkü liste tanımına uydurulur; atılan her parça için uyarı (K-89)."""
    data = json.loads(raw)
    warnings: list[str] = []

    def gone(field: str):
        msg = f"'{field}' alanı artık listede yok; görünümden çıkarıldı."
        if msg not in warnings:
            warnings.append(msg)

    def known(items: list, field_of) -> list:
        kept = []
        for item in items:
            if field_of(item) in b.columns:
                kept.append(item)
            else:
                gone(field_of(item))
        return kept

    columns = known(data.get("columns", []), lambda c: c.get("field"))
    if not columns:
        columns = [{"field": f, "width": None} for f, c in b.columns.items() if c["default_visible"]]
    sort = known(data.get("sort", []), lambda s: s.get("field"))
    filters = []
    for f in data.get("filters", []):
        try:
            b.where([FilterItem.model_validate(f)])
            filters.append(f)
        except (ListQueryError, ValidationError):
            if f.get("field") in b.columns:
                warnings.append(f"'{f.get('field')}' filtresi artık geçerli değil; görünümden çıkarıldı.")
            else:
                gone(f.get("field"))
    group_by = known(data.get("group_by", []), lambda g: g)
    aggregates = {}
    for f, spec in (data.get("aggregates") or {}).items():
        try:
            b.aggregate_specs(None, {f: AggSpec.model_validate(spec)})
            aggregates[f] = spec
        except (ListQueryError, ValidationError):
            if f in b.columns:
                warnings.append(f"'{f}' ara toplamı artık geçerli değil; görünümden çıkarıldı.")
            else:
                gone(f)
    rules = []
    for r in data.get("rules") or []:
        try:
            b.rule_columns([FormatRule.model_validate(r)])
            rules.append(r)
        except (ListQueryError, ValidationError):
            missing = [f for f in (r.get("field"), (r.get("condition") or {}).get("field_ref")) if f and f not in b.columns]
            for f in missing:
                gone(f)
            if not missing:
                warnings.append(f"'{r.get('field')}' biçim kuralı artık geçerli değil; görünümden çıkarıldı.")
    definition = {"v": 1, "columns": columns, "pinned": min(int(data.get("pinned", 0)), len(columns)),
                  "sort": sort, "filters": filters, "group_by": group_by, "aggregates": aggregates, "rules": rules}
    return definition, warnings


def _dump(d: ViewDefinition) -> str:
    return json.dumps(d.model_dump(mode="json", by_alias=True, exclude_none=True), ensure_ascii=False)


def _out(b: Builder, row: dict, user_id: int) -> dict:
    definition, warnings = _clean(b, row["Definition"])
    return {
        "id": row["Id"], "name": row["Name"], "owner_user_id": row["OwnerUserId"], "owner_name": row["OwnerName"],
        "is_shared": bool(row["IsShared"]), "is_owner": row["OwnerUserId"] == user_id,
        "updated_at": row["UpdatedAt"].replace(tzinfo=timezone.utc).isoformat(timespec="seconds"),
        "definition": definition, "warnings": warnings,
    }


def _run(session: Session | None, user_id: int, work):
    if session is None:
        raise AppError("database_unavailable", DB_DOWN, 503)
    try:
        if not repo.user_exists(session, user_id):
            raise AppError("user_not_found", "Kullanıcı bulunamadı.", 404)
        return work()
    except IntegrityError as exc:
        session.rollback()
        raise AppError("view_name_taken", "Bu adda bir görünümünüz zaten var.", 409) from exc
    except DBAPIError as exc:
        session.rollback()
        raise AppError("database_unavailable", DB_DOWN, 503) from exc


def _validated(b: Builder, d: ViewDefinition) -> ViewDefinition:
    problems = _problems(b, d)
    if problems:
        raise AppError("validation", "Gönderilen veri geçersiz.", 422, problems)
    return d


def _owned(session: Session, defn: ListDefinition, view_id: int, user_id: int) -> dict:
    row = repo.get_view(session, defn.name, view_id)
    if row is None:
        raise AppError("view_not_found", "Görünüm bulunamadı.", 404)
    if row["OwnerUserId"] != user_id:
        raise AppError("view_not_owner", "Bu görünümü yalnız sahibi değiştirebilir.", 403)
    return row


def list_views(session: Session | None, defn: ListDefinition, user_id: int) -> dict:
    def work():
        b = _builder(session, defn)
        views = [_out(b, r, user_id) for r in repo.list_views(session, defn.name, user_id)]
        default = repo.read_default(session, user_id, defn.name)
        return {"views": views, "default_view_id": default if any(v["id"] == default for v in views) else None}
    return _run(session, user_id, work)


def create(session: Session | None, defn: ListDefinition, user_id: int, body: ViewCreate) -> dict:
    def work():
        b = _builder(session, defn)
        d = _validated(b, body.definition)
        now = repo.now(session)
        view_id = repo.insert_view(session, {
            "ListName": defn.name, "OwnerUserId": user_id, "Name": body.name.strip(), "IsShared": body.is_shared,
            "Definition": _dump(d), "CreatedAt": now, "UpdatedAt": now})
        session.commit()
        return _out(b, repo.get_view(session, defn.name, view_id), user_id)
    return _run(session, user_id, work)


def update(session: Session | None, defn: ListDefinition, user_id: int, view_id: int, body: ViewUpdate) -> dict:
    def work():
        b = _builder(session, defn)
        _owned(session, defn, view_id, user_id)
        values = {"UpdatedAt": repo.now(session)}
        if body.name is not None:
            values["Name"] = body.name.strip()
        if body.is_shared is not None:
            values["IsShared"] = body.is_shared
        if body.definition is not None:
            values["Definition"] = _dump(_validated(b, body.definition))
        repo.update_view(session, view_id, values)
        session.commit()
        return _out(b, repo.get_view(session, defn.name, view_id), user_id)
    return _run(session, user_id, work)


def delete(session: Session | None, defn: ListDefinition, user_id: int, view_id: int) -> None:
    def work():
        _owned(session, defn, view_id, user_id)
        repo.delete_view(session, view_id)
        session.commit()
    _run(session, user_id, work)


def set_default(session: Session | None, defn: ListDefinition, user_id: int, body: DefaultViewRequest) -> dict:
    def work():
        if body.view_id is not None:
            row = repo.get_view(session, defn.name, body.view_id)
            if row is None or not (row["IsShared"] or row["OwnerUserId"] == user_id):
                raise AppError("view_not_found", "Görünüm bulunamadı.", 404)
        repo.set_default(session, user_id, defn.name, body.view_id)
        session.commit()
        return {"default_view_id": body.view_id}
    return _run(session, user_id, work)

"""Kayıtlı görünümler (K-89, docs/08 "Görünümler").

İçerik kaydederken liste tanımına göre doğrulanır; açılırken artık olmayan alanlar atılır ve uyarı döner.
Şirket Standart'ı (K-162): Standart'ı System owner ve Admin kaydeder, kendi varsayılanını seçmemiş herkese açılır; sonradan listeye eklenen alan
ürünün varsayılanına göre gelir (kaydedildiği andaki alan listesi `KnownFields`).
Yalnız sahibi değiştirir ya da siler; paylaşılanı şimdilik herkes görür (rol kuralı 2.2). Kullanıcı A-36 gereği
şimdilik user_id ile gelir.
"""
import json
from datetime import date, timezone

from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from ..errors import DB_UNAVAILABLE, AppError
from ..lists.definition import ListDefinition, field_title
from ..lists.query import Builder, ListQueryError
from ..lists.request import (
    AggSpec, DefaultViewRequest, FilterItem, FormatRule, StandardUpdate, ViewCreate, ViewDefinition, ViewUpdate,
)
from ..repositories import audit, lists as list_repo, views as repo
from ..permissions import ADMIN, SYSTEM_OWNER, Access
from . import authz
from .auth import CurrentUser

# Paylaşılan görünüm başkasını etkiler, iz bırakır; kişisel görünüm ve varsayılan seçimi bırakmaz (K-108).
SHARED_CREATED = "Paylaşılan görünüm oluşturuldu"
SHARED_CHANGED = "Paylaşılan görünüm değiştirildi"
SHARED_DELETED = "Paylaşılan görünüm silindi"
VIEW_OBJECT = "TableView"
STANDARD_CHANGED = "Standart görünüm değiştirildi"
STANDARD_RESET = "Standart görünüm ürün hâline döndü"
STANDARD_EDITORS = (SYSTEM_OWNER, ADMIN)
STANDARD_FORBIDDEN = "Standart görünümü yalnız System owner ve Admin değiştirebilir."



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

    def title(field: str) -> str:
        return b.columns[field]["label"] if field in b.columns else field_title(b.defn, field)

    def gone(field: str):
        msg = f"'{title(field)}' artık listede yok; görünümden çıkarıldı."
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
                warnings.append(f"'{title(f.get('field'))}' filtresi artık geçerli değil; görünümden çıkarıldı.")
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
                warnings.append(f"'{title(f)}' ara toplamı artık geçerli değil; görünümden çıkarıldı.")
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
                warnings.append(f"'{title(r.get('field'))}' biçim kuralı artık geçerli değil; görünümden çıkarıldı.")
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


def _standard_out(b: Builder, row: dict | None) -> dict | None:
    """Şirket Standart'ı bugünkü listeye uyarlanır: kalkan alan atılır (uyarı), sonradan eklenen alan ürünün varsayılanına göre sona eklenir."""
    if row is None:
        return None
    definition, warnings = _clean(b, row["Definition"])
    known = set(json.loads(row["KnownFields"] or "[]"))
    present = {c["field"] for c in definition["columns"]}
    definition["columns"] += [{"field": f, "width": None} for f, c in b.columns.items() if c["default_visible"] and f not in known and f not in present]
    return {"definition": definition, "warnings": warnings, "updated_by_name": row["UpdatedByName"],
            "updated_at": row["UpdatedAt"].replace(tzinfo=timezone.utc).isoformat(timespec="seconds")}


def _ensure_editor(user: CurrentUser, defn: ListDefinition) -> None:
    if user.role not in STANDARD_EDITORS:
        authz.record_denial(user, defn.function, Access.WRITE, {"list": defn.name, "reason": "Standart görünüm"})
        raise AppError("view_standard_forbidden", STANDARD_FORBIDDEN, 403)


def _run(session: Session | None, user_id: int, work):
    if session is None:
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503)
    try:
        if not repo.user_exists(session, user_id):
            raise AppError("user_not_found", "Kullanıcı bulunamadı.", 404)
        return work()
    except IntegrityError as exc:
        session.rollback()
        raise AppError("view_name_taken", "Bu adda bir görünümünüz zaten var.", 409) from exc
    except DBAPIError as exc:
        session.rollback()
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503) from exc


def _validated(b: Builder, d: ViewDefinition) -> ViewDefinition:
    problems = _problems(b, d)
    if problems:
        raise AppError("validation", "Girilen bilgiler geçersiz.", 422, problems)
    return d


def _owned(session: Session, defn: ListDefinition, view_id: int, user: CurrentUser) -> dict:
    """Nesne bağlamı (K-100): görünümü yalnız sahibi değiştirir ve siler; diğerleri salt okunur görür."""
    row = repo.get_view(session, defn.name, view_id)
    if row is None:
        raise AppError("view_not_found", "Görünüm bulunamadı.", 404)
    authz.ensure_owner(user, row["OwnerUserId"], defn.function, "view_not_owner", "Bu görünümü",
                       {"list": defn.name, "view_id": view_id})
    return row


def list_views(session: Session | None, defn: ListDefinition, user_id: int, role: str | None = None) -> dict:
    def work():
        b = _builder(session, defn)
        views = [_out(b, r, user_id) for r in repo.list_views(session, defn.name, user_id)]
        default = repo.read_default(session, user_id, defn.name)
        return {"views": views, "default_view_id": default if any(v["id"] == default for v in views) else None,
                "standard": _standard_out(b, repo.get_standard(session, defn.name)), "can_edit_standard": role in STANDARD_EDITORS}
    return _run(session, user_id, work)


def create(session: Session | None, defn: ListDefinition, user_id: int, body: ViewCreate) -> dict:
    def work():
        b = _builder(session, defn)
        d = _validated(b, body.definition)
        now = repo.now(session)
        view_id = repo.insert_view(session, {
            "ListName": defn.name, "OwnerUserId": user_id, "Name": body.name.strip(), "IsShared": body.is_shared,
            "Definition": _dump(d), "CreatedAt": now, "UpdatedAt": now})
        if body.is_shared:
            audit.write_audit(session, SHARED_CREATED, user_id, VIEW_OBJECT, f"{defn.name} #{view_id}",
                              {"Name": body.name.strip(), "IsShared": True})
        session.commit()
        return _out(b, repo.get_view(session, defn.name, view_id), user_id)
    return _run(session, user_id, work)


def update(session: Session | None, defn: ListDefinition, user: CurrentUser, view_id: int, body: ViewUpdate) -> dict:
    user_id = user.id

    def work():
        b = _builder(session, defn)
        row = _owned(session, defn, view_id, user)
        values = {"UpdatedAt": repo.now(session)}
        if body.name is not None:
            values["Name"] = body.name.strip()
        if body.is_shared is not None:
            values["IsShared"] = body.is_shared
        if body.definition is not None:
            values["Definition"] = _dump(_validated(b, body.definition))
        repo.update_view(session, view_id, values)
        if row["IsShared"] or values.get("IsShared"):
            new = {k: v for k, v in values.items() if k in ("Name", "IsShared") and v != row[k]}
            if "Definition" in values and values["Definition"] != row["Definition"]:
                new["Definition"] = "değişti"
            if new:
                audit.write_audit(session, SHARED_CHANGED, user_id, VIEW_OBJECT, f"{defn.name} #{view_id}", new,
                                  {k: row[k] for k in new if k != "Definition"})
        session.commit()
        return _out(b, repo.get_view(session, defn.name, view_id), user_id)
    return _run(session, user_id, work)


def delete(session: Session | None, defn: ListDefinition, user: CurrentUser, view_id: int) -> None:
    user_id = user.id

    def work():
        row = _owned(session, defn, view_id, user)
        repo.delete_view(session, view_id)
        if row["IsShared"]:
            audit.write_audit(session, SHARED_DELETED, user_id, VIEW_OBJECT, f"{defn.name} #{view_id}", None,
                              {"Name": row["Name"], "IsShared": True})
        session.commit()
    _run(session, user_id, work)


def save_standard(session: Session | None, defn: ListDefinition, user: CurrentUser, body: StandardUpdate) -> dict:
    """Şirket Standart'ını yazar (K-162); yalnız System owner ve Admin. İz aynı işlemde."""
    def work():
        _ensure_editor(user, defn)
        b = _builder(session, defn)
        d = _validated(b, body.definition)
        had = repo.get_standard(session, defn.name) is not None
        repo.save_standard(session, defn.name, _dump(d), json.dumps(list(b.columns), ensure_ascii=False), user.id, repo.now(session))
        audit.write_audit(session, STANDARD_CHANGED, user.id, VIEW_OBJECT, f"{defn.name} · Standart", {"list": defn.name, "Definition": "değişti" if had else "ilk kez kaydedildi"})
        session.commit()
        return _standard_out(b, repo.get_standard(session, defn.name))
    return _run(session, user.id, work)


def reset_standard(session: Session | None, defn: ListDefinition, user: CurrentUser) -> None:
    """Ürün Standart'ına döndür (K-162): şirket Standart'ı silinir."""
    def work():
        _ensure_editor(user, defn)
        if repo.delete_standard(session, defn.name):
            audit.write_audit(session, STANDARD_RESET, user.id, VIEW_OBJECT, f"{defn.name} · Standart", {"list": defn.name})
        session.commit()
    _run(session, user.id, work)


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

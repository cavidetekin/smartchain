"""Kaydın kartı (K-171, K-173): kod ve ad, güncel veride mi, İlişkili kayıtlar (yalnız Ana veri).

Kart güncel veride olmayan kayda da açılır (geçmiş okunur): son versiyonu okunur, kapandığı versiyon yazılır. İlişkili kayıtlar sunucuda
kimliklere çevrilir; ön yüz ilgili listeyi `Id` süzgeciyle (yalnız süzmede) açar. Okuma yetkisi olmayan ilişki gösterilmez.
Çoklu seçimde (K-171) kart seçili kayıtların ilişkilerinin birleşimini gösterir: okuyucular kayıt listesi alır, tek sorguda.
"""
from collections.abc import Callable
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.manual import core_table

from .. import permissions as perm
from ..errors import AppError
from ..lists.master_data import BY_NAME
from ..lists.query import SELECTION_MAX, in_values
from ..permissions import Access
from . import authz
from .auth import CurrentUser


def _cur(t: sa.Table) -> sa.ColumnElement:
    return t.c.VersionTo.is_(None) if "VersionTo" in t.c else sa.true()


@dataclass(frozen=True)
class Relation:
    key: str
    label: str
    list: str
    ids: Callable[[Session, list[dict]], list]  # (oturum, kayıtlar) → hedef kimliklerin birleşimi


def _vals(recs: list[dict], key: str) -> list:
    return list(dict.fromkeys(r[key] for r in recs if r.get(key) is not None))


def _ids(session: Session, t: sa.Table, *where: sa.ColumnElement) -> list:
    return session.execute(sa.select(t.c.Id).where(_cur(t), *where).distinct().order_by(t.c.Id)).scalars().all()


def _by(table: str, column: str, of: str = "Id") -> Callable[[Session, list[dict]], list]:
    def read(session: Session, recs: list[dict]) -> list:
        t, values = core_table(table), _vals(recs, of)
        return _ids(session, t, in_values(t.c[column], values)) if values else []
    return read


def _any(table: str, *columns: str, of: str = "Id") -> Callable[[Session, list[dict]], list]:
    def read(session: Session, recs: list[dict]) -> list:
        t, values = core_table(table), _vals(recs, of)
        return _ids(session, t, sa.or_(*[in_values(t.c[c], values) for c in columns])) if values else []
    return read


def _material_routes(session: Session, recs: list[dict]) -> list:
    """Malzemelerin üretim versiyonlarındaki rotalar (rota kodu ve lokasyon)."""
    r, pv = core_table("Routing"), core_table("ProductionVersion")
    hit = sa.exists().where(_cur(pv), in_values(pv.c.MaterialId, _vals(recs, "Id")), pv.c.RouteCode == r.c.RouteCode, pv.c.LocationId == r.c.LocationId)
    return _ids(session, r, hit)


def _version_part(table: str, column: str, source: str) -> Callable[[Session, list[dict]], list]:
    """Üretim versiyonlarının ürün ağacı (BOMCode) ya da rotası (RouteCode): aynı lokasyonda."""
    def read(session: Session, recs: list[dict]) -> list:
        t = core_table(table)
        pairs = list(dict.fromkeys((r[source], r["LocationId"]) for r in recs if r.get(source) is not None))
        if not pairs:
            return []
        return _ids(session, t, sa.or_(*[sa.and_(t.c[column] == code, t.c.LocationId == loc) for code, loc in pairs]))
    return read


def _customer_projects(session: Session, recs: list[dict]) -> list:
    p, so = core_table("Project"), core_table("SalesOrderLine")
    hit = sa.exists().where(_cur(so), in_values(so.c.CustomerId, _vals(recs, "Id")), so.c.ProjectId == p.c.Id)
    return _ids(session, p, hit)


# İlişkili kayıtlar (K-173): tablo → ilişkiler (ekran sırası)
RELATIONS: dict[str, tuple[Relation, ...]] = {
    "Material": (
        Relation("production-version", "Üretim versiyonu", "master-production-version", _by("ProductionVersion", "MaterialId")),
        Relation("bom", "Ürün ağacı", "master-bom", _by("BOM", "MaterialId")),
        Relation("where-used", "Kullanıldığı ağaçlar", "master-bom", _by("BOM", "ComponentMaterialId")),
        Relation("routing", "Rota", "master-routing", _material_routes),
        Relation("material-supplier", "Malzeme tedarikçisi", "master-material-supplier", _by("MaterialSupplier", "MaterialId")),
        Relation("uom-conversion", "Birim dönüşümü", "master-uom-conversion", _by("UomConversion", "MaterialId")),
        Relation("material-reference", "Benzetilen ürün", "master-material-reference", _any("MaterialReference", "MaterialId", "ReferenceMaterialId")),
    ),
    "ProductionVersion": (
        Relation("bom", "Ürün ağacı", "master-bom", _version_part("BOM", "Code", "BOMCode")),
        Relation("routing", "Rota", "master-routing", _version_part("Routing", "RouteCode", "RouteCode")),
    ),
    "Resource": (
        Relation("group-assignment", "Grup ataması", "master-resource-group-assignment", _by("ResourceGroupAssignment", "ResourceId")),
        Relation("routing", "Rota", "master-routing", _by("Routing", "ResourceId")),
    ),
    "ResourceGroup": (
        Relation("group-assignment", "Grup ataması", "master-resource-group-assignment", _by("ResourceGroupAssignment", "ResourceGroupId")),
        Relation("routing", "Rota", "master-routing", _by("Routing", "ResourceGroupId")),
    ),
    "Supplier": (
        Relation("material-supplier", "Malzeme tedarikçisi", "master-material-supplier", _by("MaterialSupplier", "SupplierId")),
        Relation("subcontract-resource", "Fason kaynak", "master-resource", _by("Resource", "SubcontractorId")),
    ),
    "Customer": (
        Relation("sales-order", "Satış siparişi", "transaction-sales-order", _by("SalesOrderLine", "CustomerId")),
        Relation("project", "Proje", "transaction-project", _customer_projects),
    ),
    "UnitOfMeasure": (
        Relation("material", "Malzeme", "materials", _by("Material", "BaseUom", of="Code")),
        Relation("uom-conversion", "Birim dönüşümü", "master-uom-conversion", _any("UomConversion", "FromUom", "ToUom", of="Code")),
    ),
}
MASTER_SCREEN = frozenset(n for n in BY_NAME if not n.startswith("transaction-"))


def label_of(rec: dict) -> tuple[str, str | None]:
    """Kaydın kodu ve adı (kartın araç çubuğu): kod, sipariş ve satır, iş emri…; yoksa iş anahtarı."""
    for key in ("Code", "OrderNo", "PurchaseOrderNo", "WorkOrderNo", "ConfirmationNo", "RouteCode"):
        value = rec.get(key)
        if value not in (None, ""):
            line = rec.get("LineNo")
            code = f"{value} / {line}" if line is not None and key.endswith("OrderNo") else str(value)
            return code, rec.get("Name") or rec.get("OperationName")
    key = rec.get("BusinessKey")
    return (str(key).replace("|", " · ") if key else f"#{rec.get('Id')}"), rec.get("Name")


def _definition(user: CurrentUser, list_name: str):
    defn = BY_NAME.get(list_name)
    if defn is None:
        raise AppError("list_not_found", "Liste bulunamadı.", 404)
    authz.ensure(user, defn.function, Access.READ, details={"list": list_name})
    return defn


def read(session: Session, user: CurrentUser, list_name: str, key: str) -> dict:
    defn = _definition(user, list_name)
    t = core_table(defn.table_name)
    id_col = t.c.Id if "Id" in t.c else t.c.Code
    try:
        value = int(key) if "Id" in t.c else key
    except ValueError:
        raise AppError("record_not_found", "Kayıt bulunamadı.", 404) from None
    order = [t.c.VersionFrom.desc()] if "VersionFrom" in t.c else []
    rec = session.execute(sa.select(t).where(id_col == value).order_by(*order).limit(1)).mappings().first()
    if rec is None:
        raise AppError("record_not_found", "Kayıt bulunamadı.", 404)
    rec = dict(rec)
    current = rec.get("VersionTo") is None if "VersionTo" in t.c else rec.get("IsActive") is not False
    code, name = label_of(rec)
    relations = _relations(session, user, list_name, defn.table_name, [rec]) if current else []
    return {"list": list_name, "table": defn.table_name, "id": str(value), "code": code, "name": name, "label": " · ".join(x for x in (code, name) if x),
            "current": current, "closed_version": (rec["VersionTo"] + 1) if rec.get("VersionTo") is not None else None, "relations": relations}


def _relations(session: Session, user: CurrentUser, list_name: str, table: str, recs: list[dict]) -> list[dict]:
    """Kayıtların İlişkili kayıtları (yalnız Ana veri, okuma yetkisi olan ilişkiler); birden çok kayıtta birleşim (K-171)."""
    out = []
    if list_name not in MASTER_SCREEN or not recs:
        return out
    for rel in RELATIONS.get(table, ()):
        target = BY_NAME[rel.list]
        if not perm.allows(user.role, target.function, Access.READ):
            continue
        ids = rel.ids(session, recs)
        out.append({"key": rel.key, "label": rel.label, "list": rel.list, "count": len(ids),
                    "filters": [{"field": "Id", "op": "in", "values": [str(i) for i in ids] or ["0"]}]})  # boş ilişki: boş tablo (K-171)
    return out


def read_many(session: Session, user: CurrentUser, list_name: str, keys: list[str]) -> dict:
    """Çoklu seçimde kart (K-171): seçili kayıtların güncel olanlarının ilişkilerinin birleşimi; Geçmiş ön yüzde `record-history-many`."""
    defn = _definition(user, list_name)
    if len(keys) > SELECTION_MAX:
        raise AppError("validation", "Girilen bilgiler geçersiz.", 422, [{"field": "body.ids", "problem": f"En çok {SELECTION_MAX} kayıt"}])
    t = core_table(defn.table_name)
    id_col = t.c.Id if "Id" in t.c else t.c.Code
    try:
        values = list(dict.fromkeys(int(k) for k in keys)) if "Id" in t.c else list(dict.fromkeys(keys))
    except ValueError:
        raise AppError("validation", "Girilen bilgiler geçersiz.", 422, [{"field": "body.ids", "problem": "Kimlik sayı olmalı"}]) from None
    recs = [dict(r) for r in session.execute(sa.select(t).where(_cur(t), in_values(id_col, values))).mappings()] if values else []
    return {"list": list_name, "table": defn.table_name, "ids": [str(v) for v in values],
            "relations": _relations(session, user, list_name, defn.table_name, recs)}

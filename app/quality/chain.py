"""Talep zinciri (K-174): uyarının önemi ve detay kartının Talep zinciri sekmesi.

Küme (`adm.DemandChain`): her kontrolde baştan, veritabanında küme tabanlı SQL ile, seviye seviye (talep başına yol çıkarılmaz). Zinciri yalnız
açık satış siparişi (aktif, açık miktarı > 0; teklif ve beklemede dahil) ve planlama ufkundaki tahmin başlatır. Her seviyede: aktif üretim
versiyonları, ağaç satırları ve bileşenleri (alternatifler dahil), rota satırları, rotadaki kaynak grubu ve grubun kaynakları (grup eşleşmesiyle; K-180),
malzeme tedarikçileri ve tedarikçi; kendi aktif versiyonu olmayan malzemede benzetilen ürünün versiyonu, ağacı ve rotası; açık üretim siparişleri,
bileşenleri ve operasyonları.

Yollar (`adm.DemandChainPath`): yalnız kart açılınca, kayıttan yukarı (nerede kullanılıyor) çıkılarak; uyarı başına en çok 1.000 yol.
"""
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.api.lists.query import in_values
from db.models import metadata

from . import PATH_LIMIT

DC = metadata.tables["adm.DemandChain"]
PATH = metadata.tables["adm.DemandChainPath"]
MONTHS = ("Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara")
MAX_LEVELS = 60


def core(name: str) -> sa.Table:
    return metadata.tables[f"core.{name}"]


def current(t) -> sa.ColumnElement:
    return t.c.VersionTo.is_(None) if "VersionTo" in t.c else sa.true()


def active(t) -> sa.ColumnElement:
    return sa.or_(t.c.IsActive.is_(None), t.c.IsActive == sa.true()) if "IsActive" in t.c else sa.true()


def horizon(session: Session, day: date) -> tuple[date, date | None]:
    """Tahminin zinciri başlattığı aralık: bu ayın başı ile Baz senaryonun planlama ufkunun sonu (fonksiyon 23, K-175); dizi yoksa üst sınır yok."""
    from app.params import service as params
    return day.replace(day=1), params.horizon_end(session, day)


def open_orders(so) -> sa.ColumnElement:
    return sa.and_(current(so), active(so), so.c.OpenQuantity > 0)


def forecasts_in(fc, start: date, end: date | None) -> sa.ColumnElement:
    parts = [current(fc), active(fc), fc.c.Quantity > 0, fc.c.Period >= start]
    if end is not None:
        parts.append(fc.c.Period <= end)
    return sa.and_(*parts)


# ------------------------------------------------------------------ küme

def _in_chain(entity: str):
    return sa.select(DC.c.RecordId).where(DC.c.EntityName == entity)


def _add(session: Session, entity: str, ids: sa.Select) -> int:
    """ids (tek kolon) kümede yoksa eklenir; eklenen satır sayısı."""
    sub = ids.subquery()
    col = list(sub.c)[0]
    sel = (sa.select(sa.literal(entity, sa.Unicode(60)), col).distinct()
           .where(col.is_not(None), ~sa.exists().where(DC.c.EntityName == entity, DC.c.RecordId == col)))
    return session.execute(sa.insert(DC).from_select(["EntityName", "RecordId"], sel)).rowcount or 0


def rebuild(session: Session, day: date) -> dict[str, int]:
    """Kümeyi baştan kurar; yeni malzeme çıkmayana kadar seviye seviye genişler. Tablo başına kayıt sayısı."""
    so, fc, pv, bom, rtg = core("SalesOrderLine"), core("Forecast"), core("ProductionVersion"), core("BOM"), core("Routing")
    rgm, ms, mr, wo, woc, woo = (core("ResourceGroupMember"), core("MaterialSupplier"), core("MaterialReference"), core("WorkOrder"),
                                 core("WorkOrderComponent"), core("WorkOrderOperation"))
    session.execute(sa.delete(DC))
    start, end = horizon(session, day)
    _add(session, "SalesOrderLine", sa.select(so.c.Id).where(open_orders(so)))
    _add(session, "Forecast", sa.select(fc.c.Id).where(forecasts_in(fc, start, end)))
    _add(session, "Material", sa.select(so.c.MaterialId).where(so.c.Id.in_(_in_chain("SalesOrderLine")), current(so)))
    _add(session, "Material", sa.select(fc.c.MaterialId).where(fc.c.Id.in_(_in_chain("Forecast")), current(fc)))
    mats = _in_chain("Material")
    for _ in range(MAX_LEVELS):
        _add(session, "ProductionVersion", sa.select(pv.c.Id).where(current(pv), active(pv), pv.c.MaterialId.in_(mats)))
        # kendi aktif versiyonu olmayan malzeme: benzetilen ürünün versiyonu (boşsa benzetilenin aktif versiyonları)
        own = sa.exists().where(pv.c.MaterialId == mr.c.MaterialId, current(pv), active(pv))
        _add(session, "MaterialReference", sa.select(mr.c.Id).where(current(mr), mr.c.MaterialId.in_(mats), ~own))
        ref = mr.alias("ref")
        _add(session, "ProductionVersion", sa.select(ref.c.ReferenceProductionVersionId).where(current(ref), ref.c.Id.in_(_in_chain("MaterialReference"))))
        pv2 = pv.alias("pv2")
        _add(session, "ProductionVersion", sa.select(pv2.c.Id).select_from(pv2.join(ref, ref.c.ReferenceMaterialId == pv2.c.MaterialId))
             .where(current(pv2), active(pv2), current(ref), ref.c.ReferenceProductionVersionId.is_(None), ref.c.Id.in_(_in_chain("MaterialReference"))))
        chain_pv = pv.alias("cpv")
        pv_ok = sa.and_(current(chain_pv), chain_pv.c.Id.in_(_in_chain("ProductionVersion")))
        _add(session, "BOM", sa.select(bom.c.Id).select_from(bom.join(chain_pv, sa.and_(chain_pv.c.BOMCode == bom.c.Code, chain_pv.c.LocationId == bom.c.LocationId)))
             .where(current(bom), pv_ok))
        _add(session, "Routing", sa.select(rtg.c.Id).select_from(rtg.join(chain_pv, sa.and_(chain_pv.c.RouteCode == rtg.c.RouteCode, chain_pv.c.LocationId == rtg.c.LocationId)))
             .where(current(rtg), pv_ok))
        _add(session, "ResourceGroup", sa.select(rtg.c.ResourceGroupId).where(current(rtg), rtg.c.Id.in_(_in_chain("Routing"))))
        _add(session, "MaterialSupplier", sa.select(ms.c.Id).where(current(ms), active(ms), ms.c.MaterialId.in_(mats)))
        _add(session, "Supplier", sa.select(ms.c.SupplierId).where(current(ms), ms.c.Id.in_(_in_chain("MaterialSupplier"))))
        _add(session, "WorkOrder", sa.select(wo.c.Id).where(current(wo), wo.c.OpenQuantity > 0, wo.c.MaterialId.in_(mats)))
        _add(session, "WorkOrderComponent", sa.select(woc.c.Id).where(current(woc), woc.c.WorkOrderId.in_(_in_chain("WorkOrder"))))
        _add(session, "WorkOrderOperation", sa.select(woo.c.Id).where(current(woo), woo.c.WorkOrderId.in_(_in_chain("WorkOrder"))))
        _add(session, "ResourceGroup", sa.select(woo.c.ResourceGroupId).where(current(woo), woo.c.Id.in_(_in_chain("WorkOrderOperation"))))
        # gruptan eşleşmeyle kaynağa (rota ve üretim siparişi operasyonu kaynağı değil grubu gösterir, K-180)
        _add(session, "ResourceGroupMember", sa.select(rgm.c.Id).where(current(rgm), rgm.c.ResourceGroupId.in_(_in_chain("ResourceGroup"))))
        _add(session, "Resource", sa.select(rgm.c.ResourceId).where(current(rgm), rgm.c.Id.in_(_in_chain("ResourceGroupMember"))))
        added = _add(session, "Material", sa.select(bom.c.ComponentMaterialId).where(current(bom), bom.c.Id.in_(_in_chain("BOM"))))
        added += _add(session, "Material", sa.select(woc.c.MaterialId).where(current(woc), woc.c.Id.in_(_in_chain("WorkOrderComponent"))))
        if not added:
            break
    return dict(session.execute(sa.select(DC.c.EntityName, sa.func.count()).group_by(DC.c.EntityName)).all())


# ------------------------------------------------------------------ yollar (kart)

@dataclass(frozen=True)
class Demand:
    entity: str
    id: int
    label: str
    kind: str
    material_id: int
    when: date
    quantity: float


def _codes(session: Session, ids: Iterable[int]) -> dict[int, str]:
    m = core("Material")
    ids = list(set(ids))
    return dict(session.execute(sa.select(m.c.Id, m.c.Code).where(current(m), in_values(m.c.Id, ids))).all()) if ids else {}


def _demands(session: Session, mats: set[int], day: date) -> dict[int, list[Demand]]:
    so, fc, m = core("SalesOrderLine"), core("Forecast"), core("Material")
    out: dict[int, list[Demand]] = {}
    if not mats:
        return out
    ids = list(mats)
    for r in session.execute(sa.select(so.c.Id, so.c.OrderNo, so.c.LineNo, so.c.MaterialId, so.c.RequestedDate, so.c.OpenQuantity)
                             .where(open_orders(so), in_values(so.c.MaterialId, ids))).all():
        out.setdefault(r.MaterialId, []).append(Demand("SalesOrderLine", r.Id, f"{r.OrderNo} / {r.LineNo}", "Satış siparişi", r.MaterialId,
                                                       r.RequestedDate, float(r.OpenQuantity)))
    start, end = horizon(session, day)
    for r in session.execute(sa.select(fc.c.Id, fc.c.MaterialId, fc.c.Period, fc.c.Quantity, m.c.Code)
                             .select_from(fc.join(m, sa.and_(m.c.Id == fc.c.MaterialId, current(m))))
                             .where(forecasts_in(fc, start, end), in_values(fc.c.MaterialId, ids))).all():
        out.setdefault(r.MaterialId, []).append(Demand("Forecast", r.Id, f"{r.Code} · {MONTHS[r.Period.month - 1]} {r.Period.year}", "Tahmin",
                                                       r.MaterialId, r.Period, float(r.Quantity)))
    return out


def _parents(session: Session, mats: set[int]) -> dict[int, set[int]]:
    """Malzemeyi kullananlar: ağacında bileşen olduğu aktif versiyonun malzemesi; onu benzetilen ürün olarak izleyen malzeme; açık üretim siparişinin malzemesi."""
    bom, pv, mr, wo, woc = core("BOM"), core("ProductionVersion"), core("MaterialReference"), core("WorkOrder"), core("WorkOrderComponent")
    out: dict[int, set[int]] = {}
    if not mats:
        return out
    ids = list(mats)
    rows = list(session.execute(sa.select(bom.c.ComponentMaterialId, pv.c.MaterialId)
                                .select_from(bom.join(pv, sa.and_(pv.c.BOMCode == bom.c.Code, pv.c.LocationId == bom.c.LocationId)))
                                .where(current(bom), current(pv), active(pv), in_values(bom.c.ComponentMaterialId, ids))).all())
    own = sa.exists().where(pv.c.MaterialId == mr.c.MaterialId, current(pv), active(pv))
    rows += session.execute(sa.select(mr.c.ReferenceMaterialId, mr.c.MaterialId).where(current(mr), ~own, in_values(mr.c.ReferenceMaterialId, ids))).all()
    rows += session.execute(sa.select(woc.c.MaterialId, wo.c.MaterialId).select_from(woc.join(wo, wo.c.Id == woc.c.WorkOrderId))
                            .where(current(woc), current(wo), wo.c.OpenQuantity > 0, in_values(woc.c.MaterialId, ids))).all()
    for child, parent in rows:
        if parent is not None and parent != child:
            out.setdefault(child, set()).add(parent)
    return out


def start_materials(session: Session, entity: str, record_id: int) -> tuple[set[int], list[Demand]]:
    """Kaydın zincirdeki malzemeleri; talebin kendisiyse (satış siparişi, tahmin) doğrudan talep."""
    t = core(entity)
    if entity in ("SalesOrderLine", "Forecast"):
        row = session.execute(sa.select(t.c.MaterialId).where(t.c.Id == record_id, current(t))).first()
        if row is None:
            return set(), []
        found = [d for d in _demands(session, {row.MaterialId}, date.today()).get(row.MaterialId, []) if d.entity == entity and d.id == record_id]
        return set(), found
    pv, rtg, rgm, ms, wo = core("ProductionVersion"), core("Routing"), core("ResourceGroupMember"), core("MaterialSupplier"), core("WorkOrder")

    def route_materials(where) -> set[int]:
        return set(session.execute(sa.select(pv.c.MaterialId).select_from(rtg.join(pv, sa.and_(pv.c.RouteCode == rtg.c.RouteCode, pv.c.LocationId == rtg.c.LocationId)))
                                   .where(current(rtg), current(pv), active(pv), where)).scalars())
    if entity == "Material":
        return {record_id}, []
    if entity == "Routing":
        return route_materials(rtg.c.Id == record_id), []
    def group_materials(groups) -> set[int]:
        """Grubu (grupları) gösteren rotaların ve açık üretim siparişi operasyonlarının malzemeleri."""
        woo = core("WorkOrderOperation")
        mats = route_materials(rtg.c.ResourceGroupId.in_(groups))
        return mats | set(session.execute(sa.select(wo.c.MaterialId).select_from(woo.join(wo, wo.c.Id == woo.c.WorkOrderId))
                                          .where(current(woo), current(wo), wo.c.OpenQuantity > 0, woo.c.ResourceGroupId.in_(groups))).scalars())
    if entity == "Resource":  # kaynak, üye olduğu gruplar üzerinden (K-180)
        return group_materials(sa.select(rgm.c.ResourceGroupId).where(current(rgm), rgm.c.ResourceId == record_id)), []
    if entity == "ResourceGroup":
        return group_materials([record_id]), []
    if entity == "ResourceGroupMember":
        group = session.execute(sa.select(rgm.c.ResourceGroupId).where(rgm.c.Id == record_id, current(rgm))).scalar()
        return (group_materials([group]) if group is not None else set()), []
    if entity == "Supplier":
        return set(session.execute(sa.select(ms.c.MaterialId).where(current(ms), ms.c.SupplierId == record_id)).scalars()), []
    if entity in ("WorkOrderComponent", "WorkOrderOperation"):
        return set(session.execute(sa.select(wo.c.MaterialId).select_from(t.join(wo, wo.c.Id == t.c.WorkOrderId))
                                   .where(t.c.Id == record_id, current(t), current(wo))).scalars()), []
    if "MaterialId" in t.c:  # ağaç satırında ana malzeme; tedarikçi, stok, satın alma, üretim siparişi, versiyon…
        return set(session.execute(sa.select(t.c.MaterialId).where(t.c.Id == record_id, current(t))).scalars()), []
    return set(), []


def paths(session: Session, entity: str, record_id: int, day: date, limit: int = PATH_LIMIT) -> tuple[list[dict], bool]:
    """Kayıttan yukarı çıkarak talepler ve malzeme yolları; (satırlar, sınır aşıldı mı)."""
    starts, direct = start_materials(session, entity, record_id)
    rows: list[dict] = []
    if direct:
        codes = _codes(session, [d.material_id for d in direct])
        rows = [_row(d, [d.material_id], codes) for d in direct]
        return rows[:limit], len(rows) > limit
    # yukarı doğru bütün ataları seviye seviye topla, sonra bellekte yolları çıkar
    parents: dict[int, set[int]] = {}
    seen, frontier = set(starts), set(starts)
    for _ in range(MAX_LEVELS):
        found = _parents(session, frontier)
        parents.update(found)
        frontier = {p for ps in found.values() for p in ps} - seen
        if not frontier:
            break
        seen |= frontier
    demands = _demands(session, seen, day)
    codes = _codes(session, seen)
    truncated = False
    stack: list[tuple[int, tuple[int, ...]]] = [(m, (m,)) for m in sorted(starts)]
    while stack:
        mat, path = stack.pop()
        for d in demands.get(mat, []):
            if len(rows) >= limit:
                truncated = True
                break
            rows.append(_row(d, list(reversed(path)), codes))
        if truncated:
            break
        for p in sorted(parents.get(mat, ()), reverse=True):
            if p not in path:
                stack.append((p, path + (p,)))
    rows.sort(key=lambda r: (r["DemandDate"], r["DemandLabel"], r["MaterialPath"]))
    return rows, truncated


def _row(d: Demand, path: list[int], codes: dict[int, str]) -> dict:
    return {"DemandEntity": d.entity, "DemandId": d.id, "DemandLabel": d.label[:100], "DemandType": d.kind,
            "MaterialPath": " → ".join(codes.get(m, str(m)) for m in path)[:400], "DemandDate": d.when, "OpenQuantity": d.quantity}


def write_paths(session: Session, warning_id: int, entity: str, record_key: str, day: date) -> dict:
    """Kartın Talep zinciri: önbellekte yoksa hesaplanıp yazılır (her kontrolde silinir)."""
    count = session.execute(sa.select(sa.func.count()).select_from(PATH).where(PATH.c.WarningId == warning_id)).scalar_one()
    if count:
        return {"count": count, "truncated": count >= PATH_LIMIT}
    try:
        record_id = int(record_key)
    except ValueError:
        return {"count": 0, "truncated": False}
    rows, truncated = paths(session, entity, record_id, day)
    if rows:
        session.execute(sa.insert(PATH), [{"WarningId": warning_id, **r} for r in rows])
    session.commit()
    return {"count": len(rows), "truncated": truncated}

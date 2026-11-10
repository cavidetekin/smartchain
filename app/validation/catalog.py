"""Hazır validasyon kuralları (K-136, K-137, K-139): docs/06 fonksiyon 04 tablosuyla birebir (tests/test_validation_catalog.py).

Her kural tablonun güncel hâline (`IsCurrent`) bakar; core'a bakılmaz (K-133). Koşulu editörle ifade edilebilen kural koşul
gruplarıyla tanımlıdır (VE grupları, aralarında VEYA): ekranda düzenlenir, "İlk hâline döndür" buraya döner (K-139). Öteki kurallar
SQL ifadesi (küme, bugün, hesaplı fark, tablolar arası) ya da Python'dur (döngü); yalnız sınıf ve aktiflik değişir.
Yapısal kontroller ön kontroldedir (K-129); listede görünmez, validasyonda yalnız "hata (kurallardan sonra)" alanlarını denetler (K-138).
"""
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration import references as refs
from app.integration.contract import AFTER_RULES, ENTITIES, entity as contract_entity, stg_columns
from app.integration.structural import has_key

from . import conditions as cond
from .conditions import Condition
from .sqlkit import alias, current, label, nz, one, present, same, text

STRUCTURAL_KIND, BUILTIN_KIND, USER_KIND = "Yapısal", "Hazır", "Kullanıcı"
KINDS = (STRUCTURAL_KIND, BUILTIN_KIND, USER_KIND)
STRUCTURAL, LOGICAL, CROSS = "Yapısal", "Mantıksal", "Tablolar arası"
CHECK_TYPES = (STRUCTURAL, LOGICAL, CROSS)
ERROR, WARNING, INFO = "Hata", "Uyarı", "Bilgi"
SEVERITIES = (ERROR, WARNING, INFO)
NO_DATA = "Karşılaştırılacak veri yok"

Where = Callable[[sa.Alias], sa.ColumnElement]
Hit = tuple[int, str | None, str | None]  # StagingRowId, alan etiketi, değer
Groups = tuple[tuple[Condition, ...], ...]


@dataclass(frozen=True)
class Check:
    where: Where
    field: str | None = None   # bulgunun alanı; değeri bu alandan


@dataclass(frozen=True)
class RuleDef:
    code: str
    table: str
    title: str                   # kullanıcı dilinde ad (listede "Kural")
    condition: str               # okunur koşul (listede "Koşul")
    severity: str
    check_type: str
    message: str
    kind: str = BUILTIN_KIND
    reads: tuple[str, ...] = ()
    groups: Groups | None = None  # editörle ifade edilen koşul (düzenlenir)
    checks: tuple[Check, ...] = ()
    python: Callable[[Session, str], list[Hit]] | None = None
    append_value: bool = False   # mesajın sonuna değer: "Yeni birim: KG"
    group: bool = False          # küme kuralı (docs TÜR "Küme"; veride Mantıksal)
    may_be_empty: tuple[str, ...] = ()  # okunan ama boş olabilecek tablolar: verisi yoksa kural atlanmaz (docs OKUNAN "(boş olabilir)", K-146)

    @property
    def runs(self) -> bool:
        return bool(self.groups or self.checks or self.python)

    @property
    def editable(self) -> bool:
        return self.groups is not None and self.kind == BUILTIN_KIND


def C(where: Where, field: str | None = None) -> Check:
    return Check(where, field)


def Q(field: str, operator: str, value=None, other: str | None = None) -> Condition:
    """Koşul: değer ya da öteki alan (other)."""
    return Condition(field, operator, None if value is None else str(value), other)


def _today() -> sa.ColumnElement:
    return sa.cast(sa.func.getdate(), sa.Date)


def _flags_not_one(t, names: Iterable[str]) -> sa.ColumnElement:
    """Bayraklardan hiçbiri ya da birden fazlası 1."""
    total = sum((sa.cast(nz(t.c[n]), sa.Integer) for n in names), sa.literal(0))
    return total != 1


# ------------------------------------------------------------------ ortak kurallar

NEGATIVE_FIELDS: dict[str, tuple[str, ...]] = {  # docs/06 fonksiyon 04 "Negatif değer alanları"
    "Material": ("GoodsReceiptDays", "SafetyStock", "StockCoverageDays", "MaxStock", "MinLot", "MaxLot", "LotMultiple", "QtyPerBox", "QtyPerPallet", "ScrapRatio", "ShelfLifeDays"),
    "UomConversion": ("Factor",),
    "ProductionVersion": ("BaseQuantity",),
    "BOM": ("Quantity", "ScrapRatio"),
    "Routing": ("Consumption", "ResourceNumber", "TransferQuantity", "WaitingTimeHours", "TransferTimeHours"),
    "MaterialReference": ("TimeFactor",),
    "EmployeeAbsence": ("HoursPerDay",),
    "MaterialSupplier": ("QuotaRatio", "FixedLeadTimeDays", "VariableLeadTimeDays", "MinimumOrderQuantity", "OrderLotSize", "MaximumOrderQuantity"),
    "SalesOrderLine": ("OpenQuantity", "OrderedQuantity", "DeliveredQuantity"),
    "Forecast": ("Quantity",),
    "BorrowPayback": ("BorrowedQuantity", "PaidBackQuantity"),
    "Stock": ("Quantity",),
    "WorkOrder": ("OrderedQuantity", "OpenQuantity", "CompletedQuantity", "ScrapQuantity"),
    "WorkOrderComponent": ("RequiredQuantity", "IssuedQuantity", "UnitUsage", "ScrapRatio"),
    "WorkOrderOperation": ("ResourceNumber", "PlannedConsumption", "ConfirmedConsumption", "TransferQuantity", "WaitingTimeHours", "TransferTimeHours"),
    "PurchaseOrderLine": ("OpenQuantity", "OrderedQuantity", "ReceivedQuantity"),
    "ProductionConfirmation": ("ConfirmedQuantity",),
}
DATE_PAIRS = (("ValidFrom", "ValidTo"), ("StartDate", "EndDate"))
RATIO_FIELDS = ("ScrapRatio", "QuotaRatio")


def _columns(entity: str) -> dict[str, sa.Column]:
    return {c.name: c for c in stg_columns(entity)}


def _after_rules(entity: str) -> list[str]:
    return [c.name for c in stg_columns(entity) if c.info.get("missing") == AFTER_RULES]


def _list_fields(entity: str) -> list[tuple[str, list[str]]]:
    return [(c.name, list(c.info["values"])) for c in stg_columns(entity) if c.info.get("values")]


def _out_of_list(name: str, values: list[str]) -> Where:
    def where(t):
        col = t.c[name].collate("Latin1_General_100_BIN2")  # ön kontroldeki gibi birebir (K-110)
        return sa.and_(t.c[name].is_not(None), col.not_in(values))
    return where


def _structural(code, entity, title, condition, message, checks=()) -> RuleDef:
    return RuleDef(code, entity, title, condition, ERROR, STRUCTURAL, message, STRUCTURAL_KIND, checks=tuple(checks))


def _grouped(code, entity, title, severity, message, groups, check_type=LOGICAL, **kw) -> RuleDef:
    groups = tuple(tuple(g) for g in groups)
    return RuleDef(code, entity, title, cond.sentence(entity, [list(g) for g in groups]), severity, check_type, message, groups=groups, **kw)


def common_rules(entity: str) -> list[RuleDef]:
    cols = _columns(entity)
    out = [
        _structural("STR.TYPE", entity, "Tip uymuyor", "Tip ya da sayı aralığı uymuyor", "Tip uymuyor."),
        _structural("STR.LENGTH", entity, "Metin alana sığmıyor", "Metin alana sığmıyor", "Metin alana sığmıyor."),
        _structural("STR.REQUIRED", entity, "Zorunlu alan boş",
                    "Zorunlu alan boş: \"hata (satır atlanır)\" ön kontrolde, \"hata (kurallardan sonra)\" validasyonda", "Zorunlu alan boş.",
                    [C(lambda t, n=n: t.c[n].is_(None), n) for n in _after_rules(entity)]),
    ]
    if has_key(entity):
        out.append(_structural("STR.DUPLICATE", entity, "Aynı kayıt birden fazla satırda", "Aynı anahtar birden fazla satırda", "Aynı kayıt birden fazla satırda."))
    if entity in NEGATIVE_FIELDS:
        out.append(_grouped("ALL.NEGATIVE", entity, "Negatif değer", ERROR, "Negatif olamaz.", [[Q(n, cond.LT, 0)] for n in NEGATIVE_FIELDS[entity]]))
    pairs = [(a, b) for a, b in DATE_PAIRS if a in cols and b in cols]
    if pairs:
        out.append(_grouped("ALL.DATE_ORDER", entity, "Başlangıç bitişten sonra", ERROR, "Başlangıç bitişten sonra.", [[Q(a, cond.GT, other=b)] for a, b in pairs]))
    ratios = [n for n in RATIO_FIELDS if n in cols]
    if ratios:
        out.append(_grouped("ALL.RATIO_RANGE", entity, "Oran 0–1 dışında", ERROR, "Oran 0 ile 1 arasında olmalı.",
                            [g for n in ratios for g in ([Q(n, cond.LT, 0)], [Q(n, cond.GT, 1)])]))
    listed = _list_fields(entity)
    if listed:
        out.append(RuleDef("ALL.OUT_OF_LIST", entity, "Liste dışı değer", "Değer listeli alanda liste dışı değer (K-110)", INFO, LOGICAL, "Smartchain değerlerinde yok.",
                           checks=tuple(C(_out_of_list(n, v), n) for n, v in listed)))
    return out


# ------------------------------------------------------------------ küme ve tablolar arası yardımcıları

def _cycle_rule(entity: str, parent: str, child: str, field: str) -> Callable[[Session, str], list[Hit]]:
    """Lokasyon içinde parent → child kenarları; aynı güçlü bileşende (2+ düğüm) kalan kenarların satırları."""
    def run(session: Session, _: str) -> list[Hit]:
        t = alias(entity)
        rows = session.execute(sa.select(t.c.StagingRowId, t.c.LocationCode, t.c[parent], t.c[child])
                               .where(current(t), t.c[parent].is_not(None), t.c[child].is_not(None))).all()
        graph: dict[tuple, list[tuple]] = {}
        for _, loc, a, b in rows:
            u, v = (str(loc).upper(), str(a).upper()), (str(loc).upper(), str(b).upper())
            if u != v:
                graph.setdefault(u, []).append(v)
        comp = _strong_components(graph)
        hits = []
        for row_id, loc, a, b in rows:
            u, v = (str(loc).upper(), str(a).upper()), (str(loc).upper(), str(b).upper())
            if u != v and comp.get(u) is not None and comp.get(u) == comp.get(v):
                hits.append((row_id, label(entity, field), str(b)))
        return hits
    return run


def _strong_components(graph: dict) -> dict:
    """Tarjan (yinelemeli); yalnız 2+ düğümlü bileşenler numaralanır."""
    index, low, on_stack, stack, comp = {}, {}, set(), [], {}
    counter, number = [0], [0]
    nodes = set(graph) | {v for vs in graph.values() for v in vs}
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(graph.get(root, ())))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on_stack.add(root)
        while work:
            node, it = work[-1]
            advanced = False
            for nxt in it:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter[0]
                    counter[0] += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(graph.get(nxt, ()))))
                    advanced = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                members = []
                while True:
                    w = stack.pop()
                    on_stack.discard(w)
                    members.append(w)
                    if w == node:
                        break
                if len(members) > 1:
                    number[0] += 1
                    for w in members:
                        comp[w] = number[0]
    return comp


def _other_differs(entity: str, keys: tuple[str, ...], field: str) -> Where:
    def where(t):
        o = alias(entity, "_o")
        return sa.and_(t.c[field].is_not(None), sa.exists().where(
            current(o), o.c.StagingRowId != t.c.StagingRowId, *[same(o.c[k], t.c[k]) for k in keys], o.c[field].is_not(None), o.c[field] != t.c[field]))
    return where


def _alone_in_group(entity: str, keys: tuple[str, ...], group: str) -> Where:
    def where(t):
        o = alias(entity, "_o")
        return sa.and_(t.c[group].is_not(None), ~sa.exists().where(
            current(o), o.c.StagingRowId != t.c.StagingRowId, *[same(o.c[k], t.c[k]) for k in keys], o.c[group] == t.c[group]))
    return where


def _uom_inverse(t):
    o = alias("UomConversion", "_o")
    return sa.exists().where(current(o), same(o.c.MaterialCode, t.c.MaterialCode), o.c.FromUom == t.c.ToUom, o.c.ToUom == t.c.FromUom,
                             sa.func.abs(o.c.Factor * t.c.Factor - 1) > 0.0001)


def _new_uom(field: str) -> Where:
    def where(t):
        m = alias("Material", "_u")
        return sa.and_(t.c[field].is_not(None), ~sa.exists().where(current(m), m.c.BaseUom == t.c[field]))
    return where


def _quota_sum(t):
    o = alias("MaterialSupplier", "_q")
    sums = (sa.select(o.c.LocationCode, o.c.MaterialCode).where(current(o), o.c.QuotaRatio.is_not(None))
            .group_by(o.c.LocationCode, o.c.MaterialCode).having(sa.func.abs(sa.func.sum(o.c.QuotaRatio) - 1) > 0.00005).subquery("q"))
    return sa.and_(t.c.QuotaRatio.is_not(None), sa.exists().where(sums.c.LocationCode == t.c.LocationCode, sums.c.MaterialCode == t.c.MaterialCode))


def _overlap(t):
    o = alias("EmployeeAbsence", "_o")
    return sa.exists().where(current(o), o.c.StagingRowId != t.c.StagingRowId, o.c.LocationCode == t.c.LocationCode, o.c.ResourceCode == t.c.ResourceCode,
                             o.c.StartDate <= t.c.EndDate, o.c.EndDate >= t.c.StartDate)


def _resource(t, code_field: str, *conditions) -> sa.ColumnElement:
    r = alias("Resource", "_r")
    return sa.exists().where(current(r), r.c.LocationCode == t.c.LocationCode, r.c.Code == t.c[code_field], *[c(r) for c in conditions])


def _not_member(t):
    a = alias("ResourceGroupAssignment", "_m")
    return sa.and_(t.c.ResourceCode.is_not(None), t.c.ResourceGroupCode.is_not(None), ~sa.exists().where(
        current(a), a.c.LocationCode == t.c.LocationCode, a.c.ResourceGroupCode == t.c.ResourceGroupCode, a.c.ResourceCode == t.c.ResourceCode))


def _group_unit(t):
    a, r = alias("ResourceGroupAssignment", "_g"), alias("Resource", "_g")
    mixed = (sa.select(a.c.LocationCode, a.c.ResourceGroupCode)
             .select_from(a.join(r, sa.and_(r.c.LocationCode == a.c.LocationCode, r.c.Code == a.c.ResourceCode)))
             .where(current(a), current(r), r.c.CapacityUnit.is_not(None))
             .group_by(a.c.LocationCode, a.c.ResourceGroupCode).having(sa.func.count(sa.distinct(r.c.CapacityUnit)) > 1).subquery("mixed"))
    return sa.and_(t.c.ResourceGroupCode.is_not(None),
                   sa.exists().where(mixed.c.LocationCode == t.c.LocationCode, mixed.c.ResourceGroupCode == t.c.ResourceGroupCode))


def _competence_not_employee(t):
    g = alias("ResourceGroup", "_c")
    return sa.and_(sa.exists().where(current(g), g.c.LocationCode == t.c.LocationCode, g.c.Code == t.c.ResourceGroupCode, one(g.c.IsCompetenceGroup)),
                   _resource(t, "ResourceCode", lambda r: nz(r.c.IsEmployee) == 0))


def _non_stockable(t):
    m = alias("Material", "_n")
    return sa.exists().where(current(m), m.c.LocationCode == t.c.LocationCode, m.c.Code == t.c.MaterialCode, one(m.c.IsNonStockable))


def _confirmation_material(t):
    w = alias("WorkOrder", "_w")
    return sa.exists().where(current(w), w.c.LocationCode == t.c.LocationCode, w.c.WorkOrderNo == t.c.WorkOrderNo, w.c.MaterialCode != t.c.MaterialCode)


# ------------------------------------------------------------------ tablo kuralları (docs/06 fonksiyon 04)

H, U, B = ERROR, WARNING, INFO
EQ, NE, GT, LT, GE, LE, EMPTY, FILLED = cond.EQ, cond.NE, cond.GT, cond.LT, cond.GE, cond.LE, cond.EMPTY, cond.FILLED
RES_TYPES = ("IsEmployee", "IsMachine", "IsFurnace", "IsMold", "IsOther", "IsSubcontractor")
OWNER = (Q("ProjectCode", EMPTY), Q("CustomerCode", EMPTY), Q("SalesOrderNo", EMPTY))


def G(code, table, title, severity, message, *groups, **kw) -> RuleDef:
    """Editörle ifade edilen hazır kural: her argüman bir VE grubu."""
    return _grouped(code, table, title, severity, message, groups, **kw)


def X(code, table, title, condition, severity, message, *checks, check_type=LOGICAL, reads=(), python=None, append_value=False, group=False,
      may_be_empty=()) -> RuleDef:
    """Editörle ifade edilemeyen hazır kural: yalnız sınıf ve aktiflik değişir."""
    return RuleDef(code, table, title, condition, severity, check_type, message, reads=tuple(reads), checks=tuple(checks), python=python,
                   append_value=append_value, group=group, may_be_empty=tuple(may_be_empty))


TABLE_RULES: tuple[RuleDef, ...] = (
    G("LOC.NO_FLAG", "Location", "Lokasyon tipi yok", U, "Lokasyon tesis, depo ya da fason deposu değil.",
      [Q("IsFactory", NE, 1), Q("IsDepot", NE, 1), Q("IsSubcontractor", NE, 1)]),
    G("UOM.FACTOR", "UomConversion", "Çarpan sıfır ya da negatif", H, "Çarpan sıfırdan büyük olmalı.", [Q("Factor", LE, 0)]),
    G("UOM.SAME_UOM", "UomConversion", "Kaynak ve hedef birim aynı", H, "Kaynak ve hedef birim aynı.", [Q("ToUom", EQ, other="FromUom")]),
    X("UOM.INVERSE", "UomConversion", "Ters dönüşümle tutarsız", "A→B ve B→A tanımlı, çarpımları 1 değil", U, "Ters yön dönüşümüyle çarpımı 1 değil.",
      C(_uom_inverse, "Factor"), group=True),
    X("UOM.NEW_UOM", "UomConversion", "Yeni birim", "Birim kodu malzemelerin temel birimlerinde geçmiyor (K-112)", B, "Yeni birim:",
      C(_new_uom("FromUom"), "FromUom"), C(_new_uom("ToUom"), "ToUom"), check_type=CROSS, reads=("Material",), append_value=True),
    G("MAT.MINLOT_MAXLOT", "Material", "Minimum lot maksimum lottan büyük", H, "Minimum lot maksimum lottan büyük.", [Q("MinLot", GT, other="MaxLot")]),
    G("MAT.SAFETY_MAX", "Material", "Güvenlik stoğu maksimum stoktan büyük", U, "Güvenlik stoğu maksimum stoktan büyük.", [Q("SafetyStock", GT, other="MaxStock")]),
    G("MAT.ZERO_PACK", "Material", "Lot katı, kutu ya da palet miktarı sıfır", U, "Sıfır olamaz; boş bırakılabilir.",
      [Q("LotMultiple", EQ, 0)], [Q("QtyPerBox", EQ, 0)], [Q("QtyPerPallet", EQ, 0)]),
    G("MAT.SUPPLY_CONFLICT", "Material", "Tedarik türü bayraklarla çelişiyor", U, "Tedarik türü bayraklarla çelişiyor.",
      [Q("DefaultSupplyType", EQ, "Üretim"), Q("IsProducible", NE, 1)], [Q("DefaultSupplyType", EQ, "Satın alma"), Q("IsPurchasable", NE, 1)],
      [Q("DefaultSupplyType", EQ, "Fason"), Q("IsSubcontractable", NE, 1)]),
    G("MAT.NO_SUPPLY", "Material", "Aktif malzemenin tedarik yolu yok", U, "Aktif malzeme üretilemez, satın alınamaz ve fasona verilemez.",
      [Q("IsProducible", NE, 1), Q("IsPurchasable", NE, 1), Q("IsSubcontractable", NE, 1), Q("IsActive", EQ, 1)]),
    G("MAT.SAFETY_COVERAGE", "Material", "Güvenlik stoğu hem miktar hem gün", B, "Güvenlik stoğu hem miktar hem gün olarak verilmiş.",
      [Q("StockCoverageDays", FILLED), Q("SafetyStock", FILLED)]),
    G("PV.BASEQTY", "ProductionVersion", "Baz miktar sıfır ya da negatif", H, "Baz miktar sıfırdan büyük olmalı.", [Q("BaseQuantity", LE, 0)]),
    X("PV.BASEQTY_DIFFERS", "ProductionVersion", "Aynı ağaçta baz miktar farklı", "Aynı ürün ağacını kullanan versiyonlarda baz miktar farklı (K-115)", U,
      "Aynı ağacı kullanan versiyonların baz miktarı farklı.", C(_other_differs("ProductionVersion", ("LocationCode", "BOMCode"), "BaseQuantity"), "BaseQuantity"), group=True),
    X("PV.EXPIRED", "ProductionVersion", "Aktif versiyonun geçerliliği bitmiş", "Aktif versiyonun geçerlilik bitişi geçmişte", U, "Aktif versiyonun geçerliliği bitmiş.",
      C(lambda t: sa.and_(one(t.c.IsActive), t.c.ValidTo < _today()), "ValidTo")),
    G("BOM.SELF", "BOM", "Bileşen üretilen malzemenin kendisi", H, "Bileşen üretilen malzemenin kendisi.", [Q("ComponentMaterialCode", EQ, other="MaterialCode")]),
    X("BOM.CYCLE", "BOM", "Ürün ağacında döngü", "Malzeme dolaylı olarak kendi bileşeni", H, "Ürün ağacında döngü.",
      python=_cycle_rule("BOM", "MaterialCode", "ComponentMaterialCode", "ComponentMaterialCode"), group=True),
    G("BOM.ZERO_QTY", "BOM", "Bileşen miktarı sıfır", U, "Bileşen miktarı sıfır.", [Q("Quantity", EQ, 0)]),
    G("BOM.PRIORITY_NO_GROUP", "BOM", "Alternatif önceliği var, grubu yok", U, "Alternatif önceliği var, alternatif grubu yok.",
      [Q("AlternativePriority", FILLED), Q("AlternativeGroup", EMPTY)]),
    X("BOM.SINGLE_ALTERNATIVE", "BOM", "Alternatif grupta tek satır", "Alternatif grupta tek satır", U, "Alternatif grupta tek satır var.",
      C(_alone_in_group("BOM", ("LocationCode", "MaterialCode", "Code"), "AlternativeGroup"), "AlternativeGroup"), group=True),
    G("RTG.NO_RESOURCE", "Routing", "Kaynak ve kaynak grubu boş", H, "Kaynak ya da kaynak grubu dolu olmalı.",
      [Q("ResourceCode", EMPTY), Q("ResourceGroupCode", EMPTY)]),
    G("RTG.RESOURCE_NUMBER", "Routing", "Kaynak adedi 1'den az", H, "Kaynak adedi en az 1 olmalı.", [Q("ResourceNumber", LT, 1)]),
    G("RTG.ZERO_CONSUMPTION", "Routing", "Tüketim sıfır", U, "Tüketim sıfır.", [Q("Consumption", EQ, 0)]),
    G("RTG.PRIORITY_NO_GROUP", "Routing", "Alternatif önceliği var, grubu yok", U, "Alternatif önceliği var, alternatif grubu yok.",
      [Q("AlternativePriority", FILLED), Q("AlternativeGroup", EMPTY)]),
    X("RTG.NOT_MEMBER", "Routing", "Kaynak, kaynak grubunun üyesi değil", "Kaynak, yazılan kaynak grubunun üyesi değil (K-116)", U,
      "Kaynak, yazılan kaynak grubunun üyesi değil.", C(_not_member, "ResourceCode"), check_type=CROSS, reads=("ResourceGroupAssignment",)),
    X("RTG.GROUP_UNIT", "Routing", "Kaynak grubunda kapasite birimleri farklı", "Yazılan kaynak grubundaki kaynakların kapasite birimi farklı (K-116)", U,
      "Kaynak grubundaki kaynakların kapasite birimi farklı.", C(_group_unit, "ResourceGroupCode"), check_type=CROSS, reads=("ResourceGroupAssignment", "Resource")),
    X("RTG.SUBCON_RESOURCE", "Routing", "Fason operasyonun kaynağı fason değil", "Fason operasyon = Evet ama kaynak fason değil", U, "Fason operasyonun kaynağı fason değil.",
      C(lambda t: sa.and_(one(t.c.IsSubcontracted), t.c.ResourceCode.is_not(None), _resource(t, "ResourceCode", lambda r: nz(r.c.IsSubcontractor) == 0)), "ResourceCode"),
      check_type=CROSS, reads=("Resource",)),
    G("REF.SELF", "MaterialReference", "Malzeme kendisine benzetilmiş", H, "Malzeme kendisine benzetilmiş.", [Q("ReferenceMaterialCode", EQ, other="MaterialCode")]),
    X("REF.CYCLE", "MaterialReference", "Referans zincirinde döngü", "Referans zincirinde döngü", H, "Referans zincirinde döngü.",
      python=_cycle_rule("MaterialReference", "MaterialCode", "ReferenceMaterialCode", "ReferenceMaterialCode"), group=True),
    G("REF.TIMEFACTOR", "MaterialReference", "Süre çarpanı sıfır ya da negatif", H, "Süre çarpanı sıfırdan büyük olmalı.", [Q("TimeFactor", LE, 0)]),
    G("RG.NO_TYPE", "ResourceGroup", "Grup tipi yok", U, "Grup ne kaynak grubu ne yetkinlik grubu.", [Q("IsResourceGroup", NE, 1), Q("IsCompetenceGroup", NE, 1)]),
    X("RES.TYPE_FLAGS", "Resource", "Kaynak tipi tek değil", "İşçi, Makine, Fırın, Kalıp, Diğer, Fason bayraklarından hiçbiri ya da birden fazlası Evet", U,
      "Kaynağın tek bir tipi olmalı.", C(lambda t: _flags_not_one(t, RES_TYPES), "IsEmployee")),
    G("RES.SUBCON_CONFLICT", "Resource", "Fason bayrağı fasoncuyla çelişiyor", U, "Fason bayrağı ile fasoncu çelişiyor.",
      [Q("SubcontractorCode", EMPTY), Q("IsSubcontractor", EQ, 1)], [Q("SubcontractorCode", FILLED), Q("IsSubcontractor", NE, 1)]),
    G("RES.MONTH_YEAR", "Resource", "Aylık kalan fazla mesai yıllıktan büyük", U, "Aylık kalan fazla mesai yıllıktan büyük.",
      [Q("RemainingOverTimeMonth", GT, other="RemainingOverTimeYear")]),
    G("RES.PHASE1_UNUSED", "Resource", "Fırın ya da kalıp Faz 1'de kullanılmaz", B, "Fırın ve kalıp Faz 1 planlamasında kullanılmaz.",
      [Q("IsFurnace", EQ, 1)], [Q("IsMold", EQ, 1)]),
    X("RGA.COMPETENCE_NOT_EMPLOYEE", "ResourceGroupAssignment", "Yetkinlik grubunda işçi olmayan kaynak", "Yetkinlik grubuna işçi olmayan kaynak atanmış", U,
      "Yetkinlik grubuna işçi olmayan kaynak atanmış.", C(_competence_not_employee, "ResourceCode"), check_type=CROSS, reads=("ResourceGroup", "Resource")),
    G("ABS.HOURS", "EmployeeAbsence", "Günlük izin saati 0–24 dışında", H, "Günlük saat 0'dan büyük, en çok 24 olmalı.",
      [Q("HoursPerDay", LE, 0)], [Q("HoursPerDay", GT, 24)]),
    X("ABS.NOT_EMPLOYEE", "EmployeeAbsence", "İzin kaydının kaynağı işçi değil", "Kaynak işçi değil", U, "İzin kaydının kaynağı işçi değil.",
      C(lambda t: _resource(t, "ResourceCode", lambda r: nz(r.c.IsEmployee) == 0), "ResourceCode"), check_type=CROSS, reads=("Resource",)),
    X("ABS.OVERLAP", "EmployeeAbsence", "İzinler çakışıyor", "Aynı kişinin izinleri çakışıyor", U, "Aynı kişinin izinleri çakışıyor.", C(_overlap, "StartDate"), group=True),
    G("MS.MIN_MAX", "MaterialSupplier", "Minimum sipariş maksimumdan büyük", H, "Minimum sipariş maksimumdan büyük.",
      [Q("MinimumOrderQuantity", GT, other="MaximumOrderQuantity")]),
    G("MS.LOT", "MaterialSupplier", "Sipariş katı sıfır ya da negatif", H, "Sipariş katı sıfırdan büyük olmalı.", [Q("OrderLotSize", LE, 0)]),
    G("MS.NO_BASIS", "MaterialSupplier", "Tedarik süresi var, süre esası yok", H, "Tedarik süresi var, tedarik süresi esası boş.",
      [Q("LeadTimeBasis", EMPTY), Q("FixedLeadTimeDays", FILLED)], [Q("LeadTimeBasis", EMPTY), Q("VariableLeadTimeDays", FILLED)]),
    G("MS.NO_LEADTIME", "MaterialSupplier", "Tedarik süresi yok", U, "Tedarik süresi yok; plan bu satırı kullanmaz.",
      [Q("FixedLeadTimeDays", EMPTY), Q("VariableLeadTimeDays", EMPTY)]),
    X("MS.QUOTA_SUM", "MaterialSupplier", "Kota toplamı 1 değil", "Aynı malzeme ve lokasyonda dolu kota oranlarının toplamı 1 değil", U, "Kota oranlarının toplamı 1 değil.",
      C(_quota_sum, "QuotaRatio"), group=True),
    G("SO.ZERO_OPEN", "SalesOrderLine", "Açık miktar sıfır", U, "Açık miktar sıfır.", [Q("OpenQuantity", EQ, 0)]),
    G("SO.DELIVERED", "SalesOrderLine", "Teslim edilen sipariş miktarından büyük", U, "Teslim edilen sipariş miktarından büyük.",
      [Q("DeliveredQuantity", GT, other="OrderedQuantity")]),
    X("SO.OPEN_MISMATCH", "SalesOrderLine", "Açık miktar sipariş eksi teslime eşit değil", "Açık miktar ≠ Sipariş miktarı − Teslim edilen miktar (üçü de doluysa)", U,
      "Açık miktar, sipariş eksi teslime eşit değil.",
      C(lambda t: sa.and_(t.c.OrderedQuantity.is_not(None), t.c.DeliveredQuantity.is_not(None),
                          sa.func.abs(t.c.OpenQuantity - (t.c.OrderedQuantity - t.c.DeliveredQuantity)) > 0.00005), "OpenQuantity")),
    G("STK.LINE_NO_ORDER", "Stock", "Sipariş satırı var, sipariş no yok", H, "Sipariş satırı var, sipariş no yok.",
      [Q("SalesOrderLineNo", FILLED), Q("SalesOrderNo", EMPTY)]),
    G("STK.ACCEPT_DATE", "Stock", "Kabul tarihi kaliteye girişten önce", H, "Beklenen kabul tarihi kaliteye girişten önce.",
      [Q("ExpectedAcceptanceDate", LT, other="QualityEntryDate")]),
    X("STK.STATUS_FLAGS", "Stock", "Stok durumu tek değil", "Kullanılabilir, Kalitede, Bloke bayraklarından hiçbiri ya da birden fazlası Evet", U, "Stokun tek bir durumu olmalı.",
      C(lambda t: _flags_not_one(t, ("IsAvailable", "IsInQuality", "IsBlocked")), "IsAvailable")),
    G("STK.QUALITY_NO_DATE", "Stock", "Kalitedeki stokun kabul tarihi yok", U, "Kalitedeki stokun beklenen kabul tarihi yok.",
      [Q("ExpectedAcceptanceDate", EMPTY), Q("IsInQuality", EQ, 1)]),
    X("STK.EXPIRED", "Stock", "Son kullanma tarihi geçmiş", "Kullanılabilir stokta son kullanma tarihi geçmiş", U, "Kullanılabilir stokun son kullanma tarihi geçmiş.",
      C(lambda t: sa.and_(one(t.c.IsAvailable), t.c.ExpiryDate < _today()), "ExpiryDate")),
    X("STK.NON_STOCKABLE", "Stock", "Stok tutulamaz malzemede stok", "Stok tutulamaz malzemede stok kaydı (K-113)", U, "Stok tutulamaz malzemede stok kaydı.",
      C(_non_stockable, "MaterialCode"), check_type=CROSS, reads=("Material",)),
    G("STK.CUSTOM_NO_OWNER", "Stock", "Özel takipli stokun sahibi yok", U, "Özel takipli kaydın sahibi yok.", [Q("IsCustomTracked", EQ, 1), *OWNER]),
    G("STK.ZERO_QTY", "Stock", "Stok miktarı sıfır", B, "Stok miktarı sıfır.", [Q("Quantity", EQ, 0)]),
    G("BP.SAME_PROJECT", "BorrowPayback", "Ödünç veren ve alan proje aynı", H, "Ödünç veren ve alan proje aynı.", [Q("BorrowingProjectCode", EQ, other="LendingProjectCode")]),
    G("BP.QTY", "BorrowPayback", "Ödünç miktarı sıfır ya da negatif", H, "Ödünç miktarı sıfırdan büyük olmalı.", [Q("BorrowedQuantity", LE, 0)]),
    G("BP.DUE_DATE", "BorrowPayback", "Geri ödeme tarihi ödünçten önce", H, "Geri ödeme tarihi ödünç tarihinden önce.", [Q("PaybackDueDate", LT, other="BorrowDate")]),
    G("BP.PAID", "BorrowPayback", "Geri ödenen ödünçten fazla", U, "Geri ödenen ödünçten fazla.", [Q("PaidBackQuantity", GT, other="BorrowedQuantity")]),
    G("WO.QTY", "WorkOrder", "İş emri miktarı sıfır ya da negatif", H, "İş emri miktarı sıfırdan büyük olmalı.", [Q("OrderedQuantity", LE, 0)]),
    G("WO.START_DUE", "WorkOrder", "Başlangıç bitişten sonra", H, "Başlangıç bitişten sonra.", [Q("StartDate", GT, other="DueDate")]),
    G("WO.SELF_PARENT", "WorkOrder", "İş emri kendisinin yeniden işlemesi", H, "İş emri kendisinin yeniden işlemesi.", [Q("ParentWorkOrderNo", EQ, other="WorkOrderNo")]),
    G("WO.LINE_NO_ORDER", "WorkOrder", "Sipariş satırı var, sipariş no yok", H, "Sipariş satırı var, sipariş no yok.",
      [Q("SalesOrderLineNo", FILLED), Q("SalesOrderNo", EMPTY)]),
    G("WO.OPEN_ORDERED", "WorkOrder", "Açık miktar iş emri miktarından büyük", U, "Açık miktar iş emri miktarından büyük.", [Q("OpenQuantity", GT, other="OrderedQuantity")]),
    G("WO.ZERO_OPEN", "WorkOrder", "Açık miktar sıfır", U, "Açık miktar sıfır.", [Q("OpenQuantity", EQ, 0)]),
    X("WO.TYPE_FLAGS", "WorkOrder", "İş emri tipi tek değil", "Üretim, Fason, Yeniden işleme bayraklarından hiçbiri ya da birden fazlası Evet", U, "İş emrinin tek bir tipi olmalı.",
      C(lambda t: _flags_not_one(t, ("IsProduction", "IsSubcontract", "IsRework")), "IsProduction")),
    G("WO.REWORK_NO_PARENT", "WorkOrder", "Yeniden işlemenin orijinal iş emri yok", U, "Yeniden işlemenin orijinal iş emri yok.",
      [Q("ParentWorkOrderNo", EMPTY), Q("IsRework", EQ, 1)]),
    G("WO.CUSTOM_NO_OWNER", "WorkOrder", "Özel takipli iş emrinin sahibi yok", U, "Özel takipli kaydın sahibi yok.", [Q("IsCustomTracked", EQ, 1), *OWNER]),
    G("WOC.ISSUED", "WorkOrderComponent", "Çekilen gereken miktardan fazla", U, "Çekilen gereken miktardan fazla.", [Q("IssuedQuantity", GT, other="RequiredQuantity")]),
    G("WOO.NO_RESOURCE", "WorkOrderOperation", "Kaynak ve kaynak grubu boş", H, "Kaynak ya da kaynak grubu dolu olmalı.",
      [Q("ResourceCode", EMPTY), Q("ResourceGroupCode", EMPTY)]),
    G("WOO.RESOURCE_NUMBER", "WorkOrderOperation", "Kaynak adedi 1'den az", H, "Kaynak adedi en az 1 olmalı.", [Q("ResourceNumber", LT, 1)]),
    G("WOO.CONFIRMED", "WorkOrderOperation", "Teyit edilen tüketim planlanandan fazla", U, "Teyit edilen tüketim planlanandan fazla.",
      [Q("ConfirmedConsumption", GT, other="PlannedConsumption")]),
    G("PO.ZERO_OPEN", "PurchaseOrderLine", "Açık miktar sıfır", U, "Açık miktar sıfır.", [Q("OpenQuantity", EQ, 0)]),
    G("PO.RECEIVED", "PurchaseOrderLine", "Teslim alınan sipariş miktarından büyük", U, "Teslim alınan sipariş miktarından büyük.",
      [Q("ReceivedQuantity", GT, other="OrderedQuantity")]),
    X("PO.TYPE_FLAGS", "PurchaseOrderLine", "Sipariş tipi tek değil", "Satın alma talebi, Satın alma, Fason bayraklarından hiçbiri ya da birden fazlası Evet", U,
      "Siparişin tek bir tipi olmalı.", C(lambda t: _flags_not_one(t, ("IsPurchaseRequest", "IsPurchase", "IsSubcontract")), "IsPurchase")),
    G("PO.SUBCON_NO_WO", "PurchaseOrderLine", "Fason siparişin iş emri yok", U, "Fason siparişin iş emri yok.", [Q("WorkOrderNo", EMPTY), Q("IsSubcontract", EQ, 1)]),
    G("PO.NO_SUPPLIER", "PurchaseOrderLine", "Tedarikçi yok", U, "Tedarikçi yok.", [Q("SupplierCode", EMPTY), Q("IsPurchaseRequest", NE, 1)]),
    G("PO.NO_DATE", "PurchaseOrderLine", "İstenen ve teyit tarihi yok", U, "İstenen ve teyit tarihi yok.", [Q("RequestedDate", EMPTY), Q("ConfirmedDate", EMPTY)]),
    G("PO.CUSTOM_NO_OWNER", "PurchaseOrderLine", "Özel takipli siparişin sahibi yok", U, "Özel takipli kaydın sahibi yok.", [Q("IsCustomTracked", EQ, 1), *OWNER]),
    G("PC.QTY", "ProductionConfirmation", "Teyit miktarı sıfır ya da negatif", H, "Teyit miktarı sıfırdan büyük olmalı.", [Q("ConfirmedQuantity", LE, 0)]),
    X("PC.MATERIAL", "ProductionConfirmation", "Malzeme iş emrininkinden farklı", "Malzeme, iş emrinin malzemesinden farklı", U, "Malzeme iş emrinin malzemesinden farklı.",
      C(_confirmation_material, "MaterialCode"), check_type=CROSS, reads=("WorkOrder",)),
)


# ------------------------------------------------------------------ referans, pasif ebeveyn ve bütünlük (K-146)

def _match(r: refs.Reference, t, p) -> list[sa.ColumnElement]:
    """Çocuk satırın ebeveyn eşleşmesi: ilk alan birebir; öteki alanlar boşsa eşleşmeyi daraltmaz (bağlı sipariş satırı)."""
    out = [p.c.LocationCode == t.c.LocationCode] if r.by_location else []
    for i, (cf, pf) in enumerate(zip(r.fields, r.parent_fields)):
        out.append(p.c[pf] == t.c[cf] if i == 0 else sa.or_(t.c[cf].is_(None), p.c[pf] == t.c[cf]))
    return out


def _missing(r: refs.Reference) -> Where:
    def where(t):
        p = alias(r.parent, "_p")
        return sa.and_(t.c[r.fields[0]].is_not(None), ~sa.exists().where(present(p), *_match(r, t, p)))
    return where


def _inactive(r: refs.Reference) -> Where:
    """Ebeveyn bulunuyor ve eşleşen bütün satırları pasif (IsActive = Hayır; boş pasif sayılmaz)."""
    def where(t):
        p, a = alias(r.parent, "_p"), alias(r.parent, "_a")
        return sa.and_(t.c[r.fields[0]].is_not(None), sa.exists().where(present(p), *_match(r, t, p), p.c.IsActive == sa.false()),
                       ~sa.exists().where(present(a), *_match(r, t, a), sa.or_(a.c.IsActive.is_(None), a.c.IsActive == sa.true())))
    return where


def _location_missing(t):
    loc = alias("Location", "_l")
    return sa.and_(t.c.LocationCode.is_not(None), ~sa.exists().where(present(loc), loc.c.Code == t.c.LocationCode))


def _suffix(r: refs.Reference) -> str:
    if r.label.endswith("satırı"):
        return ""
    return " numarası" if r.fields[0].endswith("No") else " kodu"


def _parent_name(table: str) -> str:
    found = contract_entity(table)
    return found.name if found else table


def _uom_conversion(uom: str, material: str) -> Where:
    """Birim dolu, malzemenin temel biriminden farklı ve dönüşüm yok: malzemeye özel ya da genel (MaterialCode boş), iki yönden biri (K-112)."""
    def where(t):
        m, u = alias("Material", "_m"), alias("UomConversion", "_u")
        pair = sa.or_(sa.and_(u.c.FromUom == t.c[uom], u.c.ToUom == m.c.BaseUom), sa.and_(u.c.FromUom == m.c.BaseUom, u.c.ToUom == t.c[uom]))
        return sa.and_(t.c[uom].is_not(None), sa.exists().where(
            present(m), m.c.LocationCode == t.c.LocationCode, m.c.Code == t.c[material], m.c.BaseUom.is_not(None), m.c.BaseUom != t.c[uom],
            ~sa.exists().where(present(u), pair, sa.or_(u.c.MaterialCode.is_(None), u.c.MaterialCode == t.c[material])).correlate_except(u)))
    return where


def reference_rules(entity: str) -> list[RuleDef]:
    """Ortak lokasyon ve birim dönüşümü kuralları; ilişki haritasından referans ve pasif ebeveyn kuralları (docs/03, K-146)."""
    out = []
    if "LocationCode" in _columns(entity):
        out.append(X("ALL.REF_LOCATION", entity, "Lokasyon bulunamadı", "Lokasyon kodu Lokasyon tablosunda yok", ERROR, "Lokasyon bulunamadı:",
                     C(_location_missing, "LocationCode"), check_type=CROSS, reads=("Location",), append_value=True))
    if entity in refs.UOM_FIELDS:
        uom, material = refs.UOM_FIELDS[entity]
        out.append(X("ALL.UOM_CONVERSION", entity, "Birim dönüşümü yok",
                     "Birim dolu, malzemenin temel biriminden farklı ve dönüşüm yok (malzemeye özel ya da genel, iki yönden biri; K-112)", ERROR,
                     "Birim dönüşümü yok:", C(_uom_conversion(uom, material), uom), check_type=CROSS, reads=("Material", "UomConversion"),
                     append_value=True))
    for r in refs.of(entity):
        parent = _parent_name(r.parent)
        condition = f"{r.label}{_suffix(r)} {parent} tablosunda yok" if r.kind == refs.REQUIRED else f"{r.label}{_suffix(r)} dolu ve {parent} tablosunda yok"
        out.append(X(f"{r.prefix}.REF_{r.key}", entity, f"{r.label} bulunamadı", condition, ERROR if r.is_error else WARNING, f"{r.label} bulunamadı:",
                     C(_missing(r), r.fields[0]), check_type=CROSS, reads=(r.parent,), append_value=True))
        if r.inactive:
            out.append(X(f"{r.prefix}.INACTIVE_{r.key}", entity, f"{r.label} pasif", f"{r.label} bulunuyor ama pasif (Aktif = Hayır)", r.inactive,
                         f"{r.label} pasif:", C(_inactive(r), r.fields[0]), check_type=CROSS, reads=(r.parent,), append_value=True))
    return out


def _has(name: str, suffix: str, *where) -> sa.ColumnElement:
    o = alias(name, suffix)
    return sa.exists().where(present(o), *[w(o) for w in where])


def _same_location(t):
    return lambda o: o.c.LocationCode == t.c.LocationCode


def _supply(t, value: str) -> sa.ColumnElement:
    return t.c.DefaultSupplyType == text(value)


def _active_supplier(t, *extra) -> sa.ColumnElement:
    """Kaydı aktif (IsActive ≠ Hayır) ve tedarikçisi pasif olmayan malzeme tedarikçisi."""
    ms, s = alias("MaterialSupplier", "_s"), alias("Supplier", "_t")
    return sa.exists().where(current(ms), ms.c.LocationCode == t.c.LocationCode, ms.c.MaterialCode == t.c.Code,
                             ~sa.exists().where(present(s), s.c.Code == ms.c.SupplierCode, s.c.IsActive == sa.false()),
                             *[e(ms) for e in extra])


def _subcontractor(ms) -> sa.ColumnElement:
    s = alias("Supplier", "_f")
    return sa.exists().where(present(s), s.c.Code == ms.c.SupplierCode, one(s.c.IsSubcontractor))


def _no_version(t):
    loc = _same_location(t)
    return sa.and_(_supply(t, "Üretim"),
                   ~_has("ProductionVersion", "_v", loc, lambda v: v.c.MaterialCode == t.c.Code, lambda v: one(v.c.IsActive)),
                   ~_has("MaterialReference", "_r", loc, lambda r: r.c.MaterialCode == t.c.Code))


def _bom_operation(t):
    v, r, o = alias("ProductionVersion", "_v"), alias("Routing", "_r"), alias("Routing", "_o")
    return sa.and_(t.c.OperationNo.is_not(None), sa.exists().where(
        present(v), v.c.LocationCode == t.c.LocationCode, v.c.MaterialCode == t.c.MaterialCode, v.c.BOMCode == t.c.Code,
        sa.exists().where(present(r), r.c.LocationCode == v.c.LocationCode, r.c.RouteCode == v.c.RouteCode),
        ~sa.exists().where(present(o), o.c.LocationCode == v.c.LocationCode, o.c.RouteCode == v.c.RouteCode,
                           o.c.OperationNo == t.c.OperationNo).correlate_except(o)))


def _wo_structure(t):
    loc = _same_location(t)
    wo = lambda o: o.c.WorkOrderNo == t.c.WorkOrderNo  # noqa: E731
    version = sa.and_(t.c.ProductionVersionCode.is_not(None),
                      _has("ProductionVersion", "_v", loc, lambda v: v.c.MaterialCode == t.c.MaterialCode, lambda v: v.c.Code == t.c.ProductionVersionCode))
    return sa.and_(~version, ~_has("WorkOrderComponent", "_c", loc, wo), ~_has("WorkOrderOperation", "_o", loc, wo))


def _woc_operation(t):
    loc = _same_location(t)
    wo = lambda o: o.c.WorkOrderNo == t.c.WorkOrderNo  # noqa: E731
    return sa.and_(t.c.OperationNo.is_not(None), _has("WorkOrderOperation", "_o", loc, wo),
                   ~_has("WorkOrderOperation", "_n", loc, wo, lambda o: o.c.OperationNo == t.c.OperationNo))


def _po_supplier(t):
    """Fason sipariş hariç: fasoncu malzemenin satın alma tedarikçileri arasında aranmaz."""
    return sa.and_(t.c.SupplierCode.is_not(None), nz(t.c.IsSubcontract) == 0, _has("Supplier", "_t", lambda s: s.c.Code == t.c.SupplierCode),
                   ~_has("MaterialSupplier", "_s", _same_location(t), lambda s: s.c.MaterialCode == t.c.MaterialCode,
                         lambda s: s.c.SupplierCode == t.c.SupplierCode))


def _cross(code, table, title, condition, severity, where, field, reads, may_be_empty=()) -> RuleDef:
    return X(code, table, title, condition, severity, f"{title}.", C(where, field), check_type=CROSS, reads=reads, may_be_empty=may_be_empty)


INTEGRITY_RULES: tuple[RuleDef, ...] = (
    _cross("MAT.NO_VERSION", "Material", "Üretilen malzemenin aktif versiyonu yok",
           "Tedarik türü = Üretim; aktif (Aktif = Evet) üretim versiyonu ve benzetilen ürün kaydı yok", WARNING, _no_version,
           "DefaultSupplyType", ("ProductionVersion", "MaterialReference"), ("MaterialReference",)),
    _cross("MAT.NO_SUPPLIER", "Material", "Satın alınan malzemenin aktif tedarikçisi yok",
           "Tedarik türü = Satın alma; kaydı ve tedarikçisi aktif malzeme tedarikçisi yok", WARNING,
           lambda t: sa.and_(_supply(t, "Satın alma"), ~_active_supplier(t)), "DefaultSupplyType", ("MaterialSupplier", "Supplier"), ("Supplier",)),
    _cross("MAT.NO_SUBCONTRACTOR", "Material", "Fason malzemenin fason tedarikçisi yok",
           "Tedarik türü = Fason; tedarikçisi fasoncu (Fasoncu mu = Evet) ve aktif olan aktif malzeme tedarikçisi yok", WARNING,
           lambda t: sa.and_(_supply(t, "Fason"), ~_active_supplier(t, _subcontractor)), "DefaultSupplyType", ("MaterialSupplier", "Supplier")),
    _cross("BOM.NO_VERSION", "BOM", "Ağaç hiçbir versiyonda kullanılmıyor", "Ürün ağacı kodu aynı malzemenin hiçbir üretim versiyonunda yok", WARNING,
           lambda t: ~_has("ProductionVersion", "_v", _same_location(t), lambda v: v.c.MaterialCode == t.c.MaterialCode, lambda v: v.c.BOMCode == t.c.Code),
           "Code", ("ProductionVersion",)),
    _cross("BOM.OPERATION_NOT_IN_ROUTE", "BOM", "Bileşenin operasyonu rotada yok",
           "Operasyon no dolu ve ağacı kullanan bir versiyonun rotasında bu operasyon yok", WARNING, _bom_operation, "OperationNo",
           ("ProductionVersion", "Routing")),
    _cross("RTG.NO_VERSION", "Routing", "Rota hiçbir versiyonda kullanılmıyor", "Rota kodu hiçbir üretim versiyonunda yok", WARNING,
           lambda t: ~_has("ProductionVersion", "_v", _same_location(t), lambda v: v.c.RouteCode == t.c.RouteCode), "RouteCode", ("ProductionVersion",)),
    _cross("REF.NO_VERSION", "MaterialReference", "Referans ürünün aktif versiyonu yok",
           "Referans ürün bulunuyor ve aktif (Aktif = Evet) üretim versiyonu yok", WARNING,
           lambda t: sa.and_(_has("Material", "_m", _same_location(t), lambda m: m.c.Code == t.c.ReferenceMaterialCode),
                             ~_has("ProductionVersion", "_v", _same_location(t), lambda v: v.c.MaterialCode == t.c.ReferenceMaterialCode,
                                   lambda v: one(v.c.IsActive))),
           "ReferenceMaterialCode", ("Material", "ProductionVersion")),
    _cross("RG.NO_RESOURCE", "ResourceGroup", "Kaynak grubunda kaynak yok", "Gruba atanmış kaynak yok", WARNING,
           lambda t: ~_has("ResourceGroupAssignment", "_a", _same_location(t), lambda a: a.c.ResourceGroupCode == t.c.Code),
           "Code", ("ResourceGroupAssignment",)),
    _cross("RES.UNUSED", "Resource", "Kaynak hiçbir rotada ve grupta yok", "Kaynak hiçbir rota satırında ve kaynak grubu atamasında geçmiyor", INFO,
           lambda t: sa.and_(~_has("Routing", "_r", _same_location(t), lambda r: r.c.ResourceCode == t.c.Code),
                             ~_has("ResourceGroupAssignment", "_a", _same_location(t), lambda a: a.c.ResourceCode == t.c.Code)),
           "Code", ("Routing", "ResourceGroupAssignment"), ("ResourceGroupAssignment",)),
    _cross("SUP.NO_MATERIAL", "Supplier", "Tedarikçi hiçbir malzemeye bağlı değil",
           "Tedarikçi hiçbir malzeme tedarikçisi kaydında yok ve hiçbir kaynağın fasoncusu değil", INFO,
           lambda t: sa.and_(~_has("MaterialSupplier", "_s", lambda s: s.c.SupplierCode == t.c.Code),
                             ~_has("Resource", "_r", lambda r: r.c.SubcontractorCode == t.c.Code)),
           "Code", ("MaterialSupplier", "Resource"), ("Resource",)),
    _cross("SO.NOT_SELLABLE", "SalesOrderLine", "Malzeme satılabilir değil", "Malzemenin Satılabilir alanı Evet değil", WARNING,
           lambda t: _has("Material", "_m", _same_location(t), lambda m: m.c.Code == t.c.MaterialCode, lambda m: nz(m.c.IsSellable) == 0),
           "MaterialCode", ("Material",)),
    _cross("WO.NO_STRUCTURE", "WorkOrder", "İş emrinin versiyonu ve kendi yapısı yok",
           "Üretim versiyonu boş ya da bulunamadı; iş emrinin bileşeni ve operasyonu yok", WARNING, _wo_structure, "ProductionVersionCode",
           ("ProductionVersion", "WorkOrderComponent", "WorkOrderOperation"), ("ProductionVersion", "WorkOrderComponent", "WorkOrderOperation")),
    _cross("WOC.OPERATION_NOT_IN_WO", "WorkOrderComponent", "Bileşenin operasyonu iş emrinde yok",
           "Operasyon no dolu, iş emrinin operasyonları var ve bu operasyon aralarında yok", WARNING, _woc_operation, "OperationNo",
           ("WorkOrderOperation",)),
    _cross("PO.SUPPLIER_NOT_LISTED", "PurchaseOrderLine", "Tedarikçi malzemenin tedarikçilerinde yok",
           "Fason olmayan siparişte tedarikçi bulunuyor ve bu malzemenin malzeme tedarikçisi kayıtlarında yok", INFO, _po_supplier, "SupplierCode",
           ("Supplier", "MaterialSupplier")),
)


@lru_cache(maxsize=1)
def catalog() -> tuple[RuleDef, ...]:
    """Bütün tabloların yapısal ve hazır kuralları, katalog sırasıyla."""
    out = []
    for entity in ENTITIES:
        out += common_rules(entity.table)
        out += [r for r in TABLE_RULES if r.table == entity.table]
        out += reference_rules(entity.table)
        out += [r for r in INTEGRITY_RULES if r.table == entity.table]
    return tuple(out)


def by_key() -> dict[tuple[str, str], RuleDef]:
    return {(r.table, r.code): r for r in catalog()}


def related_cross(entity: str) -> list[RuleDef]:
    """Tek tablo yüklemesinde yenilenecek tablolar arası kurallar: tablonun kendisi ya da okuduğu tablolardan biri."""
    return [r for r in catalog() if r.check_type == CROSS and (r.table == entity or entity in r.reads)]

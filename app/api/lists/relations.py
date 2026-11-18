"""İlişkili alanlar (K-182): satırın bağlı olduğu tek kaydın alanları listeye kolon olarak eklenir; veri kopyalanmaz, sorguda birleştirilir.

İlişkilerin tek kaynağı `REFS`: ilişki alanı (`…Id`) → hedef tablo. Liste tanımındaki kod kolonları (`MaterialCode`, `ResourceGroupCode`…) da
buradan üretilir (`master_data._build`). Yalnız tek karşılıklı ilişkiler vardır: hedefin Id'si güncel satırda tekildir (K-63). Zincir en çok
iki seviyedir. Alan adı yol + alandır: `ResourceGroupId/IsCritical`, `WorkOrderId/MaterialId/Name`.

Dışarıda (docs/00 K-182): çok karşılıklı ilişkiler; Lokasyon ikinci seviyede; Birim; Çalışma takvimi (listesi yok).
"""
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import sqlalchemy as sa

from db.models import metadata

from .definition import ListDefinition, columns

SEP = "/"
LABEL_SEP = " · "
MAX_FIELDS = 20   # bir istekte ilişkili alan
MAX_JOINS = 8     # bir istekte birleştirme (ilişki yolu)
MAX_DEPTH = 2
UNIT_PREFIX = "_unit" + SEP  # ilişkili miktar alanının birimi: "_unit/<yol>" (yalnız ondalık için; alan değildir)
RELATED_SOURCE = "rel"


def _code(a: sa.FromClause) -> sa.ColumnElement:
    return a.c.Code


# İlişki alanı → (hedef tablo, koda dönen kolonun adı, hedefte gösterilecek değer, o değerin hedefteki alanı)
REFS: dict[str, tuple[str, str, Callable, str | None]] = {
    "LocationId": ("Location", "LocationCode", _code, "Code"), "MaterialId": ("Material", "MaterialCode", _code, "Code"),
    "ComponentMaterialId": ("Material", "ComponentMaterialCode", _code, "Code"),
    "ReferenceMaterialId": ("Material", "ReferenceMaterialCode", _code, "Code"),
    "ReferenceProductionVersionId": ("ProductionVersion", "ReferenceProductionVersionCode", _code, "Code"),
    "ProductionVersionId": ("ProductionVersion", "ProductionVersionCode", _code, "Code"),
    "ResourceId": ("Resource", "ResourceCode", _code, "Code"), "ResourceGroupId": ("ResourceGroup", "ResourceGroupCode", _code, "Code"),
    "SupplierId": ("Supplier", "SupplierCode", _code, "Code"), "SubcontractorId": ("Supplier", "SubcontractorCode", _code, "Code"),
    "CalendarId": ("Calendar", "CalendarCode", _code, "Code"), "ProjectGroupId": ("ProjectGroup", "ProjectGroupCode", _code, "Code"),
    "CustomerId": ("Customer", "CustomerCode", _code, "Code"), "ProjectId": ("Project", "ProjectCode", _code, "Code"),
    "LendingProjectId": ("Project", "LendingProjectCode", _code, "Code"), "BorrowingProjectId": ("Project", "BorrowingProjectCode", _code, "Code"),
    "WorkOrderId": ("WorkOrder", "WorkOrderCode", lambda a: a.c.WorkOrderNo, "WorkOrderNo"),
    "ParentWorkOrderId": ("WorkOrder", "ParentWorkOrderCode", lambda a: a.c.WorkOrderNo, "WorkOrderNo"),
    "SalesOrderLineId": ("SalesOrderLine", "SalesOrderLineCode",  # "sipariş no / satır no" (K-169); tek alan değil
                         lambda a: sa.case((a.c.Id.is_(None), None), else_=sa.func.concat(a.c.OrderNo, " / ", sa.cast(a.c.LineNo, sa.Unicode(10)))), None),
}
SECOND_LEVEL_SKIP = frozenset({"LocationId"})  # Lokasyon her tabloda birinci seviyede var


class RelatedLimitError(ValueError):
    """İlişkili alan ya da birleştirme sınırı aşıldı (422)."""


@dataclass(frozen=True)
class Relation:
    column: str   # ilişki alanı (satırdaki …Id)
    target: str   # hedef tablo (core)
    label: str    # ilişkinin adı: ilişki alanının etiketi


@dataclass(frozen=True)
class Resolved:
    name: str                  # tam alan adı (yol + alan)
    path: tuple[str, ...]      # ilişki alanları
    field: str                 # hedefteki alan
    column: dict               # kolon bilgisi (columns biçimi)
    unit: bool                 # ondalık hedef kaydın biriminden


Labels = Callable[[str], dict[str, str]]
NO_LABELS: Labels = lambda _table: {}  # noqa: E731


def is_related(name: str) -> bool:
    return isinstance(name, str) and SEP in name and not name.startswith(UNIT_PREFIX)


def scan(value) -> list[str]:
    """Bir istek gövdesindeki ilişkili alan adayları: `/` içeren bütün metinler ve anahtarlar (sırayla, tekrarsız). Geçersizler çözülürken
    elenir; süzgeç değeri olarak yazılmış bir metin yalnız geçerli bir alan adıysa (pratikte olmaz) fazladan birleştirme ekler."""
    found: dict[str, None] = {}

    def walk(v):
        if isinstance(v, str):
            if is_related(v):
                found.setdefault(v)
        elif isinstance(v, dict):
            for k, x in v.items():
                walk(k)
                walk(x)
        elif isinstance(v, (list, tuple, set, frozenset)):
            for x in v:
                walk(x)
    walk(value)
    return list(found)


def _definition(table: str) -> ListDefinition | None:
    """Hedef tablonun kendi listesi (alanları, etiketleri, ondalıkları oradan)."""
    from .master_data import BY_TABLE  # döngüsel içe aktarma: liste tanımları bu modülü kullanır
    return BY_TABLE.get(table)


def core(table: str) -> sa.Table:
    return metadata.tables[f"core.{table}"]


def relations_of(table: str, labels: Labels = NO_LABELS, level: int = 1) -> list[Relation]:
    """Tablonun tek karşılıklı ilişkileri (ilişki alanı sırasıyla). Hedefinin listesi olmayan (takvim) ve ikinci seviyede Lokasyon yoktur."""
    if f"core.{table}" not in metadata.tables:
        return []
    own = labels(table)
    out = []
    for c in core(table).c:
        if c.name not in REFS or (level > 1 and c.name in SECOND_LEVEL_SKIP):
            continue
        target = REFS[c.name][0]
        if _definition(target) is None:
            continue
        out.append(Relation(c.name, target, own.get(c.name) or (c.info or {}).get("label") or c.name))
    return out


def _fields(relation: Relation, labels: Labels, level: int) -> dict[str, dict]:
    """İlişkinin sunduğu alanlar: hedef listenin alanlarından hedef tablonun kendi kolonu olanlar ("Manuel değer" ve ilişki kodları hariç);
    birinci seviyede tabloda zaten kolon olan kod da hariç."""
    defn = _definition(relation.target)
    table = core(relation.target)
    shown = REFS[relation.column][3] if level == 1 else None
    out = {}
    for c in columns(defn, labels(relation.target)):
        if c["field"] in table.c and c["field"] != shown:
            out[c["field"]] = c
    return out


def _walk(defn: ListDefinition, path: tuple[str, ...], labels: Labels) -> list[Relation] | None:
    """Yolun ilişkileri; yol tanımsızsa None."""
    if not defn.related_table or not 1 <= len(path) <= MAX_DEPTH:
        return None
    table, out = defn.related_table, []
    for level, column in enumerate(path, 1):
        rel = next((r for r in relations_of(table, labels, level) if r.column == column), None)
        if rel is None:
            return None
        out.append(rel)
        table = rel.target
    return out


def _column(rels: list[Relation], name: str, base: dict) -> dict:
    """label: tam yol (panel, Excel, ipucu). short_label: iki seviyede yalnız son ilişki ve alan (tablo başlığı; K-182 demo kararı)."""
    out = {**base, "field": name, "label": LABEL_SEP.join([*(r.label for r in rels), base["label"]]), "default_visible": False,
           "manual": False, "related": True}
    if len(rels) > 1:
        out["short_label"] = LABEL_SEP.join([rels[-1].label, base["label"]])
    return out


def resolve(defn: ListDefinition, name: str, labels: Labels = NO_LABELS) -> Resolved | None:
    """Alan adını çözer; tanımsız yol ya da alan None."""
    if not is_related(name):
        return None
    *path, field = name.split(SEP)
    rels = _walk(defn, tuple(path), labels)
    if rels is None:
        return None
    base = _fields(rels[-1], labels, len(rels)).get(field)
    if base is None:
        return None
    return Resolved(name, tuple(path), field, _column(rels, name, base), bool(base["decimals_from_unit"]))


def headings(defn: ListDefinition, labels: Labels = NO_LABELS) -> list[dict]:
    """Birinci seviye başlıklar (kolonlar cevabındaki `relations`)."""
    if not defn.related_table:
        return []
    return [{"path": r.column, "label": r.label} for r in relations_of(defn.related_table, labels)]


def catalog(defn: ListDefinition, path: str, labels: Labels = NO_LABELS) -> dict | None:
    """Bir ilişkinin alanları ve alt ilişkileri; yol tanımsızsa None."""
    parts = tuple(path.split(SEP)) if path else ()
    rels = _walk(defn, parts, labels)
    if rels is None:
        return None
    fields = [_column(rels, SEP.join([*parts, f]), c) for f, c in _fields(rels[-1], labels, len(rels)).items()]
    below = [] if len(rels) >= MAX_DEPTH else [
        {"path": SEP.join([*parts, r.column]), "label": LABEL_SEP.join([*(x.label for x in rels), r.label])}
        for r in relations_of(rels[-1].target, labels, len(rels) + 1)]
    return {"path": path, "label": LABEL_SEP.join(r.label for r in rels), "fields": fields, "relations": below}


def _valid(t: sa.FromClause, version: int | None) -> sa.ColumnElement:
    """Hedef satır listenin okuduğu veri versiyonunda geçerli (versiyonsuz hedefte koşul yok)."""
    if "VersionTo" not in t.c:
        return sa.true()
    if version is None:
        return t.c.VersionTo.is_(None)
    return sa.and_(t.c.VersionFrom <= version, sa.or_(t.c.VersionTo.is_(None), t.c.VersionTo >= version))


def _unit(target: str, alias: sa.FromClause, version: int | None) -> sa.ColumnElement:
    """Hedef kaydın birimi (hedef listenin "ondalık birimden" kuralıyla aynı kaynak): kendi kolonu, ilişkisindeki birim ya da alt sorgu."""
    from .master_data import SPEC_BY_TABLE
    spec = SPEC_BY_TABLE.get(target)
    if spec is None:  # Malzeme: temel birim
        return alias.c[_definition(target).unit_field]
    if spec.unit_query:
        return spec.unit_query(alias)
    own = alias.c[spec.unit] if spec.unit else None
    if not spec.unit_ref:
        return own
    ref, unit_col = spec.unit_ref
    other = core(REFS[ref][0]).alias(f"u_{alias.name}")
    related = sa.select(other.c[unit_col]).where(other.c.Id == alias.c[ref], _valid(other, version)).correlate(alias).scalar_subquery()
    return related if own is None else sa.func.coalesce(own, related)


def _paths(found: list[Resolved]) -> list[tuple[str, ...]]:
    return sorted({r.path[:i] for r in found for i in range(1, len(r.path) + 1)}, key=lambda p: (len(p), p))


def _limit_problem(found: list[Resolved], paths: list[tuple[str, ...]]) -> str | None:
    if len(found) > MAX_FIELDS:
        return f"En çok {MAX_FIELDS} ilişkili alan seçilebilir"
    if len(paths) > MAX_JOINS:
        return f"En çok {MAX_JOINS} ilişki birleştirilebilir"
    return None


def limit_problem(defn: ListDefinition, names: Iterable[str], labels: Labels = NO_LABELS) -> str | None:
    """Bir görünümün ilişkili alanları sınırı aşıyor mu (kaydederken doğrulama)."""
    found = [r for r in (resolve(defn, n, labels) for n in dict.fromkeys(names)) if r is not None]
    return _limit_problem(found, _paths(found))


def wrap(defn: ListDefinition, table: sa.FromClause, version: int | None, names: Iterable[str],
         labels: Labels = NO_LABELS, limit: bool = True) -> tuple[sa.FromClause, dict[str, dict], dict[str, str]]:
    """Listenin kaynağını istenen ilişkili alanlarla genişletir: (kaynak, ilişkili kolon bilgileri, alan → birim kolonu).

    Yalnız adı geçen ilişkiler birleştirilir (LEFT JOIN; hedefin Id'si geçerli satırda tekil olduğundan satır sayısı değişmez). Tanımsız adlar
    atlanır (sorgu kurucu "Bilinmeyen alan" der). Sınır aşılırsa RelatedLimitError."""
    found = [r for r in (resolve(defn, n, labels) for n in dict.fromkeys(names)) if r is not None]
    if not found:
        return table, {}, {}
    paths = _paths(found)
    if limit:
        problem = _limit_problem(found, paths)
        if problem:
            raise RelatedLimitError(problem)
    aliases: dict[tuple[str, ...], sa.FromClause] = {}
    targets: dict[tuple[str, ...], str] = {}
    joined = table
    for i, path in enumerate(paths):
        parent = aliases[path[:-1]] if len(path) > 1 else table
        target = REFS[path[-1]][0]
        a = core(target).alias(f"rf{i}")
        aliases[path], targets[path] = a, target
        joined = joined.outerjoin(a, sa.and_(a.c.Id == parent.c[path[-1]], _valid(a, version)))
    cols, info, units = list(table.c), {}, {}
    for r in found:
        cols.append(aliases[r.path].c[r.field].label(r.name))
        info[r.name] = r.column
        if r.unit:
            units[r.name] = UNIT_PREFIX + SEP.join(r.path)
    for path in sorted({r.path for r in found if r.unit}):
        cols.append(_unit(targets[path], aliases[path], version).label(UNIT_PREFIX + SEP.join(path)))
    return sa.select(*cols).select_from(joined).subquery(RELATED_SOURCE), info, units

"""prc → core kolon eşlemesi (K-146, K-153): ad kuralı ve ilişki haritasından; test core şemasının bütün kolonlarını kapsadığını denetler.

Ad kuralı: aynı adlı kolon olduğu gibi; ilişki alanı `XxxCode` → `XxxId`, `LocationCode` → `LocationId`, `WorkOrderNo` → `WorkOrderId`,
`ParentWorkOrderNo` → `ParentWorkOrderId`, bağlı sipariş üçlüsü (`SalesOrderNo` …) → `SalesOrderLineId`. Core'da Id karşılığı olmayan ilişki
(Üretim versiyonunun ağaç ve rota kodu) kod olarak kalır, aktarımda çözülmez (bütünlüğü validasyon denetler).
"""
from dataclasses import dataclass
from functools import lru_cache

import sqlalchemy as sa

from app.integration import references as refs
from app.integration.contract import ENTITIES
from app.integration.structural import key_fields
from db.models import metadata

SYSTEM = ("Id", "VersionFrom", "VersionTo", "ImportBatchId", "BusinessKey", "UpdatedAt")
# Smartchain'de tanımlanan alanlar (K-117): yeni versiyona önceki versiyondan kopyalanır, aktarım ezmez
PRESERVED: dict[str, tuple[str, ...]] = {
    "Resource": ("DailyCapacity", "Quantity", "CalendarId", "CapacitySource", "SubconPlanningType", "SubconFixedLeadTimeDays", "SubconVariableDaysPerUnit"),
}
# Ön hesap (fonksiyon 29) kolonları: aktarımda boş
PRECALC: dict[str, tuple[str, ...]] = {"WorkOrderComponent": ("RemainingQuantity",), "WorkOrderOperation": ("RemainingConsumption",)}
UNVERSIONED = {"Location"}  # core.Location versiyonsuz (Id IDENTITY)
LOCATION_ONLY = {"Location": ("IsSynthetic",)}  # sentetik veri işareti: aktarım eklediği satıra 0 yazar, var olana dokunmaz


def id_name(field: str) -> str:
    if field == "SalesOrderNo":
        return "SalesOrderLineId"
    if field.endswith("Code"):
        return field[:-4] + "Id"
    if field.endswith("No"):
        return field[:-2] + "Id"
    return field


@dataclass(frozen=True)
class RefColumn:
    column: str               # core kolonu (…Id)
    ref: refs.Reference

    @property
    def self_ref(self) -> bool:
        return self.ref.parent == self.ref.child


@dataclass(frozen=True)
class TableMap:
    entity: str
    core: sa.Table
    prc: sa.Table
    plain: tuple[str, ...]            # aynı adlı kolonlar
    refs: tuple[RefColumn, ...]       # ilişki kolonları (LocationId hariç)
    location: bool                    # LocationCode → LocationId
    preserved: tuple[str, ...]
    precalc: tuple[str, ...]
    key: tuple[str, ...]              # core'un güncel tekil anahtarı (kolon adları)
    business_key: tuple[str, ...]     # prc anahtar alanları (BusinessKey için)

    @property
    def compare(self) -> tuple[str, ...]:
        """"Değişti" karşılaştırmasının kolonları: iş kolonları (sistem, korunan ve ön hesap kolonları hariç)."""
        return self.plain + tuple(r.column for r in self.refs) + (("LocationId",) if self.location else ())

    def prc_to_core(self, field: str) -> str | None:
        """Kural izindeki alan adının core karşılığı (değerin kaynağı, K-148)."""
        if field in self.plain:
            return field
        if field == "LocationCode" and self.location:
            return "LocationId"
        for r in self.refs:
            if r.ref.fields[0] == field:
                return r.column
        return None


def _unique_key(table: sa.Table) -> tuple[str, ...]:
    for ix in table.indexes:
        if ix.unique and ix.name.startswith("UX_"):
            return tuple(c.name for c in ix.columns)
    raise LookupError(f"{table.fullname}: tekil güncel anahtar yok")


@lru_cache(maxsize=None)
def table_map(entity: str) -> TableMap:
    core, prc = metadata.tables[f"core.{entity}"], metadata.tables[f"prc.{entity}"]
    core_cols = {c.name for c in core.columns}
    prc_cols = {c.name for c in prc.columns}
    ref_cols = []
    for r in refs.of(entity):
        column = id_name(r.fields[0])
        if column in core_cols and column not in prc_cols:
            ref_cols.append(RefColumn(column, r))
    taken = set(SYSTEM) | {r.column for r in ref_cols} | set(PRESERVED.get(entity, ())) | set(PRECALC.get(entity, ())) | set(LOCATION_ONLY.get(entity, ()))
    location = "LocationId" in core_cols and "LocationCode" in prc_cols
    plain = tuple(c.name for c in core.columns if c.name not in taken and c.name != "LocationId" and c.name in prc_cols)
    try:
        key = _unique_key(core)
    except LookupError:
        key = ("Code",)
    return TableMap(entity, core, prc, plain, tuple(ref_cols), location, PRESERVED.get(entity, ()), PRECALC.get(entity, ()), key,
                    tuple(key_fields(entity)))


def unmapped(entity: str) -> list[str]:
    """Eşlemenin kapsamadığı core kolonları (test boş bekler)."""
    m = table_map(entity)
    known = set(SYSTEM) | set(m.plain) | {r.column for r in m.refs} | set(m.preserved) | set(m.precalc) | set(LOCATION_ONLY.get(entity, ()))
    if m.location:
        known.add("LocationId")
    return [c.name for c in m.core.columns if c.name not in known]


@lru_cache(maxsize=1)
def order() -> tuple[str, ...]:
    """Aktarım sırası: ilişki haritasına göre ebeveyn önce (lokasyon hepsinden önce); eşitlikte katalog sırası."""
    catalog = [e.table for e in ENTITIES]
    parents = {t: {r.parent for r in refs.of(t) if r.parent != t} for t in catalog}
    parents.update({t: parents[t] | {"Location"} for t in catalog if t != "Location"})
    done: list[str] = []
    while len(done) < len(catalog):
        ready = [t for t in catalog if t not in done and parents[t] <= set(done)]
        if not ready:
            raise RuntimeError(f"İlişki haritasında döngü: {sorted(set(catalog) - set(done))}")
        done.append(ready[0])
    return tuple(done)

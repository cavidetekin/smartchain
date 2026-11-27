"""Malzeme hareketlerinin tek tanımı (K-202): ana hareket → hareket türleri ve yön.

`planning.MaterialTransaction` ve `planning.Pegging` bu adları saklar; Parametreler › Pegging'in ölçütleri (`app/params/pegging.py`) tür adlarını
buradan alır. Talep türleri Hedefler'le aynı kaynaktandır (`catalog.DEMAND_TYPES`); ikinci bir liste yazılmaz. docs/02'deki değer listeleri bu
tanımla birebirdir (test).
"""
from app.params import catalog as cat

PLUS, MINUS = "+", "-"

STOCK, QUALITY_STOCK = "Stok", "Kalitedeki stok"
PURCHASE_ORDER, PURCHASE_PLAN = "Satın alma siparişi", "Satın alma planı"
PRODUCTION_ORDER, PRODUCTION_PLAN = "Üretim siparişi", "Üretim planı"
PRODUCTION_ORDER_NEED, PRODUCTION_PLAN_NEED = "Üretim siparişi ihtiyacı", "Üretim planı ihtiyacı"
ALLOCATION_TRANSFER = "Alokasyon transferi"

MAIN_STOCK, MAIN_PURCHASE, MAIN_PRODUCTION, MAIN_DEMAND, MAIN_PRODUCTION_NEED, MAIN_TRANSFER = "Stok", "Satın alma", "Üretim", "Talep", "Üretim ihtiyacı", "Transfer"

# ana hareket → hareket türleri (docs/02 `MaterialTransaction`)
MAIN: dict[str, tuple[str, ...]] = {
    MAIN_STOCK: (STOCK, QUALITY_STOCK),
    MAIN_PURCHASE: (PURCHASE_ORDER, PURCHASE_PLAN),
    MAIN_PRODUCTION: (PRODUCTION_ORDER, PRODUCTION_PLAN),
    MAIN_DEMAND: cat.DEMAND_TYPES,
    MAIN_PRODUCTION_NEED: (PRODUCTION_ORDER_NEED, PRODUCTION_PLAN_NEED),
    MAIN_TRANSFER: (ALLOCATION_TRANSFER,),
}
TYPES: tuple[str, ...] = tuple(t for types in MAIN.values() for t in types)
MAIN_OF: dict[str, str] = {t: main for main, types in MAIN.items() for t in types}
assert len(MAIN_OF) == len(TYPES), "hareket türü yinelendi"

# yön: arz + , ihtiyaç − ; transfer iki satırdır (genelden −, özele +)
SUPPLY_MAIN = (MAIN_STOCK, MAIN_PURCHASE, MAIN_PRODUCTION)
NEED_MAIN = (MAIN_DEMAND, MAIN_PRODUCTION_NEED)
SUPPLY_TYPES: tuple[str, ...] = tuple(t for m in SUPPLY_MAIN for t in MAIN[m])
NEED_TYPES: tuple[str, ...] = tuple(t for m in NEED_MAIN for t in MAIN[m])

# Tedarik planı (docs/02 `PlannedSupply`)
SUPPLY_PRODUCTION, SUPPLY_PURCHASE = "Üretim", "Satın alma"
SOURCE_PLAN, SOURCE_ORDER = "Plan", "Sipariş"
NUMBER_PREFIX = {SUPPLY_PRODUCTION: "ÜP", SUPPLY_PURCHASE: "SP"}


def supply_number(supply_type: str, seq: int) -> str:
    """Plan kaydının numarası: ÜP-000071, SP-000214 (plan hesabı içinde sıra; taşıma kuralı 8.11'de)."""
    return f"{NUMBER_PREFIX[supply_type]}-{seq:06d}"

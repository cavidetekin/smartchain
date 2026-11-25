"""Üretim akışı (K-200) için küçük yapı kümesi: sentetik veride örneği olmayan durumlar (aynı ağaçlı versiyonlar, pasif versiyon, alternatif grubu,
hayalet, versiyonlu benzetme, 20'den çok bileşen ve 20'den çok kullanan). Ayrı lokasyonda (`UA-1`) doğrudan ana tablolara yazılır.

Testler bir işlem içinde kurar ve geri alır; görsel kontrol test veritabanına kurar, bitince `remove` ile siler (K-172)."""
from sqlalchemy import text

LOC = "UA-1"
BASE = 8_500_000
WIDE, USERS = 25, 25

# kod: (ad, seviye, hayalet, birim)
MATERIALS = {
    "U-TOP": ("Üst ürün", "Nihai ürün", 0, "ADET"), "U-A": ("Alt montaj", "Yarı mamul", 0, "ADET"), "U-PH": ("Hayalet takım", "Yarı mamul", 1, "ADET"),
    "U-G1": ("Conta A", "Hammadde", 0, "ADET"), "U-G2": ("Conta B", "Hammadde", 0, "ADET"), "U-RAW": ("Çelik sac", "Hammadde", 0, "KG"),
    "U-X": ("Yalnız pasif versiyonda", "Hammadde", 0, "ADET"), "U-OLD": ("Yalnız eski satırda", "Hammadde", 0, "ADET"),
    "U-REF": ("Benzetilen ürün", "Nihai ürün", 0, "ADET"), "U-REF2": ("Versiyona benzetilen ürün", "Nihai ürün", 0, "ADET"),
    "U-WIDE": ("Geniş ürün", "Nihai ürün", 0, "ADET"), "U-BOLT": ("Cıvata M8", "Hammadde", 0, "ADET"),
    **{f"U-C{n:02d}": (f"Bileşen {n:02d}", "Hammadde", 0, "ADET") for n in range(1, WIDE + 1)},
    **{f"U-P{n:02d}": (f"Kullanan {n:02d}", "Yarı mamul", 0, "ADET") for n in range(1, USERS + 1)},
}
# (malzeme, versiyon, öncelik, aktif, ağaç kodu, taban miktar)
VERSIONS = [
    ("U-TOP", "V1", 1, 1, "B1", 1), ("U-TOP", "V2", 2, 1, "B2", 2), ("U-TOP", "V3", 3, 1, "B1", 1), ("U-TOP", "V9", 4, 0, "B9", 1),
    ("U-A", "V1", 1, 1, "BA", 1), ("U-PH", "V1", 1, 1, "BPH", 1), ("U-WIDE", "V1", 1, 1, "BW", 1),
    *[(f"U-P{n:02d}", "V1", 1, 1, f"BP{n:02d}", 1) for n in range(1, USERS + 1)],
]
# (üst, ağaç kodu, bileşen, operasyon, miktar, birim, grup, grup önceliği, güncel)
LINES = [
    ("U-TOP", "B1", "U-A", 10, 2, None, None, None, 1), ("U-TOP", "B1", "U-A", 20, 1, None, None, None, 1), ("U-TOP", "B1", "U-PH", 10, 1, None, None, None, 1),
    ("U-TOP", "B1", "U-G1", 10, 1, None, "G1", 1, 1), ("U-TOP", "B1", "U-G2", 10, 1, None, "G1", 2, 1), ("U-TOP", "B1", "U-TOP", 10, 1, None, None, None, 1),
    ("U-TOP", "B1", "U-OLD", 10, 1, None, None, None, 0),
    ("U-TOP", "B2", "U-A", 10, 4, None, None, None, 1), ("U-TOP", "B2", "U-RAW", 10, 1, "KG", None, None, 1),
    ("U-TOP", "B9", "U-X", 10, 1, None, None, None, 1),
    ("U-A", "BA", "U-RAW", 10, 1.5, None, None, None, 1), ("U-PH", "BPH", "U-RAW", 10, 1, None, None, None, 1),
    *[("U-WIDE", "BW", f"U-C{n:02d}", 10, n, None, None, None, 1) for n in range(1, WIDE + 1)],
    *[(f"U-P{n:02d}", f"BP{n:02d}", "U-BOLT", 10, n, None, None, None, 1) for n in range(1, USERS + 1)],
]
# (benzetilen, referans ürün, referans versiyon)
REFERENCES = [("U-REF", "U-TOP", None), ("U-REF2", "U-TOP", "V2")]


def _q(value) -> str:
    return "NULL" if value is None else f"N'{value}'" if isinstance(value, str) else str(value)


def _insert(conn, table: str, columns: str, rows: list[tuple]) -> None:
    for i in range(0, len(rows), 500):
        conn.execute(text(f"INSERT INTO {table} ({columns}) VALUES " + ", ".join("(" + ", ".join(_q(v) for v in row) + ")" for row in rows[i:i + 500])))


def build(conn) -> dict:
    """Kümeyi kurar; {kod: malzeme kimliği} ve "location" döner."""
    v = int(conn.execute(text("SELECT MAX(Id) FROM adm.DataVersion")).scalar())
    loc = conn.execute(text("INSERT INTO core.Location (Code, Name, IsActive, IsSynthetic) OUTPUT inserted.Id VALUES (:c, N'Üretim akışı', 1, 0)"), {"c": LOC}).scalar_one()
    ids = {code: BASE + n for n, code in enumerate(MATERIALS)}
    tail = "VersionFrom, BusinessKey, UpdatedAt"
    _insert(conn, "core.Material", f"Id, LocationId, Code, Name, MaterialLevel, IsPhantom, BaseUom, IsActive, {tail}",
            [(ids[c], loc, c, name, level, phantom, uom, 1, v, f"{LOC}|{c}", "2026-11-25") for c, (name, level, phantom, uom) in MATERIALS.items()])
    pv = {(m, code): BASE + 1000 + n for n, (m, code, *_rest) in enumerate(VERSIONS)}
    _insert(conn, "core.ProductionVersion", f"Id, LocationId, MaterialId, Code, Priority, IsActive, BOMCode, RouteCode, BaseQuantity, {tail}",
            [(pv[m, code], loc, ids[m], code, priority, on, bom, "R", base, v, f"{LOC}|{m}|{code}", "2026-11-25") for m, code, priority, on, bom, base in VERSIONS])
    _insert(conn, "core.BOM", f"Id, LocationId, MaterialId, Code, ComponentMaterialId, OperationNo, SequenceNo, Quantity, ComponentUom, AlternativeGroup, AlternativePriority, "
            f"VersionFrom, VersionTo, BusinessKey, UpdatedAt",
            [(BASE + 2000 + n, loc, ids[m], bom, ids[c], op, 1, qty, uom, group, gp, v if cur else v - 1, None if cur else v - 1, f"{LOC}|{m}|{bom}|{c}|{op}", "2026-11-25")
             for n, (m, bom, c, op, qty, uom, group, gp, cur) in enumerate(LINES)])
    _insert(conn, "core.MaterialReference", f"Id, LocationId, MaterialId, ReferenceMaterialId, ReferenceProductionVersionId, {tail}",
            [(BASE + 3000 + n, loc, ids[m], ids[ref], pv[ref, version] if version else None, v, f"{LOC}|{m}|{ref}", "2026-11-25") for n, (m, ref, version) in enumerate(REFERENCES)])
    return {**ids, "location": loc}


def remove(conn) -> None:
    """Kümeyi siler (görsel kontrolden sonra)."""
    loc = conn.execute(text("SELECT Id FROM core.Location WHERE Code = :c"), {"c": LOC}).scalar()
    if loc is None:
        return
    for table in ("BOM", "MaterialReference", "ProductionVersion", "Material"):
        conn.execute(text(f"DELETE FROM core.[{table}] WHERE LocationId = :l"), {"l": loc})
    conn.execute(text("DELETE FROM core.Location WHERE Id = :l"), {"l": loc})

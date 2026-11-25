"""Üretim akışı (K-200; ekran 03, fonksiyon 10): bir malzemenin yapısı seviye seviye. Yalnız yapı verisi (üretim versiyonu, ürün ağacı,
benzetilen ürün); plan, senaryo ve stok yok. Kenar tanımı `app/structure.py`.

Alternatif farklı ürün ağacı başınadır: aynı ağacı ve aynı taban miktarı kullanan versiyonlar birleşir. Miktar bir üst malzeme içindir
(`Quantity / BaseQuantity`); fire katılmaz. Aynı bileşenin satırları toplanır."""
import re
from collections import defaultdict
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app import structure as st

from ..errors import AppError
from ..repositories import export as export_repo

LIST, TITLE = "production-flow", "Üretim akışı"   # denetim izindeki nesne ve ad

# Kimlik listesi iki yolla geçer (ölçüm: docs/08). Kısa liste (tek kutu, bir sayfa) parametreyle: liste sabit boylara tamamlanır (ilk kimlik
# yinelenir), sorgu metni birkaç boyda sabit kalır ve planı bir kez derlenir. Uzun liste ("+N malzeme": 200 kutu) geçici tabloyla: 200 kimlik
# parametre olarak geçince tek malzeme okuması bile 500 ms sürüyordu.
SIZES = (1, 8, 32)
IDS = "/*ids*/"
TEMP = "(SELECT Id FROM #pf_ids)"

MATERIAL = ("SELECT m.Id, m.Code, m.Name, m.MaterialLevel, m.IsPhantom, m.BaseUom, m.LocationId, l.Code AS LocationCode "
            "FROM core.Material m JOIN core.Location l ON l.Id = m.LocationId WHERE m.VersionTo IS NULL AND m.Id IN " + IDS)

# Malzemenin ağaçları: kendi aktif versiyonları; yoksa benzetildiği ürününkiler (K-126). Owner: sorulan malzeme, TreeCode: ağacın sahibi malzemenin kodu
_LINE = ("pv.Code AS VersionCode, pv.Priority, pv.BOMCode, pv.BaseQuantity, b.ComponentMaterialId, b.Quantity, b.ComponentUom, b.AlternativeGroup, "
         "b.AlternativePriority, b.OperationNo, b.SequenceNo, c.BaseUom")
TREES = f"""
SELECT m.Id AS Owner, CAST(NULL AS nvarchar(50)) AS TreeCode, {_LINE}
FROM core.Material m
JOIN core.ProductionVersion pv ON pv.LocationId = m.LocationId AND pv.MaterialId = m.Id AND {st.active('pv')}
JOIN core.BOM b ON {st.bom_of('pv', 'b')}
JOIN core.Material c ON c.Id = b.ComponentMaterialId AND c.VersionTo IS NULL
WHERE m.VersionTo IS NULL AND m.Id IN {IDS} AND b.ComponentMaterialId <> b.MaterialId
UNION ALL
SELECT m.Id, t.Code, {_LINE}
FROM core.Material m
JOIN core.MaterialReference r ON r.MaterialId = m.Id AND r.VersionTo IS NULL
JOIN core.ProductionVersion pv ON {st.active('pv')} AND {st.reference_of('r', 'pv')}
JOIN core.Material t ON t.Id = pv.MaterialId AND t.VersionTo IS NULL
JOIN core.BOM b ON {st.bom_of('pv', 'b')}
JOIN core.Material c ON c.Id = b.ComponentMaterialId AND c.VersionTo IS NULL
WHERE m.VersionTo IS NULL AND m.Id IN {IDS} AND b.ComponentMaterialId <> b.MaterialId AND b.ComponentMaterialId <> m.Id AND NOT {st.has_own_version('m.Id', 'm.LocationId')}"""

# Kendine bağlanan satır (bileşen = ağacın malzemesi) hiçbir yerde kenar değildir.
# Malzemeyi kullananlar: ağacında geçtiği aktif versiyonların malzemeleri ve o ağaçlara benzetilen (kendi versiyonu olmayan) malzemeler
_USED = f"FROM core.BOM b JOIN core.ProductionVersion pv ON {st.bom_of('pv', 'b')} AND {st.active('pv')}"
PARENTS = f"""
SELECT p.Id, p.Code FROM (
    SELECT pv.MaterialId AS P {_USED} WHERE b.ComponentMaterialId = :id AND b.MaterialId <> :id
    UNION
    SELECT r.MaterialId {_USED}
    JOIN core.MaterialReference r ON r.VersionTo IS NULL AND {st.reference_of('r', 'pv')}
    WHERE b.ComponentMaterialId = :id AND b.MaterialId <> :id AND NOT {st.has_own_version('r.MaterialId', 'r.LocationId')}
) x JOIN core.Material p ON p.Id = x.P AND p.VersionTo IS NULL
WHERE x.P <> :id ORDER BY p.Code, p.Id"""

HAS_PARENTS = f"SELECT DISTINCT b.ComponentMaterialId AS Id {_USED} WHERE b.ComponentMaterialId IN {IDS} AND b.MaterialId <> b.ComponentMaterialId"
HAS_COMPONENTS = f"""
SELECT m.Id FROM core.Material m WHERE m.VersionTo IS NULL AND m.Id IN {IDS} AND (
    EXISTS (SELECT 1 FROM core.ProductionVersion pv JOIN core.BOM b ON {st.bom_of('pv', 'b')}
            WHERE pv.LocationId = m.LocationId AND pv.MaterialId = m.Id AND {st.active('pv')} AND b.ComponentMaterialId <> m.Id)
    OR (NOT {st.has_own_version('m.Id', 'm.LocationId')} AND EXISTS (
            SELECT 1 FROM core.MaterialReference r JOIN core.ProductionVersion pv ON {st.active('pv')} AND {st.reference_of('r', 'pv')}
            JOIN core.BOM b ON {st.bom_of('pv', 'b')}
            WHERE r.MaterialId = m.Id AND r.VersionTo IS NULL AND b.ComponentMaterialId <> m.Id AND b.ComponentMaterialId <> b.MaterialId)))"""


def _rows(session: Session, sql: str, ids) -> list:
    """Kimlik listesiyle sorgu: kısa liste parametreyle, uzun liste geçici tabloyla (yukarıdaki not)."""
    ids = list(dict.fromkeys(int(i) for i in ids))
    if not ids:
        return []
    if len(ids) <= SIZES[-1]:
        size = next(n for n in SIZES if n >= len(ids))
        stmt = sa.text(sql.replace(IDS, ":ids")).bindparams(sa.bindparam("ids", expanding=True))
        return session.execute(stmt, {"ids": ids + [ids[0]] * (size - len(ids))}).mappings().all()
    session.execute(sa.text("IF OBJECT_ID('tempdb..#pf_ids') IS NULL CREATE TABLE #pf_ids (Id bigint NOT NULL PRIMARY KEY) ELSE TRUNCATE TABLE #pf_ids"))
    for i in range(0, len(ids), 1000):
        session.execute(sa.text("INSERT INTO #pf_ids (Id) VALUES " + ", ".join(f"({n})" for n in ids[i:i + 1000])))   # tam sayılar; metin birleştirme güvenli
    # plan sabit: geçici tablonun satır sayısı değiştikçe sorgu yeniden derlenmesin
    return session.execute(sa.text(sql.replace(IDS, TEMP) + " OPTION (KEEPFIXED PLAN)")).mappings().all()


def _number(value: Decimal) -> float:
    return float(round(value, 6))


def _boxes(session: Session, ids) -> dict[int, dict]:
    """Malzeme kutuları: kod, ad, seviye, hayalet ve iki yönde açılacak bir şey olup olmadığı."""
    ids = list(dict.fromkeys(ids))
    up = {r["Id"] for r in _rows(session, HAS_PARENTS, ids)}
    down = {r["Id"] for r in _rows(session, HAS_COMPONENTS, ids)}
    return {r["Id"]: {"id": r["Id"], "code": r["Code"], "name": r["Name"], "level": r["MaterialLevel"], "phantom": bool(r["IsPhantom"]),
                      "has_parents": r["Id"] in up, "has_components": r["Id"] in down, "_location": r["LocationCode"]}
            for r in _rows(session, MATERIAL, ids)}


def _box(boxes: dict, material_id: int) -> dict:
    return {k: v for k, v in boxes[material_id].items() if not k.startswith("_")}


def _trees(session: Session, ids) -> dict[int, dict]:
    """Malzeme → {"reference": benzetilen ürünün kodu ya da None, "alternatives": [{no, versions, bom_code, items}]}.

    items: (bileşen kimliği, miktar, birim, grup, grup önceliği), ağaçtaki sırayla; aynı bileşenin satırları toplanır."""
    found: dict[int, dict] = defaultdict(lambda: {"reference": set(), "trees": {}})
    for r in _rows(session, TREES, ids):
        entry = found[r["Owner"]]
        if r["TreeCode"]:
            entry["reference"].add(r["TreeCode"])
        base = r["BaseQuantity"] or Decimal(1)
        tree = entry["trees"].setdefault((r["TreeCode"] or "", r["BOMCode"], base), {"versions": {}, "lines": {}})
        tree["versions"][r["VersionCode"]] = r["Priority"]
        # satır anahtarı versiyondan bağımsız: aynı ağacı kullanan ikinci versiyon aynı satırları yeniden getirir
        tree["lines"][(r["ComponentMaterialId"], r["OperationNo"], r["SequenceNo"])] = r
    out = {}
    for owner, entry in found.items():
        alternatives = []
        for (_, bom_code, base), tree in entry["trees"].items():
            versions = sorted(tree["versions"].items(), key=lambda v: (v[1] is None, v[1] or 0, v[0]))
            items: dict[tuple, dict] = {}
            for (component, operation, sequence), r in sorted(tree["lines"].items(), key=lambda x: (x[0][1] or 0, x[0][2] or 0, x[0][0])):
                key = (component, r["ComponentUom"] or r["BaseUom"], r["AlternativeGroup"], r["AlternativePriority"])
                item = items.setdefault(key, {"material": component, "quantity": Decimal(0), "uom": key[1], "group": key[2], "group_priority": key[3]})
                item["quantity"] += (r["Quantity"] or Decimal(0)) / base
            first = versions[0]
            alternatives.append({"_order": (first[1] is None, first[1] or 0, first[0], bom_code), "versions": [v[0] for v in versions], "bom_code": bom_code,
                                 "items": list(items.values())})
        alternatives.sort(key=lambda a: a.pop("_order"))
        for no, alternative in enumerate(alternatives, 1):
            alternative["no"] = no
        out[owner] = {"reference": ", ".join(sorted(entry["reference"])) or None, "alternatives": alternatives}
    return out


def _root(session: Session, material_id: int) -> dict:
    boxes = _boxes(session, [material_id])
    if material_id not in boxes:
        raise AppError("not_found", "Malzeme güncel veride bulunamadı.", 404)
    return boxes


def read(session: Session, material_id: int) -> dict:
    """Seçili malzemenin kutusu."""
    boxes = _root(session, material_id)
    reference = _trees(session, [material_id]).get(material_id, {}).get("reference")   # benzetilen ürün: başlığın altındaki not (K-200)
    return {"material": _box(boxes, material_id), "location": boxes[material_id]["_location"], "reference": {"code": reference} if reference else None}


def export_log(session: Session, user_id: int, material_id: int) -> dict:
    """Çizimin PNG olarak indirilmesi (K-200): görsel tarayıcıda üretilir; burada yalnız iz yazılır ve dosya adı verilir (grafik görseli gibi, K-179).
    İz yazılamazsa ad dönmez, dosya inmez (K-108)."""
    boxes = _root(session, material_id)
    code = boxes[material_id]["code"]
    file_name = f"uretim-akisi-{re.sub(r'[^0-9A-Za-zÇĞİÖŞÜçğıöşü._-]+', '-', code).strip('-') or material_id}.png"
    export_repo.write_audit(session, user_id, LIST, file_name, {"list": LIST, "title": TITLE, "material": code, "location": boxes[material_id]["_location"],
                                                                "format": "png", "background": False, "job_id": None})
    session.commit()
    return {"file_name": file_name}


def components(session: Session, material_id: int) -> dict:
    """Malzemenin kullandıkları: alternatifleri ve bileşenleri (bir seviye)."""
    _root(session, material_id)
    tree = _trees(session, [material_id]).get(material_id, {"reference": None, "alternatives": []})
    boxes = _boxes(session, [i["material"] for a in tree["alternatives"] for i in a["items"]])
    alternatives = [{"no": a["no"], "versions": a["versions"], "bom_code": a["bom_code"],
                     "items": [{**i, "material": _box(boxes, i["material"]), "quantity": _number(i["quantity"])} for i in a["items"] if i["material"] in boxes]}
                    for a in tree["alternatives"]]
    return {"reference": {"code": tree["reference"]} if tree["reference"] else None, "alternatives": alternatives}


def parents(session: Session, material_id: int, offset: int, limit: int) -> dict:
    """Malzemeyi kullananlar (bir seviye), koda göre sıralı ve sayfalı; her üst malzemede hangi alternatifinde, ne kadar kullanıldığı."""
    _root(session, material_id)
    everyone = [r[0] for r in session.execute(sa.text(PARENTS), {"id": material_id})]
    page = everyone[offset:offset + limit]
    boxes = _boxes(session, page)
    trees = _trees(session, page)
    items = []
    for parent in page:
        alternatives = trees.get(parent, {"alternatives": []})["alternatives"]
        uses = [{"alternative": a["no"], "quantity": _number(i["quantity"]), "uom": i["uom"], "group": i["group"]}
                for a in alternatives for i in a["items"] if i["material"] == material_id]
        if parent in boxes:
            items.append({"material": _box(boxes, parent), "alternatives": len(alternatives), "uses": uses})
    return {"total": len(everyone), "items": items}

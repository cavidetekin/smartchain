"""Alokasyon kuralı (K-199; `core.MaterialAllocationRule`): plandaki sayılı örnek, kenar durumları, versiyon ve fark, sentetik veri, liste ve kart.

Satırlar ham katmana yazılır, işlenmiş katman kurulur; aktarım commit edilmez (test veritabanının sentetik verisi değişmez)."""
from collections import defaultdict

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.allocation import rules
from app.api.deps import COOKIE
from app.api.lists import relations
from app.api.lists.definition import columns
from app.api.lists.master_data import BY_NAME, MASTER_TABS
from app.api.main import create_app
from app.data.synthetic import dataset as d
from app.manual import not_manual_reason
from app.transfer import engine as transfer
from db.models import metadata

from auth_helpers import token
from test_transfer import by_entity, set_prc
from test_validation_references import put
from validation_helpers import clean

pytestmark = pytest.mark.db

LOC = "AR-1"
OWN, BELOW = rules.OWN, rules.BELOW
ALLOCATED = {"P1", "H1", "H2", "H4", "H5", "H6", "H7", "Z2"}
MATERIALS = ["M", "A1", "A2", "P1", "H1", "H2", "H3", "M2", "PH", "H4", "F1", "H5", "K1", "K2", "H6", "H7", "Z1", "Z2"]
# üst → (ağaç kodu, bileşenler); M iki versiyonlu (alternatif)
TREES = [("M", "B-M-1", ["A1", "H3"]), ("M", "B-M-2", ["A2"]), ("A1", "B-A1", ["P1"]), ("P1", "B-P1", ["H1"]), ("A2", "B-A2", ["H2"]),
         ("M2", "B-M2", ["PH"]), ("PH", "B-PH", ["H4"]), ("F1", "B-F1", ["H5"]), ("K1", "B-K1", ["H6"]), ("K2", "B-K2", ["H6"]),
         ("Z1", "B-Z1", ["Z2"]), ("Z2", "B-Z2", ["Z1"])]   # Z1 ↔ Z2: döngü


def mat(code):
    return {"LocationCode": LOC, "Code": f"AR-{code}", "Name": f"Ad {code}", "BaseUom": "ADET", "IsActive": 1, "DefaultSupplyType": "Satın alma",
            "IsCustomAllocated": int(code in ALLOCATED), "IsPhantom": int(code == "PH")}


def so(order, line, material, customer, project=None, **extra):
    return {"LocationCode": LOC, "OrderNo": order, "LineNo": line, "LineItemNo": 0, "CustomerCode": customer, "ProjectCode": project, "MaterialCode": f"AR-{material}",
            "OpenQuantity": 5, "IsActive": 1, "RequestedDate": "2026-12-01", "OrderedQuantity": 5, "DeliveredQuantity": 0, "IsOnHold": 0, "IsQuote": 0, **extra}


def stock(lot, material, quantity=1, **owner):
    return {"LocationCode": LOC, "Warehouse": "ANA", "Uom": "ADET", "IsAvailable": 1, "IsInQuality": 0, "IsBlocked": 0, "IsActive": 1, "MaterialCode": f"AR-{material}",
            "Quantity": quantity, "LotNo": lot, **owner}


WO = {"LocationCode": LOC, "OpenQuantity": 1, "OrderedQuantity": 1, "CompletedQuantity": 0, "StartDate": "2026-12-01", "DueDate": "2026-12-10", "IsProduction": 1,
      "IsSubcontract": 0, "IsRework": 0, "IsReleased": 1, "IsOnHold": 0}
PO = {"LocationCode": LOC, "LineNo": 1, "OpenQuantity": 1, "OrderedQuantity": 1, "IsActive": 1, "IsPurchase": 1, "IsPurchaseRequest": 0, "IsSubcontract": 0}
DATA = {
    "Location": [{"Code": LOC, "Name": "Alokasyon kuralı", "IsFactory": 1, "IsActive": 1}],
    "Material": [mat(c) for c in MATERIALS],
    "Customer": [{"Code": c, "Name": c, "IsActive": 1} for c in ("ARC-1", "ARC-2", "ARC-3", "ARC-4")],
    "Project": [{"Code": c, "Name": c, "IsActive": 1} for c in ("ARP-1", "ARP-2")],
    "ProductionVersion": [{"LocationCode": LOC, "MaterialCode": f"AR-{m}", "Code": f"V{1 + [t[1] for t in TREES if t[0] == m].index(code)}", "BOMCode": code,
                           "RouteCode": f"R-{m}", "IsActive": 1} for m, code, _ in TREES],
    "BOM": [{"LocationCode": LOC, "MaterialCode": f"AR-{m}", "Code": code, "ComponentMaterialCode": f"AR-{c}", "OperationNo": 10, "SequenceNo": 1, "Quantity": 1}
            for m, code, comps in TREES for c in comps],
    "SalesOrderLine": [so("ARS-1", 10, "M", "ARC-1", "ARP-1"), so("ARS-2", 10, "M", "ARC-2"), so("ARS-3", 10, "M2", "ARC-1"),
                       so("ARS-4", 10, "K1", "ARC-3"), so("ARS-4", 20, "K2", "ARC-3"), so("ARS-5", 10, "Z1", "ARC-4"),
                       so("ARS-6", 10, "M", "ARC-3", OpenQuantity=0)],                                         # açık miktarı 0: talep sayılmaz
    "Forecast": [{"LocationCode": LOC, "MaterialCode": "AR-F1", "ProjectCode": "ARP-2", "Period": "2020-01-01", "Type": "T", "Quantity": 5, "IsActive": 1}],  # dönemi geçmiş de sayılır
    "Stock": [
        stock("S1", "H1", ProjectCode="ARP-1"),                              # örnek: H1'de projeye ayrılmış stok
        stock("S2", "H2", 0, ProjectCode="ARP-1"),                           # miktarı 0: kural üretmez
        stock("S3", "H1", CustomerCode="ARC-YOK"),                           # sahibi bulunamayan: satır açmaz
        stock("S4", "H3", ProjectCode="ARP-1"),                              # malzeme özel alokasyonlu değil: anahtar yok
        stock("S5", "H4", CustomerCode="ARC-1"),                             # hayaletin altında
        stock("S6", "H5", ProjectCode="ARP-2"),                              # tahminin projesi
        stock("S7", "H6", SalesOrderNo="ARS-4"),                             # kalemsiz: siparişin bütün satırları
        stock("S8", "H6", SalesOrderNo="ARS-4", SalesOrderLineNo=10, SalesOrderLineItemNo=0),   # kalemli: yalnız kendi satırı
        stock("S9", "Z2", CustomerCode="ARC-4"),                             # döngü
        stock("S10", "H2", CustomerCode="ARC-3"),                            # ARC-3'ün M talebi açık değil (ARS-6): satır açmaz
    ],
    "WorkOrder": [{**WO, "WorkOrderNo": "ARW-1", "MaterialCode": "AR-P1", "SalesOrderNo": "ARS-1", "SalesOrderLineNo": 10, "SalesOrderLineItemNo": 0},   # örnek: P1'de siparişe ayrılmış
                  {**WO, "WorkOrderNo": "ARW-2", "MaterialCode": "AR-A2"}],                                                                              # bileşeni ağaçtan farklı
    "WorkOrderComponent": [{"LocationCode": LOC, "WorkOrderNo": "ARW-2", "MaterialCode": "AR-H7", "OperationNo": 10, "SequenceNo": 1, "RequiredQuantity": 1}],
    "PurchaseOrderLine": [{**PO, "PurchaseOrderNo": "ARO-1", "MaterialCode": "AR-H2", "CustomerCode": "ARC-2"},     # örnek: H2'de müşteriye ayrılmış
                          {**PO, "PurchaseOrderNo": "ARO-2", "MaterialCode": "AR-H7", "CustomerCode": "ARC-2"}],    # üretim siparişi bileşeninde
}
S, P, C = "Sipariş", "Proje", "Müşteri"
EXPECTED = {
    # plandaki sayılı örnek (H7 üretim siparişi bileşeni olarak A2'nin altına eklendi: Müşteri / ARC-2'nin iki kaynağı var)
    ("H1", P, "ARP-1"): (OWN, None), ("P1", S, "ARS-1|10|0"): (OWN, None), ("P1", P, "ARP-1"): (BELOW, "AR-H1"),
    ("A1", S, "ARS-1|10|0"): (BELOW, "AR-P1"), ("A1", P, "ARP-1"): (BELOW, "AR-H1"),
    ("M", S, "ARS-1|10|0"): (BELOW, "AR-P1"), ("M", P, "ARP-1"): (BELOW, "AR-H1"), ("M", C, "ARC-2"): (BELOW, "AR-H2 +1"),
    ("A2", C, "ARC-2"): (BELOW, "AR-H2 +1"), ("H2", C, "ARC-2"): (OWN, None), ("H7", C, "ARC-2"): (OWN, None),
    # hayalet: içinden geçilir, kendisine satır açılmaz
    ("H4", C, "ARC-1"): (OWN, None), ("M2", C, "ARC-1"): (BELOW, "AR-H4"),
    # tahmin: proje
    ("H5", P, "ARP-2"): (OWN, None), ("F1", P, "ARP-2"): (BELOW, "AR-H5"),
    # kalemsiz anahtar iki satırın ağacında; kalemli yalnız kendi satırında
    ("H6", S, "ARS-4"): (OWN, None), ("K1", S, "ARS-4"): (BELOW, "AR-H6"), ("K2", S, "ARS-4"): (BELOW, "AR-H6"),
    ("H6", S, "ARS-4|10|0"): (OWN, None), ("K1", S, "ARS-4|10|0"): (BELOW, "AR-H6"),
    # döngü
    ("Z2", C, "ARC-4"): (OWN, None), ("Z1", C, "ARC-4"): (BELOW, "AR-Z2"),
}


@pytest.fixture(scope="module")
def staged(db_engine):
    clean(db_engine)
    put(db_engine, DATA)
    yield db_engine
    clean(db_engine)


@pytest.fixture
def s(staged):
    with Session(staged) as session:
        yield session
        session.rollback()


ROWS = ("SELECT m.Code, r.AllocationLevel, r.AllocationKey, r.Reason, r.SourceMaterials, r.Id, r.VersionFrom, r.VersionTo, r.BusinessKey "
        "FROM core.MaterialAllocationRule r JOIN core.Location l ON l.Id = r.LocationId JOIN core.Material m ON m.Id = r.MaterialId AND m.VersionTo IS NULL "
        "WHERE l.Code = :l")


def found(s, current: bool = True) -> dict:
    rows = s.execute(sa.text(ROWS + (" AND r.VersionTo IS NULL" if current else "")), {"l": LOC}).mappings().all()
    return {(r["Code"][3:], r["AllocationLevel"], r["AllocationKey"]): dict(r) for r in rows} if current else [dict(r) for r in rows]


def shape(rows: dict) -> dict:
    return {k: (r["Reason"], r["SourceMaterials"]) for k, r in rows.items()}


def changes(s, version: int) -> list[tuple]:
    """Bu testin lokasyonundaki kuralların Geçmiş kayıtları (aktarım, sentetik lokasyonun kurallarını da kapatır: orada talep kalmaz)."""
    return [tuple(r) for r in s.execute(sa.text(
        "SELECT f.RecordKey, f.ChangeType, f.FieldName, f.OldValue, f.NewValue FROM adm.FieldChange f WHERE f.TableName = N'MaterialAllocationRule' AND f.DataVersionId = :v "
        "AND f.RecordKey IN (SELECT CAST(r.Id AS nvarchar(60)) FROM core.MaterialAllocationRule r JOIN core.Location l ON l.Id = r.LocationId WHERE l.Code = :l) "
        "ORDER BY f.ChangeType, f.RecordKey, f.FieldName"), {"v": version, "l": LOC})]


def test_example_and_edge_cases(s):
    """Plandaki örnek ve kenar durumları: yalnız talebin ağacında, anahtarlı açık arza inen yol üzerindeki malzemelerde satır."""
    r = transfer.run_transfer(s, None)
    rows = found(s)
    assert shape(rows) == EXPECTED
    assert all(x["VersionFrom"] == r["data_version"] and x["VersionTo"] is None for x in rows.values())
    assert rows["M", C, "ARC-2"]["BusinessKey"] == f"{LOC}|AR-M|Müşteri|ARC-2" and (OWN, BELOW) == ("Kendi arzı", "Alt seviye arzı")
    assert "MaterialAllocationRule" not in by_entity(r)                                                                          # aktarım raporunda görünmez
    assert [c[1] for c in changes(s, r["data_version"])] == ["Oluştu"] * len(EXPECTED)


def test_unchanged_transfer_keeps_rows_and_ids(s):
    first = transfer.run_transfer(s, None)["data_version"]
    before = found(s)
    second = transfer.run_transfer(s, None)["data_version"]
    after = found(s)
    assert {k: (v["Id"], v["VersionFrom"]) for k, v in after.items()} == {k: (v["Id"], first) for k, v in before.items()}
    assert changes(s, second) == []


def test_supply_that_goes_closes_rules_and_returns_with_the_same_id(s):
    """Kısmi aktarım (Stok): H1'deki proje stoğu kalktı → o anahtarın satırları yol boyunca kapanır; sipariş satırları kalır. Stok geri gelince kural
    aynı Id ile yeniden açılır (kimlik anahtara bağlı)."""
    transfer.run_transfer(s, None)
    before = found(s)
    project = [k for k in EXPECTED if k[1:] == (P, "ARP-1")]
    set_prc(s, "Stock", "LotNo = N'S1'", IsActive=0)
    v2 = transfer.run_transfer(s, None, groups=["Stok"])["data_version"]
    after = found(s)
    assert set(before) - set(after) == set(project) and ("M", S, "ARS-1|10|0") in after
    closed = {(x["Code"][3:], x["AllocationLevel"], x["AllocationKey"]): x for x in found(s, current=False) if x["VersionTo"] == v2 - 1}
    assert set(closed) == set(project)
    assert sorted(c[:2] for c in changes(s, v2)) == sorted((str(before[k]["Id"]), "Kapandı") for k in project)
    set_prc(s, "Stock", "LotNo = N'S1'", IsActive=1)
    v3 = transfer.run_transfer(s, None, groups=["Stok"])["data_version"]
    back = found(s)
    assert shape(back) == EXPECTED and {k: (back[k]["Id"], back[k]["VersionFrom"]) for k in project} == {k: (before[k]["Id"], v3) for k in project}


def test_source_change_opens_a_new_version(s):
    """Kısmi aktarım (Satın alma): H7'deki arz kalktı → M ve A2'nin kaynağı "AR-H2 +1" iken "AR-H2" olur; satır yeni versiyon açar, Geçmiş'e yazılır."""
    first = transfer.run_transfer(s, None)["data_version"]
    before = found(s)
    set_prc(s, "PurchaseOrderLine", "PurchaseOrderNo = N'ARO-2'", IsActive=0)
    v = transfer.run_transfer(s, None, groups=["Satın alma"])["data_version"]
    after = found(s)
    assert ("H7", C, "ARC-2") not in after
    for key in (("M", C, "ARC-2"), ("A2", C, "ARC-2")):
        assert (after[key]["SourceMaterials"], after[key]["Id"], after[key]["VersionFrom"]) == ("AR-H2", before[key]["Id"], v)
    assert after["H2", C, "ARC-2"]["VersionFrom"] == first                                   # değişmeyen satır yerinde
    assert (str(before["M", C, "ARC-2"]["Id"]), "Değişti", "SourceMaterials", "AR-H2 +1", "AR-H2") in changes(s, v)


def test_demand_that_goes_closes_rules(s):
    """Kısmi aktarım (Talep): ARS-2 kapandı → ARC-2'nin kullanacak talebi kalmadı; arz yerinde dursa da satırlar kapanır."""
    transfer.run_transfer(s, None)
    set_prc(s, "SalesOrderLine", "OrderNo = N'ARS-2'", IsActive=0)
    transfer.run_transfer(s, None, groups=["Talep"])
    assert shape(found(s)) == {k: v for k, v in EXPECTED.items() if k[1:] != (C, "ARC-2")}


def test_compute_without_sources_gives_the_same_rules(s):
    """Kaynak malzemesiz hesap (performans karşılaştırması) aynı satırları ve sebepleri verir."""
    transfer.run_transfer(s, None)
    try:
        rules.compute(s, sources=False)
        got = {(r[0][3:], r[1], r[2]): r[3] for r in s.execute(sa.text(
            "SELECT m.Code, r.L, r.K, r.Reason FROM #ar_rule r JOIN core.Material m ON m.Id = r.MaterialId AND m.VersionTo IS NULL "
            "JOIN core.Location l ON l.Id = r.LocationId WHERE l.Code = :l"), {"l": LOC})}
    finally:
        rules._drop(s)
    assert got == {k: v[0] for k, v in EXPECTED.items()}


# ------------------------------------------------------------------ sentetik veri (docs/11 durum 13)

def reference(ds) -> dict:
    """Bağımsız hesap (Python, kaba kuvvet): veri setinden kenarlar, arz ve talep anahtarları; her (talep, arz) çifti için yol üzerindeki malzemeler."""
    t = ds.tables
    code = {m["Id"]: m["Code"] for m in t["Material"]}
    allocated = {m["Id"] for m in t["Material"] if m["IsCustomAllocated"]}
    project = {p["Id"]: p["Code"] for p in t["Project"]}
    customer = {c["Id"]: c["Code"] for c in t["Customer"]}
    kids = defaultdict(set)
    bom_of = {(pv["MaterialId"], pv["BOMCode"]) for pv in t["ProductionVersion"] if pv["IsActive"]}
    for b in t["BOM"]:
        if (b["MaterialId"], b["Code"]) in bom_of:
            kids[b["MaterialId"]].add(b["ComponentMaterialId"])
    versioned = {pv["MaterialId"] for pv in t["ProductionVersion"] if pv["IsActive"]}
    for ref in t["MaterialReference"]:
        if ref["MaterialId"] not in versioned:
            kids[ref["MaterialId"]] |= kids[ref["ReferenceMaterialId"]]
    open_wo = {w["Id"]: w["MaterialId"] for w in t["WorkOrder"] if w["OpenQuantity"] > 0}
    for c in t["WorkOrderComponent"]:
        if c["WorkOrderId"] in open_wo and c["MaterialId"] != open_wo[c["WorkOrderId"]]:
            kids[open_wo[c["WorkOrderId"]]].add(c["MaterialId"])

    def below(m, seen=None):
        seen = {m} if seen is None else seen
        for k in kids[m]:
            if k not in seen:
                seen.add(k)
                below(k, seen)
        return seen

    supply = defaultdict(set)   # anahtar → arzın durduğu malzemeler
    for name, qty in (("Stock", "Quantity"), ("WorkOrder", "OpenQuantity"), ("PurchaseOrderLine", "OpenQuantity")):
        for r in t[name]:
            if r["MaterialId"] not in allocated or not r[qty] > 0:
                continue
            if r.get("SalesOrderNo"):
                key = (S, f"{r['SalesOrderNo']}|{r['SalesOrderLineNo']}|{r['SalesOrderLineItemNo'] or 0}" if r.get("SalesOrderLineNo") is not None else r["SalesOrderNo"])
            elif r.get("ProjectCode"):
                key = (P, r["ProjectCode"])
            elif r.get("CustomerCode"):
                key = (C, r["CustomerCode"])
            else:
                continue
            supply[key].add(r["MaterialId"])
    demand = defaultdict(set)   # anahtar → talep malzemeleri
    for o in t["SalesOrderLine"]:
        if o["IsActive"] and o["OpenQuantity"] > 0:
            keys = [(S, f"{o['OrderNo']}|{o['LineNo']}|{o['LineItemNo'] or 0}"), (S, o["OrderNo"]), (C, customer[o["CustomerId"]])]
            keys += [(P, project[o["ProjectId"]])] if o.get("ProjectId") else []
            for key in keys:
                demand[key].add(o["MaterialId"])
    for f in t["Forecast"]:
        if f.get("IsActive", True) and f["Quantity"] > 0:
            if f.get("ProjectId"):
                demand[P, project[f["ProjectId"]]].add(f["MaterialId"])
            if f.get("CustomerId"):
                demand[C, customer[f["CustomerId"]]].add(f["MaterialId"])
    out = {}
    for key, sources in supply.items():
        reach = set().union(*[below(m) for m in demand.get(key, ())]) if demand.get(key) else set()
        for m in reach:
            under = sorted(code[x] for x in sources if x in below(m) and x != m)
            if m in sources:
                out[(code[m], *key)] = (OWN, None)
            elif under:
                out[(code[m], *key)] = (BELOW, under[0] + (f" +{len(under) - 1}" if len(under) > 1 else ""))
    return out


def synthetic_rules(engine) -> dict:
    with engine.connect() as c:
        rows = c.execute(sa.text("SELECT m.Code, r.AllocationLevel, r.AllocationKey, r.Reason, r.SourceMaterials FROM core.MaterialAllocationRule r "
                                 "JOIN core.Location l ON l.Id = r.LocationId AND l.Code = :l JOIN core.Material m ON m.Id = r.MaterialId AND m.VersionTo IS NULL "
                                 "WHERE r.VersionTo IS NULL"), {"l": d.LOCATION_CODE}).all()
    return {(r[0], r[1], r[2]): (r[3], r[4]) for r in rows}


def test_synthetic_rules_match_an_independent_computation(db_engine):
    """Sentetik yükleme kuralları üretir; veritabanındaki hesap, veri setinden bağımsız yapılan hesapla aynıdır."""
    got = synthetic_rules(db_engine)
    assert got == reference(d.generate())


def test_synthetic_examples(db_engine):
    """docs/11 durum 13: çok seviye, alternatifli ağaç; talebi olmayan ve sahibi bulunamayan arz satır açmaz."""
    got = synthetic_rules(db_engine)
    for material in ("PRC-046", "ALT-017"):                                               # MAM-006 → ALT-017 → PRC-046 → HAM-008
        assert got[material, P, "PRJ-01"] == got[material, S, "SO-1020|1|0"] == (BELOW, d.DEEP_ALLOCATED), material
    assert got[d.DEEP_ALLOCATED, P, "PRJ-01"] == got[d.DEEP_ALLOCATED, S, "SO-1020|1|0"] == (OWN, None)
    assert got["MAM-006", P, "PRJ-01"] == got["MAM-006", S, "SO-1020|1|0"] == (OWN, None)   # kendi stoğu da var: sebep kendi arzı
    assert got[d.ALTERNATIVE_PARENT, C, d.ALTERNATIVE_CUSTOMER] == got["MAM-006", C, d.ALTERNATIVE_CUSTOMER] == (BELOW, d.ALTERNATIVE_ONLY)   # yalnız ikinci ağaçta
    assert got[d.ALLOCATED_RAW, S, "SO-1021"] == (OWN, None) and got["MAM-006", S, "SO-1021"] == (BELOW, d.ALLOCATED_RAW)   # kalemsiz arz
    keys = {k[1:] for k in got}
    assert not {(C, d.MISSING_CUSTOMER), (S, d.MISSING_ORDER), (P, d.MISSING_PROJECT), (P, "PRJ-02")} & keys   # kullanacak talep yok ya da sahip yok
    assert d.ALLOCATION_EMPTY not in {k[0] for k in got}


# ------------------------------------------------------------------ liste ve kart

LIST = "master-allocation-rule"


def test_list_definition():
    c = {x["field"]: x for x in columns(BY_NAME[LIST], {})}
    visible = [f for f, x in c.items() if x["default_visible"]]
    assert visible == ["LocationCode", "MaterialCode", "AllocationLevel", "AllocationKey", "Reason", "SourceMaterials"]
    assert [c[f]["label"] for f in visible] == ["Lokasyon", "Malzeme", "Alokasyon seviyesi", "Alokasyon anahtarı", "Sebep", "Kaynak malzeme"]
    assert not any(x["manual"] for x in c.values()) and "SourceMaterialCode" not in c and "SourceMaterialId" not in c
    heads = [r.column for r in relations.relations_of("MaterialAllocationRule")]   # kaynak birden çok malzeme olabilir: "Kaynak malzeme · …" ilişkili alanı yok
    assert heads == ["LocationId", "MaterialId"] and "SourceMaterialId" not in metadata.tables["core.MaterialAllocationRule"].c
    assert all(not_manual_reason("MaterialAllocationRule", f) for f in ("AllocationKey", "Reason", "SourceMaterials"))
    assert ("malzeme", ("materials", "master-material-reference", LIST)) in MASTER_TABS and BY_NAME[LIST].title == "Alokasyon kuralı"
    assert BY_NAME[LIST].function == 10 and c["Reason"]["values"] == [OWN, BELOW]


@pytest.fixture(scope="module")
def api(db_engine, test_users):
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.cookies.set(COOKIE, token(test_users[0]))
    return client


def test_list_rows_and_material_card(api, db_engine):
    r = api.post(f"/api/{LIST}/query", json={"fields": ["MaterialCode", "AllocationLevel", "AllocationKey", "Reason", "SourceMaterials"], "limit": 100})
    assert r.status_code == 200, r.text
    rows = {(x["MaterialCode"], x["AllocationLevel"], x["AllocationKey"]): (x["Reason"], x["SourceMaterials"]) for x in r.json()["rows"]}
    assert rows == synthetic_rules(db_engine)
    related = api.post(f"/api/{LIST}/query", json={"fields": ["MaterialCode", "MaterialId/Name", "SourceMaterials"], "limit": 5,
                                                   "filters": [{"field": "Reason", "op": "in", "values": [BELOW]}]})
    assert related.status_code == 200 and all(x["MaterialId/Name"] and x["SourceMaterials"] for x in related.json()["rows"]), related.text
    assert api.post(f"/api/{LIST}/query", json={"fields": ["MaterialCode", "SourceMaterialId/Name"], "limit": 5}).status_code == 422
    with db_engine.connect() as c:
        material = c.execute(sa.text("SELECT Id FROM core.Material WHERE Code = N'MAM-006' AND VersionTo IS NULL")).scalar_one()
        plain = c.execute(sa.text("SELECT Id FROM core.Material WHERE Code = N'MAM-001' AND VersionTo IS NULL")).scalar_one()
    card = {x["key"]: x for x in api.get(f"/api/records/materials/{material}").json()["relations"]}
    tab = card["allocation-rule"]
    assert (tab["label"], tab["list"]) == ("Alokasyon kuralı", LIST) and tab["count"] == sum(1 for k in rows if k[0] == "MAM-006") > 3
    assert "allocation-rule" in {x["key"] for x in api.get(f"/api/records/materials/{plain}").json()["relations"]}
    counts = api.get("/api/master-data/counts").json()
    assert LIST in str(counts)

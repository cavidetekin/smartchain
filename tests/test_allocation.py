"""Özel alokasyon (K-198): arz satırının seviyesi, anahtarı ve bayrağı; kalemsiz arz; aktarım sonunda yeniden hesap; manuel yasağı; veri kalitesi.

Satırlar ham katmana yazılır, işlenmiş katman kurulur; aktarım commit edilmez (test veritabanının sentetik verisi değişmez)."""
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app import allocation
from app.data.synthetic import dataset as d
from app.manual import RELATION_REASON, RULE_ONLY_REASON, SYSTEM_REASON, not_manual_reason
from app.quality import run as quality_run
from app.transfer import engine as transfer

from test_transfer import by_entity, core_rows, set_prc
from test_validation_references import put
from validation_helpers import clean

pytestmark = pytest.mark.db

LOC = "AL-1"


def mat(code, allocated):
    return {"LocationCode": LOC, "Code": code, "Name": f"Ad {code}", "BaseUom": "ADET", "IsActive": 1, "DefaultSupplyType": "Satın alma",
            "IsCustomAllocated": allocated}


def so(order, line, item, material="A-ALLOC"):
    return {"LocationCode": LOC, "OrderNo": order, "LineNo": line, "LineItemNo": item, "CustomerCode": "AC-1", "MaterialCode": material, "OpenQuantity": 5,
            "IsActive": 1, "RequestedDate": "2026-12-01", "OrderedQuantity": 5, "DeliveredQuantity": 0, "IsOnHold": 0, "IsQuote": 0}


def stock(lot, material="A-ALLOC", **owner):
    return {"LocationCode": LOC, "Warehouse": "ANA", "Uom": "ADET", "IsAvailable": 1, "IsInQuality": 0, "IsBlocked": 0, "IsActive": 1,
            "MaterialCode": material, "Quantity": 1, "LotNo": lot, **owner}


WO = {"LocationCode": LOC, "MaterialCode": "A-ALLOC", "OpenQuantity": 1, "OrderedQuantity": 1, "CompletedQuantity": 0, "StartDate": "2026-12-01",
      "DueDate": "2026-12-10", "IsProduction": 1, "IsSubcontract": 0, "IsRework": 0, "IsReleased": 1, "IsOnHold": 0}
PO = {"LocationCode": LOC, "LineNo": 1, "MaterialCode": "A-ALLOC", "OpenQuantity": 1, "OrderedQuantity": 1, "IsActive": 1, "IsPurchase": 1,
      "IsPurchaseRequest": 0, "IsSubcontract": 0}
DATA = {
    "Location": [{"Code": LOC, "Name": "Alokasyon", "IsFactory": 1, "IsActive": 1}],
    "Material": [mat("A-ALLOC", 1), mat("A-GEN", 0), mat("A-NULL", None)],
    "Customer": [{"Code": "AC-1", "Name": "Müşteri", "IsActive": 1}],
    "Project": [{"Code": "AP-1", "Name": "Proje", "IsActive": 1}],
    "SalesOrderLine": [so("AS-1", 10, 1), so("AS-1", 20, 0), so("AS-2", 10, 0)],
    "Stock": [
        stock("L1", SalesOrderNo="AS-1", SalesOrderLineNo=10, SalesOrderLineItemNo=1, ProjectCode="AP-1", CustomerCode="AC-1"),  # en detaylı: sipariş
        stock("L2", SalesOrderNo="AS-1", SalesOrderLineNo=20, SalesOrderLineItemNo=0),                                           # alt satır 0
        stock("L3", SalesOrderNo="AS-1", ProjectCode="AP-1"),                                                                    # kalemsiz
        stock("L3", SalesOrderNo="AS-2", ProjectCode="AP-1"),                                                                    # aynı lot, başka sipariş: çakışmaz
        stock("L4", ProjectCode="AP-1", CustomerCode="AC-1"),                                                                    # proje
        stock("L5", CustomerCode="AC-1"),                                                                                        # müşteri
        stock("L6"),                                                                                                             # sahipsiz
        stock("L7", "A-GEN", ProjectCode="AP-1"),                                                                                # malzeme özel alokasyonlu değil
        stock("L8", "A-NULL", CustomerCode="AC-1"),                                                                              # malzemede alan boş
        stock("L9", ProjectCode="AP-YOK"),                                                                                       # bulunamayan proje
        stock("L9", SalesOrderNo="AS-YOK", SalesOrderLineNo=5),                                                                  # bulunamayan sipariş satırı
    ],
    "WorkOrder": [{**WO, "WorkOrderNo": "AW-1", "SalesOrderNo": "AS-YOK", "SalesOrderLineNo": 1, "CustomerCode": "AC-1"},        # bulunamayan sipariş satırı
                  {**WO, "WorkOrderNo": "AW-2", "SalesOrderNo": "AS-YOK"},                                                       # bulunamayan kalemsiz sipariş
                  {**WO, "WorkOrderNo": "AW-3", "ProjectCode": "AP-1"}],
    "PurchaseOrderLine": [{**PO, "PurchaseOrderNo": "APO-1", "SalesOrderNo": "AS-1"},                                            # kalemsiz
                          {**PO, "PurchaseOrderNo": "APO-2", "CustomerCode": "AC-1"}],
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


def alloc(row) -> tuple:
    return row["IsCustomAllocated"], row["AllocationLevel"], row["AllocationKey"]


def stocks(s) -> dict:
    return {(r["LotNo"], r["SalesOrderNo"]): r for r in core_rows(s, "Stock", "LotNo LIKE N'L_' AND Warehouse = N'ANA' AND LocationId = (SELECT Id FROM core.Location WHERE Code = :l)", l=LOC)}


def test_level_and_key_come_from_the_most_detailed_owner(s):
    """4a–4g: sipariş → proje → müşteri; kalemli anahtar üç parça; kalemsiz arz yalnız sipariş no; malzeme Hayır ya da boşsa satır genel."""
    r = transfer.run_transfer(s, None)
    got = stocks(s)
    assert len(got) == 11 and by_entity(r)["Stock"]["new"] == 11 and by_entity(r)["Stock"]["not_transferred"] == 0
    assert alloc(got["L1", "AS-1"]) == (True, "Sipariş", "AS-1|10|1")
    assert alloc(got["L2", "AS-1"]) == (True, "Sipariş", "AS-1|20|0")
    assert alloc(got["L3", "AS-1"]) == (True, "Sipariş", "AS-1") and alloc(got["L3", "AS-2"]) == (True, "Sipariş", "AS-2")
    assert alloc(got["L4", None]) == (True, "Proje", "AP-1")
    assert alloc(got["L5", None]) == (True, "Müşteri", "AC-1")
    assert alloc(got["L6", None]) == alloc(got["L7", None]) == alloc(got["L8", None]) == (False, None, None)
    assert got["L7", None]["ProjectId"] is not None and got["L8", None]["CustomerId"] is not None       # sahip alanları dolu, satır yine genel
    assert LOC not in "".join(r["AllocationKey"] or "" for r in got.values())                              # lokasyon anahtara girmez
    assert r["allocation"] == {}                                                                             # yazılan satır zaten güncel


def test_whole_order_supply_is_not_linked_to_the_first_line(s):
    """Kalemsiz arz: bağlantı boş, sipariş no ERP'den geldiği gibi; kalemli arzda üç alan ve bağlantı dolu."""
    transfer.run_transfer(s, None)
    got = stocks(s)
    line = core_rows(s, "SalesOrderLine", "OrderNo = N'AS-1' AND [LineNo] = 10")[0]
    whole, linked = got["L3", "AS-1"], got["L1", "AS-1"]
    assert (whole["SalesOrderLineId"], whole["SalesOrderNo"], whole["SalesOrderLineNo"], whole["SalesOrderLineItemNo"]) == (None, "AS-1", None, None)
    assert (linked["SalesOrderLineId"], linked["SalesOrderNo"], linked["SalesOrderLineNo"], linked["SalesOrderLineItemNo"]) == (line["Id"], "AS-1", 10, 1)
    po = {r["PurchaseOrderNo"]: r for r in core_rows(s, "PurchaseOrderLine", "PurchaseOrderNo LIKE N'APO-%'")}
    assert po["APO-1"]["SalesOrderLineId"] is None and alloc(po["APO-1"]) == (True, "Sipariş", "AS-1")
    assert alloc(po["APO-2"]) == (True, "Müşteri", "AC-1")


def test_owner_that_is_not_found_keeps_its_key(s):
    """Sahibi sistemde bulunmayan ayrılmış arz genele düşmez, bir alt seviyeye de düşmez: anahtar ERP'nin yazdığı en detaylı sahipten; iç bağ boş."""
    transfer.run_transfer(s, None)
    got = stocks(s)
    assert alloc(got["L9", None]) == (True, "Proje", "AP-YOK") and (got["L9", None]["ProjectId"], got["L9", None]["ProjectCode"]) == (None, "AP-YOK")
    assert alloc(got["L9", "AS-YOK"]) == (True, "Sipariş", "AS-YOK|5|0") and got["L9", "AS-YOK"]["SalesOrderLineId"] is None
    wo = {r["WorkOrderNo"]: r for r in core_rows(s, "WorkOrder", "WorkOrderNo LIKE N'AW-%'")}
    assert wo["AW-1"]["SalesOrderLineId"] is None and alloc(wo["AW-1"]) == (True, "Sipariş", "AS-YOK|1|0")   # müşteriye düşmez
    assert alloc(wo["AW-2"]) == (True, "Sipariş", "AS-YOK")                                                    # kalemsiz, sipariş yok
    assert alloc(wo["AW-3"]) == (True, "Proje", "AP-1")


def test_owner_that_closes_later_keeps_its_key(s):
    """Müşteri sonradan kapandı: ona ayrılmış stok aynı anahtarla kalır (genele düşmez); iç bağ boşalır, ERP'nin yazdığı kod durur."""
    first = transfer.run_transfer(s, None)["data_version"]
    before = stocks(s)["L5", None]
    assert before["CustomerId"] is not None
    set_prc(s, "Customer", "Code = N'AC-1'", IsActive=0)
    r = transfer.run_transfer(s, None)
    assert not core_rows(s, "Customer", "Code = N'AC-1'")                       # müşteri kapandı
    after = stocks(s)["L5", None]
    assert alloc(after) == (True, "Müşteri", "AC-1") and (after["CustomerId"], after["CustomerCode"]) == (None, "AC-1")
    assert after["VersionFrom"] == r["data_version"] > first and r["allocation"] == {}   # yalnız iç bağ değişti; anahtar aynı


def test_unchanged_transfer_opens_no_version(s):
    first = transfer.run_transfer(s, None)["data_version"]
    r = transfer.run_transfer(s, None)
    assert by_entity(r)["Stock"]["changed"] == 0 and by_entity(r)["Stock"]["new"] == 0 and r["allocation"] == {}
    assert {x["VersionFrom"] for x in stocks(s).values()} == {first}


def test_material_change_refreshes_a_table_that_was_not_transferred(s):
    """Malzemenin alanı değişti, Stok bu aktarımda yazılmadı (veri gelmedi): satırlar yine yeniden hesaplanır, yeni versiyon açar, Geçmiş'e yazılır."""
    first = transfer.run_transfer(s, None)["data_version"]
    set_prc(s, "Material", "Code = N'A-ALLOC'", IsCustomAllocated=0)
    s.execute(sa.text("UPDATE stg.Stock SET IsCurrent = 0"))
    r = transfer.run_transfer(s, None)
    v, got = r["data_version"], stocks(s)
    assert r["allocation"]["Stock"] == 8 and by_entity(r)["Stock"]["new"] is None            # tablo aktarılmadı
    assert by_entity(r)["Stock"]["note"] == f"{transfer.NOTE_EMPTY} {transfer.ALLOCATION_NOTE.format(n=8)}"
    assert len(got) == 11 and all(alloc(x) == (False, None, None) for x in got.values())
    changed = [k for k, x in got.items() if x["VersionFrom"] == v]
    assert sorted(changed, key=str) == sorted([("L1", "AS-1"), ("L2", "AS-1"), ("L3", "AS-1"), ("L3", "AS-2"), ("L4", None), ("L5", None), ("L9", None), ("L9", "AS-YOK")], key=str)
    row = got["L4", None]
    old = core_rows(s, "Stock", "Id = :i AND VersionTo IS NOT NULL", current=False, i=row["Id"])
    assert [(x["VersionFrom"], x["VersionTo"], x["AllocationKey"]) for x in old] == [(first, v - 1, "AP-1")] and row["Quantity"] == old[0]["Quantity"]
    hist = s.execute(sa.text("SELECT FieldName, OldValue, NewValue FROM adm.FieldChange WHERE TableName = N'Stock' AND RecordKey = :k AND DataVersionId = :v "
                             "ORDER BY FieldName"), {"k": str(row["Id"]), "v": v}).all()
    assert [tuple(h) for h in hist] == [("AllocationKey", "AP-1", None), ("AllocationLevel", "Proje", None), ("IsCustomAllocated", "1", "0")]
    # üretim siparişi ve satın alma bu aktarımda yazıldı: değer aktarımın kendi hesabından, ayrıca yeniden hesap yok
    assert "WorkOrder" not in r["allocation"] and all(alloc(x) == (False, None, None) for x in core_rows(s, "WorkOrder", "WorkOrderNo LIKE N'AW-%'"))


def test_partial_transfer_keeps_supply_of_a_closed_order_line(s):
    """Kısmi aktarım (Talep): sipariş satırı kapandı; ona ayrılmış stok aktarılmadı ve anahtarını korur (genele ya da projeye düşmez, yeni versiyon açmaz)."""
    first = transfer.run_transfer(s, None)["data_version"]
    set_prc(s, "SalesOrderLine", "OrderNo = N'AS-1' AND [LineNo] = 10", IsActive=0)
    r = transfer.run_transfer(s, None, groups=["Talep"])
    got = stocks(s)
    assert not core_rows(s, "SalesOrderLine", "OrderNo = N'AS-1' AND [LineNo] = 10") and r["allocation"] == {} and "Stock" not in by_entity(r)
    assert alloc(got["L1", "AS-1"]) == (True, "Sipariş", "AS-1|10|1") and got["L1", "AS-1"]["VersionFrom"] == first


def test_fields_cannot_be_set_by_hand():
    """Malzemede alan kuraldır (yalnız ERP ya da veri kuralı); arz satırında sistem hesaplar; bağlı sipariş alanları ilişkidir."""
    assert not_manual_reason("Material", "IsCustomAllocated") == RULE_ONLY_REASON
    for table in allocation.TABLES:
        assert all(not_manual_reason(table, f) == SYSTEM_REASON for f in allocation.FIELDS), table
        assert all(not_manual_reason(table, f) is not None for f in ("ProjectCode", "CustomerCode", "SalesOrderNo", "SalesOrderLineNo", "SalesOrderLineItemNo")), table
        assert all(not_manual_reason(table, f) == SYSTEM_REASON for f in ("ProjectId", "CustomerId", "SalesOrderLineId")), table   # iç bağ
    assert not_manual_reason("WorkOrder", "SalesOrderNo") == RELATION_REASON


def test_synthetic_examples(db_engine):
    """docs/11: özel alokasyon örnekleri sentetik veride, aktarımdaki hesapla aynı işlevden."""
    with db_engine.connect() as c:
        stock_rows = c.execute(sa.text(
            "SELECT m.Code, s.Quantity, s.IsCustomAllocated, s.AllocationLevel, s.AllocationKey FROM core.Stock s JOIN core.Material m ON m.Id = s.MaterialId "
            "AND m.VersionTo IS NULL WHERE s.VersionTo IS NULL AND (s.ProjectCode IS NOT NULL OR s.CustomerCode IS NOT NULL OR s.SalesOrderNo IS NOT NULL)")).all()
        wo = dict((r[0], tuple(r[1:])) for r in c.execute(sa.text(
            "SELECT WorkOrderNo, IsCustomAllocated, AllocationLevel, AllocationKey FROM core.WorkOrder WHERE VersionTo IS NULL AND WorkOrderNo IN (N'WO-5001', N'WO-5013')")))
        po = dict((r[0], tuple(r[1:])) for r in c.execute(sa.text(
            "SELECT PurchaseOrderNo, SalesOrderLineId, AllocationLevel, AllocationKey FROM core.PurchaseOrderLine WHERE VersionTo IS NULL AND IsCustomAllocated = 1 "
            "AND SalesOrderLineId IS NULL")))
        deep = tuple(c.execute(sa.text("SELECT AllocationLevel, AllocationKey FROM core.PurchaseOrderLine WHERE VersionTo IS NULL AND PurchaseOrderNo = :n "
                                       "AND SalesOrderLineId IS NOT NULL"), {"n": d.DEEP_ORDER_PO}).one())
        stale = sum(c.execute(sa.text(f"SELECT COUNT(*) FROM core.[{t}] WHERE VersionTo IS NULL AND IsCustomAllocated IS NULL")).scalar() for t in allocation.TABLES)
    assert sorted((m, float(q), f, lv, k) for m, q, f, lv, k in stock_rows) == sorted([
        ("MAM-006", 3.0, True, "Proje", "PRJ-01"), ("MAM-006", 2.0, True, "Müşteri", "MUS-A"), ("MAM-006", 1.0, True, "Sipariş", "SO-1020|1|0"),
        (d.ALLOCATION_EMPTY, 20.0, False, None, None),
        ("MAM-006", 1.0, True, "Proje", d.MISSING_PROJECT), (d.ALLOCATED_RAW, 30.0, True, "Müşteri", d.MISSING_CUSTOMER),   # durum 12: genele düşmez
        (d.DEEP_ALLOCATED, 50.0, True, "Proje", "PRJ-01"), (d.ALTERNATIVE_ONLY, 15.0, True, "Müşteri", d.ALTERNATIVE_CUSTOMER)], key=str)   # durum 13
    assert wo == {"WO-5001": (False, None, None), "WO-5013": (True, "Proje", "PRJ-02")}
    assert po == {d.ALLOCATED_ORDER_PO: (None, "Sipariş", "SO-1021"), d.ALLOCATED_CUSTOMER_PO: (None, "Müşteri", "MUS-A"),
                  d.MISSING_ORDER_PO: (None, "Sipariş", d.MISSING_ORDER)}
    assert deep == ("Sipariş", "SO-1020|1|0")   # durum 13: satıra bağlı (iç bağ dolu) satın alma
    assert stale == 0


def test_empty_material_flag_is_a_warning_high_when_it_has_owned_supply(db_engine):
    """`SC.MAT_ALLOC_EMPTY` (durum 11): özel alokasyonu boş malzeme; sahipli arzı varsa Yüksek, yoksa Normal."""
    try:
        with Session(db_engine) as s:
            quality_run.run(s, {"Material"})
        with db_engine.connect() as c:
            found = [tuple(r) for r in c.execute(sa.text("SELECT RecordLabel, RuleName, Importance, FixField FROM adm.DataQualityWarning WHERE CheckCode = N'SC.MAT_ALLOC_EMPTY'"))]
        assert found == [(f"Malzeme: {d.ALLOCATION_EMPTY}", "Özel alokasyon boş", quality_run.HIGH, "IsCustomAllocated")]
        with db_engine.begin() as c:   # sahipli stok güncel veriden çıkınca Normal (satır kapatılır; sonda yeniden açılır)
            owned = c.execute(sa.text("SELECT s.Id FROM core.Stock s JOIN core.Material m ON m.Id = s.MaterialId AND m.VersionTo IS NULL "
                                      "WHERE m.Code = :c AND s.VersionTo IS NULL AND s.ProjectId IS NOT NULL"), {"c": d.ALLOCATION_EMPTY}).scalar_one()
            c.execute(sa.text("UPDATE core.Stock SET VersionTo = VersionFrom WHERE Id = :i AND VersionTo IS NULL"), {"i": owned})
        with Session(db_engine) as s:
            quality_run.run(s, {"Material"})
        with db_engine.connect() as c:
            assert c.execute(sa.text("SELECT Importance FROM adm.DataQualityWarning WHERE CheckCode = N'SC.MAT_ALLOC_EMPTY'")).scalars().all() == [quality_run.NORMAL]
    finally:
        with db_engine.begin() as c:
            c.execute(sa.text("DELETE FROM adm.DataQualityWarning WHERE CheckCode = N'SC.MAT_ALLOC_EMPTY'"))
            c.execute(sa.text("UPDATE s SET VersionTo = NULL FROM core.Stock s JOIN core.Material m ON m.Id = s.MaterialId AND m.VersionTo IS NULL "
                              "WHERE m.Code = :c AND s.ProjectId IS NOT NULL AND s.VersionTo = s.VersionFrom"), {"c": d.ALLOCATION_EMPTY})

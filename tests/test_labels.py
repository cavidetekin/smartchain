"""Aynı alan, aynı etiket (K-198; docs/02 "Aynı alan, aynı etiket"): aynı adlı alan hangi ana tabloda olursa olsun aynı etiketi taşır.

Bugün bilinen farklar `KNOWN`'da listelidir ve karar bekler (bu test onları düzeltmez). Yeni bir fark eklenirse ya da listedeki bir fark değişirse
test düşer: ya etiketi öteki tablolardakiyle aynı yapın ya da kararla birlikte listeyi güncelleyin.
"""
from app import allocation
from app.api.lists.master_data import BY_TABLE
from app.api.lists.definition import columns
from app.api.lists import relations
from app.integration import contract
from db.dictionary import standard_label
from db.models import metadata

# alan → etiket → tablolar (yalnız farklı etiket taşıyan alanlar; 25.11.2026)
KNOWN = {
    "AllowPartialDelivery": {"Kısmi teslimata izin": {"Customer"}, "Kısmi teslimat": {"SalesOrderLine"}},
    "Code": {"Lokasyon kodu": {"Location"}, "Birim kodu": {"UnitOfMeasure"}, "Kaynak kodu": {"Resource"}, "Grup kodu": {"ResourceGroup"}, "Malzeme kodu": {"Material"},
             "Tedarikçi kodu": {"Supplier"}, "Versiyon kodu": {"ProductionVersion"}, "Ürün ağacı kodu": {"BOM"}, "Proje kodu": {"Project"}, "Müşteri kodu": {"Customer"}},
    "ConfirmedDate": {"Teyit tarihi": {"SalesOrderLine"}, "Tedarikçi teyit tarihi": {"PurchaseOrderLine"}},
    "IsCritical": {"Kritik": {"ResourceGroup"}, "Kritik malzeme": {"Material"}},
    "IsPhantom": {"Hayalet yarı mamul": {"Material"}, "Hayalet bileşen": {"BOM", "WorkOrderComponent"}},
    "IsSubcontractor": {"Fason deposu": {"Location"}, "Fason": {"ResourceGroup"}, "Fasoncu mu": {"Supplier"}},
    "MaterialId": {"Malzeme": {"UomConversion", "MaterialSupplier", "SalesOrderLine", "Forecast", "BorrowPayback", "Stock", "PurchaseOrderLine", "TransferOrder"},
                   "Üretilen malzeme": {"ProductionVersion", "BOM", "WorkOrder", "ProductionConfirmation"}, "Benzetilen ürün": {"MaterialReference"},
                   "Bileşen": {"WorkOrderComponent"}},
    "Name": {"Lokasyon adı": {"Location"}, "Birim adı": {"UnitOfMeasure"}, "Kaynak adı": {"Resource"}, "Grup adı": {"ResourceGroup"}, "Malzeme adı": {"Material"},
             "Tedarikçi adı": {"Supplier"}, "Versiyon adı": {"ProductionVersion"}, "Proje adı": {"Project"}, "Müşteri adı": {"Customer"}},
    "OrderNo": {"Sipariş no": {"SalesOrderLine"}, "Transfer no": {"TransferOrder"}},
    "OrderedQuantity": {"Sipariş miktarı": {"SalesOrderLine", "PurchaseOrderLine"}, "İş emri miktarı": {"WorkOrder"}},
    "Priority": {"Öncelik": {"MaterialSupplier", "ProductionVersion", "WorkOrder"}, "ERP önceliği": {"Project", "Customer", "SalesOrderLine"}},
    "Quantity": {"Bileşen miktarı": {"BOM"}, "Miktar": {"Forecast", "Stock"}},
    "RequestedDate": {"İstek tarihi": {"SalesOrderLine"}, "İstenen tarih": {"PurchaseOrderLine"}},
    "Status": {"Sipariş durumu": {"SalesOrderLine"}, "Stok durumu": {"Stock"}, "İş emri durumu": {"WorkOrder"}, "Operasyon durumu": {"WorkOrderOperation"},
               "Durum": {"PurchaseOrderLine"}},
    "Type": {"Lokasyon tipi": {"Location"}, "Grup tipi": {"ResourceGroup"}, "Versiyon tipi": {"ProductionVersion"}, "Sipariş tipi": {"SalesOrderLine"},
             "Tahmin tipi": {"Forecast"}},
    "Uom": {"Sipariş birimi": {"SalesOrderLine"}, "Birim": {"Forecast", "Stock", "WorkOrder", "WorkOrderComponent", "PurchaseOrderLine"}},
    "WorkOrderId": {"İş emri": {"WorkOrderComponent", "WorkOrderOperation", "ProductionConfirmation"}, "Bağlı iş emri": {"PurchaseOrderLine"}},
}
OWNER = {"ProjectCode": "Bağlı proje", "CustomerCode": "Bağlı müşteri", "SalesOrderNo": "Bağlı sipariş no", "SalesOrderLineNo": "Bağlı sipariş satırı",
         "SalesOrderLineItemNo": "Bağlı sipariş alt satırı"}
LINKS = {"ProjectId": "Bağlı proje", "CustomerId": "Bağlı müşteri", "SalesOrderLineId": "Bağlı sipariş"}


def _labels() -> dict:
    found: dict = {}
    for table in metadata.tables.values():
        if table.schema != "core":
            continue
        for c in table.columns:
            if (c.info or {}).get("source", "Sistem") == "Sistem":
                continue
            found.setdefault(c.name, {}).setdefault(standard_label(c.name, c.info.get("label")), set()).add(table.name)
    return found


def test_same_field_has_the_same_label_in_every_table():
    different = {name: labels for name, labels in _labels().items() if len(labels) > 1}
    assert different == KNOWN, {n: different.get(n) for n in set(different) ^ set(KNOWN) | {n for n in different if different[n] != KNOWN.get(n)}}


def test_supply_owner_fields_share_one_set_of_names():
    """Stok, İş emri ve Satın alma satırı: beş sahip alanı aynı adla; iç bağ kolon değildir; "sahip" kelimesi bu alanlarda geçmez."""
    for table in allocation.TABLES:
        core = metadata.tables[f"core.{table}"].c
        assert {f: core[f].info.get("label") for f in OWNER} == OWNER, table
        assert {f: core[f].info.get("label") for f in LINKS} == LINKS, table
        for schema in ("core", "stg", "prc"):
            t = metadata.tables[f"{schema}.{table}"]
            texts = [f"{c.info.get('label') or ''} {c.comment or ''}" for c in t.columns if c.name in (*OWNER, *LINKS)]
            assert not [x for x in texts if "sahip" in x.lower()], (schema, table)
        cols = {c["field"]: c for c in columns(BY_TABLE[table], {})}
        assert {f: cols[f]["label"] for f in OWNER} == OWNER, table                                       # tabloda ve Alanlar panelinde
        assert [cols[f]["default_visible"] for f in OWNER] == [True, True, True, False, False], table
        assert "SalesOrderLineCode" not in cols and not {"ProjectId", "CustomerId", "SalesOrderLineId"} & set(cols), table  # iç bağ kolon değil
        template = {f.name: f.label for f in contract.fields(table)}
        assert {f: template[f] for f in OWNER} == OWNER and "SalesOrderLineId" not in template, table       # şablonda
        heads = {r.column: r.label for r in relations.relations_of(table)}
        assert {k: heads[k] for k in LINKS} == LINKS, table                                               # ilişkili alan grupları

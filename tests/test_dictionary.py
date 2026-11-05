"""Veri sözlüğünün kurulumu (K-104): core ve param alanları docs/02'den, geçişle; System owner'ın değeri ezilmez."""
import re

import pytest
from sqlalchemy import text

from app.data.synthetic.dataset import generate as generate_data
from app.data.synthetic.load import load
from db import dictionary, generate
from db.models import metadata

SPEC = [t for t in generate.build_spec() if t["schema"] in ("core", "param")]
EXPECTED = {(t["name"], f["name"]): (t, f) for t in SPEC for f in t["fields"] if f["source"] != dictionary.SYSTEM_SOURCE}


def test_fields_match_docs():
    rows = {(r["TableName"], r["FieldName"]): r for r in dictionary.fields(metadata)}
    assert set(rows) == set(EXPECTED) and len(rows) > 400
    assert not [k for k in rows if k[1] in ("VersionFrom", "VersionTo", "BusinessKey")]
    for key, (table, field) in EXPECTED.items():
        row = rows[key]
        assert row["FieldClass"] == table["cls"], key
        assert row["IsRequired"] == field["required"], key
        assert row["EditableInWorkspace"] == field["workspace"], key
        assert (row["DefaultValue"] or "") == field["default"], key


def test_only_core_and_param_with_no_name_clash():
    names = [t["name"] for t in SPEC]
    assert len(names) == len(set(names))
    assert {t.schema for t in metadata.tables.values() if t.info.get("field_class")} == {"core", "param"}


def test_standard_label():
    assert dictionary.standard_label("AdditionalText3", None) == "Ek metin alanı 3"
    assert dictionary.standard_label("AdditionalNumber2", None) == "Ek sayı alanı 2"
    assert dictionary.standard_label("Name", "Malzeme adı") == "Malzeme adı"
    assert dictionary.standard_label("Status", None) == "Status"
    assert len(dictionary.standard_label("X", "a" * 300)) == dictionary.LABEL_LENGTH


UNIT = re.compile(r" \((%|gün|iş günü|dk|saat|adam-saat)\)$")


def test_standard_labels_are_short_and_turkish():
    """K-104: en çok 40 karakter, aynı tabloda tekrar yok, alan adına düşmez, parantezde yalnız birim."""
    seen = set()
    for f in dictionary.fields(metadata):
        table, field, label = f["TableName"], f["FieldName"], f["StandardLabel"]
        assert len(label) <= 40, (table, field, label)
        assert label != field, (table, field)
        assert "(" not in UNIT.sub("", label), (table, field, label)
        assert (table, label) not in seen, (table, label)
        seen.add((table, label))


def test_descriptions_come_from_docs_for_the_screen():
    """K-104: her alanda açıklama; tek satıra sığar, karar numarası ve ek alanın teknik notu yok."""
    rows = {(r["TableName"], r["FieldName"]): r["Description"] for r in dictionary.fields(metadata)}
    assert all(rows.values())
    assert max(len(v) for v in rows.values()) <= metadata.tables["adm.FieldDefinition"].c.Description.type.length
    assert not [k for k, v in rows.items() if re.search(r"K-\d", v) or "FieldDefinition" in v]
    assert rows[("Resource", "CapacityUnit")] == "Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir"
    assert rows[("UnitOfMeasure", "Decimals")] == "Miktar ondalığı; ERP'den gelmez, Smartchain'de tutulur"
    assert rows[("Material", "AdditionalText1")] == "Ek metin alanları"
    assert rows[("Material", "ShelfLifeDays")] == "Raf ömrü; şimdilik yalnız uyarı için kullanılır"
    assert rows[("ProductionVersion", "RouteCode")] == "Rota kodu"
    assert rows[("Routing", "IsLotBasedUsage")] == "Doluysa tüketim üretilen miktardan bağımsız, lot başına sabit; pratikte hazırlık süresi"
    assert rows[("PlanningSetting", "SettingKey")] == "Parametre adı"
    assert metadata.tables["core.Material"].c.ShelfLifeDays.info["label"] == "Raf ömrü (gün)"


def test_label_and_description_are_separate():
    """K-88: ETİKET doluysa etiket odur; açıklama veritabanı yorumunda, değer listesi yerinde kalır."""
    critical = metadata.tables["core.Resource"].c.IsCritical
    assert critical.info["label"] == "Kritik kaynak" and "sonsuz kapasite" in critical.comment
    status = metadata.tables["core.SalesOrderLine"].c.Status
    assert status.info["label"] == "Sipariş durumu" and "values" not in status.info  # K-127: ham değer
    policy = metadata.tables["core.Material"].c.LotSizePolicy
    assert policy.info["label"] == "Lot politikası" and policy.info["values"] == ["Lot-for-lot", "Sabit", "Dönemsel"]
    assert metadata.tables["core.Material"].c.Name.info["label"] == "Malzeme adı"  # ETİKET boşsa AÇIKLAMA'dan


@pytest.mark.db
def test_every_field_is_in_the_dictionary(db_engine):
    """Yeni kolon eklenip geçişte sync unutulursa bu test düşer."""
    with db_engine.connect() as c:
        stored = {(r[0], r[1]) for r in c.execute(text("SELECT TableName, FieldName FROM adm.FieldDefinition"))}
    missing = set(EXPECTED) - stored
    assert not missing, f"Sözlükte yok; geçişe db/dictionary.sync ekleyin: {sorted(missing)[:10]}"
    extra = stored - set(EXPECTED)
    assert not extra, f"Docs'ta yok: {sorted(extra)[:10]}"


@pytest.mark.db
def test_location_flags_in_the_dictionary(db_engine):
    """K-111: bayraklar etiketleriyle sözlükte; Type kalır; Name zorunlu değil."""
    with db_engine.connect() as c:
        rows = {r.FieldName: r for r in c.execute(text(
            "SELECT FieldName, StandardLabel, IsRequired, DefaultValue FROM adm.FieldDefinition WHERE TableName = N'Location'"))}
    assert rows["Type"].StandardLabel == "Lokasyon tipi" and not rows["Name"].IsRequired
    assert {n: (rows[n].StandardLabel, rows[n].DefaultValue) for n in ("IsFactory", "IsDepot", "IsSubcontractor", "IsActive")} == {
        "IsFactory": ("Tesis", "0"), "IsDepot": ("Depo", "0"), "IsSubcontractor": ("Fason deposu", "0"), "IsActive": ("Aktif", "1")}


@pytest.mark.db
def test_unit_fields_in_the_dictionary(db_engine):
    """K-112: ondalığın varsayılanı yok; dönüşümün ad alanları etiketleriyle sözlükte."""
    with db_engine.connect() as c:
        decimals = c.execute(text("SELECT DefaultValue FROM adm.FieldDefinition WHERE TableName = N'UnitOfMeasure' AND FieldName = N'Decimals'")).scalar_one()
        rows = dict(c.execute(text("SELECT FieldName, StandardLabel FROM adm.FieldDefinition WHERE TableName = N'UomConversion'")).all())
        factor = c.execute(text("SELECT Description FROM adm.FieldDefinition WHERE TableName = N'UomConversion' AND FieldName = N'Factor'")).scalar_one()
    assert decimals is None
    assert (rows["FromUomName"], rows["ToUomName"], rows["Factor"]) == ("Kaynak birim adı", "Hedef birim adı", "Çarpan")
    assert factor == "1 kaynak birim = çarpan × hedef birim"


@pytest.mark.db
def test_dictionary_holds_only_current_fields(db_engine):
    """3.1b: kalkan ya da adı değişen alanın satırı kalmaz; sözlük modelle birebir."""
    with db_engine.connect() as c:
        rows = {(r.TableName, r.FieldName) for r in c.execute(text("SELECT TableName, FieldName FROM adm.FieldDefinition"))}
    assert rows == {(f["TableName"], f["FieldName"]) for f in dictionary.fields(metadata)}


@pytest.mark.db
def test_closing_changes_in_the_dictionary(db_engine):
    """K-127: ham alanlar zorunlu ve varsayılansız; teklif bayrağı; RemainingQuantity."""
    with db_engine.connect() as c:
        rows = {(r.TableName, r.FieldName): r for r in c.execute(text("SELECT TableName, FieldName, StandardLabel, DefaultValue, IsRequired FROM adm.FieldDefinition WHERE TableName IN (N'SalesOrderLine', N'WorkOrderComponent')"))}
    assert not rows[("SalesOrderLine", "Type")].IsRequired and rows[("SalesOrderLine", "Type")].DefaultValue is None and not rows[("SalesOrderLine", "Status")].IsRequired
    assert rows[("SalesOrderLine", "IsQuote")].StandardLabel == "Teklif" and rows[("SalesOrderLine", "IsQuote")].DefaultValue is None
    assert ("WorkOrderComponent", "RemainingQuantity") in rows and ("WorkOrderComponent", "RemainingQty") not in rows


@pytest.mark.db
def test_material_reference_and_capacity_unit_in_the_dictionary(db_engine):
    """K-126: yeni tablo etiketleriyle; K-117: kapasite biriminin varsayılanı kalktı, zorunlu kaldı."""
    with db_engine.connect() as c:
        rows = {(r.TableName, r.FieldName): r for r in c.execute(text("SELECT TableName, FieldName, StandardLabel, DefaultValue, IsRequired FROM adm.FieldDefinition WHERE TableName IN (N'MaterialReference', N'Resource')"))}
    assert rows[("MaterialReference", "MaterialId")].StandardLabel == "Benzetilen ürün" and rows[("MaterialReference", "ReferenceMaterialId")].IsRequired
    assert rows[("MaterialReference", "TimeFactor")].StandardLabel == "Süre çarpanı" and rows[("MaterialReference", "TimeFactor")].DefaultValue == "1"
    assert rows[("MaterialReference", "ReferenceProductionVersionId")].StandardLabel == "Referans ürünün versiyonu" and not rows[("MaterialReference", "ReferenceProductionVersionId")].IsRequired
    assert rows[("Resource", "CapacityUnit")].IsRequired and rows[("Resource", "CapacityUnit")].DefaultValue is None


@pytest.mark.db
def test_purchase_and_confirmation_in_the_dictionary(db_engine):
    """K-125: eski ve kalkan alanlar yok; tip zorunlu kalır; bayraklar varsayılansız."""
    with db_engine.connect() as c:
        rows = {(r.TableName, r.FieldName): r for r in c.execute(text("SELECT TableName, FieldName, StandardLabel, DefaultValue, IsRequired FROM adm.FieldDefinition WHERE TableName IN (N'PurchaseOrderLine', N'ProductionConfirmation')"))}
    assert not {("PurchaseOrderLine", "OrderNo"), ("PurchaseOrderLine", "OpenQty")} & set(rows)
    assert not {("ProductionConfirmation", n) for n in ("OpNo", "SeqNo", "ResourceId", "ActualConsumption", "ConfirmedQty", "StartAt", "EndAt")} & set(rows)
    assert not rows[("PurchaseOrderLine", "OrderType")].IsRequired and not rows[("PurchaseOrderLine", "Status")].IsRequired and rows[("PurchaseOrderLine", "PurchaseOrderNo")].StandardLabel == "Sipariş no"
    assert rows[("PurchaseOrderLine", "IsPurchaseRequest")].StandardLabel == "Satın alma talebi" and rows[("PurchaseOrderLine", "IsPurchaseRequest")].DefaultValue is None
    assert rows[("PurchaseOrderLine", "SalesOrderLineId")].StandardLabel == "Bağlı sipariş satırı" and rows[("PurchaseOrderLine", "ReceivedQuantity")].StandardLabel == "Teslim alınan miktar"
    assert rows[("ProductionConfirmation", "ConfirmationNo")].StandardLabel == "Teyit no" and rows[("ProductionConfirmation", "ConfirmationNo")].IsRequired
    assert rows[("ProductionConfirmation", "MaterialId")].StandardLabel == "Üretilen malzeme" and rows[("ProductionConfirmation", "ConfirmedQuantity")].IsRequired and rows[("ProductionConfirmation", "StartDate")].StandardLabel == "Başlangıç"


@pytest.mark.db
def test_work_orders_in_the_dictionary(db_engine):
    """K-124: eski adlar yok; tipin varsayılanı ve zorunluluğu kalktı; operasyonda kaynak zorunlu değil."""
    with db_engine.connect() as c:
        rows = {(r.TableName, r.FieldName): r for r in c.execute(text("SELECT TableName, FieldName, StandardLabel, DefaultValue, IsRequired FROM adm.FieldDefinition WHERE TableName LIKE N'WorkOrder%'"))}
    assert not {("WorkOrder", n) for n in ("OrderNo", "OrderType", "OrderQty", "OpenQty")} & set(rows)
    assert not {("WorkOrderComponent", "RequiredQty"), ("WorkOrderComponent", "IssuedQty"), ("WorkOrderOperation", "OpNo"), ("WorkOrderOperation", "SeqNo")} & set(rows)
    kind = rows[("WorkOrder", "ProductionOrderType")]
    assert kind.StandardLabel == "İş emri tipi" and kind.DefaultValue is None and not kind.IsRequired and not rows[("WorkOrder", "Status")].IsRequired
    assert rows[("WorkOrder", "ProductionVersionId")].StandardLabel == "Üretim versiyonu" and rows[("WorkOrder", "IsFixed")].StandardLabel == "Sabit" and rows[("WorkOrder", "IsFixed")].DefaultValue is None
    assert rows[("WorkOrderComponent", "UnitUsage")].StandardLabel == "Birim kullanım" and rows[("WorkOrderComponent", "IssuedQuantity")].DefaultValue == "0" and rows[("WorkOrderComponent", "ScrapRatio")].DefaultValue == "0"
    assert not rows[("WorkOrderOperation", "ResourceId")].IsRequired and rows[("WorkOrderOperation", "ResourceRole")].DefaultValue == "Primary" and rows[("WorkOrderOperation", "IsCompleted")].StandardLabel == "Tamamlandı"
    assert rows[("WorkOrderOperation", "SequenceNo")].StandardLabel == "Sıra no"


@pytest.mark.db
def test_stock_in_the_dictionary(db_engine):
    """K-123: durumun varsayılanı ve zorunluluğu kalktı; yeni alanlar etiketleriyle."""
    with db_engine.connect() as c:
        rows = {r.FieldName: r for r in c.execute(text("SELECT FieldName, StandardLabel, DefaultValue, IsRequired FROM adm.FieldDefinition WHERE TableName = N'Stock'"))}
    assert "StockStatus" not in rows and rows["Status"].StandardLabel == "Stok durumu" and rows["Status"].DefaultValue is None and not rows["Status"].IsRequired
    assert {n: rows[n].StandardLabel for n in ("CustomerId", "SalesOrderLineId", "ExpectedAcceptanceDate", "Uom", "IsAvailable", "IsInQuality", "IsBlocked", "IsActive", "IsCustomTracked")} == {
        "CustomerId": "Sahip müşteri", "SalesOrderLineId": "Sahip sipariş satırı", "ExpectedAcceptanceDate": "Beklenen kabul tarihi", "Uom": "Birim",
        "IsAvailable": "Kullanılabilir", "IsInQuality": "Kalitede", "IsBlocked": "Bloke", "IsActive": "Aktif", "IsCustomTracked": "Özel takip"}
    assert all(rows[n].DefaultValue is None for n in ("IsAvailable", "IsInQuality", "IsBlocked", "IsActive", "IsCustomTracked"))


@pytest.mark.db
def test_forecast_in_the_dictionary(db_engine):
    """K-122: yeni alanlar etiketleriyle; bayrak ve teslim noktasının varsayılanı yok."""
    with db_engine.connect() as c:
        rows = {r.FieldName: r for r in c.execute(text("SELECT FieldName, StandardLabel, DefaultValue FROM adm.FieldDefinition WHERE TableName = N'Forecast'"))}
    assert {n: rows[n].StandardLabel for n in ("Uom", "Type", "DeliveryPoint", "IsActive")} == {"Uom": "Birim", "Type": "Tahmin tipi", "DeliveryPoint": "Teslim noktası", "IsActive": "Aktif"}
    assert rows["DeliveryPoint"].DefaultValue is None and rows["IsActive"].DefaultValue is None


@pytest.mark.db
def test_sales_order_in_the_dictionary(db_engine):
    """K-120: yeni ve adı değişen alanlar sözlükte."""
    with db_engine.connect() as c:
        rows = {(r.TableName, r.FieldName): r for r in c.execute(text("SELECT TableName, FieldName, StandardLabel, DefaultValue, IsRequired FROM adm.FieldDefinition WHERE FieldName IN (N'OpenQty', N'OpenQuantity', N'OrderedQuantity', N'Uom', N'IsOnHold')"))}
    assert ("SalesOrderLine", "OpenQty") not in rows
    assert rows[("SalesOrderLine", "OpenQuantity")].IsRequired and rows[("SalesOrderLine", "OpenQuantity")].StandardLabel == "Açık miktar"
    assert rows[("SalesOrderLine", "Uom")].StandardLabel == "Sipariş birimi" and rows[("SalesOrderLine", "IsOnHold")].DefaultValue is None


@pytest.mark.db
def test_customer_and_project_in_the_dictionary(db_engine):
    """K-119: yeni ve adı değişen alanlar sözlükte; eski adlar yok; IsActive varsayılansız."""
    with db_engine.connect() as c:
        rows = {(r.TableName, r.FieldName): r for r in c.execute(text("SELECT TableName, FieldName, StandardLabel, DefaultValue FROM adm.FieldDefinition WHERE TableName IN (N'Customer', N'ProjectGroup', N'Project', N'BorrowPayback')"))}
    assert not {("ProjectGroup", "IsolationRule"), ("Project", "IsolationRule"), ("Project", "IsClosed")} & set(rows)
    assert rows[("ProjectGroup", "TrackingRule")].StandardLabel == rows[("Project", "TrackingRule")].StandardLabel == "Takip kuralı"
    assert rows[("ProjectGroup", "TrackingRule")].DefaultValue == "Ortaktan beslenir" and rows[("Project", "IsActive")].DefaultValue is None
    assert rows[("Customer", "IsCustomTracked")].StandardLabel == "Özel takip" and rows[("Customer", "IsCustomTracked")].DefaultValue is None
    assert rows[("ProjectGroup", "IsActive")].DefaultValue is None and rows[("BorrowPayback", "LendingProjectId")].StandardLabel == "Ödünç veren proje"


@pytest.mark.db
def test_supplier_fields_in_the_dictionary(db_engine):
    """K-118: yeni ve adı değişen alanlar sözlükte; eski adlar yok; süre zorunlu değil."""
    with db_engine.connect() as c:
        rows = {(r.TableName, r.FieldName): r for r in c.execute(text("SELECT TableName, FieldName, StandardLabel, DefaultValue, IsRequired FROM adm.FieldDefinition WHERE TableName IN (N'Supplier', N'MaterialSupplier')"))}
    assert not {f for _, f in rows} & {"LeadTimeDays", "QuotaPct", "MinOrderQty", "OrderMultiple", "MaxOrderQty"}
    assert rows[("MaterialSupplier", "QuotaRatio")].StandardLabel == "Kota oranı" and rows[("MaterialSupplier", "OrderLotSize")].StandardLabel == "Sipariş katı"
    assert not rows[("MaterialSupplier", "FixedLeadTimeDays")].IsRequired and rows[("MaterialSupplier", "LocationId")].IsRequired
    assert rows[("MaterialSupplier", "IsActive")].DefaultValue is None and rows[("Supplier", "IsActive")].DefaultValue is None
    assert rows[("Supplier", "Country")].StandardLabel == "Ülke" and rows[("Supplier", "City")].StandardLabel == "Şehir"


@pytest.mark.db
def test_resource_side_in_the_dictionary(db_engine):
    """K-117: kalkan tablolar sözlükte yok; yeni tablolar ve alanlar var; kapasite alanı zorunlu değil."""
    with db_engine.connect() as c:
        rows = {(r.TableName, r.FieldName): r for r in c.execute(text("SELECT TableName, FieldName, StandardLabel, DefaultValue, IsRequired FROM adm.FieldDefinition"))}
    assert not {t for t, _ in rows} & {"Worker", "CompetenceGroup", "WorkerCompetence", "WorkerAbsence"}
    assert not {("Resource", "ResourceRole"), ("Resource", "ResourceGroupId"), ("Resource", "IsConstrained"), ("Resource", "SupplierId"), ("ShiftPlan", "CompetenceGroupId")} & set(rows)
    assert rows[("Resource", "IsCritical")].StandardLabel == "Kritik kaynak" and rows[("Resource", "IsCritical")].DefaultValue is None
    assert rows[("Resource", "SubcontractorId")].StandardLabel == "Fasoncu" and rows[("Resource", "IsEmployee")].StandardLabel == "İşçi"
    assert not rows[("Resource", "DailyCapacity")].IsRequired and not rows[("Resource", "CalendarId")].IsRequired and not rows[("Resource", "ResourceType")].IsRequired
    assert rows[("ResourceGroupAssignment", "ResourceGroupId")].IsRequired and rows[("EmployeeAbsence", "HoursPerDay")].StandardLabel == "Günlük saat"
    assert rows[("ResourceGroup", "IsCompetenceGroup")].StandardLabel == "Yetkinlik grubu" and rows[("ShiftPlan", "ResourceGroupId")].StandardLabel == "Kaynak ya da yetkinlik grubu"


@pytest.mark.db
def test_routing_fields_in_the_dictionary(db_engine):
    """K-116: yeni ve adı değişen alanlar sözlükte; işçilik alanları yok; kaynak zorunlu değil."""
    with db_engine.connect() as c:
        rows = {r.FieldName: r for r in c.execute(text("SELECT FieldName, StandardLabel, DefaultValue, IsRequired FROM adm.FieldDefinition WHERE TableName = N'Routing'"))}
    assert not {"OpNo", "SeqNo", "TransferLotQty", "LaborType", "LaborRefId", "LaborBasis", "CrewSize", "LaborTime"} & set(rows)
    assert {n: rows[n].StandardLabel for n in ("OperationNo", "SequenceNo", "TransferQuantity", "ResourceGroupId", "IsActive", "IsLotBasedUsage", "ProductionLocation", "WaitingTimeHours", "TransferTimeHours")} == {
        "OperationNo": "Operasyon no", "SequenceNo": "Sıra no", "TransferQuantity": "Transfer miktarı", "ResourceGroupId": "Kaynak grubu", "IsActive": "Aktif",
        "IsLotBasedUsage": "Lot bazlı kullanım", "ProductionLocation": "Üretim yeri", "WaitingTimeHours": "Bekleme süresi (saat)", "TransferTimeHours": "Taşıma süresi (saat)"}
    assert not rows["ResourceId"].IsRequired and rows["LocationId"].IsRequired and rows["IsActive"].DefaultValue is None
    assert (rows["ResourceRole"].DefaultValue, rows["ResourceNumber"].DefaultValue) == ("Primary", "1")


@pytest.mark.db
def test_bom_fields_in_the_dictionary(db_engine):
    """K-115: yeni ve adı değişen alanlar sözlükte; eski bağ yok."""
    with db_engine.connect() as c:
        rows = {r.FieldName: r for r in c.execute(text("SELECT FieldName, StandardLabel, DefaultValue, IsRequired FROM adm.FieldDefinition WHERE TableName = N'BOM'"))}
    assert not {"ProductionVersionId", "OpNo", "ScrapPct", "IsFixedQuantity"} & set(rows)
    assert {n: rows[n].StandardLabel for n in ("OperationNo", "SequenceNo", "ScrapRatio", "IsLotBasedUsage", "ComponentUom", "Code")} == {
        "OperationNo": "Operasyon no", "SequenceNo": "Sıra no", "ScrapRatio": "Fire oranı", "IsLotBasedUsage": "Lot bazlı kullanım",
        "ComponentUom": "Bileşen birimi", "Code": "Ürün ağacı kodu"}
    assert rows["Code"].IsRequired and rows["LocationId"].IsRequired and rows["MaterialId"].IsRequired


@pytest.mark.db
def test_production_version_fields_in_the_dictionary(db_engine):
    """K-114: yeni alanlar etiketleriyle sözlükte; IsDefault yok; ParameterSet.IsDefault durur."""
    with db_engine.connect() as c:
        rows = {r.FieldName: r for r in c.execute(text("SELECT FieldName, StandardLabel, DefaultValue, IsRequired FROM adm.FieldDefinition WHERE TableName = N'ProductionVersion'"))}
        critical = c.execute(text("SELECT StandardLabel, DefaultValue FROM adm.FieldDefinition WHERE TableName = N'Material' AND FieldName = N'IsCritical'")).one()
    assert "IsDefault" not in rows and tuple(critical) == ("Kritik malzeme", None)
    assert {n: rows[n].StandardLabel for n in ("Name", "Type", "IsActive", "Priority", "BOMCode")} == {
        "Name": "Versiyon adı", "Type": "Versiyon tipi", "IsActive": "Aktif", "Priority": "Öncelik", "BOMCode": "Ürün ağacı kodu"}
    assert rows["BOMCode"].IsRequired and rows["LocationId"].IsRequired and rows["IsActive"].DefaultValue is None
    assert ("ParameterSet", "IsDefault") in EXPECTED


@pytest.mark.db
def test_material_fields_in_the_dictionary(db_engine):
    """K-113: yeni ve adı değişen alanlar sözlükte; kalkanlar yok; yeni bayrakların varsayılanı yok."""
    with db_engine.connect() as c:
        rows = {r.FieldName: r for r in c.execute(text("SELECT FieldName, StandardLabel, DefaultValue FROM adm.FieldDefinition WHERE TableName = N'Material'"))}
    assert not {"DefaultProcurement", "AssemblyScrapPct", "IsProjectTracked", "ProductionLeadTimeDays", "Ownership"} & set(rows)
    assert (rows["DefaultSupplyType"].StandardLabel, rows["ScrapRatio"].StandardLabel, rows["IsCustomTracked"].StandardLabel) == ("Tedarik türü", "Fire oranı", "Özel takip")
    assert all(rows[n].DefaultValue is None for n in ("IsActive", "IsSubcontractable", "IsCustomerSupplied"))
    assert rows["QtyPerPallet"].StandardLabel == "Palet içi miktar" and rows["StockCoverageDays"].StandardLabel == "Stok gün kapsamı"


@pytest.mark.db
def test_sync_is_idempotent_and_keeps_owner_values(db_engine):
    with db_engine.connect() as conn:
        trans = conn.begin()
        try:
            assert dictionary.sync(conn, metadata) == {"added": 0, "updated": 0}
            conn.execute(text("UPDATE adm.FieldDefinition SET IsRequired = 1, Label = N'Özel', StandardLabel = N'eski', Description = N'eski' "
                              "WHERE TableName = N'Material' AND FieldName = N'Name'"))
            conn.execute(text("DELETE FROM adm.FieldDefinition WHERE TableName = N'Material' AND FieldName = N'MinLot'"))
            assert dictionary.sync(conn, metadata) == {"added": 1, "updated": 1}
            row = conn.execute(text("SELECT IsRequired, Label, StandardLabel, Description FROM adm.FieldDefinition "
                                    "WHERE TableName = N'Material' AND FieldName = N'Name'")).one()
            assert tuple(row) == (True, "Özel", "Malzeme adı", "Malzeme adı")
            assert conn.execute(text("SELECT COUNT(*) FROM adm.FieldDefinition WHERE TableName = N'Material' "
                                     "AND FieldName = N'MinLot'")).scalar_one() == 1
        finally:
            trans.rollback()


@pytest.mark.db
def test_synthetic_load_writes_label_only_when_empty(db_engine):
    where = "WHERE TableName = N'Material' AND FieldName = N'AdditionalText1'"
    def label():
        with db_engine.connect() as c:
            return c.execute(text(f"SELECT Label FROM adm.FieldDefinition {where}")).scalar_one()
    data = generate_data()
    try:
        with db_engine.begin() as c:
            c.execute(text(f"UPDATE adm.FieldDefinition SET Label = NULL {where}"))
        load(db_engine, data)
        assert label() == "Malzeme sınıfı"
        with db_engine.begin() as c:
            c.execute(text(f"UPDATE adm.FieldDefinition SET Label = N'pytest Özel' {where}"))
        load(db_engine, data)
        assert label() == "pytest Özel"
    finally:
        with db_engine.begin() as c:
            c.execute(text(f"UPDATE adm.FieldDefinition SET Label = N'Malzeme sınıfı' {where}"))

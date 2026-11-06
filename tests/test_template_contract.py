"""Veri sözleşmesi ve varlık kataloğu (docs/03, K-110). Veritabanı istemez."""
import json
import re
from datetime import date, datetime
from pathlib import Path

import pytest

from app.data.synthetic.dataset import generate
from app.data.synthetic.excel import to_staging
from app.integration import contract
from app.integration.contract import ENTITIES, MASTER_DATA, TRANSACTION_DATA, contract_hash, fields, stg_columns
from db.models import metadata

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "tests" / "template_versions.json"
RULE_FILLED = {"Yok sayılır", "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez"}  # kuralla dolan bayrak ve IsActive (K-138)
TABLES = [e.table for e in ENTITIES]


def catalog_rows() -> list[list[str]]:
    text = (ROOT / "docs" / "03-entegrasyon.md").read_text(encoding="utf-8")
    start = text.index("| VARLIK | AD | SINIF | AÇIKLAMA | DOSYA ADI | SÜRÜM |")
    rows = []
    for line in text[start:].splitlines()[2:]:
        if not line.startswith("|"):
            break
        rows.append([c.strip() for c in line.strip("|").split("|")])
    return rows


def test_catalog_matches_docs():
    """Katalog docs/03'ten üretilir; farklıysa: python db/generate.py."""
    assert catalog_rows() == [[e.table, e.name, e.data_class, e.description, e.slug, str(e.version)] for e in ENTITIES]


def test_descriptions_are_one_short_plain_sentence():
    for e in ENTITIES:
        assert 5 <= len(e.description) <= 70 and not e.description.endswith(".") and "." not in e.description, e.table
        assert not re.search(r"K-\d+|stg\.|[A-Z][a-z]+[A-Z]", e.description), e.table  # karar numarası ve teknik ad yok


def stg_key(table: str) -> list[str]:
    """stg indeks taşımaz, anahtar sözleşmede (K-129)."""
    return [c.name for c in stg_columns(table) if "UK" in c.info.get("key", "")]


def test_catalog_covers_every_staging_table():
    assert sorted(TABLES) == sorted(t.name for t in metadata.sorted_tables if t.schema == "stg") and len(TABLES) == 25
    assert {e.data_class for e in ENTITIES} == {MASTER_DATA, TRANSACTION_DATA}
    assert len({e.slug for e in ENTITIES}) == 25 and all(re.fullmatch(r"[a-z-]+", e.slug) for e in ENTITIES)
    assert contract.entity("Resource").file_name == "smartchain_kaynak_v3.xlsx" and contract.entity("yok") is None


@pytest.mark.parametrize("table", TABLES)
def test_labels_are_short_readable_and_unique(table):
    found = fields(table)
    labels = [f.label for f in found]
    assert all(labels) and all(len(x) <= 40 for x in labels), labels
    assert len(labels) == len(set(labels)), labels
    assert [f.name for f in found if f.label == f.name] == []
    assert not [f.name for f in found if f.name.startswith("Additional")]  # etiketsiz ek alan yok
    assert not [f.name for f in found if re.search(r"K-\d+", f.description)]


def test_required_and_blank_rules():
    """Boşsa satır yüklenmeyen 88 alan zorunludur; her YOKSA kuralının somut karşılığı var."""
    every = [f for t in TABLES for f in fields(t)]
    assert sum(f.required for f in every) == 88 and all(f.blank == contract.BLANK_ROW_REJECTED for f in every if f.required)
    assert sum(1 for f in every if f.values) == 9
    assert contract.blank_text("hata (satır atlanır)") == "Satır yüklenmez" and contract.blank_text("tam gün") == "Tam gün kabul edilir"
    assert contract.blank_text("hata (kurallardan sonra)") == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez" and contract.blank_text("yok") == "Yok sayılır"
    assert contract.blank_text("alternatif Kaynak grubu") == "Kaynak grubu da boşsa satır yüklenmez"
    assert contract.blank_text("bilinmiyor") == "Bilinmiyor; planda kullanılmaz" and contract.blank_text("sınırsız") == "Sınır yok"
    for old in ("varsayılan Takvim günü", "kural ya da elle", "boş kalır", "kural, yoksa varsayılan 1", "yeni bir kural"):  # varsayılan yok (K-138)
        with pytest.raises(ValueError):
            contract.blank_text(old)


def test_every_reference_says_which_table():
    """docs/03'te REF olan her alanın metni var; yeni referans unutulursa düşer."""
    refs = {c.name for t in TABLES for c in stg_columns(t) if "REF" in c.info.get("key", "")}
    assert refs == set(contract.REF_TEXT), refs ^ set(contract.REF_TEXT)
    every = [f for t in TABLES for f in fields(t)]
    assert not [f.name for f in every if f.values and f.ref_text]


def test_material_reference_v1():
    """K-126: kendi ağacı ya da rotası olmayan ürün; anahtar; versiyon boşsa motor seçer; süre çarpanı."""
    found = {f.name: f for f in fields("MaterialReference")}
    core = metadata.tables["core.MaterialReference"].c
    assert list(found) == ["LocationCode", "MaterialCode", "ReferenceMaterialCode", "ReferenceProductionVersionCode", "ValidFrom", "ValidTo", "TimeFactor"]
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "MaterialCode", "ReferenceMaterialCode"]
    assert {n: found[n].label for n in ("MaterialCode", "ReferenceMaterialCode", "ReferenceProductionVersionCode", "ValidFrom", "ValidTo", "TimeFactor")} == {
        "MaterialCode": "Benzetilen ürün", "ReferenceMaterialCode": "Referans ürün", "ReferenceProductionVersionCode": "Referans ürünün versiyonu",
        "ValidFrom": "Geçerlilik başlangıcı", "ValidTo": "Geçerlilik bitişi", "TimeFactor": "Süre çarpanı"}
    assert found["TimeFactor"].blank == "Yok sayılır" and found["TimeFactor"].example == 1.2 and core["TimeFactor"].type.scale == 4
    assert [c.name for c in stg_columns("MaterialReference") if "UK" in c.info.get("key", "")] == ["LocationCode", "MaterialCode", "ReferenceMaterialCode", "ValidFrom"]
    key = next(i for i in metadata.tables["core.MaterialReference"].indexes if i.unique)
    assert [c.name for c in key.columns] == ["LocationId", "MaterialId", "ReferenceMaterialId", "ValidFrom"] and str(key.dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("MaterialReference").file_name == "smartchain_benzetilen-urun_v1.xlsx"
    assert "AdditionalText1" not in core


def test_purchase_order_line_v2():
    """K-125, K-127: anahtar lokasyonlu; yeni adlar; tip ve durum ham değer, zorunlu değil; bayraklar varsayılansız."""
    found = {f.name: f for f in fields("PurchaseOrderLine")}
    core = metadata.tables["core.PurchaseOrderLine"].c
    assert list(found) == ["LocationCode", "PurchaseOrderNo", "LineNo", "OrderType", "SupplierCode", "MaterialCode", "OpenQuantity", "OrderedQuantity", "ReceivedQuantity", "Uom", "RequestedDate", "ConfirmedDate",
                           "ProjectCode", "CustomerCode", "SalesOrderNo", "SalesOrderLineNo", "SalesOrderLineItemNo", "WorkOrderNo", "Status", "IsPurchaseRequest", "IsPurchase", "IsSubcontract", "IsActive", "IsCustomTracked"]
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "PurchaseOrderNo", "LineNo", "MaterialCode", "OpenQuantity"]
    assert {n: found[n].label for n in ("PurchaseOrderNo", "OrderType", "OpenQuantity", "OrderedQuantity", "ReceivedQuantity", "Uom", "CustomerCode", "SalesOrderNo", "SalesOrderLineNo",
                                        "IsPurchaseRequest", "IsPurchase", "IsSubcontract", "IsActive", "IsCustomTracked")} == {
        "PurchaseOrderNo": "Sipariş no", "OrderType": "Sipariş tipi", "OpenQuantity": "Açık miktar", "OrderedQuantity": "Sipariş miktarı", "ReceivedQuantity": "Teslim alınan miktar", "Uom": "Birim",
        "CustomerCode": "Müşteri", "SalesOrderNo": "Bağlı sipariş no", "SalesOrderLineNo": "Bağlı sipariş satırı",
        "IsPurchaseRequest": "Satın alma talebi", "IsPurchase": "Satın alma", "IsSubcontract": "Fason", "IsActive": "Aktif", "IsCustomTracked": "Özel takip"}
    assert not {"OrderNo", "OpenQty"} & set(core.keys()) and not {"OrderNo", "OpenQty"} & set(found)
    assert found["OrderType"].values == () and found["OrderType"].blank == "Bilinmiyor; planda kullanılmaz" and core["OrderType"].nullable and core["OrderType"].type.length == 50
    assert found["Status"].blank == "Bilinmiyor; planda kullanılmaz" and core["Status"].nullable and core["Status"].type.length == 50 and found["Status"].label == "Durum"
    assert found["Uom"].blank == "Temel birimde kabul edilir" and found["Uom"].ref_text == contract.UNIT_CODE
    for name in ("IsPurchaseRequest", "IsPurchase", "IsSubcontract", "IsActive", "IsCustomTracked"):
        assert found[name].blank in RULE_FILLED and core[name].server_default is None and core[name].nullable, name
    assert [c.name for c in stg_columns("PurchaseOrderLine") if "UK" in c.info.get("key", "")] == ["LocationCode", "PurchaseOrderNo", "LineNo"]
    key = next(i for i in metadata.tables["core.PurchaseOrderLine"].indexes if i.unique)
    assert [c.name for c in key.columns] == ["LocationId", "PurchaseOrderNo", "LineNo"] and str(key.dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("PurchaseOrderLine").file_name == "smartchain_satin-alma-siparisi_v3.xlsx"


def test_production_confirmation_v2():
    """K-125: iş emri bazlı stoğa giriş; operasyon ve kaynak alanları yok; tarih saatsiz."""
    found = {f.name: f for f in fields("ProductionConfirmation")}
    core = metadata.tables["core.ProductionConfirmation"].c
    assert list(found) == ["LocationCode", "ConfirmationNo", "WorkOrderNo", "MaterialCode", "ConfirmedQuantity", "StartDate", "EndDate"]
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "ConfirmationNo", "WorkOrderNo", "MaterialCode", "ConfirmedQuantity"]
    assert {n: found[n].label for n in ("ConfirmationNo", "ConfirmedQuantity", "StartDate", "EndDate", "MaterialCode")} == {
        "ConfirmationNo": "Teyit no", "ConfirmedQuantity": "Teyit miktarı", "StartDate": "Başlangıç", "EndDate": "Bitiş", "MaterialCode": "Üretilen malzeme"}
    gone = {"OpNo", "SeqNo", "ConfirmedQty", "ActualConsumption", "StartAt", "EndAt"}
    assert not (gone | {"ResourceId"}) & set(core.keys()) and not (gone | {"ResourceCode"}) & set(found)
    assert found["StartDate"].kind == "date" and found["EndDate"].kind == "date"
    assert [c.name for c in stg_columns("ProductionConfirmation") if "UK" in c.info.get("key", "")] == ["LocationCode", "ConfirmationNo"]
    key = next(i for i in metadata.tables["core.ProductionConfirmation"].indexes if i.unique)
    assert [c.name for c in key.columns] == ["LocationId", "ConfirmationNo"] and str(key.dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("ProductionConfirmation").file_name == "smartchain_uretim-gerceklesmesi_v2.xlsx"


def test_work_order_v2():
    """K-124: anahtar lokasyonlu; yeni adlar; tip ve durum ham değer; bayraklar varsayılansız."""
    found = {f.name: f for f in fields("WorkOrder")}
    core = metadata.tables["core.WorkOrder"].c
    assert list(found) == ["LocationCode", "WorkOrderNo", "MaterialCode", "ProductionVersionCode", "ProductionOrderType", "Status", "Priority", "OrderedQuantity", "OpenQuantity", "CompletedQuantity", "ScrapQuantity", "Uom",
                           "StartDate", "DueDate", "ProjectCode", "CustomerCode", "SalesOrderNo", "SalesOrderLineNo", "SalesOrderLineItemNo", "ParentWorkOrderNo", "LastActivityDate",
                           "IsFixed", "IsReleased", "IsStarted", "IsProduction", "IsSubcontract", "IsRework", "IsOnHold", "IsCustomTracked"]
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "WorkOrderNo", "MaterialCode", "OrderedQuantity", "OpenQuantity", "DueDate"]
    assert {n: found[n].label for n in ("WorkOrderNo", "ProductionVersionCode", "ProductionOrderType", "Status", "Priority", "OrderedQuantity", "OpenQuantity", "CompletedQuantity", "ScrapQuantity", "Uom", "CustomerCode",
                                        "IsFixed", "IsReleased", "IsStarted", "IsProduction", "IsSubcontract", "IsRework", "IsOnHold", "IsCustomTracked")} == {
        "WorkOrderNo": "İş emri no", "ProductionVersionCode": "Üretim versiyonu", "ProductionOrderType": "İş emri tipi", "Status": "İş emri durumu", "Priority": "Öncelik", "OrderedQuantity": "İş emri miktarı",
        "OpenQuantity": "Açık miktar", "CompletedQuantity": "Tamamlanan miktar", "ScrapQuantity": "Hurda miktarı", "Uom": "Birim", "CustomerCode": "Müşteri",
        "IsFixed": "Sabit", "IsReleased": "Yayınlandı", "IsStarted": "Başladı", "IsProduction": "Üretim", "IsSubcontract": "Fason", "IsRework": "Yeniden işleme", "IsOnHold": "Beklemede", "IsCustomTracked": "Özel takip"}
    assert not {"OrderNo", "OrderType", "OrderQty", "OpenQty"} & set(core.keys()) and not {"OrderNo", "OrderType", "OrderQty", "OpenQty"} & set(found)
    assert found["ProductionOrderType"].values == () and found["ProductionOrderType"].blank == "Bilinmiyor; planda kullanılmaz" and core["ProductionOrderType"].server_default is None and core["ProductionOrderType"].nullable
    assert found["Status"].values == () and not found["Status"].required and found["Status"].blank == "Bilinmiyor; planda kullanılmaz" and core["Status"].nullable and core["Status"].type.length == 50 and core["ProductionOrderType"].type.length == 50
    assert found["Uom"].blank == "Temel birimde kabul edilir" and found["Uom"].ref_text == contract.UNIT_CODE
    for name in ("IsFixed", "IsReleased", "IsStarted", "IsProduction", "IsSubcontract", "IsRework", "IsOnHold", "IsCustomTracked"):
        assert found[name].blank in RULE_FILLED and core[name].server_default is None and core[name].nullable, name
    assert [c.name for c in stg_columns("WorkOrder") if "UK" in c.info.get("key", "")] == ["LocationCode", "WorkOrderNo"]
    key = next(i for i in metadata.tables["core.WorkOrder"].indexes if i.unique)
    assert [c.name for c in key.columns] == ["LocationId", "WorkOrderNo"] and str(key.dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("WorkOrder").file_name == "smartchain_is-emri_v3.xlsx"


def test_work_order_component_v2():
    """K-124: anahtar; yeni adlar; ağaçtaki alanlar var, alternatiflik yok."""
    found = {f.name: f for f in fields("WorkOrderComponent")}
    core = metadata.tables["core.WorkOrderComponent"].c
    assert list(found) == ["LocationCode", "WorkOrderNo", "MaterialCode", "OperationNo", "SequenceNo", "RequiredQuantity", "IssuedQuantity", "UnitUsage", "Uom", "ScrapRatio", "IsLotBasedUsage", "IsPhantom"]
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "WorkOrderNo", "MaterialCode", "RequiredQuantity"]
    assert {n: found[n].label for n in ("OperationNo", "SequenceNo", "RequiredQuantity", "IssuedQuantity", "UnitUsage", "Uom", "ScrapRatio", "IsLotBasedUsage", "IsPhantom")} == {
        "OperationNo": "Operasyon no", "SequenceNo": "Sıra no", "RequiredQuantity": "Gereken miktar", "IssuedQuantity": "Çekilen miktar", "UnitUsage": "Birim kullanım", "Uom": "Birim",
        "ScrapRatio": "Fire oranı", "IsLotBasedUsage": "Lot bazlı kullanım", "IsPhantom": "Hayalet bileşen"}
    assert "RemainingQuantity" in core and "RemainingQty" not in core  # K-127
    assert not {"RequiredQty", "IssuedQty", "AlternativeGroup", "AlternativePriority"} & set(core.keys()) and not {"RequiredQty", "IssuedQty", "AlternativeGroup", "AlternativePriority"} & set(found)
    assert found["Uom"].blank == "Temel birimde kabul edilir" and found["IssuedQuantity"].blank == "Yok sayılır" and found["ScrapRatio"].blank == "Yok sayılır"
    assert core["ScrapRatio"].type.scale == 4 and core["UnitUsage"].type.scale == 6
    assert [c.name for c in stg_columns("WorkOrderComponent") if "UK" in c.info.get("key", "")] == ["LocationCode", "WorkOrderNo", "MaterialCode", "OperationNo", "SequenceNo"]
    key = next(i for i in metadata.tables["core.WorkOrderComponent"].indexes if i.unique)
    assert [c.name for c in key.columns] == ["LocationId", "WorkOrderId", "MaterialId", "OperationNo", "SequenceNo"] and str(key.dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("WorkOrderComponent").file_name == "smartchain_is-emri-bileseni_v2.xlsx"


def test_work_order_operation_v2():
    """K-124: anahtar; yeni adlar; kaynak ya da grup; durum ham değer; rotadaki alanlar var, alternatiflik yok."""
    found = {f.name: f for f in fields("WorkOrderOperation")}
    core = metadata.tables["core.WorkOrderOperation"].c
    assert list(found) == ["LocationCode", "WorkOrderNo", "OperationNo", "SequenceNo", "OperationName", "ResourceCode", "ResourceGroupCode", "ResourceRole", "ResourceNumber", "PlannedConsumption", "ConfirmedConsumption",
                           "Status", "IsCompleted", "IsLotBasedUsage", "IsSubcontracted", "IsActive", "ProductionLocation", "TransferQuantity", "WaitingTimeHours", "TransferTimeHours"]
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "WorkOrderNo", "OperationNo", "SequenceNo"]
    assert found["ResourceCode"].blank == "Kaynak grubu da boşsa satır yüklenmez" and found["ResourceGroupCode"].blank == "Kaynak da boşsa satır yüklenmez" and core["ResourceId"].nullable
    assert found["Status"].values == () and found["Status"].label == "Operasyon durumu" and found["IsCompleted"].blank == "Yok sayılır" and core["IsCompleted"].server_default is None
    assert found["IsCompleted"].label == "Tamamlandı" and found["SequenceNo"].label == "Sıra no" and found["ResourceRole"].values == ("Primary", "Secondary")
    assert not {"OpNo", "SeqNo", "AlternativeGroup", "AlternativePriority", "Consumption"} & set(core.keys()) and not {"OpNo", "SeqNo", "AlternativeGroup", "AlternativePriority", "Consumption"} & set(found)
    assert [c.name for c in stg_columns("WorkOrderOperation") if "UK" in c.info.get("key", "")] == ["LocationCode", "WorkOrderNo", "OperationNo", "SequenceNo"]
    key = next(i for i in metadata.tables["core.WorkOrderOperation"].indexes if i.unique)
    assert [c.name for c in key.columns] == ["LocationId", "WorkOrderId", "OperationNo", "SequenceNo"] and str(key.dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("WorkOrderOperation").file_name == "smartchain_is-emri-operasyonu_v2.xlsx"


def test_stock_v2():
    """K-123: durum ham değer; bayraklar kuralla, varsayılansız; sahip müşteri ve sipariş; anahtar."""
    found = {f.name: f for f in fields("Stock")}
    core = metadata.tables["core.Stock"].c
    assert list(found) == ["LocationCode", "MaterialCode", "Warehouse", "LotNo", "Status", "ProjectCode", "CustomerCode", "SalesOrderNo", "SalesOrderLineNo", "SalesOrderLineItemNo", "Quantity", "Uom",
                           "QualityEntryDate", "ExpectedAcceptanceDate", "ExpiryDate", "IsAvailable", "IsInQuality", "IsBlocked", "IsActive", "IsCustomTracked"]
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "MaterialCode", "Quantity"]
    assert {n: found[n].label for n in ("Status", "CustomerCode", "SalesOrderNo", "SalesOrderLineNo", "ExpectedAcceptanceDate", "Uom", "IsAvailable", "IsInQuality", "IsBlocked", "IsActive", "IsCustomTracked")} == {
        "Status": "Stok durumu", "CustomerCode": "Sahip müşteri", "SalesOrderNo": "Sahip sipariş no", "SalesOrderLineNo": "Sahip sipariş satırı", "ExpectedAcceptanceDate": "Beklenen kabul tarihi",
        "Uom": "Birim", "IsAvailable": "Kullanılabilir", "IsInQuality": "Kalitede", "IsBlocked": "Bloke", "IsActive": "Aktif", "IsCustomTracked": "Özel takip"}
    assert "StockStatus" not in core and found["Status"].values == () and found["Status"].blank == "Bilinmiyor; planda kullanılmaz"
    assert core["Status"].type.length == 50 and core["Status"].nullable and core["Status"].server_default is None
    assert found["Uom"].blank == "Temel birimde kabul edilir" and found["Uom"].ref_text == contract.UNIT_CODE
    for name in ("IsAvailable", "IsInQuality", "IsBlocked", "IsActive", "IsCustomTracked"):
        assert found[name].blank in RULE_FILLED and core[name].server_default is None and core[name].nullable, name
    assert [c.name for c in stg_columns("Stock") if "UK" in c.info.get("key", "")] == ["LocationCode", "MaterialCode", "Warehouse", "LotNo", "Status", "ProjectCode", "CustomerCode", "SalesOrderNo", "SalesOrderLineNo", "SalesOrderLineItemNo"]
    assert [i.name for i in metadata.tables["stg.Stock"].indexes if i.unique] == ["UX_Stock_Current"] and found["SalesOrderLineItemNo"].label == "Bağlı sipariş alt satırı"
    assert found["ProjectCode"].label == "Sahip proje" and "müşteri ve sipariş boşsa" in found["ProjectCode"].description
    key = next(i for i in metadata.tables["core.Stock"].indexes if i.unique)
    assert [c.name for c in key.columns] == ["LocationId", "MaterialId", "Warehouse", "LotNo", "Status", "ProjectId", "CustomerId", "SalesOrderLineId"] and str(key.dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("Stock").file_name == "smartchain_stok_v3.xlsx"


def test_forecast_v2():
    """K-122: anahtar; birim, tip, teslim noktası, aktif; dönem tipi ve özel takip yok."""
    found = {f.name: f for f in fields("Forecast")}
    core = metadata.tables["core.Forecast"].c
    assert list(found) == ["LocationCode", "MaterialCode", "CustomerCode", "ProjectCode", "Period", "Type", "Quantity", "Uom", "DeliveryPoint", "IsActive"]
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "MaterialCode", "Period", "Quantity"]
    assert {n: found[n].label for n in ("Uom", "Type", "DeliveryPoint", "IsActive")} == {"Uom": "Birim", "Type": "Tahmin tipi", "DeliveryPoint": "Teslim noktası", "IsActive": "Aktif"}
    assert found["Type"].values == () and found["Type"].blank == "Bilinmiyor; planda kullanılmaz" and found["DeliveryPoint"].values == ("Başı", "Sonu")
    assert found["Uom"].blank == "Temel birimde kabul edilir" and found["Uom"].ref_text == contract.UNIT_CODE
    for name in ("DeliveryPoint", "IsActive"):
        assert found[name].blank in RULE_FILLED and core[name].server_default is None and core[name].nullable, name
    assert not {"PeriodType", "IsCustomTracked"} & set(core.keys())
    assert [c.name for c in stg_columns("Forecast") if "UK" in c.info.get("key", "")] == ["LocationCode", "MaterialCode", "CustomerCode", "ProjectCode", "Period", "Type"]
    key = next(i for i in metadata.tables["core.Forecast"].indexes if i.unique)
    assert [c.name for c in key.columns] == ["LocationId", "MaterialId", "CustomerId", "ProjectId", "Period", "Type"] and str(key.dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("Forecast").file_name == "smartchain_tahmin_v2.xlsx"


def test_sales_order_line_v2():
    """K-120: anahtar lokasyonlu; OpenQuantity; yeni miktarlar, birim ve bayraklar."""
    found = {f.name: f for f in fields("SalesOrderLine")}
    core = metadata.tables["core.SalesOrderLine"].c
    assert "OpenQty" not in found and "OpenQty" not in core
    assert {n: found[n].label for n in ("OpenQuantity", "OrderedQuantity", "DeliveredQuantity", "Uom", "IsActive", "IsOnHold", "IsCustomTracked")} == {
        "OpenQuantity": "Açık miktar", "OrderedQuantity": "Sipariş miktarı", "DeliveredQuantity": "Teslim edilen miktar", "Uom": "Sipariş birimi",
        "IsActive": "Aktif", "IsOnHold": "Beklemede", "IsCustomTracked": "Özel takip"}
    assert found["OpenQuantity"].required and not found["OrderedQuantity"].required and found["DeliveredQuantity"].blank == "Yok sayılır"
    assert found["Uom"].blank == "Temel birimde kabul edilir" and found["Uom"].ref_text == contract.UNIT_CODE
    for name in ("IsActive", "IsOnHold", "IsCustomTracked"):
        assert found[name].blank in RULE_FILLED and core[name].server_default is None and core[name].nullable, name
    assert found["LineItemNo"].blank == "Yok sayılır"  # değişmeyen varsayılan
    for name in ("Type", "Status"):  # K-127: ham değer, boşsa boş kalır
        assert found[name].values == () and found[name].blank == "Bilinmiyor; planda kullanılmaz" and not found[name].required and core[name].nullable and core[name].type.length == 50 and core[name].server_default is None, name
    assert found["IsQuote"].label == "Teklif" and found["IsQuote"].blank == "Yok sayılır" and core["IsQuote"].server_default is None and core["IsQuote"].nullable
    assert not {"IsClosed", "IsCancelled"} & set(core.keys())
    assert [c.name for c in stg_columns("SalesOrderLine") if "UK" in c.info.get("key", "")] == ["LocationCode", "OrderNo", "LineNo", "LineItemNo"]
    key = next(i for i in metadata.tables["core.SalesOrderLine"].indexes if i.unique)
    assert [c.name for c in key.columns] == ["LocationId", "OrderNo", "LineNo", "LineItemNo"] and str(key.dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("SalesOrderLine").file_name == "smartchain_satis-siparisi_v3.xlsx"


def test_customer_and_project_v2():
    """K-119: müşteri alanları; takip kuralı; IsClosed yerine IsActive."""
    customer = {f.name: f for f in fields("Customer")}
    assert "LocationCode" not in customer and [c.name for c in stg_columns("Customer") if "UK" in c.info.get("key", "")] == ["Code"]
    assert {n: customer[n].label for n in ("CustomerGroup", "IsActive", "Country", "City", "Region", "IsCustomTracked")} == {
        "CustomerGroup": "Müşteri grubu", "IsActive": "Aktif", "Country": "Ülke", "City": "Şehir", "Region": "Bölge", "IsCustomTracked": "Özel takip"}
    core, location = metadata.tables["core.Customer"].c, metadata.tables["core.Location"].c
    for name in ("Country", "City", "Region"):
        assert str(core[name].type) == str(location[name].type), name
    for name in ("IsActive", "IsCustomTracked"):
        assert customer[name].blank in RULE_FILLED and core[name].server_default is None and core[name].nullable, name
    group = {f.name: f for f in fields("ProjectGroup")}
    project = {f.name: f for f in fields("Project")}
    for table, found in (("ProjectGroup", group), ("Project", project)):
        assert "IsolationRule" not in found and "IsolationRule" not in metadata.tables[f"core.{table}"].c
        assert found["TrackingRule"].label == "Takip kuralı" and [c.name for c in stg_columns(table) if "UK" in c.info.get("key", "")] == ["Code"]
    assert group["TrackingRule"].values == ("Tam izolasyon", "Ortaktan beslenir", "Grup içi paylaşım") and group["TrackingRule"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez"
    assert group["Priority"].label == "Öncelik" and group["IsActive"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez"
    assert metadata.tables["core.ProjectGroup"].c.IsActive.server_default is None
    assert "IsClosed" not in project and project["IsActive"].label == "Aktif" and project["IsActive"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez"
    assert metadata.tables["core.Project"].c.IsActive.server_default is None and "default" not in metadata.tables["core.Project"].c.IsActive.info
    assert project["TrackingRule"].description == "Proje bazında takip kuralı (grubu ezer)"
    assert (contract.entity("Customer").version, contract.entity("ProjectGroup").version, contract.entity("Project").version) == (2, 2, 2)


def test_borrow_payback_v1():
    """K-119: yeni tablo; anahtar; proje referansları."""
    found = {f.name: f for f in fields("BorrowPayback")}
    assert list(found) == ["LocationCode", "MaterialCode", "LendingProjectCode", "BorrowingProjectCode", "BorrowedQuantity", "PaidBackQuantity", "BorrowDate", "PaybackDueDate"]
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "MaterialCode", "LendingProjectCode", "BorrowingProjectCode", "BorrowedQuantity", "BorrowDate"]
    assert {n: found[n].label for n in list(found)[2:]} == {
        "LendingProjectCode": "Ödünç veren proje", "BorrowingProjectCode": "Ödünç alan proje", "BorrowedQuantity": "Ödünç miktarı",
        "PaidBackQuantity": "Geri ödenen miktar", "BorrowDate": "Ödünç tarihi", "PaybackDueDate": "Geri ödeme tarihi"}
    assert found["LendingProjectCode"].ref_text == found["BorrowingProjectCode"].ref_text == "Proje tablosundaki kod"
    assert [c.name for c in stg_columns("BorrowPayback") if "UK" in c.info.get("key", "")] == ["LocationCode", "MaterialCode", "LendingProjectCode", "BorrowingProjectCode", "BorrowDate"]
    key = next(i for i in metadata.tables["core.BorrowPayback"].indexes if i.unique)
    assert [c.name for c in key.columns] == ["LocationId", "MaterialId", "LendingProjectId", "BorrowingProjectId", "BorrowDate"]
    assert str(key.dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("BorrowPayback").file_name == "smartchain_odunc-ve-geri-odeme_v1.xlsx" and contract.entity("BorrowPayback").data_class == TRANSACTION_DATA


def test_supplier_and_material_supplier_v2():
    """K-118: Supplier lokasyonsuz; MaterialSupplier anahtarı; tedarik süresi ikiye ayrıldı; ad değişiklikleri."""
    supplier = {f.name: f for f in fields("Supplier")}
    assert "LocationCode" not in supplier and [c.name for c in stg_columns("Supplier") if "UK" in c.info.get("key", "")] == ["Code"]
    assert {n: supplier[n].label for n in ("IsActive", "Country", "City")} == {"IsActive": "Aktif", "Country": "Ülke", "City": "Şehir"}
    assert supplier["IsActive"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez" and contract.entity("Supplier").file_name == "smartchain_tedarikci_v2.xlsx"
    location, core_supplier = metadata.tables["core.Location"].c, metadata.tables["core.Supplier"].c
    assert str(core_supplier.Country.type) == str(location.Country.type) and str(core_supplier.City.type) == str(location.City.type)
    assert core_supplier.IsActive.nullable and core_supplier.IsActive.server_default is None
    found = {f.name: f for f in fields("MaterialSupplier")}
    core = metadata.tables["core.MaterialSupplier"].c
    assert not {"LeadTimeDays", "QuotaPct", "MinOrderQty", "OrderMultiple", "MaxOrderQty"} & (set(found) | set(core.keys()))
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "MaterialCode", "SupplierCode"]
    assert {n: found[n].label for n in ("QuotaRatio", "FixedLeadTimeDays", "VariableLeadTimeDays", "MinimumOrderQuantity", "OrderLotSize", "MaximumOrderQuantity", "IsActive")} == {
        "QuotaRatio": "Kota oranı", "FixedLeadTimeDays": "Sabit tedarik süresi (gün)", "VariableLeadTimeDays": "Değişken tedarik süresi",
        "MinimumOrderQuantity": "Minimum sipariş miktarı", "OrderLotSize": "Sipariş katı", "MaximumOrderQuantity": "Maksimum sipariş miktarı", "IsActive": "Aktif"}
    assert found["FixedLeadTimeDays"].blank == found["VariableLeadTimeDays"].blank == "Bilinmiyor; planda kullanılmaz" and core.FixedLeadTimeDays.nullable
    assert found["IsActive"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez" and core.IsActive.server_default is None
    assert (core.QuotaRatio.type.precision, core.QuotaRatio.type.scale) == (6, 4) and found["QuotaRatio"].example == 0.3
    assert found["OrderLotSize"].description == "Sipariş miktarı bu sayının katı olur"
    assert [c.name for c in stg_columns("MaterialSupplier") if "UK" in c.info.get("key", "")] == ["LocationCode", "MaterialCode", "SupplierCode"]
    keys = {t: next(i for i in metadata.tables[f"{t}.MaterialSupplier"].indexes if i.unique) for t in ("core",)}
    assert [c.name for c in keys["core"].columns] == ["LocationId", "MaterialId", "SupplierId"]
    assert str(keys["core"].dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("MaterialSupplier").file_name == "smartchain_malzeme-tedarikcisi_v2.xlsx"


def test_resource_example_in_docs():
    """K-117: kimlik, ilişkiler ve kapasite birimi; öteki kapasite alanları sözleşmede yok, core'da durur."""
    found = {f.name: f for f in fields("Resource")}
    assert list(found) == ["LocationCode", "Code", "Name", "ResourceType", "IsEmployee", "IsMachine", "IsFurnace", "IsMold", "IsOther", "IsSubcontractor", "CapacityUnit",
                           "SubcontractorCode", "ProductionLocation", "IsActive", "IsCritical", "RemainingOverTimeYear", "RemainingOverTimeMonth"]
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "Code"]
    assert contract.base_counts("Resource") == (17, 2)
    assert found["ResourceType"].values == () and found["ResourceType"].blank == "Bilinmiyor; planda kullanılmaz" and "en çok 50" in found["ResourceType"].type_text
    assert {n: found[n].label for n in ("IsEmployee", "IsCritical", "SubcontractorCode", "ProductionLocation")} == {
        "IsEmployee": "İşçi", "IsCritical": "Kritik kaynak", "SubcontractorCode": "Fasoncu", "ProductionLocation": "Üretim yeri"}
    for name in ("IsEmployee", "IsMachine", "IsFurnace", "IsMold", "IsOther", "IsSubcontractor", "IsActive", "IsCritical"):
        assert found[name].blank in RULE_FILLED, name
    core = metadata.tables["core.Resource"].c
    for name in ("IsEmployee", "IsMachine", "IsFurnace", "IsMold", "IsOther", "IsSubcontractor", "IsActive", "IsCritical", "ResourceType"):
        assert core[name].nullable and core[name].server_default is None and "default" not in core[name].info, name
    assert not {"ResourceGroupId", "ResourceRole", "IsConstrained", "SupplierId"} & set(core.keys())
    assert found["CapacityUnit"].label == "Kapasite birimi" and found["CapacityUnit"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez" and found["CapacityUnit"].ref_text == contract.UNIT_CODE
    assert not found["CapacityUnit"].required and not core.CapacityUnit.nullable and core.CapacityUnit.server_default is None and "default" not in core.CapacityUnit.info  # K-117
    for name in ("DailyCapacity", "Quantity", "CapacitySource", "SubconPlanningType", "SubconFixedLeadTimeDays", "SubconVariableDaysPerUnit", "CalendarId"):
        assert name in core and name not in found, name
    assert core.DailyCapacity.nullable and core.CalendarId.nullable
    keys = {t: next(i for i in metadata.tables[f"{t}.Resource"].indexes if i.unique) for t in ("core",)}
    assert stg_key("Resource") == ["LocationCode", "Code"] and [c.name for c in keys["core"].columns] == ["LocationId", "Code"]


def test_resource_group_v2_and_new_tables():
    """K-117: grup bayrakları; atama ve devamsızlık tabloları; kalkan tablolar yok."""
    for gone in ("Worker", "CompetenceGroup", "WorkerCompetence", "WorkerAbsence"):
        assert contract.entity(gone) is None and f"stg.{gone}" not in metadata.tables and f"core.{gone}" not in metadata.tables
    assert "CompetenceGroupId" not in metadata.tables["core.ShiftPlan"].c
    group = {f.name: f for f in fields("ResourceGroup")}
    assert {n: group[n].label for n in ("IsResourceGroup", "IsCompetenceGroup", "IsActive")} == {"IsResourceGroup": "Kaynak grubu", "IsCompetenceGroup": "Yetkinlik grubu", "IsActive": "Aktif"}
    assert contract.entity("ResourceGroup").version == 2 and [c.name for c in stg_columns("ResourceGroup") if "UK" in c.info.get("key", "")] == ["LocationCode", "Code"]
    link = {f.name: f for f in fields("ResourceGroupAssignment")}
    assert list(link) == ["LocationCode", "ResourceGroupCode", "ResourceCode", "ValidFrom", "ValidTo"] and [f.name for f in link.values() if f.required] == ["LocationCode", "ResourceGroupCode", "ResourceCode"]
    assert contract.entity("ResourceGroupAssignment").file_name == "smartchain_kaynak-grubu-atamasi_v1.xlsx"
    absence = {f.name: f for f in fields("EmployeeAbsence")}
    assert list(absence) == ["LocationCode", "ResourceCode", "AbsenceType", "StartDate", "EndDate", "HoursPerDay"]
    assert absence["EndDate"].description == "Bitiş günü dahil" and absence["EndDate"].label == "Bitiş"
    assert absence["HoursPerDay"].blank == "Tam gün kabul edilir" and absence["AbsenceType"].values == () and absence["StartDate"].kind == "date"
    assert sorted(c.name for c in stg_columns("EmployeeAbsence") if "UK" in c.info.get("key", "")) == ["AbsenceType", "LocationCode", "ResourceCode", "StartDate"]
    assert contract.entity("EmployeeAbsence").file_name == "smartchain_calisan-izni_v1.xlsx"



def test_location_flags_and_type():
    """K-111: Type kalır, yanına dört bayrak gelir; yalnız Code zorunlu, boş bayrak önce kurala gider."""
    found = {f.name: f for f in fields("Location")}
    assert found["Type"].values == ("Tesis", "Depo", "Fason deposu") and found["Type"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez"
    assert [f.name for f in found.values() if f.required] == ["Code"] and found["Name"].blank == "Bilinmiyor; planda kullanılmaz"
    assert [c.name for c in stg_columns("Location") if c.info.get("key")] == ["Code"]
    assert {n: found[n].label for n in ("IsFactory", "IsDepot", "IsSubcontractor", "IsActive")} == {
        "IsFactory": "Tesis", "IsDepot": "Depo", "IsSubcontractor": "Fason deposu", "IsActive": "Aktif"}
    assert all(found[n].kind == "bool" for n in ("IsFactory", "IsDepot", "IsSubcontractor", "IsActive"))
    assert all(found[n].blank == "Yok sayılır" for n in ("IsFactory", "IsDepot", "IsSubcontractor"))  # K-138: varsayılan yok
    assert found["IsActive"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez"
    assert contract.entity("Location").file_name == "smartchain_lokasyon_v2.xlsx" and contract.base_counts("Location") == (13, 1)


def test_unit_has_no_template_only_core():
    """K-112: Birim yüklemede oluşur; entegrasyon tablosu ve şablonu yok, Decimals'ın varsayılanı yok."""
    assert contract.entity("UnitOfMeasure") is None and "stg.UnitOfMeasure" not in metadata.tables
    core = metadata.tables["core.UnitOfMeasure"]
    assert [c.name for c in core.columns] == ["Code", "Name", "Decimals"]
    assert core.c.Decimals.server_default is None and "default" not in core.c.Decimals.info


def test_uom_conversion_v2():
    """K-112: ad alanları, çarpanın açıklaması, anahtar MaterialCode + FromUom + ToUom."""
    found = {f.name: f for f in fields("UomConversion")}
    assert list(found) == ["MaterialCode", "FromUom", "FromUomName", "ToUom", "ToUomName", "Factor"]
    assert [f.name for f in found.values() if f.required] == ["FromUom", "ToUom", "Factor"]
    assert (found["FromUomName"].label, found["ToUomName"].label) == ("Kaynak birim adı", "Hedef birim adı")
    assert found["FromUomName"].blank == found["ToUomName"].blank == "Bilinmiyor; planda kullanılmaz" and found["MaterialCode"].blank == "Bütün malzemelere uygulanır"
    assert found["Factor"].label == "Çarpan" and found["Factor"].description == "1 kaynak birim = çarpan × hedef birim"
    assert [c.name for c in stg_columns("UomConversion") if "UK" in c.info.get("key", "")] == ["MaterialCode", "FromUom", "ToUom"]
    assert contract.entity("UomConversion").file_name == "smartchain_birim-donusumu_v2.xlsx"
    keys = {t: next(i for i in metadata.tables[f"{t}.UomConversion"].indexes if i.unique) for t in ("core",)}
    assert stg_key("UomConversion") == ["MaterialCode", "FromUom", "ToUom"]
    assert [c.name for c in keys["core"].columns] == ["MaterialId", "FromUom", "ToUom"]
    assert str(keys["core"].dialect_options["mssql"]["where"]) == "VersionTo IS NULL"  # K-63: tekillik güncel kayıtta


def test_routing_v2():
    """K-116: anahtar; ad değişiklikleri; kaynak ya da grup; yeni alanlar; işçilik alanları yok."""
    found = {f.name: f for f in fields("Routing")}
    core = metadata.tables["core.Routing"].c
    assert not {"OpNo", "SeqNo", "TransferLotQty", "LaborType", "LaborRefCode", "LaborBasis", "CrewSize", "LaborTime"} & set(found)
    assert not {"OpNo", "SeqNo", "TransferLotQty", "LaborType", "LaborRefId", "LaborBasis", "CrewSize", "LaborTime"} & set(core.keys())
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "RouteCode", "OperationNo", "SequenceNo", "Consumption"]
    assert found["ResourceCode"].blank == "Kaynak grubu da boşsa satır yüklenmez" and found["ResourceGroupCode"].blank == "Kaynak da boşsa satır yüklenmez"
    assert found["ResourceGroupCode"].ref_text == "Kaynak grubu tablosundaki kod" and found["ResourceCode"].ref_text == "Kaynak tablosundaki kod"
    assert core.ResourceId.nullable and core.ResourceGroupId.nullable and not core.LocationId.nullable
    assert {n: found[n].label for n in ("OperationNo", "SequenceNo", "TransferQuantity", "ResourceGroupCode", "IsActive", "IsLotBasedUsage", "ProductionLocation",
                                        "WaitingTimeHours", "TransferTimeHours", "AlternativeGroup", "AlternativePriority")} == {
        "OperationNo": "Operasyon no", "SequenceNo": "Sıra no", "TransferQuantity": "Transfer miktarı", "ResourceGroupCode": "Kaynak grubu", "IsActive": "Aktif",
        "IsLotBasedUsage": "Lot bazlı kullanım", "ProductionLocation": "Üretim yeri", "WaitingTimeHours": "Bekleme süresi (saat)",
        "TransferTimeHours": "Taşıma süresi (saat)", "AlternativeGroup": "Alternatif grubu", "AlternativePriority": "Alternatif önceliği"}
    assert found["IsActive"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez" and core.IsActive.server_default is None and core.IsActive.nullable
    assert found["ResourceRole"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez" and found["ResourceNumber"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez"  # değişmeyen varsayılanlar
    assert found["Consumption"].description == "Baz miktar için kaynak tüketimi (kaynağın kapasite biriminde)"
    assert [c.name for c in stg_columns("Routing") if "UK" in c.info.get("key", "")] == ["LocationCode", "RouteCode", "OperationNo", "SequenceNo"]
    keys = {t: next(i for i in metadata.tables[f"{t}.Routing"].indexes if i.unique) for t in ("core",)}
    assert stg_key("Routing") == ["LocationCode", "RouteCode", "OperationNo", "SequenceNo"]
    assert [c.name for c in keys["core"].columns] == ["LocationId", "RouteCode", "OperationNo", "SequenceNo"]
    assert str(keys["core"].dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("Routing").file_name == "smartchain_rota_v2.xlsx"


def test_bom_v2():
    """K-115: ağaç kendi koduyla; anahtar; yeni alanlar; ad değişiklikleri; versiyon bağı yok."""
    found = {f.name: f for f in fields("BOM")}
    core = metadata.tables["core.BOM"].c
    assert not {"ProductionVersionCode", "OpNo", "ScrapPct", "IsFixedQuantity"} & set(found)
    assert not {"ProductionVersionId", "OpNo", "ScrapPct", "IsFixedQuantity"} & set(core.keys())
    assert list(found) == ["LocationCode", "MaterialCode", "Code", "ComponentMaterialCode", "OperationNo", "SequenceNo", "Quantity", "ComponentUom",
                           "ScrapRatio", "IsPhantom", "IsLotBasedUsage", "AlternativeGroup", "AlternativePriority"]
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "MaterialCode", "Code", "ComponentMaterialCode", "Quantity"]
    assert {n: found[n].label for n in ("Code", "OperationNo", "SequenceNo", "ScrapRatio", "IsPhantom", "IsLotBasedUsage", "ComponentUom", "AlternativeGroup", "AlternativePriority")} == {
        "Code": "Ürün ağacı kodu", "OperationNo": "Operasyon no", "SequenceNo": "Sıra no", "ScrapRatio": "Fire oranı", "IsPhantom": "Hayalet bileşen",
        "IsLotBasedUsage": "Lot bazlı kullanım", "ComponentUom": "Bileşen birimi", "AlternativeGroup": "Alternatif grubu", "AlternativePriority": "Alternatif önceliği"}
    assert found["ComponentUom"].blank == "Temel birimde kabul edilir" and found["ComponentUom"].ref_text == contract.UNIT_CODE
    assert found["SequenceNo"].blank == "Bilinmiyor; planda kullanılmaz" and found["ScrapRatio"].example == 0.015
    assert (core.ScrapRatio.type.precision, core.ScrapRatio.type.scale) == (6, 4)
    assert not core.LocationId.nullable and not core.MaterialId.nullable and not core.Code.nullable
    expected = ["LocationCode", "MaterialCode", "Code", "ComponentMaterialCode", "OperationNo", "SequenceNo"]
    assert [c.name for c in stg_columns("BOM") if "UK" in c.info.get("key", "")] == expected
    keys = {t: next(i for i in metadata.tables[f"{t}.BOM"].indexes if i.unique) for t in ("core",)}
    assert stg_key("BOM") == expected
    assert [c.name for c in keys["core"].columns] == ["LocationId", "MaterialId", "Code", "ComponentMaterialId", "OperationNo", "SequenceNo"]
    assert str(keys["core"].dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("BOM").file_name == "smartchain_urun-agaci_v2.xlsx"


def test_production_version_v2():
    """K-114: anahtar LocationCode + MaterialCode + Code, yeni alanlar, BOMCode zorunlu, IsDefault yok."""
    found = {f.name: f for f in fields("ProductionVersion")}
    assert "IsDefault" not in found and "IsDefault" not in metadata.tables["core.ProductionVersion"].c
    assert list(found) == ["LocationCode", "MaterialCode", "Code", "Name", "Type", "IsActive", "Priority", "BaseQuantity", "BOMCode", "RouteCode", "ValidFrom", "ValidTo"]
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "MaterialCode", "Code", "BOMCode", "RouteCode"]
    assert {n: found[n].label for n in ("Name", "Type", "IsActive", "Priority", "BOMCode")} == {
        "Name": "Versiyon adı", "Type": "Versiyon tipi", "IsActive": "Aktif", "Priority": "Öncelik", "BOMCode": "Ürün ağacı kodu"}
    assert found["Type"].values == () and found["IsActive"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez" and found["Priority"].kind == "integer"
    core = metadata.tables["core.ProductionVersion"].c
    assert core.IsActive.nullable and core.IsActive.server_default is None and not core.BOMCode.nullable and not core.LocationId.nullable
    assert [c.name for c in stg_columns("ProductionVersion") if "UK" in c.info.get("key", "")] == ["LocationCode", "MaterialCode", "Code"]
    keys = {t: next(i for i in metadata.tables[f"{t}.ProductionVersion"].indexes if i.unique) for t in ("core",)}
    assert stg_key("ProductionVersion") == ["LocationCode", "MaterialCode", "Code"]
    assert [c.name for c in keys["core"].columns] == ["LocationId", "MaterialId", "Code"]
    assert str(keys["core"].dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("ProductionVersion").file_name == "smartchain_uretim-versiyonu_v2.xlsx"


def test_material_v3():
    """K-113: anahtar LocationCode + Code, yeni alanlar, ad değişiklikleri, kalkanlar."""
    found = {f.name: f for f in fields("Material")}
    assert not {"DefaultProcurement", "AssemblyScrapPct", "IsProjectTracked", "ProductionLeadTimeDays", "Ownership"} & (set(found) | set(metadata.tables["core.Material"].c.keys()))
    assert {n: found[n].label for n in ("MaterialType", "Brand", "PlannerCode", "MRPGroup", "IsActive", "IsSubcontractable", "IsCustomerSupplied",
                                        "StockCoverageDays", "QtyPerBox", "QtyPerPallet", "DefaultSupplyType", "ScrapRatio", "IsCustomTracked", "IsCritical", "IsNonStockable")} == {
        "MaterialType": "Malzeme tipi", "Brand": "Marka", "PlannerCode": "Planlamacı", "MRPGroup": "MRP grubu", "IsActive": "Aktif",
        "IsSubcontractable": "Fasona verilebilir", "IsCustomerSupplied": "Müşteri temin malzemesi", "StockCoverageDays": "Stok gün kapsamı",
        "QtyPerBox": "Kutu içi miktar", "QtyPerPallet": "Palet içi miktar", "DefaultSupplyType": "Tedarik türü", "ScrapRatio": "Fire oranı", "IsCustomTracked": "Özel takip", "IsCritical": "Kritik malzeme", "IsNonStockable": "Stok tutulamaz"}
    core = metadata.tables["core.Material"].c
    for name in ("IsActive", "IsSubcontractable", "IsCustomerSupplied", "IsCritical", "IsNonStockable"):  # boşsa kural; varsayılan yok
        assert found[name].blank in RULE_FILLED and core[name].server_default is None and "default" not in core[name].info and core[name].nullable
    assert (core.ScrapRatio.type.precision, core.ScrapRatio.type.scale) == (6, 4) and found["ScrapRatio"].example == 0.02
    assert found["DefaultSupplyType"].values == ("Üretim", "Satın alma", "Fason")
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "Code", "BaseUom"]
    assert [c.name for c in stg_columns("Material") if "UK" in c.info.get("key", "")] == ["LocationCode", "Code"]
    keys = {t: next(i for i in metadata.tables[f"{t}.Material"].indexes if i.unique) for t in ("core",)}
    assert stg_key("Material") == ["LocationCode", "Code"] and [c.name for c in keys["core"].columns] == ["LocationId", "Code"]
    assert str(keys["core"].dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("Material").file_name == "smartchain_malzeme_v4.xlsx"


def test_out_of_phase_flags_stay_in_contract():
    """K-117: IsFurnace ve IsMold sözleşmede; Faz 1 planlamada kullanılmaz."""
    found = {f.name: f for f in fields("Resource")}
    assert found["IsFurnace"].label == "Fırın" and "Faz 1 planlamada kullanılmaz" in found["IsFurnace"].description
    assert found["IsMold"].label == "Kalıp" and "Faz 1 planlamada kullanılmaz" in found["IsMold"].description



def test_additional_field_needs_a_label():
    found = {f.name: f for f in fields("Material", {"AdditionalText1": "Malzeme sınıfı", "Code": "Ürün kodu"})}
    assert found["AdditionalText1"].label == "Malzeme sınıfı" and found["Code"].label == "Ürün kodu"
    assert "AdditionalText2" not in found


def test_system_fields_are_not_in_template():
    for table in TABLES:
        assert not {"StagingRowId", "ImportBatchId", "RowStatus", "ErrorText", "Id", "VersionFrom", "VersionTo"} & {f.name for f in fields(table)}


@pytest.mark.parametrize("table", TABLES)
def test_examples_fit_the_field(table):
    """Örnek gerçek: tipi tutar, uzunluğa sığar, listede vardır, referansta kod biçiminde. Boş ya da yer tutucu yok."""
    columns = {c.name: c for c in stg_columns(table)}
    for f in fields(table):
        value = f.example
        assert value not in (None, "") and "ÖRN" not in str(value), f.name
        if f.kind == "text":
            assert isinstance(value, str) and len(value) <= columns[f.name].type.length, f.name
        elif f.kind == "bool":
            assert value in (0, 1), f.name
        elif f.kind == "integer":
            assert isinstance(value, int), f.name
        elif f.kind == "number":
            assert isinstance(value, (int, float)), f.name
        elif f.kind == "date":
            assert isinstance(value, date), f.name
        else:
            assert isinstance(value, datetime), f.name
        if f.values:
            assert value in f.values, f.name


def test_examples_file_has_no_stale_fields():
    saved = json.loads(contract.EXAMPLES.read_text(encoding="utf-8"))
    assert saved.keys() == set(TABLES)
    for table, values in saved.items():
        assert set(values) == {c.name for c in stg_columns(table) if not c.name.startswith("Additional")}, table


def test_additional_field_example_by_kind():
    found = {f.name: f for f in fields("Material", {"AdditionalText1": "Sınıf", "AdditionalNumber1": "Ağırlık"})}
    assert found["AdditionalText1"].example == "Örnek" and found["AdditionalNumber1"].example == 10


def test_contract_change_needs_a_new_version():
    """Sözleşme değişip sürüm artmazsa test düşer. Sürümü docs/03'te artırın, python db/generate.py, sonra bu dosyayı güncelleyin."""
    saved = json.loads(VERSIONS.read_text(encoding="utf-8"))
    current = {e.table: {"version": e.version, "contract": contract_hash(e.table)} for e in ENTITIES}
    assert saved.keys() == current.keys()
    stale = [t for t, c in current.items() if c["contract"] != saved[t]["contract"] and c["version"] <= saved[t]["version"]]
    assert stale == [], f"Sözleşme değişti, sürüm artmadı: {stale}. Yeni özetler: { {t: current[t]['contract'] for t in stale} }"
    assert [t for t, c in current.items() if c["version"] < saved[t]["version"]] == []


def test_synthetic_rows_fit_the_contract():
    """Temiz sentetik veri sözleşmeye uyar: zorunlu dolu, değer listede, Faz 1 dışı değer yok."""
    stg = to_staging(generate(date(2026, 10, 27)))
    for table, rows in stg.items():
        columns = {c.name: c for c in stg_columns(table)}
        for f in fields(table):
            for r in rows:
                value = r.get(f.name)
                if f.required:
                    assert value not in (None, ""), (table, f.name)
                if f.values and value not in (None, ""):
                    assert value in f.values, (table, f.name, value)
                length = getattr(columns[f.name].type, "length", None)
                if length and isinstance(value, str):
                    assert len(value) <= length, (table, f.name)

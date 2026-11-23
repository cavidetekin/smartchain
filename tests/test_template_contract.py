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
    assert contract.entity("Resource").file_name == "smartchain_kaynak_v4.xlsx" and contract.entity("yok") is None


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
    """Boşsa satır yüklenmeyen 90 alan zorunludur (K-180: rota ve iş emri operasyonunda kaynak grubu); her YOKSA kuralının somut karşılığı var."""
    every = [f for t in TABLES for f in fields(t)]
    assert sum(f.required for f in every) == 90 and all(f.blank == contract.BLANK_ROW_REJECTED for f in every if f.required)
    assert sum(1 for f in every if f.values) == 8  # Location.Type ham ERP değeri, listesi yok (K-143)
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


def test_work_order_operation_v3():
    """K-124, K-180: anahtar; kaynak alanı yok, kaynak grubu zorunlu; durum ham değer; rotadaki alanlar var, alternatiflik yok."""
    found = {f.name: f for f in fields("WorkOrderOperation")}
    core = metadata.tables["core.WorkOrderOperation"].c
    assert list(found) == ["LocationCode", "WorkOrderNo", "OperationNo", "SequenceNo", "OperationName", "ResourceGroupCode", "ResourceRole", "ResourceNumber", "PlannedConsumption", "ConfirmedConsumption",
                           "Status", "IsCompleted", "IsLotBasedUsage", "IsSubcontracted", "IsActive", "ProductionLocation", "TransferQuantity", "WaitingTimeHours", "TransferTimeHours"]
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "WorkOrderNo", "OperationNo", "SequenceNo", "ResourceGroupCode"]
    assert found["ResourceGroupCode"].blank == contract.BLANK_ROW_REJECTED and not core["ResourceGroupId"].nullable and "ResourceId" not in core
    assert found["Status"].values == () and found["Status"].label == "Operasyon durumu" and found["IsCompleted"].blank == "Yok sayılır" and core["IsCompleted"].server_default is None
    assert found["IsCompleted"].label == "Tamamlandı" and found["SequenceNo"].label == "Sıra no" and found["ResourceRole"].values == ("Primary", "Secondary")
    assert not {"OpNo", "SeqNo", "AlternativeGroup", "AlternativePriority", "Consumption"} & set(core.keys()) and not {"OpNo", "SeqNo", "AlternativeGroup", "AlternativePriority", "Consumption"} & set(found)
    assert contract.entity("WorkOrderOperation").file_name == "smartchain_is-emri-operasyonu_v3.xlsx"
    assert contract.entity("MaterialSupplier").file_name == "smartchain_malzeme-tedarikcisi_v2.xlsx"


def test_resource_keeps_identity_only():
    """K-180: kaynakta kimlik, ham tip (yalnız bilgi), aktif, üretim yeri, kalan fazla mesai; tip bayrakları, kritik, birim ve fasoncu grupta.
    Geçici kapasite alanları sözleşmede yok, core'da durur (7.9'da kalkar)."""
    found = {f.name: f for f in fields("Resource")}
    assert list(found) == ["LocationCode", "Code", "Name", "ResourceType", "IsActive", "ProductionLocation", "RemainingOverTimeYear", "RemainingOverTimeMonth"]
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "Code"]
    assert contract.base_counts("Resource") == (8, 2)
    assert found["ResourceType"].values == () and found["ResourceType"].blank == "Bilinmiyor; planda kullanılmaz" and "en çok 50" in found["ResourceType"].type_text
    assert "yalnız bilgi" in found["ResourceType"].description and found["ProductionLocation"].label == "Üretim yeri"
    assert found["IsActive"].blank in RULE_FILLED
    core = metadata.tables["core.Resource"].c
    gone = ("IsEmployee", "IsMachine", "IsFurnace", "IsMold", "IsOther", "IsSubcontractor", "IsCritical", "CapacityUnit", "SubcontractorId", "CapacitySource", "Quantity")
    assert not set(gone) & set(core.keys()) and not {"SubcontractorCode", *gone} & set(found)
    temporary = {"DailyCapacity", "SubconPlanningType", "SubconFixedLeadTimeDays", "SubconVariableDaysPerUnit", "CalendarId"}
    assert not temporary & set(core.keys()) and not temporary & set(found)               # 7.5'in geçici alanları 7.9'da kalktı (K-185)
    keys = {t: next(i for i in metadata.tables[f"{t}.Resource"].indexes if i.unique) for t in ("core",)}
    assert stg_key("Resource") == ["LocationCode", "Code"] and [c.name for c in keys["core"].columns] == ["LocationId", "Code"]
    assert contract.entity("Resource").version == 4


def test_resource_group_is_the_planning_unit():
    """K-180: tip bayrakları, kritik, kapasite birimi ve fasoncu kaynak grubunda; grup eşleşmesi tarihsiz ve ek alanlı; vardiya tabloları yok."""
    for gone in ("Worker", "CompetenceGroup", "WorkerCompetence", "WorkerAbsence", "ResourceGroupAssignment", "Shift", "ShiftPlan"):
        assert contract.entity(gone) is None and f"stg.{gone}" not in metadata.tables and f"core.{gone}" not in metadata.tables
    limit = metadata.tables["param.OvertimeLimit"].c                    # vardiyaya bağlı tablo kalktı; yenisi grup ya da kaynak için günlük limit (K-185)
    assert {"ResourceGroupId", "ResourceId", "DailyLimit", "ValidFrom"} <= set(limit.keys()) and not {"ShiftId", "WeeklyLimit"} & set(limit.keys())
    group = {f.name: f for f in fields("ResourceGroup")}
    assert list(group) == ["LocationCode", "Code", "Name", "Type", "IsEmployee", "IsMachine", "IsFurnace", "IsMold", "IsOther", "IsSubcontractor", "IsActive", "IsCritical",
                           "CapacityUnit", "SubcontractorCode"]
    assert [f.name for f in group.values() if f.required] == ["LocationCode", "Code"] and contract.base_counts("ResourceGroup") == (14, 2)
    assert {n: group[n].label for n in ("IsEmployee", "IsCritical", "SubcontractorCode", "IsActive", "Type")} == {
        "IsEmployee": "İşçi", "IsCritical": "Kritik", "SubcontractorCode": "Fasoncu", "IsActive": "Aktif", "Type": "Grup tipi"}
    for name in ("IsEmployee", "IsMachine", "IsFurnace", "IsMold", "IsOther", "IsSubcontractor", "IsActive", "IsCritical"):
        assert group[name].blank in RULE_FILLED, name
    core = metadata.tables["core.ResourceGroup"].c
    assert not {"IsResourceGroup", "IsCompetenceGroup"} & (set(core.keys()) | set(group))
    for name in ("IsEmployee", "IsMachine", "IsFurnace", "IsMold", "IsOther", "IsSubcontractor", "IsActive", "IsCritical", "Type"):
        assert core[name].nullable and core[name].server_default is None and "default" not in core[name].info, name
    assert group["CapacityUnit"].label == "Kapasite birimi" and group["CapacityUnit"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez" and group["CapacityUnit"].ref_text == contract.UNIT_CODE
    assert not group["CapacityUnit"].required and not core.CapacityUnit.nullable and core.CapacityUnit.server_default is None and "default" not in core.CapacityUnit.info  # K-117, K-180
    assert contract.entity("ResourceGroup").version == 3 and [c.name for c in stg_columns("ResourceGroup") if "UK" in c.info.get("key", "")] == ["LocationCode", "Code"]
    link = {f.name: f for f in fields("ResourceGroupMember")}
    assert list(link) == ["LocationCode", "ResourceGroupCode", "ResourceCode"] and [f.name for f in link.values() if f.required] == ["LocationCode", "ResourceGroupCode", "ResourceCode"]
    member = metadata.tables["core.ResourceGroupMember"].c
    assert not {"ValidFrom", "ValidTo"} & set(member.keys())
    assert [c for c in member.keys() if c.startswith("Additional")] == ["AdditionalText1", "AdditionalText2", "AdditionalText3", "AdditionalNumber1", "AdditionalNumber2"]  # K-59
    assert contract.entity("ResourceGroupMember").file_name == "smartchain_kaynak-grup-eslesmesi_v2.xlsx" and contract.entity("ResourceGroupMember").name == "Kaynak grup eşleşmesi"
    absence = {f.name: f for f in fields("EmployeeAbsence")}
    assert list(absence) == ["LocationCode", "ResourceCode", "AbsenceType", "StartDate", "EndDate", "HoursPerDay"]
    load = metadata.tables["planning.CapacityLoad"].c
    assert "ResourceGroupId" in load and "ResourceId" not in load and not load.ResourceGroupId.nullable     # plan ve yük grup düzeyinde
    assert "param.AllocationRule" not in metadata.tables                                                    # alokasyon Faz 1 dışı; tablo kalktı (K-193)


def test_routing_v3():
    """K-116, K-180: anahtar; ad değişiklikleri; kaynak alanı yok, kaynak grubu zorunlu; yeni alanlar; işçilik alanları yok."""
    found = {f.name: f for f in fields("Routing")}
    core = metadata.tables["core.Routing"].c
    assert not {"OpNo", "SeqNo", "TransferLotQty", "LaborType", "LaborRefCode", "LaborBasis", "CrewSize", "LaborTime"} & set(found)
    assert not {"OpNo", "SeqNo", "TransferLotQty", "LaborType", "LaborRefId", "LaborBasis", "CrewSize", "LaborTime"} & set(core.keys())
    assert [f.name for f in found.values() if f.required] == ["LocationCode", "RouteCode", "OperationNo", "SequenceNo", "ResourceGroupCode", "Consumption"]
    assert "ResourceCode" not in found and "ResourceId" not in core and found["ResourceGroupCode"].blank == contract.BLANK_ROW_REJECTED
    assert found["ResourceGroupCode"].ref_text == "Kaynak grubu tablosundaki kod"
    assert not core.ResourceGroupId.nullable and not core.LocationId.nullable
    assert contract.entity("Routing").version == 3
    assert {n: found[n].label for n in ("OperationNo", "SequenceNo", "TransferQuantity", "ResourceGroupCode", "IsActive", "IsLotBasedUsage", "ProductionLocation",
                                        "WaitingTimeHours", "TransferTimeHours", "AlternativeGroup", "AlternativePriority")} == {
        "OperationNo": "Operasyon no", "SequenceNo": "Sıra no", "TransferQuantity": "Transfer miktarı", "ResourceGroupCode": "Kaynak grubu", "IsActive": "Aktif",
        "IsLotBasedUsage": "Lot bazlı kullanım", "ProductionLocation": "Üretim yeri", "WaitingTimeHours": "Bekleme süresi (saat)",
        "TransferTimeHours": "Taşıma süresi (saat)", "AlternativeGroup": "Alternatif grubu", "AlternativePriority": "Alternatif önceliği"}
    assert found["IsActive"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez" and core.IsActive.server_default is None and core.IsActive.nullable
    assert found["ResourceRole"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez" and found["ResourceNumber"].blank == "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez"  # değişmeyen varsayılanlar
    assert found["Consumption"].description == "Baz miktar için kaynak tüketimi (kaynak grubunun kapasite biriminde)"
    assert [c.name for c in stg_columns("Routing") if "UK" in c.info.get("key", "")] == ["LocationCode", "RouteCode", "OperationNo", "SequenceNo"]
    keys = {t: next(i for i in metadata.tables[f"{t}.Routing"].indexes if i.unique) for t in ("core",)}
    assert stg_key("Routing") == ["LocationCode", "RouteCode", "OperationNo", "SequenceNo"]
    assert [c.name for c in keys["core"].columns] == ["LocationId", "RouteCode", "OperationNo", "SequenceNo"]
    assert str(keys["core"].dialect_options["mssql"]["where"]) == "VersionTo IS NULL"
    assert contract.entity("Routing").file_name == "smartchain_rota_v3.xlsx"


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
    """K-117, K-180: IsFurnace ve IsMold sözleşmede (kaynak grubunda); Faz 1 planlamada kullanılmaz."""
    found = {f.name: f for f in fields("ResourceGroup")}
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

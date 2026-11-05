"""Excel şablonu dosyası (fonksiyon 02, K-110): gerçek dosya üretilip openpyxl ile okunur. Veritabanı istemez."""
import io
from datetime import date, datetime

import pytest
from openpyxl import load_workbook

from app import __version__
from app.api.export import formats
from app.integration import contract
from app.integration.contract import ENTITIES, FIRST_DATA_ROW, fields
from app.integration.template import NOTE_HEADERS, NOTES_INTRO, write_template


def build(table="Resource", labels=None, **kw):
    buffer = io.BytesIO()
    write_template(buffer, contract.entity(table), labels, **kw)
    buffer.seek(0)
    return load_workbook(buffer)


def column_of(ws, name):
    return next(c.column_letter for c in ws[1] if c.value == name)


def notes(wb) -> dict[str, dict]:
    ws = wb["Açıklama"]
    headers = [c.value for c in ws[2]]
    return {r[0]: dict(zip(headers, r)) for r in ws.iter_rows(min_row=3, values_only=True)}


def rgb(hex_color: str) -> str:
    return "FF" + hex_color.lstrip("#").upper()


@pytest.mark.parametrize("entity", ENTITIES, ids=lambda e: e.table)
def test_every_table_builds(entity):
    wb = build(entity.table)
    assert wb.sheetnames == [entity.name, "Açıklama", "_Surum"]
    assert wb["_Surum"].sheet_state == "hidden" and wb.active.title == entity.name
    ws = wb[entity.name]
    assert FIRST_DATA_ROW == 2
    assert [c.value for c in ws[1]] == [f.name for f in fields(entity.table)]
    assert ws.max_row == 1 and ws.freeze_panes == "A2"  # 2. satır veri satırı
    assert not ws.data_validations.dataValidation  # zorlama yok (K-58)
    info = dict(wb["_Surum"].iter_rows(values_only=True))
    assert info["Tablo"] == entity.table and info["Sürüm"] == entity.version and info["İlk veri satırı"] == 2 and info["Smartchain"] == __version__


def test_required_headers_are_dark():
    ws = build()["Kaynak"]
    required, other = ws[f"{column_of(ws, 'Code')}1"], ws[f"{column_of(ws, 'Name')}1"]
    assert required.fill.fgColor.rgb == rgb(formats.color("indigo-900")) and required.font.color.rgb == rgb(formats.color("surface"))
    assert other.fill.fgColor.rgb == rgb(formats.color("indigo-100")) and other.font.color.rgb == rgb(formats.color("indigo-900"))
    darks = [c.value for c in ws[1] if c.fill.fgColor.rgb == rgb(formats.color("indigo-900"))]
    assert darks == [f.name for f in fields("Resource") if f.required] == ["LocationCode", "Code"]


def test_notes_sheet_layout():
    wb = build()
    ws = wb["Açıklama"]
    assert ws["A1"].value == NOTES_INTRO == "Koyu başlıklı alanlar zorunludur."
    assert tuple(c.value for c in ws[2]) == NOTE_HEADERS == ("Alan", "Etiket", "Açıklama", "Tip", "Boş bırakılırsa", "Smartchain değerleri", "Örnek")
    assert ws.freeze_panes == "A3"
    assert list(notes(wb)) == [f.name for f in fields("Resource")]


def test_description_empty_when_it_repeats():
    found = notes(build())
    assert found["Code"]["Etiket"] == "Kaynak kodu" and found["Code"]["Açıklama"] is None
    assert notes(build("Material"))["MaterialLevel"]["Açıklama"] is None  # yalnız değer listesiydi
    assert found["IsCritical"]["Açıklama"] == "1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır)"


def test_blank_column_is_concrete():
    found = notes(build())
    assert found["Code"]["Boş bırakılırsa"] == "Satır yüklenmez"
    assert found["IsMachine"]["Boş bırakılırsa"] == "Veri kuralıyla doldurulur"
    assert found["Name"]["Boş bırakılırsa"] == "Boş kalır"
    route = notes(build("Routing"))
    assert route["ResourceRole"]["Boş bırakılırsa"] == "Primary kabul edilir"
    assert route["IsSubcontracted"]["Boş bırakılırsa"] == "0 kabul edilir"


def test_location_template_v2():
    wb = build("Location")
    assert dict(wb["_Surum"].iter_rows(values_only=True))["Sürüm"] == 2
    ws = wb["Lokasyon"]
    assert "Type" in [c.value for c in ws[1]]
    assert [c.value for c in ws[1] if c.fill.fgColor.rgb == rgb(formats.color("indigo-900"))] == ["Code"]
    found = notes(wb)
    assert found["IsDepot"]["Etiket"] == "Depo" and found["IsDepot"]["Tip"] == "1 = Evet, 0 = Hayır" and found["IsDepot"]["Örnek"] == 1
    assert found["IsDepot"]["Açıklama"] == "Depo mu" and found["Type"]["Boş bırakılırsa"] == "Tesis kabul edilir"
    assert found["IsSubcontractor"]["Boş bırakılırsa"] == "Veri kuralıyla doldurulur; kural yoksa 0 kabul edilir"
    assert found["IsActive"]["Boş bırakılırsa"] == "Veri kuralıyla doldurulur; kural yoksa 1 kabul edilir"
    assert found["Name"]["Boş bırakılırsa"] == "Boş kalır"


def test_uom_conversion_template_v2():
    wb = build("UomConversion")
    assert dict(wb["_Surum"].iter_rows(values_only=True))["Sürüm"] == 2
    assert [c.value for c in wb["Birim dönüşümü"][1]] == ["MaterialCode", "FromUom", "FromUomName", "ToUom", "ToUomName", "Factor"]
    found = notes(wb)
    assert found["Factor"]["Etiket"] == "Çarpan" and found["Factor"]["Açıklama"] == "1 kaynak birim = çarpan × hedef birim"
    assert (found["FromUomName"]["Etiket"], found["FromUomName"]["Örnek"]) == ("Kaynak birim adı", "Metre")
    assert (found["ToUomName"]["Etiket"], found["ToUomName"]["Örnek"]) == ("Hedef birim adı", "Kilogram")


def test_smartchain_values():
    route = notes(build("Routing"))
    assert route["ResourceRole"]["Smartchain değerleri"] == "Primary, Secondary. ERP'deki farklı değerler veri kuralıyla bu değerlere çevrilir."
    assert route["ResourceGroupCode"]["Smartchain değerleri"] == "Kaynak grubu tablosundaki kod"
    assert route["OperationName"]["Smartchain değerleri"] is None
    assert notes(build("Material"))["BaseUom"]["Smartchain değerleri"] == "Birim kodu; yeni kod yüklemede oluşur"  # K-112
    assert notes(build("UomConversion"))["FromUom"]["Smartchain değerleri"] == "Birim kodu; yeni kod yüklemede oluşur"
    assert notes(build())["SubcontractorCode"]["Smartchain değerleri"] == "Tedarikçi tablosundaki kod"


def test_material_reference_and_resource_templates():
    assert dict(build("MaterialReference")["_Surum"].iter_rows(values_only=True))["Sürüm"] == 1
    found = notes(build("MaterialReference"))
    assert found["TimeFactor"]["Etiket"] == "Süre çarpanı" and found["TimeFactor"]["Boş bırakılırsa"] == "1 kabul edilir" and found["ReferenceMaterialCode"]["Boş bırakılırsa"] == "Satır yüklenmez"
    wb = build("Resource")
    assert dict(wb["_Surum"].iter_rows(values_only=True))["Sürüm"] == 3
    found = notes(wb)
    assert found["CapacityUnit"]["Etiket"] == "Kapasite birimi" and found["CapacityUnit"]["Boş bırakılırsa"] == "Veri kuralıyla doldurulur" and found["CapacityUnit"]["Örnek"] == "SAAT"


def test_purchase_and_confirmation_templates_v2():
    for table, version in (("PurchaseOrderLine", 3), ("ProductionConfirmation", 2)):
        assert dict(build(table)["_Surum"].iter_rows(values_only=True))["Sürüm"] == version, table
    found = notes(build("PurchaseOrderLine"))
    assert not {"OrderNo", "OpenQty"} & set(found) and found["OrderType"]["Smartchain değerleri"] is None and found["OrderType"]["Boş bırakılırsa"] == "Boş kalır" and found["Status"]["Boş bırakılırsa"] == "Boş kalır"
    assert found["IsPurchaseRequest"]["Etiket"] == "Satın alma talebi" and found["IsPurchaseRequest"]["Boş bırakılırsa"] == "Veri kuralıyla doldurulur"
    wb = build("ProductionConfirmation")
    found = notes(wb)
    assert not {"OpNo", "SeqNo", "ResourceCode", "ActualConsumption", "StartAt", "EndAt", "ConfirmedQty"} & set(found)
    assert found["ConfirmationNo"]["Boş bırakılırsa"] == "Satır yüklenmez" and found["ConfirmationNo"]["Örnek"] == "T-5002"
    ws = wb["Üretim gerçekleşmesi"]
    assert [c.value for c in ws[1]] == ["LocationCode", "ConfirmationNo", "WorkOrderNo", "MaterialCode", "ConfirmedQuantity", "StartDate", "EndDate"]


def test_work_order_templates_v2():
    for table, version in (("WorkOrder", 3), ("WorkOrderComponent", 2), ("WorkOrderOperation", 2)):
        assert dict(build(table)["_Surum"].iter_rows(values_only=True))["Sürüm"] == version, table
    found = notes(build("WorkOrder"))
    assert not {"OrderNo", "OrderType", "OrderQty", "OpenQty"} & set(found)
    assert found["ProductionOrderType"]["Smartchain değerleri"] is None and found["Status"]["Smartchain değerleri"] is None and found["Status"]["Boş bırakılırsa"] == "Boş kalır"
    assert found["IsFixed"]["Etiket"] == "Sabit" and found["IsFixed"]["Boş bırakılırsa"] == "Veri kuralıyla doldurulur" and found["ProductionVersionCode"]["Örnek"] == "V1"
    found = notes(build("WorkOrderComponent"))
    assert found["UnitUsage"]["Etiket"] == "Birim kullanım" and found["Uom"]["Boş bırakılırsa"] == "Bileşenin temel birimi kabul edilir"
    found = notes(build("WorkOrderOperation"))
    assert not {"OpNo", "SeqNo"} & set(found) and found["ResourceCode"]["Boş bırakılırsa"] == "Kaynak grubu da boşsa satır yüklenmez"
    assert found["ResourceRole"]["Smartchain değerleri"] == "Primary, Secondary. ERP'deki farklı değerler veri kuralıyla bu değerlere çevrilir." and found["Status"]["Smartchain değerleri"] is None


def test_stock_template_v2():
    wb = build("Stock")
    assert dict(wb["_Surum"].iter_rows(values_only=True))["Sürüm"] == 3
    found = notes(wb)
    assert "StockStatus" not in found and found["Status"]["Etiket"] == "Stok durumu" and found["Status"]["Smartchain değerleri"] is None and found["Status"]["Örnek"] == "Karantina"
    assert found["Status"]["Boş bırakılırsa"] == "Boş kalır" and found["IsAvailable"]["Boş bırakılırsa"] == "Veri kuralıyla doldurulur"
    assert found["SalesOrderLineNo"]["Etiket"] == "Sahip sipariş satırı" and found["Uom"]["Boş bırakılırsa"] == "Malzemenin temel birimi kabul edilir"


def test_forecast_template_v2():
    wb = build("Forecast")
    assert dict(wb["_Surum"].iter_rows(values_only=True))["Sürüm"] == 2
    found = notes(wb)
    assert found["DeliveryPoint"]["Etiket"] == "Teslim noktası" and found["DeliveryPoint"]["Smartchain değerleri"] == "Başı, Sonu. ERP'deki farklı değerler veri kuralıyla bu değerlere çevrilir."
    assert found["Type"]["Etiket"] == "Tahmin tipi" and found["Type"]["Smartchain değerleri"] is None and found["Type"]["Örnek"] == "Satış tahmini"
    assert found["Uom"]["Boş bırakılırsa"] == "Malzemenin temel birimi kabul edilir"


def test_sales_order_template_v2():
    wb = build("SalesOrderLine")
    assert dict(wb["_Surum"].iter_rows(values_only=True))["Sürüm"] == 3
    found = notes(wb)
    assert found["Type"]["Smartchain değerleri"] is None and found["Type"]["Boş bırakılırsa"] == "Boş kalır" and found["Status"]["Smartchain değerleri"] is None
    assert found["IsQuote"]["Etiket"] == "Teklif" and found["IsQuote"]["Boş bırakılırsa"] == "Veri kuralıyla doldurulur"
    assert found["Uom"]["Etiket"] == "Sipariş birimi" and found["Uom"]["Boş bırakılırsa"] == "Malzemenin temel birimi kabul edilir" and found["Uom"]["Smartchain değerleri"] == "Birim kodu; yeni kod yüklemede oluşur"
    assert found["IsOnHold"]["Açıklama"] == "Kredi, teknik onay ya da müşteri talebiyle bekletilen satır" and found["IsOnHold"]["Tip"] == "1 = Evet, 0 = Hayır"
    assert found["OrderedQuantity"]["Açıklama"] == "Satırın orijinal miktarı"


def test_project_templates_v2_and_borrow_v1():
    assert notes(build("Project"))["IsActive"]["Boş bırakılırsa"] == "Veri kuralıyla doldurulur"
    rule = notes(build("ProjectGroup"))["TrackingRule"]
    assert rule["Etiket"] == "Takip kuralı" and rule["Smartchain değerleri"].startswith("Tam izolasyon, Ortaktan beslenir, Grup içi paylaşım.")
    wb = build("BorrowPayback")
    assert dict(wb["_Surum"].iter_rows(values_only=True))["Sürüm"] == 1 and wb.sheetnames[0] == "Ödünç ve geri ödeme"
    assert notes(wb)["BorrowDate"]["Örnek"] == datetime(2026, 10, 20)
    assert notes(build("Customer"))["IsCustomTracked"]["Açıklama"] == "Bu müşterinin talepleri ortak havuzdan değil, müşteriye ayrılmış olarak takip edilir"


def test_material_supplier_template_v2():
    wb = build("MaterialSupplier")
    assert dict(wb["_Surum"].iter_rows(values_only=True))["Sürüm"] == 2
    found = notes(wb)
    assert found["QuotaRatio"]["Açıklama"] == "Oran olarak kota (0,30 = %30)" and found["QuotaRatio"]["Örnek"] == 0.3
    assert found["FixedLeadTimeDays"]["Boş bırakılırsa"] == "Boş kalır" and found["VariableLeadTimeDays"]["Açıklama"] == "Birim başına gün; miktar arttıkça uzayan kısım"
    assert notes(build("Supplier"))["Country"]["Tip"] == "Metin, en çok 100"


def test_employee_absence_says_end_day_is_included():
    found = notes(build("EmployeeAbsence"))
    assert found["EndDate"]["Etiket"] == "Bitiş" and found["EndDate"]["Açıklama"] == "Bitiş günü dahil"


def test_types_and_examples():
    found = notes(build())
    assert found["IsCritical"]["Tip"] == "1 = Evet, 0 = Hayır" and found["Code"]["Tip"] == "Metin, en çok 50"
    assert found["Code"]["Örnek"] == "TORNA-01"
    assert isinstance(found["RemainingOverTimeYear"]["Örnek"], (int, float)) and isinstance(notes(build("Routing"))["ResourceNumber"]["Örnek"], int)
    assert not [r for r in found.values() if "ÖRN" in str(r["Örnek"])]
    day = notes(build("ProductionVersion"))["ValidTo"]["Örnek"]
    assert day == datetime(2026, 12, 31)


def test_additional_field_appears_with_its_label_version_stays():
    wb = build("Material", labels={"AdditionalNumber1": "Birim ağırlık"})
    assert "AdditionalNumber1" in [c.value for c in wb["Malzeme"][1]] and "AdditionalNumber2" not in [c.value for c in wb["Malzeme"][1]]
    extra = notes(wb)["AdditionalNumber1"]
    assert extra["Etiket"] == "Birim ağırlık" and extra["Açıklama"] is None and extra["Örnek"] == 10
    assert dict(wb["_Surum"].iter_rows(values_only=True))["Sürüm"] == 3  # ek alan etiketi sürümü artırmaz; Malzeme v3 sözleşmeden (K-113)


def test_routing_template_v2():
    wb = build("Routing")
    assert dict(wb["_Surum"].iter_rows(values_only=True))["Sürüm"] == 2
    ws = wb["Rota"]
    assert not {"OpNo", "SeqNo", "LaborType", "CrewSize"} & {c.value for c in ws[1]}
    assert [c.value for c in ws[1] if c.fill.fgColor.rgb == rgb(formats.color("indigo-900"))] == ["LocationCode", "RouteCode", "OperationNo", "SequenceNo", "Consumption"]
    found = notes(wb)
    assert found["ResourceCode"]["Boş bırakılırsa"] == "Kaynak grubu da boşsa satır yüklenmez"
    assert found["ResourceGroupCode"]["Etiket"] == "Kaynak grubu" and found["ResourceGroupCode"]["Örnek"] == "MONTAJ"
    assert found["WaitingTimeHours"]["Etiket"] == "Bekleme süresi (saat)" and found["WaitingTimeHours"]["Tip"] == "Sayı"
    assert found["IsLotBasedUsage"]["Tip"] == "1 = Evet, 0 = Hayır" and "hazırlık süresi" in found["IsLotBasedUsage"]["Açıklama"]


def test_bom_template_v2():
    wb = build("BOM")
    assert dict(wb["_Surum"].iter_rows(values_only=True))["Sürüm"] == 2
    ws = wb["Ürün ağacı"]
    header = [c.value for c in ws[1]]
    assert not {"ProductionVersionCode", "OpNo", "ScrapPct", "IsFixedQuantity"} & set(header)
    assert [c.value for c in ws[1] if c.fill.fgColor.rgb == rgb(formats.color("indigo-900"))] == ["LocationCode", "MaterialCode", "Code", "ComponentMaterialCode", "Quantity"]
    found = notes(wb)
    assert found["ComponentUom"]["Boş bırakılırsa"] == "Bileşenin temel birimi kabul edilir" and found["ComponentUom"]["Smartchain değerleri"] == "Birim kodu; yeni kod yüklemede oluşur"
    assert found["ScrapRatio"]["Açıklama"] == "Oran olarak fire (0,05 = %5)" and found["ScrapRatio"]["Örnek"] == 0.015
    assert found["IsLotBasedUsage"]["Etiket"] == "Lot bazlı kullanım" and found["IsLotBasedUsage"]["Tip"] == "1 = Evet, 0 = Hayır"
    assert found["AlternativeGroup"]["Açıklama"] == "Aynı grup koduna sahip satırlar birbirinin alternatifidir"


def test_production_version_template_v2():
    wb = build("ProductionVersion")
    assert dict(wb["_Surum"].iter_rows(values_only=True))["Sürüm"] == 2
    ws = wb["Üretim versiyonu"]
    assert "IsDefault" not in [c.value for c in ws[1]]
    assert [c.value for c in ws[1] if c.fill.fgColor.rgb == rgb(formats.color("indigo-900"))] == ["LocationCode", "MaterialCode", "Code", "BOMCode", "RouteCode"]
    found = notes(wb)
    assert found["BOMCode"]["Etiket"] == "Ürün ağacı kodu" and found["BOMCode"]["Boş bırakılırsa"] == "Satır yüklenmez" and found["BOMCode"]["Örnek"] == "B-MAM-001"
    assert found["Type"]["Etiket"] == "Versiyon tipi" and found["Type"]["Smartchain değerleri"] is None and found["Priority"]["Tip"] == "Tam sayı"
    assert found["IsActive"]["Boş bırakılırsa"] == "Veri kuralıyla doldurulur"


def test_material_template_v3():
    wb = build("Material")
    header = [c.value for c in wb["Malzeme"][1]]
    assert "Ownership" not in header and "ProductionLeadTimeDays" not in header
    found = notes(wb)
    assert found["ScrapRatio"]["Etiket"] == "Fire oranı" and found["ScrapRatio"]["Açıklama"] == "Oran olarak fire (0,05 = %5)" and found["ScrapRatio"]["Örnek"] == 0.02
    assert found["IsCustomerSupplied"]["Boş bırakılırsa"] == "Veri kuralıyla doldurulur" and found["IsCustomerSupplied"]["Tip"] == "1 = Evet, 0 = Hayır"
    assert found["IsCustomTracked"]["Etiket"] == "Özel takip" and "talep kaydından gelir" in found["IsCustomTracked"]["Açıklama"]
    assert found["IsCritical"]["Etiket"] == "Kritik malzeme" and found["IsCritical"]["Boş bırakılırsa"] == "Veri kuralıyla doldurulur"
    assert found["MRPGroup"]["Etiket"] == "MRP grubu" and found["MRPGroup"]["Açıklama"] == "MRP grubu; planlama parametreleri aynı olan malzemeleri gruplar"


def test_rows_are_typed_and_text_stays_text():
    rows = [{"Code": "=1+1", "Name": "001", "IsCritical": True, "RemainingOverTimeYear": -5.5, "RemainingOverTimeMonth": 3}]
    ws = build(rows=rows)["Kaynak"]
    value = lambda name: ws[f"{column_of(ws, name)}{FIRST_DATA_ROW}"]  # noqa: E731
    assert value("Code").value == "=1+1" and value("Code").data_type == "s"
    assert value("Name").value == "001" and value("Name").number_format == "@"
    assert value("IsCritical").value == 1 and value("RemainingOverTimeYear").value == -5.5 and value("RemainingOverTimeMonth").value == 3


def test_dates_keep_their_format():
    ws = build("ProductionVersion", rows=[{"MaterialCode": "M-1", "ValidFrom": date(2026, 11, 4)}])["Üretim versiyonu"]
    cell = ws[f"{column_of(ws, 'ValidFrom')}{FIRST_DATA_ROW}"]
    assert cell.value == datetime(2026, 11, 4) and cell.number_format == "dd.mm.yyyy"

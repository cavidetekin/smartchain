"""Kirli hâl: entegrasyon biçiminde Excel ve beklenen hatalar (docs/11, K-78). Veritabanı gerekmez."""
import json
from datetime import date, datetime

import pytest
from openpyxl import load_workbook

from app.data.synthetic import dataset as d
from app.data.synthetic.dataset import generate
from app.data.synthetic.excel import FIRST_DATA_ROW, labels_of, stg_entities, to_staging, write_excel
from app.integration import contract

DAY = date(2026, 10, 27)


@pytest.fixture(scope="module")
def written(tmp_path_factory):
    out = tmp_path_factory.mktemp("kirli")
    ds = generate(DAY)
    manifest = write_excel(ds, out)
    return ds, out, manifest


def read(out, entity):
    ws = load_workbook(out / f"{entity}.xlsx", read_only=True).worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    header, data = rows[0], rows[FIRST_DATA_ROW - 1:]
    return list(header), [dict(zip(header, r)) for r in data]


def norm(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, datetime) and v.time() == datetime.min.time():
        return v.date()
    return v


def test_one_file_per_integration_entity_with_stg_headers(written):
    ds, out, manifest = written
    files = sorted(p.name for p in out.glob("*.xlsx"))
    assert files == sorted(f"{e}.xlsx" for e in stg_entities()) and len(files) == 23
    for entity in stg_entities():
        header, data = read(out, entity)
        assert header == [f.name for f in contract.fields(entity, labels_of(entity))]  # şablonla aynı (K-110)
        assert len(data) == manifest["files"][f"{entity}.xlsx"]
    assert (out / "beklenen-hatalar.json").exists()


def test_units_in_the_files(written):
    """K-112: Birim dosyası yok; dönüşüm dosyası adları taşır."""
    _, out, _ = written
    assert not (out / "UnitOfMeasure.xlsx").exists()
    header, data = read(out, "UomConversion")
    assert header == ["MaterialCode", "FromUom", "FromUomName", "ToUom", "ToUomName", "Factor"] and len(data) == 4
    assert {(r["FromUomName"], r["ToUomName"]) for r in data} == {("Metre", "Kilogram")}


def test_purchase_and_confirmation_files(written):
    """K-125: yeni adlar; bayraklar ham tiple uyumlu; gerçekleşme iş emri bazlı."""
    _, out, _ = written
    header, data = read(out, "PurchaseOrderLine")
    assert not {"OrderNo", "OpenQty"} & set(header) and {r["OrderType"] for r in data} == {"Satın alma", "Fason", "Satın alma talebi"}
    assert all((r["IsPurchaseRequest"], r["IsPurchase"], r["IsSubcontract"]) == (int(r["OrderType"] == "Satın alma talebi"), int(r["OrderType"] == "Satın alma"), int(r["OrderType"] == "Fason")) for r in data)
    assert {r["IsActive"] for r in data} == {1} and {r["ReceivedQuantity"] for r in data} == {0} and all(r["Uom"] is None and r["CustomerCode"] is None and r["SalesOrderNo"] is None for r in data)
    header, data = read(out, "ProductionConfirmation")
    assert not {"OpNo", "SeqNo", "ResourceCode", "ActualConsumption", "ConfirmedQty", "StartAt", "EndAt"} & set(header)
    orders = {r["WorkOrderNo"]: r for r in read(out, "WorkOrder")[1]}
    started = {n for n, r in orders.items() if r["Status"] == "Başladı"}
    assert {r["WorkOrderNo"] for r in data} == started and len(data) == len(started)
    assert all(r["ConfirmationNo"] == f"T-{r['WorkOrderNo']}" and r["MaterialCode"] == orders[r["WorkOrderNo"]]["MaterialCode"] and r["ConfirmedQuantity"] == orders[r["WorkOrderNo"]]["CompletedQuantity"] for r in data)


def test_work_order_files(written):
    """K-124: yeni adlar dosyada; bayraklar ham durumla uyumlu; bileşen ve operasyon kaynaktan gelir."""
    _, out, _ = written
    header, data = read(out, "WorkOrder")
    assert not {"OrderNo", "OrderType", "OrderQty", "OpenQty"} & set(header) and {r["ProductionOrderType"] for r in data} == {"Üretim"} and {r["ProductionVersionCode"] for r in data} == {"V1"}
    assert all(r["IsStarted"] == int(r["Status"] == "Başladı") and r["IsReleased"] == 1 and r["IsProduction"] == 1 and r["CompletedQuantity"] == r["OrderedQuantity"] - r["OpenQuantity"] for r in data)
    assert [r["WorkOrderNo"] for r in data if r["CustomerCode"]] == ["WO-5001"] and [r["SalesOrderLineItemNo"] for r in data if r["SalesOrderNo"]] == [0]
    header, data = read(out, "WorkOrderComponent")
    assert not {"RequiredQty", "IssuedQty"} & set(header) and {r["LocationCode"] for r in data} == {d.LOCATION_CODE} and all(r["UnitUsage"] and r["SequenceNo"] and r["Uom"] is None for r in data)
    header, data = read(out, "WorkOrderOperation")
    assert not {"OpNo", "SeqNo"} & set(header) and {r["IsCompleted"] for r in data} == {0} and {r["ResourceRole"] for r in data} == {"Primary"} and all(r["ResourceCode"] or r["ResourceGroupCode"] for r in data)


def test_stock_file(written):
    """K-123: ham durum dosyada; bayraklar durumla uyumlu; sahip müşteri, sipariş ve birim boş."""
    ds, out, _ = written
    header, data = read(out, "Stock")
    assert "StockStatus" not in header and {r["Status"] for r in data} == {"Serbest", "Kalitede", "Bloke"}
    assert all((r["IsAvailable"], r["IsInQuality"], r["IsBlocked"]) == (int(r["Status"] == "Serbest"), int(r["Status"] == "Kalitede"), int(r["Status"] == "Bloke")) for r in data)
    assert {r["IsActive"] for r in data} == {1} and all(r["IsCustomTracked"] == (1 if r["ProjectCode"] else 0) for r in data)
    assert all(r["CustomerCode"] is None and r["SalesOrderNo"] is None and r["SalesOrderLineNo"] is None and r["Uom"] is None for r in data)
    assert [r["Status"] for r in data if r["ExpectedAcceptanceDate"]] == ["Kalitede"]
    lot = next(r for r in data if r["Status"] == "Kalitede")
    assert lot["QualityEntryDate"].date() < ds.generated_on < lot["ExpectedAcceptanceDate"].date()


def test_sales_order_file(written):
    """K-120: yeni adlar dosyada; birim boş (temel birim); projeli satır özel takipli."""
    _, out, _ = written
    header, data = read(out, "SalesOrderLine")
    assert "OpenQty" not in header and all(r["OpenQuantity"] == r["OrderedQuantity"] and r["DeliveredQuantity"] == 0 and r["Uom"] is None for r in data)
    assert {r["IsActive"] for r in data} == {1} and {r["IsOnHold"] for r in data} == {0} and {r["LineItemNo"] for r in data} == {0}
    assert all(r["IsCustomTracked"] == (1 if r["ProjectCode"] else 0) for r in data)
    assert all(r["IsQuote"] == int(r["Type"] == "Teklif") for r in data) and {r["IsQuote"] for r in data} == {0, 1}  # K-127


def test_customer_project_and_borrow_files(written):
    """K-119: yeni adlar dosyada; ödünç kaydı kodlarla."""
    _, out, _ = written
    header, data = read(out, "Project")
    assert not {"IsolationRule", "IsClosed"} & set(header) and {r["IsActive"] for r in data} == {1} and {r["TrackingRule"] for r in data} == {"Ortaktan beslenir", "Tam izolasyon"}
    _, customers = read(out, "Customer")
    assert {r["Code"] for r in customers if r["IsCustomTracked"] == 1} == {"MUS-A"} and all(r["Country"] and r["Region"] and r["City"] for r in customers)
    _, borrow = read(out, "BorrowPayback")
    assert [(r["LocationCode"], r["MaterialCode"], r["LendingProjectCode"], r["BorrowingProjectCode"], r["BorrowedQuantity"]) for r in borrow] == [(d.LOCATION_CODE, "MAM-006", "PRJ-01", "PRJ-02", 2)]


def test_supplier_files(written):
    """K-118: lokasyon ve yeni adlar dosyada; kota oran olarak."""
    _, out, _ = written
    header, data = read(out, "MaterialSupplier")
    assert not {"LeadTimeDays", "QuotaPct", "MinOrderQty", "OrderMultiple", "MaxOrderQty"} & set(header)
    assert {r["LocationCode"] for r in data} == {d.LOCATION_CODE} and all(r["FixedLeadTimeDays"] is not None for r in data)
    assert {r["QuotaRatio"] for r in data if r["QuotaRatio"] is not None} == {0.3} and {r["IsActive"] for r in data} == {1}
    _, suppliers = read(out, "Supplier")
    assert all(r["Country"] == "Türkiye" and r["City"] and r["IsActive"] == 1 for r in suppliers)


def test_resource_side_files(written):
    """K-117: kalkan tablo dosyası yok; kapasite alanı dosyada yok; yeni dosyalar dolu."""
    _, out, _ = written
    for gone in ("Worker", "CompetenceGroup", "WorkerCompetence", "WorkerAbsence"):
        assert not (out / f"{gone}.xlsx").exists()
    header, data = read(out, "Resource")
    assert {r["CapacityUnit"] for r in data} == {"SAAT"} and not {"ResourceGroupCode", "ResourceRole", "DailyCapacity", "Quantity", "CapacitySource", "SubconPlanningType", "SupplierCode", "IsConstrained"} & set(header)
    assert sum(1 for r in data if r["IsEmployee"] == 1) == 25 and {r["SubcontractorCode"] for r in data if r["IsSubcontractor"] == 1} == {"TED-07", "TED-08"}
    _, groups = read(out, "ResourceGroup")
    assert {r["Code"] for r in groups if r["IsCompetenceGroup"] == 1} == {"CG-CNC", "CG-MON", "CG-KAL"}
    _, assignments = read(out, "ResourceGroupAssignment")
    assert {"LocationCode", "ResourceGroupCode", "ResourceCode"} <= set(assignments[0]) and any(r["ResourceGroupCode"] == "CG-MON" for r in assignments)
    _, absences = read(out, "EmployeeAbsence")
    assert {r["AbsenceType"] for r in absences} == {"İzin", "Rapor"} and [r["HoursPerDay"] for r in absences if r["ResourceCode"] == "W-021"] == [4]


def test_routing_file(written):
    """K-116: işçilik ayrı satır, kaynak grubu dolu; eski alanlar yok."""
    _, out, _ = written
    header, data = read(out, "Routing")
    assert not {"OpNo", "SeqNo", "TransferLotQty", "LaborType", "LaborRefCode", "LaborBasis", "CrewSize", "LaborTime"} & set(header)
    labor = [r for r in data if r["ResourceRole"] == "Secondary"]
    assert labor and all(r["ResourceCode"] is None and r["ResourceGroupCode"] == d.LABOR_GROUP and r["ResourceNumber"] == 2 and r["SequenceNo"] == 2 for r in labor)
    assert all(r["ResourceCode"] or r["ResourceGroupCode"] for r in data) and {r["LocationCode"] for r in data} == {d.LOCATION_CODE}
    assert all(r["ResourceCode"] and not r["ResourceGroupCode"] for r in data if r["ResourceRole"] == "Primary")


def test_bom_file(written):
    """K-115: ağaç kodu versiyonun BOMCode'u; eski bağ ve adlar yok."""
    _, out, _ = written
    header, data = read(out, "BOM")
    assert not {"ProductionVersionCode", "OpNo", "ScrapPct", "IsFixedQuantity"} & set(header)
    assert {r["LocationCode"] for r in data} == {d.LOCATION_CODE} and all(r["Code"] == f"B-{r['MaterialCode']}" for r in data)
    assert {r["SequenceNo"] for r in data} == {1} and {r["IsLotBasedUsage"] for r in data} == {0} and {r["IsPhantom"] for r in data} == {0}
    _, versions = read(out, "ProductionVersion")
    assert {r["Code"] for r in data} <= {v["BOMCode"] for v in versions}


def test_production_version_file(written):
    """K-114: lokasyon, ürün ağacı kodu ve yeni alanlar dolu; IsDefault yok."""
    _, out, _ = written
    header, data = read(out, "ProductionVersion")
    assert "IsDefault" not in header and data
    assert {r["LocationCode"] for r in data} == {d.LOCATION_CODE} and all(r["BOMCode"] == f"B-{r['MaterialCode']}" for r in data)
    assert {(r["Code"], r["Type"], r["IsActive"], r["Priority"]) for r in data} == {("V1", "Standart", 1, 1)}


def test_material_file(written):
    """K-113: kalkan alan yok; müşteri temin ve özel takip yeni adlarıyla."""
    _, out, _ = written
    header, data = read(out, "Material")
    assert not {"Ownership", "ProductionLeadTimeDays", "DefaultProcurement", "IsProjectTracked", "AssemblyScrapPct"} & set(header)
    assert {r["Code"] for r in data if r["IsCustomerSupplied"] == 1} == {d.ISOLATED_MATERIAL} and all(r["IsActive"] == 1 for r in data)
    assert {r["Code"] for r in data if r["IsCustomTracked"] == 1} == {"MAM-006"}
    assert d.LATE_MATERIAL in {r["Code"] for r in data if r["IsCritical"] == 1} and all(r["IsCritical"] in (0, 1) for r in data)
    assert any(r["IsSubcontractable"] == 1 for r in data) and {r["DefaultSupplyType"] for r in data} == {"Üretim", "Satın alma"}
    marked = {r["Code"]: r for r in data if r["IsNonStockable"] == 1}
    assert set(marked) == set(d.NON_STOCKABLE) and all(r["IsNonStockable"] in (0, 1) for r in data)  # K-113 eki
    assert {r["IsProducible"] for r in marked.values()} == {0, 1}  # biri üretilen, biri satın alınan
    _, stock = read(out, "Stock")
    assert not set(d.NON_STOCKABLE) & {r["MaterialCode"] for r in stock}  # temiz veride uyarı çıkmaz (3.4)


def test_location_flags_in_the_file(written):
    """K-111: ORM-01 hem tesis hem depo; Type yanında durur."""
    _, out, _ = written
    header, data = read(out, "Location")
    assert "Type" in header and len(data) == 1 and data[0]["Type"] == "Tesis"
    assert [data[0][n] for n in ("IsFactory", "IsDepot", "IsSubcontractor", "IsActive")] == [1, 1, 0, 1]


def test_same_layout_as_template(written):
    ds, out, manifest = written
    wb = load_workbook(out / "Resource.xlsx")
    assert wb.sheetnames == ["Kaynak", "Açıklama", "_Surum"] and wb["_Surum"].sheet_state == "hidden"
    info = dict(wb["_Surum"].iter_rows(values_only=True))
    assert info["Tablo"] == "Resource" and info["Sürüm"] == 3 and info["Set"] == d.SET_NAME and info["Tohum"] == ds.seed
    assert FIRST_DATA_ROW == 2 and manifest["first_data_row"] == 2 and info["İlk veri satırı"] == 2
    ws = wb["Kaynak"]
    assert not ws.data_validations.dataValidation and ws.freeze_panes == "A2"
    assert ws["A2"].value == d.LOCATION_CODE  # veri 2. satırda


def test_only_labelled_additional_fields(written):
    ds, out, _ = written
    header, rows = read(out, "Material")
    assert [h for h in header if h.startswith("Additional")] == ["AdditionalText1"] and len(header) == 34
    assert {r["AdditionalText1"] for r in rows} >= {"A", "B", "C"}
    notes = {r[0]: r[1] for r in load_workbook(out / "Material.xlsx")["Açıklama"].iter_rows(min_row=3, values_only=True)}
    assert notes["AdditionalText1"] == "Malzeme sınıfı"


def test_filled_field_missing_from_template_stops_the_writer(tmp_path, monkeypatch):
    from app.data.synthetic import excel
    monkeypatch.setattr(excel, "labels_of", lambda entity: {})  # etiket kalkarsa Material.AdditionalText1 dolu kalır
    with pytest.raises(ValueError, match="AdditionalText1"):
        write_excel(generate(DAY), tmp_path)


def test_expected_errors_are_where_listed(written):
    ds, out, manifest = written
    saved = json.loads((out / "beklenen-hatalar.json").read_text(encoding="utf-8"))
    assert {e["code"] for e in saved["errors"]} == {"H1", "H2", "H3", "H4"}
    for e in saved["errors"]:
        header, data = read(out, e["file"].removesuffix(".xlsx"))
        for row in e["rows"]:
            assert norm(data[row - FIRST_DATA_ROW][e["field"]]) == e["value"], e
        assert e["severity"] in ("hata", "uyarı") and e["message"] and e["step"]
    h4 = next(e for e in saved["errors"] if e["code"] == "H4")
    _, mats = read(out, "Material")
    a, b = (mats[r - FIRST_DATA_ROW] for r in h4["rows"])
    assert a["Code"] == b["Code"] == d.ISOLATED_MATERIAL and a["Name"] != b["Name"]


def test_isolated_and_missing_route(written):
    ds, out, _ = written
    _, routing = read(out, "Routing")
    assert not [r for r in routing if r["RouteCode"] == f"R-{d.NO_ROUTE_PART}"]
    _, pv = read(out, "ProductionVersion")
    assert [r["RouteCode"] for r in pv if r["MaterialCode"] == d.NO_ROUTE_PART] == [f"R-{d.NO_ROUTE_PART}"]
    for entity in stg_entities():  # H4'teki malzeme başka dosyada geçmez: zincirleme hata yok
        if entity != "Material":
            _, data = read(out, entity)
            assert d.ISOLATED_MATERIAL not in {v for r in data for v in r.values()}, entity


def test_other_rows_equal_clean_state(written):
    """Hatalı satırlar dışındaki her satır temiz hâlin stg biçimiyle aynı: ETL sonrası = temiz − beklenen fark."""
    ds, out, manifest = written
    clean = to_staging(ds)
    error_rows = {}
    for e in manifest["errors"]:
        if e["severity"] == "hata":  # uyarılı satır (H1) yüklenir, temiz hâlde de vardır
            error_rows.setdefault(e["file"].removesuffix(".xlsx"), set()).update(e["rows"])
    for entity in stg_entities():
        header, data = read(out, entity)
        kept = [{k: norm(v) for k, v in r.items()} for i, r in enumerate(data, FIRST_DATA_ROW)
                if i not in error_rows.get(entity, set())]
        expected = [{k: norm(v) for k, v in r.items() if k in header} for r in clean[entity]]  # etiketsiz ek alan dosyada yok
        if entity == "Routing":
            expected = [r for r in expected if r["RouteCode"] != f"R-{d.NO_ROUTE_PART}"]
        if entity in ("PurchaseOrderLine", "BOM", "Material"):  # değiştirilen satırlar temizden düşer
            dropped = {("PurchaseOrderLine", "PO-2060"), ("BOM", "ALT-012|SAT-010"), ("Material", d.ISOLATED_MATERIAL)}
            keyf = {"PurchaseOrderLine": lambda r: r["PurchaseOrderNo"],
                    "BOM": lambda r: f"{r['MaterialCode']}|{r['ComponentMaterialCode']}",
                    "Material": lambda r: r["Code"]}[entity]
            expected = [r for r in expected if (entity, keyf(r)) not in dropped]
        assert kept == expected, entity


def test_codes_resolve_outside_error_rows(written):
    ds, out, manifest = written
    _, mats = read(out, "Material")
    material_codes = {r["Code"] for r in mats}
    bad = {e["value"] for e in manifest["errors"] if e["code"] == "H2"}
    for entity in stg_entities():
        _, data = read(out, entity)
        for r in data:
            for k in ("MaterialCode", "ComponentMaterialCode"):
                if r.get(k) is not None and r[k] not in bad:
                    assert r[k] in material_codes, (entity, k, r[k])

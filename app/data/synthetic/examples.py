"""Kirli hâlde hazır validasyon kurallarının örnekleri (docs/11, K-137): her hazır kural için en az bir satır.

Örnekler kendi anahtarlarıyla eklenen satırlardır ("V" ile başlayan kodlar); bilerek konmuş durumlara ve H1–H4'e
dokunmaz. Tablolar arası kurallar için karşı tablodaki satırlar da eklenir. Bir satır birden fazla kuralı tetikleyebilir;
beklenen kurallar satırda yazılıdır. Temiz veride çıkan tek bulgu "Yeni birim: M"dir (UOM.NEW_UOM, Bilgi).
"""
from datetime import date

from app.integration.contract import stg_columns
from app.integration.structural import key_fields

from . import dataset as d

LOC = d.LOCATION_CODE
FAR = date(2027, 3, 1)


class Examples:
    def __init__(self, stg: dict[str, list[dict]]):
        self.stg = stg
        self.expected: list[dict] = []

    def base(self, table: str, **match) -> dict:
        rows = [r for r in self.stg[table] if all(r.get(k) == v for k, v in match.items())]
        if not rows:
            raise KeyError(f"{table}: {match}")
        return dict(rows[0])

    def empty(self, table: str) -> dict:
        return {c.name: None for c in stg_columns(table)}

    def add(self, table: str, base: dict, rules: list[str] | None, with_rules: list[str] | None = None, **values) -> dict:
        """with_rules: demo veri kuralları uygulandıktan sonra beklenen kurallar (K-141); verilmezse kurallar yokkenki gibi."""
        row = {**base, **values}
        self.stg.setdefault(table, []).append(row)
        self.expect(table, row, rules or [], example=True, with_rules=with_rules)  # kural tetiklemeyen yardımcı satır da (ör. karşı tablodaki kaynak)
        return row

    def expect(self, table: str, row: dict, rules: list[str], example: bool = False, with_rules: list[str] | None = None) -> None:
        self.expected.append({"table": table, "key": {k: row.get(k) for k in key_fields(table)}, "rules": sorted(rules), "example": example,
                              "rules_with_demo": sorted(rules if with_rules is None else with_rules)})


def add_examples(stg: dict[str, list[dict]]) -> list[dict]:
    """Örnek satırları stg'ye ekler; beklenen (tablo, anahtar, kurallar) listesi döner."""
    x = Examples(stg)
    for row in stg["UomConversion"]:  # temiz veri: M hiçbir malzemenin temel birimi değil
        if row["FromUom"] == "M":
            x.expect("UomConversion", row, ["UOM.NEW_UOM"])

    # Lokasyon
    x.add("Location", x.base("Location", Code=LOC), ["LOC.NO_FLAG"], Code="V-LOC-1", Name="Örnek lokasyon", IsFactory=False, IsDepot=False, IsSubcontractor=False)

    # Birim dönüşümü
    uom = x.base("UomConversion", MaterialCode="HAM-001")
    x.add("UomConversion", uom, ["UOM.FACTOR"], MaterialCode="HAM-001", FromUom="ADET", ToUom="KG", FromUomName="Adet", ToUomName="Kilogram", Factor=0.0)
    x.add("UomConversion", uom, ["UOM.SAME_UOM"], MaterialCode="HAM-002", FromUom="KG", ToUom="KG", FromUomName="Kilogram", ToUomName="Kilogram", Factor=1.0)
    x.add("UomConversion", uom, ["UOM.INVERSE"], MaterialCode="HAM-004", FromUom="ADET", ToUom="KG", FromUomName="Adet", ToUomName="Kilogram", Factor=2.0)
    x.add("UomConversion", uom, ["UOM.INVERSE"], MaterialCode="HAM-004", FromUom="KG", ToUom="ADET", FromUomName="Kilogram", ToUomName="Adet", Factor=2.0)

    # Malzeme
    mat = {**x.base("Material", Code="HAM-001"), "MinLot": None, "MaxLot": None, "LotMultiple": None, "QtyPerBox": None, "QtyPerPallet": None,
           "SafetyStock": None, "StockCoverageDays": None, "MaxStock": None, "ScrapRatio": None}
    m = lambda n, rules, **v: x.add("Material", mat, rules, Code=f"V-MAT-{n}", Name=f"Örnek malzeme {n}", **v)  # noqa: E731
    m(1, ["MAT.MINLOT_MAXLOT"], MinLot=10.0, MaxLot=5.0)
    m(2, ["MAT.SAFETY_MAX"], SafetyStock=50.0, MaxStock=10.0)
    m(3, ["MAT.ZERO_PACK"], LotMultiple=0.0)
    m(4, ["MAT.SUPPLY_CONFLICT"], DefaultSupplyType="Üretim", IsProducible=False)
    m(5, ["MAT.NO_SUPPLY", "MAT.SUPPLY_CONFLICT"], IsProducible=False, IsPurchasable=False, IsSubcontractable=False)
    m(6, ["MAT.SAFETY_COVERAGE"], SafetyStock=5.0, StockCoverageDays=3.0)
    m(7, ["ALL.RATIO_RANGE"], ScrapRatio=1.5)
    m(8, ["ALL.OUT_OF_LIST"], MaterialLevel="Ham madde")

    # Üretim versiyonu (kendi ağaç kodlarıyla: öteki versiyonların baz miktarını etkilemez)
    pv = {**x.base("ProductionVersion", MaterialCode="MAM-001"), "ValidFrom": None, "ValidTo": None}
    x.add("ProductionVersion", pv, ["PV.BASEQTY"], Code="V-PV-1", BOMCode="V-BOM-1", BaseQuantity=0.0)
    x.add("ProductionVersion", pv, ["PV.BASEQTY_DIFFERS"], Code="V-PV-2", BOMCode="V-BOM-2", BaseQuantity=1.0)
    x.add("ProductionVersion", pv, ["PV.BASEQTY_DIFFERS"], Code="V-PV-3", BOMCode="V-BOM-2", BaseQuantity=2.0)
    x.add("ProductionVersion", pv, ["PV.EXPIRED"], Code="V-PV-4", BOMCode="V-BOM-4", IsActive=True, ValidTo=date(2020, 1, 1))

    # Ürün ağacı
    bom = {**x.base("BOM", MaterialCode="ALT-005", ComponentMaterialCode="PRC-013"), "AlternativeGroup": None, "AlternativePriority": None}
    x.add("BOM", bom, ["BOM.SELF"], MaterialCode="V-CYC-S", Code="V-B-1", ComponentMaterialCode="V-CYC-S")
    x.add("BOM", bom, ["BOM.CYCLE"], MaterialCode="V-CYC-A", Code="V-B-2", ComponentMaterialCode="V-CYC-B")
    x.add("BOM", bom, ["BOM.CYCLE"], MaterialCode="V-CYC-B", Code="V-B-3", ComponentMaterialCode="V-CYC-A")
    x.add("BOM", bom, ["BOM.ZERO_QTY"], Code="V-B-4", Quantity=0.0)
    x.add("BOM", bom, ["BOM.PRIORITY_NO_GROUP"], Code="V-B-5", AlternativePriority=1)
    x.add("BOM", bom, ["BOM.SINGLE_ALTERNATIVE"], Code="V-B-6", AlternativeGroup="V-ALT")

    # Kaynak, kaynak grubu, atama (tablolar arası örnekler için de)
    res = x.base("Resource", Code="T-01")
    r = lambda n, rules, **v: x.add("Resource", res, rules, Code=f"V-RES-{n}", Name=f"Örnek kaynak {n}", **v)  # noqa: E731
    r(1, None, CapacityUnit="ADET")
    r(2, ["RES.TYPE_FLAGS"], IsEmployee=True)
    r(3, ["RES.SUBCON_CONFLICT"], SubcontractorCode="TED-07")
    r(4, ["RES.MONTH_YEAR"], RemainingOverTimeMonth=50.0, RemainingOverTimeYear=10.0)
    r(5, ["RES.PHASE1_UNUSED"], IsMachine=False, IsFurnace=True)
    group = x.base("ResourceGroup", Code="TORNA")
    x.add("ResourceGroup", group, None, Code="V-RG-1", Name="Örnek karışık birimli grup")
    x.add("ResourceGroup", group, ["RG.NO_TYPE"], Code="V-RG-2", Name="Örnek tipsiz grup", IsResourceGroup=False, IsCompetenceGroup=False)
    rga = x.base("ResourceGroupAssignment", ResourceGroupCode="TORNA", ResourceCode="T-01")
    x.add("ResourceGroupAssignment", rga, None, ResourceGroupCode="V-RG-1", ResourceCode="V-RES-1")
    x.add("ResourceGroupAssignment", rga, None, ResourceGroupCode="V-RG-1", ResourceCode="T-01")
    x.add("ResourceGroupAssignment", rga, ["RGA.COMPETENCE_NOT_EMPLOYEE"], ResourceGroupCode="CG-CNC", ResourceCode="T-02")

    # Rota
    rtg = {**x.base("Routing", RouteCode="R-MAM-001", OperationNo=10, SequenceNo=1), "ResourceGroupCode": None, "AlternativeGroup": None, "AlternativePriority": None}
    rt = lambda n, rules, **v: x.add("Routing", rtg, rules, RouteCode=f"V-R-{n}", **v)  # noqa: E731
    rt(1, ["RTG.NO_RESOURCE"], ResourceCode=None)
    rt(2, ["RTG.RESOURCE_NUMBER"], ResourceNumber=0)
    rt(3, ["RTG.ZERO_CONSUMPTION"], Consumption=0.0)
    rt(4, ["RTG.PRIORITY_NO_GROUP"], AlternativePriority=1)
    rt(5, ["RTG.NOT_MEMBER"], ResourceCode="T-01", ResourceGroupCode="MONTAJ")
    rt(6, ["RTG.GROUP_UNIT"], ResourceCode=None, ResourceGroupCode="V-RG-1")
    rt(7, ["RTG.SUBCON_RESOURCE"], ResourceCode="T-01", IsSubcontracted=True)

    # Benzetilen ürün (temiz veride yok; hepsi Hata, ana veriye girmez)
    ref = {**x.empty("MaterialReference"), "LocationCode": LOC, "TimeFactor": 1.0}
    x.add("MaterialReference", ref, ["REF.SELF"], MaterialCode="MAM-001", ReferenceMaterialCode="MAM-001")
    x.add("MaterialReference", ref, ["REF.CYCLE"], MaterialCode="MAM-002", ReferenceMaterialCode="MAM-003")
    x.add("MaterialReference", ref, ["REF.CYCLE"], MaterialCode="MAM-003", ReferenceMaterialCode="MAM-002")
    x.add("MaterialReference", ref, ["REF.TIMEFACTOR"], MaterialCode="MAM-004", ReferenceMaterialCode="MAM-005", TimeFactor=0.0)

    # Çalışan izni (uzak tarihlerde: plan ufkunu etkilemez)
    workers = [row["Code"] for row in stg["Resource"] if row.get("IsEmployee") and row["Code"].startswith("W-")]
    absence = {**x.base("EmployeeAbsence", ResourceCode="W-007"), "HoursPerDay": None}
    x.add("EmployeeAbsence", absence, ["ABS.HOURS"], ResourceCode=workers[0], AbsenceType="İzin", StartDate=FAR, EndDate=date(2027, 3, 2), HoursPerDay=30.0)
    x.add("EmployeeAbsence", absence, ["ABS.NOT_EMPLOYEE"], ResourceCode="T-03", AbsenceType="İzin", StartDate=date(2027, 3, 5), EndDate=date(2027, 3, 6))
    x.add("EmployeeAbsence", absence, ["ABS.OVERLAP"], ResourceCode=workers[1], AbsenceType="İzin", StartDate=date(2027, 4, 1), EndDate=date(2027, 4, 5))
    x.add("EmployeeAbsence", absence, ["ABS.OVERLAP"], ResourceCode=workers[1], AbsenceType="Rapor", StartDate=date(2027, 4, 3), EndDate=date(2027, 4, 7))

    # Malzeme tedarikçisi (fason tedarikçisiyle yeni ilişkiler)
    ms = {**x.base("MaterialSupplier", MaterialCode="HAM-001", SupplierCode="TED-01"), "QuotaRatio": None, "MinimumOrderQuantity": None,
          "OrderLotSize": None, "MaximumOrderQuantity": None, "ValidFrom": None, "ValidTo": None}
    s = lambda material, rules, **v: x.add("MaterialSupplier", ms, rules, MaterialCode=material, SupplierCode="TED-08", Priority=9, **v)  # noqa: E731
    s("HAM-001", ["MS.MIN_MAX"], MinimumOrderQuantity=100.0, MaximumOrderQuantity=10.0)
    s("HAM-002", ["MS.LOT"], OrderLotSize=0.0)
    s("HAM-003", ["MS.NO_BASIS"], LeadTimeBasis=None)
    s("HAM-004", ["MS.NO_LEADTIME"], FixedLeadTimeDays=None, VariableLeadTimeDays=None, LeadTimeBasis=None)
    s("HAM-005", ["MS.QUOTA_SUM"], QuotaRatio=0.5)
    s("HAM-006", ["ALL.DATE_ORDER"], ValidFrom=date(2027, 1, 10), ValidTo=date(2027, 1, 1))

    # Satış siparişi
    so = x.base("SalesOrderLine", OrderNo="SO-1001")
    x.add("SalesOrderLine", so, ["SO.ZERO_OPEN"], OrderNo="V-SO-1", OpenQuantity=0.0, OrderedQuantity=0.0, DeliveredQuantity=0.0)
    x.add("SalesOrderLine", so, ["SO.DELIVERED", "SO.OPEN_MISMATCH"], OrderNo="V-SO-2", OpenQuantity=2.0, OrderedQuantity=5.0, DeliveredQuantity=8.0)
    x.add("SalesOrderLine", so, ["SO.OPEN_MISMATCH"], OrderNo="V-SO-3", OpenQuantity=5.0, OrderedQuantity=10.0, DeliveredQuantity=2.0)

    # Stok
    stock = {**x.base("Stock", MaterialCode="HAM-003", Warehouse="ANA", Status="Serbest"), "LotNo": None}
    st = lambda n, rules, **v: x.add("Stock", stock, rules, LotNo=f"V-LOT-{n}", **v)  # noqa: E731
    st(1, ["STK.LINE_NO_ORDER"], SalesOrderLineNo=1)
    st(2, ["STK.ACCEPT_DATE"], IsAvailable=False, IsInQuality=True, QualityEntryDate=date(2026, 11, 1), ExpectedAcceptanceDate=date(2026, 10, 1))
    st(3, ["STK.STATUS_FLAGS"], IsBlocked=True)
    st(4, ["STK.QUALITY_NO_DATE"], IsAvailable=False, IsInQuality=True)
    st(5, ["STK.EXPIRED"], ExpiryDate=date(2020, 1, 1))
    st(6, ["STK.NON_STOCKABLE"], MaterialCode="ALT-013")
    st(7, ["STK.CUSTOM_NO_OWNER"], IsCustomTracked=True)
    st(8, ["STK.ZERO_QTY"], Quantity=0.0)

    # Ödünç ve geri ödeme
    bp = {**x.base("BorrowPayback"), "PaybackDueDate": None, "PaidBackQuantity": None}
    x.add("BorrowPayback", bp, ["BP.SAME_PROJECT"], BorrowingProjectCode=bp["LendingProjectCode"], BorrowDate=date(2027, 2, 1))
    x.add("BorrowPayback", bp, ["BP.QTY"], BorrowedQuantity=0.0, BorrowDate=date(2027, 2, 2))
    x.add("BorrowPayback", bp, ["BP.DUE_DATE"], BorrowDate=date(2027, 2, 3), PaybackDueDate=date(2027, 1, 1))
    x.add("BorrowPayback", bp, ["BP.PAID"], BorrowDate=date(2027, 2, 4), BorrowedQuantity=2.0, PaidBackQuantity=5.0)

    # İş emri ve satırları
    wo = x.base("WorkOrder", WorkOrderNo="WO-5001")
    w = lambda n, rules, **v: x.add("WorkOrder", wo, rules, WorkOrderNo=f"V-WO-{n}", **v)  # noqa: E731
    w(1, ["WO.QTY", "WO.ZERO_OPEN"], OrderedQuantity=0.0, OpenQuantity=0.0)
    w(2, ["WO.START_DUE"], StartDate=date(2026, 12, 20), DueDate=date(2026, 12, 10))
    w(3, ["WO.SELF_PARENT"], ParentWorkOrderNo="V-WO-3")
    w(4, ["WO.LINE_NO_ORDER"], SalesOrderNo=None)
    w(5, ["WO.OPEN_ORDERED"], OpenQuantity=20.0)
    w(6, ["WO.ZERO_OPEN"], OpenQuantity=0.0)
    w(7, ["WO.TYPE_FLAGS"], IsSubcontract=True)
    w(8, ["WO.REWORK_NO_PARENT"], IsProduction=False, IsRework=True)
    w(9, ["WO.CUSTOM_NO_OWNER"], IsCustomTracked=True, ProjectCode=None, CustomerCode=None, SalesOrderNo=None, SalesOrderLineNo=None, SalesOrderLineItemNo=None)
    comp = x.base("WorkOrderComponent", WorkOrderNo="WO-5001")
    x.add("WorkOrderComponent", comp, ["WOC.ISSUED"], WorkOrderNo="V-WO-C", IssuedQuantity=comp["RequiredQuantity"] + 1)
    op = x.base("WorkOrderOperation", WorkOrderNo="WO-5001")
    x.add("WorkOrderOperation", op, ["WOO.NO_RESOURCE"], WorkOrderNo="V-WO-O1", ResourceCode=None, ResourceGroupCode=None)
    x.add("WorkOrderOperation", op, ["WOO.RESOURCE_NUMBER"], WorkOrderNo="V-WO-O2", ResourceNumber=0)
    x.add("WorkOrderOperation", op, ["WOO.CONFIRMED"], WorkOrderNo="V-WO-O3", PlannedConsumption=1.0, ConfirmedConsumption=5.0)

    # Satın alma
    po = x.base("PurchaseOrderLine", PurchaseOrderNo="PO-2001")
    p = lambda n, rules, **v: x.add("PurchaseOrderLine", po, rules, PurchaseOrderNo=f"V-PO-{n}", **v)  # noqa: E731
    p(1, ["PO.ZERO_OPEN"], OpenQuantity=0.0, OrderedQuantity=0.0)
    p(2, ["PO.RECEIVED"], OrderedQuantity=10.0, ReceivedQuantity=50.0)
    p(3, ["PO.TYPE_FLAGS"], IsSubcontract=True, WorkOrderNo="WO-5001")
    p(4, ["PO.SUBCON_NO_WO"], IsPurchase=False, IsSubcontract=True, WorkOrderNo=None)
    p(5, ["PO.NO_SUPPLIER"], SupplierCode=None)
    p(6, ["PO.NO_DATE"], RequestedDate=None, ConfirmedDate=None)
    p(7, ["PO.CUSTOM_NO_OWNER"], IsCustomTracked=True)

    # Üretim gerçekleşmesi
    pc = x.base("ProductionConfirmation", WorkOrderNo="WO-5002")
    x.add("ProductionConfirmation", pc, ["PC.QTY"], ConfirmationNo="V-T-1", ConfirmedQuantity=0.0)
    x.add("ProductionConfirmation", pc, ["PC.MATERIAL"], ConfirmationNo="V-T-2", MaterialCode="MAM-001")
    from .rules import add_rule_examples  # veri kuralı örnekleri (K-141)
    add_rule_examples(x, LOC)
    return x.expected

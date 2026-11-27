"""Kirli hâlde hazır validasyon kurallarının örnekleri (docs/11, K-137, K-146): her hazır kural için en az bir satır.

Örnekler kendi anahtarlarıyla eklenen satırlardır ("V" ile başlayan kodlar; pasif ebeveyn yardımcıları "L" ile); bilerek konmuş
durumlara ve H1–H4'e dokunmaz. Tablolar arası kurallar için karşı tablodaki satırlar da eklenir. Bir satır birden fazla kuralı
tetikleyebilir; beklenen kurallar satırda yazılıdır. Referans örneklerinde olmayan kod "V-YOK-…"tur. Temiz veride çıkan tek bulgu
"Yeni birim: M"dir (UOM.NEW_UOM, Bilgi).
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
    # Sahibi sistemde olmayan ayrılmış arz (K-198; docs/11 durum 12): temiz verideki bilerek konmuş Uyarılar; satır aktarılır, genele düşmez
    for row in stg["Stock"]:
        if row["ProjectCode"] == d.MISSING_PROJECT:
            x.expect("Stock", row, ["STK.REF_PROJECT"])
        if row["CustomerCode"] == d.MISSING_CUSTOMER:
            x.expect("Stock", row, ["STK.REF_CUSTOMER"])
    for row in stg["PurchaseOrderLine"]:
        if row["SalesOrderNo"] == d.MISSING_ORDER:
            x.expect("PurchaseOrderLine", row, ["PO.REF_SALES_ORDER"])
    # Veri kalitesi durumları (6.5, K-174; docs/11 durum 6–9): temiz verideki bilerek konmuş Uyarılar
    for row in stg["MaterialSupplier"]:
        if (row["MaterialCode"], row["SupplierCode"]) == (d.DEEP_MATERIAL, d.DEEP_SUPPLIER):
            x.expect("MaterialSupplier", row, ["MS.NO_LEADTIME"])
    for row in stg["BOM"]:
        if row["MaterialCode"] == d.NO_DEMAND_MATERIAL:
            x.expect("BOM", row, ["BOM.ZERO_QTY"])
    for row in stg["SalesOrderLine"]:
        if row["OrderNo"] == d.PAST_DUE_ORDER:
            x.expect("SalesOrderLine", row, ["SO.PAST_DUE"])

    # Lokasyon
    x.add("Location", x.base("Location", Code=LOC), ["LOC.NO_FLAG"], Code="V-LOC-1", Name="Örnek lokasyon", IsFactory=False, IsDepot=False, IsSubcontractor=False)

    # Pasif ebeveynler (K-146): kendileri validasyona girmez (K-145), onlara bakan satırlar pasif ebeveyn bulgusu alır
    plain = {k: None for k in x.base("Material", Code="MAM-002") if k.startswith("Additional")}  # ek alan notu vermesin
    x.add("Material", {**x.base("Material", Code="MAM-002"), **plain}, None, Code="L-MAT-PAS", Name="Pasif malzeme", IsActive=False)
    x.add("Supplier", x.base("Supplier", Code="TED-01"), None, Code="L-SUP-PAS", Name="Pasif tedarikçi", IsActive=False)
    x.add("Customer", x.base("Customer", Code="MUS-A"), None, Code="L-CUS-PAS", Name="Pasif müşteri", IsActive=False)
    x.add("Resource", x.base("Resource", Code="T-01"), None, Code="L-RES-PAS", Name="Pasif kaynak", IsActive=False)
    x.add("Supplier", x.base("Supplier", Code="TED-01"), ["SUP.NO_MATERIAL"], Code="V-SUP-1", Name="Hiçbir malzemeye bağlı olmayan tedarikçi")

    # Birim dönüşümü
    uom = x.base("UomConversion", MaterialCode="HAM-001")
    x.add("UomConversion", uom, ["UOM.FACTOR"], MaterialCode="HAM-001", FromUom="ADET", ToUom="KG", FromUomName="Adet", ToUomName="Kilogram", Factor=0.0)
    x.add("UomConversion", uom, ["UOM.SAME_UOM"], MaterialCode="HAM-002", FromUom="KG", ToUom="KG", FromUomName="Kilogram", ToUomName="Kilogram", Factor=1.0)
    x.add("UomConversion", uom, ["UOM.INVERSE"], MaterialCode="HAM-004", FromUom="ADET", ToUom="KG", FromUomName="Adet", ToUomName="Kilogram", Factor=2.0)
    x.add("UomConversion", uom, ["UOM.INVERSE"], MaterialCode="HAM-004", FromUom="KG", ToUom="ADET", FromUomName="Kilogram", ToUomName="Adet", Factor=2.0)
    x.add("UomConversion", uom, ["UOM.REF_MATERIAL"], MaterialCode="V-YOK-MAT", FromUom="ADET", ToUom="KG", FromUomName="Adet", ToUomName="Kilogram", Factor=2.0)

    # Malzeme
    mat = {**x.base("Material", Code="HAM-001"), "MinLot": None, "MaxLot": None, "LotMultiple": None, "QtyPerBox": None, "QtyPerPallet": None,
           "SafetyStock": None, "StockCoverageDays": None, "MaxStock": None, "ScrapRatio": None}
    m = lambda n, rules, **v: x.add("Material", mat, rules, Code=f"V-MAT-{n}", Name=f"Örnek malzeme {n}", **v)  # noqa: E731
    m(1, ["MAT.MINLOT_MAXLOT"], MinLot=10.0, MaxLot=5.0)
    m(2, ["MAT.SAFETY_MAX"], SafetyStock=50.0, MaxStock=10.0)
    m(3, ["MAT.ZERO_PACK"], LotMultiple=0.0)
    m(4, ["MAT.SUPPLY_CONFLICT", "MAT.NO_VERSION"], DefaultSupplyType="Üretim", IsProducible=False)
    m(5, ["MAT.NO_SUPPLY", "MAT.SUPPLY_CONFLICT"], IsProducible=False, IsPurchasable=False, IsSubcontractable=False)
    m(6, ["MAT.SAFETY_COVERAGE"], SafetyStock=5.0, StockCoverageDays=3.0)
    m(7, ["ALL.RATIO_RANGE"], ScrapRatio=1.5)
    m(8, ["ALL.OUT_OF_LIST"], MaterialLevel="Ham madde")
    m(9, ["MAT.NO_SUPPLIER"])
    m(10, ["MAT.NO_SUBCONTRACTOR"], DefaultSupplyType="Fason", IsSubcontractable=True)

    # Üretim versiyonu (kendi ağaç kodlarıyla: öteki versiyonların baz miktarını etkilemez)
    pv = {**x.base("ProductionVersion", MaterialCode="MAM-001"), "ValidFrom": None, "ValidTo": None}
    x.add("ProductionVersion", pv, ["PV.BASEQTY", "PV.REF_BOM"], Code="V-PV-1", BOMCode="V-BOM-1", BaseQuantity=0.0)
    x.add("ProductionVersion", pv, ["PV.BASEQTY_DIFFERS"], Code="V-PV-2", BOMCode="V-BOM-2", BaseQuantity=1.0)
    x.add("ProductionVersion", pv, ["PV.BASEQTY_DIFFERS"], Code="V-PV-3", BOMCode="V-BOM-2", BaseQuantity=2.0)
    x.add("ProductionVersion", pv, ["PV.EXPIRED"], Code="V-PV-4", BOMCode="V-BOM-4", IsActive=True, ValidTo=date(2020, 1, 1))
    x.add("ProductionVersion", pv, ["PV.REF_MATERIAL", "PV.REF_BOM"], MaterialCode="V-YOK-MAT", Code="V-PV-5")  # ağaç malzemeyle eşleşir
    x.add("ProductionVersion", x.base("ProductionVersion", MaterialCode="MAM-002", Code="V1"), ["PV.INACTIVE_MATERIAL"],
          MaterialCode="L-MAT-PAS", Code="V-PV-P", BOMCode="L-BOM")
    tree = {**x.base("BOM", MaterialCode="MAM-001", ComponentMaterialCode="SAT-008"), "AlternativeGroup": None, "AlternativePriority": None}
    for code in ("V-BOM-2", "V-BOM-4"):  # versiyon örneklerinin ağaçları
        x.add("BOM", tree, None, Code=code)
    x.add("BOM", {**x.base("BOM", MaterialCode="MAM-002"), "AlternativeGroup": None, "AlternativePriority": None}, None,
          MaterialCode="L-MAT-PAS", Code="L-BOM")
    x.add("BOM", tree, ["BOM.OPERATION_NOT_IN_ROUTE"], OperationNo=990, SequenceNo=9)

    # Ürün ağacı
    bom = {**x.base("BOM", MaterialCode="ALT-005", ComponentMaterialCode="PRC-013"), "AlternativeGroup": None, "AlternativePriority": None}
    loose = ["BOM.REF_MATERIAL", "BOM.REF_COMPONENT", "BOM.NO_VERSION"]  # döngü düğümleri malzeme değil, ağaçları versiyonsuz
    x.add("BOM", bom, ["BOM.SELF", *loose], MaterialCode="V-CYC-S", Code="V-B-1", ComponentMaterialCode="V-CYC-S")
    x.add("BOM", bom, ["BOM.CYCLE", *loose], MaterialCode="V-CYC-A", Code="V-B-2", ComponentMaterialCode="V-CYC-B")
    x.add("BOM", bom, ["BOM.CYCLE", *loose], MaterialCode="V-CYC-B", Code="V-B-3", ComponentMaterialCode="V-CYC-A")
    x.add("BOM", bom, ["BOM.ZERO_QTY", "BOM.NO_VERSION"], Code="V-B-4", Quantity=0.0)
    x.add("BOM", bom, ["BOM.PRIORITY_NO_GROUP", "BOM.NO_VERSION"], Code="V-B-5", AlternativePriority=1)
    x.add("BOM", bom, ["BOM.SINGLE_ALTERNATIVE", "BOM.NO_VERSION"], Code="V-B-6", AlternativeGroup="V-ALT")
    x.add("BOM", bom, ["BOM.INACTIVE_COMPONENT"], ComponentMaterialCode="L-MAT-PAS", SequenceNo=7)

    # Kaynak, kaynak grubu, grup eşleşmesi (K-180: tip, birim, kritik ve fasoncu grupta; tablolar arası örnekler için de)
    res = x.base("Resource", Code="T-01")
    r = lambda n, rules, **v: x.add("Resource", res, rules, Code=f"V-RES-{n}", Name=f"Örnek kaynak {n}", **v)  # noqa: E731
    r(1, None)  # iki farklı birimli gruba üye (RGM.UNIT_MISMATCH eşleşme satırlarında)
    r(2, None)  # hem makine hem işçi grubuna üye (RGM.MIXED_TYPES eşleşme satırlarında)
    r(3, ["RES.UNUSED"])  # hiçbir grupta yok
    r(4, ["RES.MONTH_YEAR", "RES.UNUSED"], RemainingOverTimeMonth=50.0, RemainingOverTimeYear=10.0)
    group = x.base("ResourceGroup", Code="TORNA")
    g = lambda n, rules, name, **v: x.add("ResourceGroup", group, rules, Code=f"V-RG-{n}", Name=name, **v)  # noqa: E731
    g(1, None, "Örnek adet birimli grup", CapacityUnit="ADET")
    g(2, ["RG.TYPE_FLAGS", "RG.NO_RESOURCE"], "Örnek tipsiz grup", IsMachine=False)
    x.add("ResourceGroup", group, ["ALL.REF_LOCATION", "RG.NO_RESOURCE"], LocationCode="V-YOK-LOC", Code="V-RG-3", Name="Lokasyonu tanımsız grup")
    g(4, None, "Örnek makine grubu")
    g(5, None, "Örnek işçi grubu", IsMachine=False, IsEmployee=True)
    g(6, ["RG.SUBCON_CONFLICT", "RG.NO_RESOURCE"], "Fasoncusu olan, fason olmayan grup", SubcontractorCode="TED-07")
    g(7, ["RG.PHASE1_UNUSED", "RG.NO_RESOURCE"], "Örnek fırın grubu", IsMachine=False, IsFurnace=True)
    g(8, ["RG.REF_SUBCONTRACTOR", "RG.NO_RESOURCE"], "Fasoncusu tanımsız grup", IsMachine=False, IsSubcontractor=True, SubcontractorCode="V-YOK-SUP")
    x.add("ResourceGroup", group, None, Code="L-RG-PAS", Name="Pasif kaynak grubu", IsActive=False)  # pasif ebeveyn (K-146)
    rgm = x.base("ResourceGroupMember", ResourceGroupCode="TORNA", ResourceCode="T-01")
    m = lambda rules, group_code, resource_code: x.add("ResourceGroupMember", rgm, rules, ResourceGroupCode=group_code, ResourceCode=resource_code)  # noqa: E731
    m(["RGM.UNIT_MISMATCH"], "V-RG-1", "V-RES-1")
    m(["RGM.UNIT_MISMATCH"], "V-RG-4", "V-RES-1")
    m(["RGM.MIXED_TYPES"], "V-RG-4", "V-RES-2")
    m(["RGM.MIXED_TYPES"], "V-RG-5", "V-RES-2")
    m(["RGM.REF_RESOURCE_GROUP"], "V-YOK-RG", "T-01")
    m(["RGM.REF_RESOURCE"], "TORNA", "V-YOK-RES")

    # Rota (K-180: kaynak alanı yok, kaynak grubu zorunlu)
    rtg = {**x.base("Routing", RouteCode="R-MAM-001", OperationNo=10, SequenceNo=1), "AlternativeGroup": None, "AlternativePriority": None}
    rt = lambda n, rules, **v: x.add("Routing", rtg, [*rules, "RTG.NO_VERSION"], RouteCode=f"V-R-{n}", **v)  # noqa: E731  örnek rotalar versiyonsuz
    rt(2, ["RTG.RESOURCE_NUMBER"], ResourceNumber=0)
    rt(3, ["RTG.ZERO_CONSUMPTION"], Consumption=0.0)
    rt(4, ["RTG.PRIORITY_NO_GROUP"], AlternativePriority=1)
    rt(5, ["RTG.NUMBER_OVER_GROUP"], ResourceNumber=99)
    rt(7, ["RTG.SUBCON_RESOURCE"], IsSubcontracted=True)
    x.add("Routing", rtg, ["RTG.INACTIVE_RESOURCE_GROUP"], SequenceNo=8, ResourceGroupCode="L-RG-PAS")
    x.add("Routing", rtg, ["RTG.REF_RESOURCE_GROUP"], SequenceNo=7, ResourceGroupCode="V-YOK-RG")

    # Benzetilen ürün (temiz veride yok; hepsi Hata, ana veriye girmez)
    ref = {**x.empty("MaterialReference"), "LocationCode": LOC, "TimeFactor": 1.0}
    x.add("MaterialReference", ref, ["REF.SELF"], MaterialCode="MAM-001", ReferenceMaterialCode="MAM-001")
    x.add("MaterialReference", ref, ["REF.CYCLE"], MaterialCode="MAM-002", ReferenceMaterialCode="MAM-003")
    x.add("MaterialReference", ref, ["REF.CYCLE"], MaterialCode="MAM-003", ReferenceMaterialCode="MAM-002")
    x.add("MaterialReference", ref, ["REF.TIMEFACTOR"], MaterialCode="MAM-004", ReferenceMaterialCode="MAM-005", TimeFactor=0.0)
    x.add("MaterialReference", ref, ["REF.REF_MATERIAL"], MaterialCode="V-YOK-MAT", ReferenceMaterialCode="MAM-005")
    x.add("MaterialReference", ref, ["REF.REF_REFERENCE_MATERIAL"], MaterialCode="MAM-006", ReferenceMaterialCode="V-YOK-MAT")
    x.add("MaterialReference", ref, ["REF.REF_REFERENCE_VERSION"], MaterialCode="MAM-007", ReferenceMaterialCode="MAM-005",
          ReferenceProductionVersionCode="V-YOK-PV")
    x.add("MaterialReference", ref, ["REF.NO_VERSION"], MaterialCode="MAM-008", ReferenceMaterialCode="V-MAT-4")

    # Çalışan izni (uzak tarihlerde: plan ufkunu etkilemez)
    workers = [row["Code"] for row in stg["Resource"] if row["Code"].startswith("W-")]  # işçiler: işçi gruplarının üyeleri
    absence = {**x.base("EmployeeAbsence", ResourceCode="W-007"), "HoursPerDay": None}
    x.add("EmployeeAbsence", absence, ["ABS.HOURS"], ResourceCode=workers[0], AbsenceType="İzin", StartDate=FAR, EndDate=date(2027, 3, 2), HoursPerDay=30.0)
    x.add("EmployeeAbsence", absence, ["ABS.NOT_EMPLOYEE"], ResourceCode="T-03", AbsenceType="İzin", StartDate=date(2027, 3, 5), EndDate=date(2027, 3, 6))
    x.add("EmployeeAbsence", absence, ["ABS.OVERLAP"], ResourceCode=workers[1], AbsenceType="İzin", StartDate=date(2027, 4, 1), EndDate=date(2027, 4, 5))
    x.add("EmployeeAbsence", absence, ["ABS.OVERLAP"], ResourceCode=workers[1], AbsenceType="Rapor", StartDate=date(2027, 4, 3), EndDate=date(2027, 4, 7))
    x.add("EmployeeAbsence", absence, ["ABS.REF_RESOURCE"], ResourceCode="V-YOK-RES", AbsenceType="İzin", StartDate=date(2027, 5, 1), EndDate=date(2027, 5, 2))

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
    x.add("MaterialSupplier", ms, ["MS.REF_MATERIAL"], MaterialCode="V-YOK-MAT", SupplierCode="TED-01")
    x.add("MaterialSupplier", ms, ["MS.REF_SUPPLIER"], MaterialCode="HAM-001", SupplierCode="V-YOK-SUP")
    x.add("MaterialSupplier", ms, ["MS.INACTIVE_SUPPLIER"], MaterialCode="HAM-002", SupplierCode="L-SUP-PAS")

    # Satış siparişi
    so = x.base("SalesOrderLine", OrderNo="SO-1001")
    x.add("SalesOrderLine", so, ["SO.ZERO_OPEN"], OrderNo="V-SO-1", OpenQuantity=0.0, OrderedQuantity=0.0, DeliveredQuantity=0.0)
    x.add("SalesOrderLine", so, ["SO.DELIVERED", "SO.OPEN_MISMATCH"], OrderNo="V-SO-2", OpenQuantity=2.0, OrderedQuantity=5.0, DeliveredQuantity=8.0)
    x.add("SalesOrderLine", so, ["SO.OPEN_MISMATCH"], OrderNo="V-SO-3", OpenQuantity=5.0, OrderedQuantity=10.0, DeliveredQuantity=2.0)
    x.add("SalesOrderLine", so, ["SO.REF_CUSTOMER"], OrderNo="V-SO-4", CustomerCode="V-YOK-CUS")
    x.add("SalesOrderLine", so, ["SO.INACTIVE_CUSTOMER"], OrderNo="V-SO-5", CustomerCode="L-CUS-PAS")
    x.add("SalesOrderLine", so, ["SO.INACTIVE_MATERIAL"], OrderNo="V-SO-6", MaterialCode="L-MAT-PAS")
    x.add("SalesOrderLine", so, ["SO.REF_PROJECT"], OrderNo="V-SO-7", ProjectCode="V-YOK-PRJ")
    x.add("SalesOrderLine", so, ["SO.NOT_SELLABLE"], OrderNo="V-SO-8", MaterialCode="HAM-001")
    x.add("SalesOrderLine", so, ["ALL.UOM_CONVERSION"], OrderNo="V-SO-9", Uom="PALET")

    # Tahmin (temiz veride yok; yalnız tablolar arası örnekler)
    fc = {**x.empty("Forecast"), "LocationCode": LOC, "MaterialCode": "MAM-001", "Period": date(2027, 1, 1), "Type": "Satış tahmini", "Quantity": 10.0,
          "IsActive": True, "DeliveryPoint": "Sonu"}
    x.add("Forecast", fc, ["FC.REF_MATERIAL"], MaterialCode="V-YOK-MAT")
    x.add("Forecast", fc, ["FC.INACTIVE_MATERIAL"], MaterialCode="L-MAT-PAS")
    x.add("Forecast", fc, ["FC.REF_CUSTOMER"], CustomerCode="V-YOK-CUS")
    x.add("Forecast", fc, ["FC.REF_PROJECT"], ProjectCode="V-YOK-PRJ")

    # Stok
    stock = {**x.base("Stock", MaterialCode="HAM-003", Warehouse="ANA", Status="Serbest"), "LotNo": None}
    st = lambda n, rules, **v: x.add("Stock", stock, rules, LotNo=f"V-LOT-{n}", **v)  # noqa: E731
    st(1, ["STK.LINE_NO_ORDER"], SalesOrderLineNo=1)
    st(2, ["STK.ACCEPT_DATE"], IsAvailable=False, IsInQuality=True, QualityEntryDate=date(2026, 11, 1), ExpectedAcceptanceDate=date(2026, 10, 1))
    st(3, ["STK.STATUS_FLAGS"], IsBlocked=True)
    st(4, ["STK.QUALITY_NO_DATE"], IsAvailable=False, IsInQuality=True)
    st(5, ["STK.EXPIRED"], ExpiryDate=date(2020, 1, 1))
    st(6, ["STK.NON_STOCKABLE"], MaterialCode="ALT-013")
    st(8, ["STK.ZERO_QTY"], Quantity=0.0)
    st(9, ["STK.REF_MATERIAL"], MaterialCode="V-YOK-MAT")
    st(10, ["STK.INACTIVE_MATERIAL"], MaterialCode="L-MAT-PAS")
    st(11, ["STK.REF_PROJECT"], ProjectCode="V-YOK-PRJ")
    st(12, ["STK.REF_CUSTOMER"], CustomerCode="V-YOK-CUS")
    st(13, ["STK.REF_SALES_ORDER"], SalesOrderNo="V-YOK-SO")

    # Ödünç ve geri ödeme
    bp = {**x.base("BorrowPayback"), "PaybackDueDate": None, "PaidBackQuantity": None}
    x.add("BorrowPayback", bp, ["BP.SAME_PROJECT"], BorrowingProjectCode=bp["LendingProjectCode"], BorrowDate=date(2027, 2, 1))
    x.add("BorrowPayback", bp, ["BP.QTY"], BorrowedQuantity=0.0, BorrowDate=date(2027, 2, 2))
    x.add("BorrowPayback", bp, ["BP.DUE_DATE"], BorrowDate=date(2027, 2, 3), PaybackDueDate=date(2027, 1, 1))
    x.add("BorrowPayback", bp, ["BP.PAID"], BorrowDate=date(2027, 2, 4), BorrowedQuantity=2.0, PaidBackQuantity=5.0)
    x.add("BorrowPayback", bp, ["BP.REF_MATERIAL"], BorrowDate=date(2027, 2, 5), MaterialCode="V-YOK-MAT")
    x.add("BorrowPayback", bp, ["BP.REF_LENDING_PROJECT"], BorrowDate=date(2027, 2, 6), LendingProjectCode="V-YOK-PRJ")
    x.add("BorrowPayback", bp, ["BP.REF_BORROWING_PROJECT"], BorrowDate=date(2027, 2, 7), BorrowingProjectCode="V-YOK-PRJ")

    # Üretim siparişi ve satırları
    wo = x.base("WorkOrder", WorkOrderNo="WO-5001")
    w = lambda n, rules, **v: x.add("WorkOrder", wo, rules, WorkOrderNo=f"V-WO-{n}", **v)  # noqa: E731
    w(1, ["WO.QTY", "WO.ZERO_OPEN"], OrderedQuantity=0.0, OpenQuantity=0.0)
    w(2, ["WO.START_DUE"], StartDate=date(2099, 12, 20), DueDate=date(2099, 12, 10))  # uzak gelecek: WO.PAST_DUE tetiklenmesin
    w(3, ["WO.SELF_PARENT"], ParentWorkOrderNo="V-WO-3")
    w(4, ["WO.LINE_NO_ORDER"], SalesOrderNo=None)
    w(5, ["WO.OPEN_ORDERED"], OpenQuantity=20.0)
    w(6, ["WO.ZERO_OPEN"], OpenQuantity=0.0)
    w(7, ["WO.TYPE_FLAGS"], IsSubcontract=True)
    w(8, ["WO.REWORK_NO_PARENT"], IsProduction=False, IsRework=True)
    w(10, ["WO.REF_MATERIAL", "WO.NO_STRUCTURE"], MaterialCode="V-YOK-MAT", ProductionVersionCode=None)
    w(11, ["WO.INACTIVE_MATERIAL"], MaterialCode="L-MAT-PAS", ProductionVersionCode="V-PV-P")
    w(12, ["WO.REF_VERSION", "WO.NO_STRUCTURE"], ProductionVersionCode="V-YOK-PV")
    w(13, ["WO.REF_PROJECT"], ProjectCode="V-YOK-PRJ")
    w(14, ["WO.REF_CUSTOMER"], CustomerCode="V-YOK-CUS")
    w(15, ["WO.REF_SALES_ORDER"], SalesOrderNo="V-YOK-SO")
    w(16, ["WO.REF_PARENT_WORK_ORDER"], ParentWorkOrderNo="V-YOK-WO")
    w(17, ["WO.PAST_DUE"], StartDate=date(2020, 1, 1), DueDate=date(2020, 1, 10))  # 6.5, K-174
    comp = x.base("WorkOrderComponent", WorkOrderNo="WO-5001")
    x.add("WorkOrderComponent", comp, ["WOC.ISSUED", "WOC.REF_WORK_ORDER"], WorkOrderNo="V-WO-C", IssuedQuantity=comp["RequiredQuantity"] + 1)
    x.add("WorkOrderComponent", comp, ["WOC.REF_MATERIAL"], MaterialCode="V-YOK-MAT")
    x.add("WorkOrderComponent", comp, ["WOC.OPERATION_NOT_IN_WO"], OperationNo=990)
    op = x.base("WorkOrderOperation", WorkOrderNo="WO-5001")
    x.add("WorkOrderOperation", op, ["WOO.RESOURCE_NUMBER", "WOO.REF_WORK_ORDER"], WorkOrderNo="V-WO-O2", ResourceNumber=0)
    x.add("WorkOrderOperation", op, ["WOO.CONFIRMED", "WOO.REF_WORK_ORDER"], WorkOrderNo="V-WO-O3", PlannedConsumption=1.0, ConfirmedConsumption=5.0)
    x.add("WorkOrderOperation", op, ["WOO.REF_RESOURCE_GROUP"], OperationNo=981, ResourceGroupCode="V-YOK-RG")

    # Satın alma
    po = x.base("PurchaseOrderLine", PurchaseOrderNo="PO-2001")
    p = lambda n, rules, **v: x.add("PurchaseOrderLine", po, rules, PurchaseOrderNo=f"V-PO-{n}", **v)  # noqa: E731
    p(1, ["PO.ZERO_OPEN"], OpenQuantity=0.0, OrderedQuantity=0.0)
    p(2, ["PO.RECEIVED"], OrderedQuantity=10.0, ReceivedQuantity=50.0)
    p(3, ["PO.TYPE_FLAGS"], IsSubcontract=True, WorkOrderNo="WO-5001")
    p(4, ["PO.SUBCON_NO_WO"], IsPurchase=False, IsSubcontract=True, WorkOrderNo=None)
    p(5, ["PO.NO_SUPPLIER"], SupplierCode=None)
    p(6, ["PO.NO_DATE"], RequestedDate=None, ConfirmedDate=None)
    p(8, ["PO.REF_MATERIAL", "PO.SUPPLIER_NOT_LISTED"], MaterialCode="V-YOK-MAT")
    p(9, ["PO.INACTIVE_MATERIAL", "PO.SUPPLIER_NOT_LISTED"], MaterialCode="L-MAT-PAS")
    p(10, ["PO.REF_SUPPLIER"], SupplierCode="V-YOK-SUP")
    p(11, ["PO.INACTIVE_SUPPLIER", "PO.SUPPLIER_NOT_LISTED"], SupplierCode="L-SUP-PAS")
    p(12, ["PO.REF_PROJECT"], ProjectCode="V-YOK-PRJ")
    p(13, ["PO.REF_CUSTOMER"], CustomerCode="V-YOK-CUS")
    p(14, ["PO.REF_SALES_ORDER"], SalesOrderNo="V-YOK-SO")
    p(15, ["PO.REF_WORK_ORDER"], WorkOrderNo="V-YOK-WO")
    p(16, ["PO.PAST_DUE"], RequestedDate=date(2020, 1, 10), ConfirmedDate=None)  # 6.5, K-174

    # Üretim gerçekleşmesi
    pc = x.base("ProductionConfirmation", WorkOrderNo="WO-5002")
    x.add("ProductionConfirmation", pc, ["PC.QTY"], ConfirmationNo="V-T-1", ConfirmedQuantity=0.0)
    x.add("ProductionConfirmation", pc, ["PC.MATERIAL"], ConfirmationNo="V-T-2", MaterialCode="MAM-001")
    x.add("ProductionConfirmation", pc, ["PC.REF_WORK_ORDER"], ConfirmationNo="V-T-3", WorkOrderNo="V-YOK-WO")
    x.add("ProductionConfirmation", pc, ["PC.REF_MATERIAL", "PC.MATERIAL"], ConfirmationNo="V-T-4", MaterialCode="V-YOK-MAT")
    from .rules import add_rule_examples  # veri kuralı örnekleri (K-141)
    add_rule_examples(x, LOC)

    # Satın alınan örnek malzemelere tedarikçi: yalnız kendi kurallarının bulgusunu versinler (MAT.NO_SUPPLIER'ın örneği V-MAT-9)
    linked = {r["MaterialCode"] for r in stg["MaterialSupplier"]}
    for row in [r for r in stg["Material"] if r["Code"].startswith(("V-MAT-", "R-MAT-")) and r["Code"] != "V-MAT-9"]:
        if row.get("DefaultSupplyType") == "Satın alma" and row["Code"] not in linked:
            x.add("MaterialSupplier", ms, None, MaterialCode=row["Code"], SupplierCode="TED-01")
    return x.expected

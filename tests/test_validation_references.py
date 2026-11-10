"""Referans, pasif ebeveyn ve bütünlük kuralları (K-146): zorunlu ilişki Hata, isteğe bağlı bağlantı Uyarı, pasif ebeveyn haritadaki sınıf,
pasif çocuk hiçbir kurala girmez, bakılan tablo boşsa "Karşılaştırılacak veri yok", birim dönüşümü, bütünlük bulguları ebeveynde.

Satırlar doğrudan ham katmana güncel hâlde yazılır, işlenmiş katman kurulur ve tablolar arası adım çalışır (çekim ve ön kontrol burada ölçülmez)."""
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.validation import catalog as cat, engine, processed
from app.validation.sqlkit import raw_table

from validation_helpers import clean

pytestmark = pytest.mark.db

LOC = "ORM-01"


def mat(code, supply="Satın alma", **extra):
    return {"LocationCode": LOC, "Code": code, "BaseUom": "ADET", "IsActive": 1, "DefaultSupplyType": supply, "IsSellable": 1, **extra}


def so(no, material, **extra):
    return {"LocationCode": LOC, "OrderNo": no, "LineNo": 10, "LineItemNo": 0, "CustomerCode": "C-1", "MaterialCode": material,
            "OpenQuantity": 5, "IsActive": 1, **extra}


DATA = {
    "Location": [{"Code": LOC, "Name": "Fabrika", "IsFactory": 1, "IsActive": 1}],
    "Material": [mat("M-OK"), mat("M-PAS", IsActive=0), mat("M-NOSELL", IsSellable=0), mat("M-PRD", "Üretim"), mat("M-PRD2", "Üretim"),
                 mat("M-REF", "Üretim"), mat("M-BUY", "Satın alma"), mat("M-BUY2", "Satın alma"), mat("M-FSN", "Fason"), mat("M-FSN2", "Fason"),
                 mat("M-COMP")],
    "UomConversion": [{"MaterialCode": None, "FromUom": "KOLI", "ToUom": "ADET", "Factor": 12}, {"MaterialCode": "M-YOK", "FromUom": "KG", "ToUom": "ADET", "Factor": 2}],
    "Project": [{"Code": "P-1", "Name": "Proje", "IsActive": 1, "ProjectGroupCode": "PG-YOK"}],
    "Customer": [{"Code": "C-1", "Name": "Müşteri", "IsActive": 1}, {"Code": "C-PAS", "Name": "Pasif", "IsActive": 0}],
    "Supplier": [{"Code": "S-1", "Name": "Tedarikçi", "IsActive": 1}, {"Code": "S-PAS", "Name": "Pasif", "IsActive": 0},
                 {"Code": "S-FSN", "Name": "Fasoncu", "IsActive": 1, "IsSubcontractor": 1}, {"Code": "S-BOS", "Name": "Bağsız", "IsActive": 1}],
    "MaterialSupplier": [{"LocationCode": LOC, "MaterialCode": "M-BUY", "SupplierCode": "S-1", "IsActive": 1},
                         {"LocationCode": LOC, "MaterialCode": "M-BUY2", "SupplierCode": "S-PAS", "IsActive": 1},
                         {"LocationCode": LOC, "MaterialCode": "M-FSN", "SupplierCode": "S-FSN", "IsActive": 1},
                         {"LocationCode": LOC, "MaterialCode": "M-FSN2", "SupplierCode": "S-1", "IsActive": 1},
                         {"LocationCode": LOC, "MaterialCode": "M-OK", "SupplierCode": "S-1", "IsActive": 1},
                         {"LocationCode": LOC, "MaterialCode": "M-COMP", "SupplierCode": "S-1", "IsActive": 1},
                         {"LocationCode": LOC, "MaterialCode": "M-NOSELL", "SupplierCode": "S-1", "IsActive": 1}],
    "ProductionVersion": [{"LocationCode": LOC, "MaterialCode": "M-PRD2", "Code": "V1", "BOMCode": "A-1", "RouteCode": "R-1", "IsActive": 1},
                          {"LocationCode": LOC, "MaterialCode": "M-PRD2", "Code": "V2", "BOMCode": "A-YOK", "RouteCode": "R-YOK", "IsActive": 1}],
    "BOM": [{"LocationCode": LOC, "MaterialCode": "M-PRD2", "Code": "A-1", "ComponentMaterialCode": "M-COMP", "OperationNo": 10, "SequenceNo": 1, "Quantity": 1},
            {"LocationCode": LOC, "MaterialCode": "M-PRD2", "Code": "A-1", "ComponentMaterialCode": "M-PAS", "OperationNo": 30, "SequenceNo": 2, "Quantity": 1},
            {"LocationCode": LOC, "MaterialCode": "M-PRD2", "Code": "A-2", "ComponentMaterialCode": "SAT-999", "OperationNo": 10, "SequenceNo": 1, "Quantity": 1,
             "ComponentUom": "KOLI"}],
    "Routing": [{"LocationCode": LOC, "RouteCode": "R-1", "OperationNo": 10, "SequenceNo": 1, "ResourceCode": "K-1", "IsActive": 1},
                {"LocationCode": LOC, "RouteCode": "R-BOS", "OperationNo": 10, "SequenceNo": 1, "ResourceCode": "K-PAS", "IsActive": 1},
                {"LocationCode": LOC, "RouteCode": "R-1", "OperationNo": 10, "SequenceNo": 2, "ResourceCode": "K-YOK", "IsActive": 1},
                {"LocationCode": LOC, "RouteCode": "R-1", "OperationNo": 10, "SequenceNo": 3, "ResourceGroupCode": "G-1", "IsActive": 1}],
    "Resource": [{"LocationCode": LOC, "Code": "K-1", "IsMachine": 1, "CapacityUnit": "SAAT", "IsActive": 1},
                 {"LocationCode": LOC, "Code": "K-PAS", "IsMachine": 1, "CapacityUnit": "SAAT", "IsActive": 0},
                 {"LocationCode": LOC, "Code": "K-BOS", "IsMachine": 1, "CapacityUnit": "SAAT", "IsActive": 1, "SubcontractorCode": "S-YOK"}],
    "ResourceGroup": [{"LocationCode": LOC, "Code": "G-BOS", "IsActive": 1}, {"LocationCode": LOC, "Code": "G-1", "IsActive": 1}],
    "ResourceGroupAssignment": [{"LocationCode": LOC, "ResourceGroupCode": "G-1", "ResourceCode": "K-1"}],
    "MaterialReference": [{"LocationCode": LOC, "MaterialCode": "M-REF", "ReferenceMaterialCode": "M-PRD"}],
    "SalesOrderLine": [so("SO-1", "M-OK"), so("SO-1099", "MAM-099"), so("SO-PAS", "M-PAS"), so("SO-CPAS", "M-OK", CustomerCode="C-PAS"),
                       so("SO-PRJ", "M-OK", ProjectCode="P-YOK"), so("SO-OFF", "MAM-098", IsActive=0), so("SO-SELL", "M-NOSELL"),
                       so("SO-UOM", "M-OK", Uom="KOLI"), so("SO-UOM2", "M-OK", Uom="KG"), so("SO-LOC", "M-OK", LocationCode="ORM-99")],
    "Stock": [{"LocationCode": LOC, "MaterialCode": "M-PAS", "Warehouse": "ANA", "Quantity": 3, "IsActive": 1}],
    "WorkOrder": [{"LocationCode": LOC, "WorkOrderNo": "WO-1", "MaterialCode": "M-PRD2", "ProductionVersionCode": "V1", "OpenQuantity": 5},
                  {"LocationCode": LOC, "WorkOrderNo": "WO-BOS", "MaterialCode": "M-PRD2", "OpenQuantity": 5, "ParentWorkOrderNo": "WO-YOK"},
                  {"LocationCode": LOC, "WorkOrderNo": "WO-OP", "MaterialCode": "M-PRD2", "OpenQuantity": 5, "ParentWorkOrderNo": "WO-1"}],
    "WorkOrderOperation": [{"LocationCode": LOC, "WorkOrderNo": "WO-OP", "OperationNo": 10, "SequenceNo": 1, "ResourceCode": "K-1", "IsActive": 1}],
    "WorkOrderComponent": [{"LocationCode": LOC, "WorkOrderNo": "WO-OP", "MaterialCode": "M-COMP", "OperationNo": 20, "SequenceNo": 1},
                           {"LocationCode": LOC, "WorkOrderNo": "WO-OP", "MaterialCode": "M-COMP", "OperationNo": 10, "SequenceNo": 2}],
    "PurchaseOrderLine": [{"LocationCode": LOC, "PurchaseOrderNo": "PO-1", "LineNo": 1, "MaterialCode": "M-OK", "SupplierCode": "S-1", "SalesOrderNo": "SO-1",
                           "OpenQuantity": 1, "IsActive": 1},
                          {"LocationCode": LOC, "PurchaseOrderNo": "PO-2", "LineNo": 1, "MaterialCode": "M-OK", "SupplierCode": "S-FSN", "SalesOrderNo": "SO-1",
                           "SalesOrderLineNo": 99, "OpenQuantity": 1, "IsActive": 1},
                          {"LocationCode": LOC, "PurchaseOrderNo": "PO-3", "LineNo": 1, "MaterialCode": "M-OK", "SupplierCode": "S-PAS", "OpenQuantity": 1,
                           "IsActive": 1}],
    "Forecast": [{"LocationCode": LOC, "MaterialCode": "M-OK", "Period": "2026-12-01", "Type": "T", "Quantity": 5, "ProjectCode": "P-YOK", "IsActive": 1}],
}


def put(eng, data: dict) -> None:
    with eng.begin() as c:
        for table, rows in data.items():
            batch = c.execute(sa.text("INSERT INTO adm.ImportBatch (Method, EntityName, LoadType, ReceivedAt, Status, [RowCount], ErrorCount) OUTPUT inserted.Id "
                                      "VALUES (N'Excel', :t, N'Tam', SYSUTCDATETIME(), N'Alındı', :n, 0)"), {"t": table, "n": len(rows)}).scalar_one()
            names = {k for r in rows for k in r}
            c.execute(sa.insert(raw_table(table)), [{"ImportBatchId": batch, "SourceRowNo": i + 2, "IsCurrent": True, **dict.fromkeys(names), **r}
                                                    for i, r in enumerate(rows)])
    with Session(eng) as s:
        for table in data:
            processed.rebuild(s, table)
        s.commit()


def run_cross(eng) -> None:
    with Session(eng) as s:
        engine.sync_rules(s, force=True)
        run_id = engine._new_run(s, None, engine.SCOPE_CROSS, engine.TRIGGER_BULK, None, None, None)
        s.commit()
        engine.run_cross(s, run_id, lambda _: None)


def found(eng) -> list[tuple]:
    with eng.connect() as c:
        rows = c.execute(sa.text("SELECT r.Code, f.EntityName, f.RowKey, f.Severity, f.Message FROM adm.ValidationFinding f "
                                 "JOIN adm.ValidationRule r ON r.Id = f.ValidationRuleId WHERE r.CheckType = N'Tablolar arası'")).all()
    return sorted(tuple(r) for r in rows)


@pytest.fixture(scope="module")
def hits(db_engine):
    clean(db_engine)
    put(db_engine, DATA)
    run_cross(db_engine)
    yield found(db_engine)
    clean(db_engine)


def of(hits, code: str) -> list[tuple]:
    return [(key, severity, message) for c, _, key, severity, message in hits if c == code]


def test_required_reference_is_error_with_the_value(hits):
    assert of(hits, "SO.REF_MATERIAL") == [(f"{LOC} · SO-1099 · 10 · 0", "Hata", "Malzeme bulunamadı: MAM-099"),
                                           ("ORM-99 · SO-LOC · 10 · 0", "Hata", "Malzeme bulunamadı: M-OK")]  # malzeme lokasyon içinde aranır
    assert of(hits, "BOM.REF_COMPONENT") == [(f"{LOC} · M-PRD2 · A-2 · SAT-999 · 10 · 1", "Hata", "Bileşen bulunamadı: SAT-999")]
    assert [m for _, _, m in of(hits, "PV.REF_BOM")] == ["Ürün ağacı bulunamadı: A-YOK"]
    assert [m for _, _, m in of(hits, "PV.REF_ROUTE")] == ["Rota bulunamadı: R-YOK"]


def test_optional_link_is_warning_only_when_filled(hits):
    assert of(hits, "SO.REF_PROJECT") == [(f"{LOC} · SO-PRJ · 10 · 0", "Uyarı", "Proje bulunamadı: P-YOK")]
    assert [(s, m) for _, s, m in of(hits, "WO.REF_PARENT_WORK_ORDER")] == [("Uyarı", "Orijinal iş emri bulunamadı: WO-YOK")]
    assert [(s, m) for _, s, m in of(hits, "RES.REF_SUBCONTRACTOR")] == [("Uyarı", "Fasoncu bulunamadı: S-YOK")]
    assert [(s, m) for _, s, m in of(hits, "UOM.REF_MATERIAL")] == [("Hata", "Malzeme bulunamadı: M-YOK")]  # anahtarın parçası: Zorunlu (doluysa), K-153


def test_resource_is_required_if_filled(hits):
    """Rotada kaynak sözleşmede isteğe bağlı (biri dolu olmalı), ama doluysa ve yoksa Hata; boş kaynak referans bulgusu vermez."""
    assert of(hits, "RTG.REF_RESOURCE") == [(f"{LOC} · R-1 · 10 · 2", "Hata", "Kaynak bulunamadı: K-YOK")]
    assert not of(hits, "RTG.REF_RESOURCE_GROUP")


def test_multi_field_link_narrows_only_by_filled_fields(hits):
    """Bağlı sipariş: satır no boşsa sipariş no yeter; satır no doluysa o satır aranır."""
    assert [k for k, _, _ in of(hits, "PO.REF_SALES_ORDER")] == [f"{LOC} · PO-2 · 1"]


def test_inactive_parent_has_its_class_and_no_reference_error(hits):
    assert of(hits, "SO.INACTIVE_MATERIAL") == [(f"{LOC} · SO-PAS · 10 · 0", "Uyarı", "Malzeme pasif: M-PAS")]
    assert [k for k, _, _ in of(hits, "SO.INACTIVE_CUSTOMER")] == [f"{LOC} · SO-CPAS · 10 · 0"]
    assert [(s, m) for _, s, m in of(hits, "STK.INACTIVE_MATERIAL")] == [("Bilgi", "Malzeme pasif: M-PAS")]
    assert [(s, m) for _, s, m in of(hits, "BOM.INACTIVE_COMPONENT")] == [("Uyarı", "Bileşen pasif: M-PAS")]
    assert [(s, m) for _, s, m in of(hits, "RTG.INACTIVE_RESOURCE")] == [("Uyarı", "Kaynak pasif: K-PAS")]
    assert [(s, m) for _, s, m in of(hits, "MS.INACTIVE_SUPPLIER")] == [("Uyarı", "Tedarikçi pasif: S-PAS")]
    assert [(s, m) for _, s, m in of(hits, "PO.INACTIVE_SUPPLIER")] == [("Uyarı", "Tedarikçi pasif: S-PAS")]
    assert not of(hits, "STK.REF_MATERIAL") and not of(hits, "BOM.REF_MATERIAL") and not [m for _, _, m in of(hits, "RTG.REF_RESOURCE") if "K-PAS" in m]


def test_inactive_child_enters_no_rule(hits):
    assert not [h for h in hits if "SO-OFF" in (h[2] or "")]


def test_common_location_and_unit_conversion(hits):
    assert of(hits, "ALL.REF_LOCATION") == [("ORM-99 · SO-LOC · 10 · 0", "Hata", "Lokasyon bulunamadı: ORM-99")]
    assert of(hits, "ALL.UOM_CONVERSION") == [(f"{LOC} · SO-UOM2 · 10 · 0", "Hata", "Birim dönüşümü yok: KG")]  # KOLI genel dönüşümle, ters yönden


def test_integrity_findings_are_on_the_parent(hits):
    keys = lambda code: [k for k, _, _ in of(hits, code)]  # noqa: E731
    assert keys("MAT.NO_VERSION") == [f"{LOC} · M-PRD"]                      # M-PRD2 aktif versiyonlu, M-REF benzetilen ürün
    assert sorted(keys("MAT.NO_SUPPLIER")) == [f"{LOC} · M-BUY2"]            # tedarikçisi pasif
    assert keys("MAT.NO_SUBCONTRACTOR") == [f"{LOC} · M-FSN2"]               # tedarikçisi fason değil
    assert keys("REF.NO_VERSION") == [f"{LOC} · M-REF · M-PRD"]
    assert keys("RTG.NO_VERSION") == [f"{LOC} · R-BOS · 10 · 1"]
    assert keys("BOM.NO_VERSION") == [f"{LOC} · M-PRD2 · A-2 · SAT-999 · 10 · 1"]
    assert keys("BOM.OPERATION_NOT_IN_ROUTE") == [f"{LOC} · M-PRD2 · A-1 · M-PAS · 30 · 2"]
    assert keys("RG.NO_RESOURCE") == [f"{LOC} · G-BOS"]
    assert sorted(keys("RES.UNUSED")) == [f"{LOC} · K-BOS"]
    assert keys("SUP.NO_MATERIAL") == ["S-BOS"]
    assert keys("SO.NOT_SELLABLE") == [f"{LOC} · SO-SELL · 10 · 0"]
    assert keys("WO.NO_STRUCTURE") == [f"{LOC} · WO-BOS"]
    assert keys("WOC.OPERATION_NOT_IN_WO") == [f"{LOC} · WO-OP · M-COMP · 20 · 1"]
    assert keys("PO.SUPPLIER_NOT_LISTED") == [f"{LOC} · PO-2 · 1", f"{LOC} · PO-3 · 1"]
    assert {s for c, *_, s, _ in [(h[0], h[3], h[4]) for h in hits] if c.startswith(("RES.UNUSED", "SUP.", "PO.SUPPLIER"))} == {"Bilgi"}


def test_missing_parent_table_is_no_data(hits):
    """Proje grubu yüklenmedi: kural satır satır bulgu yazmaz, "Karşılaştırılacak veri yok"; boş olabilecek tablo kuralı durdurmaz."""
    assert of(hits, "PRJ.REF_PROJECT_GROUP") == [(None, "Bilgi", "Karşılaştırılacak veri yok: Proje grubu.")]
    assert of(hits, "FC.REF_PROJECT") == [(f"{LOC} · M-OK · P-YOK · 01.12.2026 · T", "Hata", "Proje bulunamadı: P-YOK")]  # anahtarın parçası (K-153)
    assert of(hits, "FC.REF_MATERIAL") == []
    assert not [h for h in hits if h[0] == "MAT.NO_VERSION" and h[2] is None]  # benzetilen ürün tablosu doluysa da boşsa da çalışır


def test_cross_rules_refresh_when_parent_reloads():
    """Ebeveyn tablo yeniden yüklenince ona bakan kurallar tek tablo yolunda yenilenir (K-134)."""
    codes = {r.code for r in cat.related_cross("Material")}
    assert {"SO.REF_MATERIAL", "SO.INACTIVE_MATERIAL", "BOM.REF_COMPONENT", "ALL.UOM_CONVERSION", "SO.NOT_SELLABLE"} <= codes
    assert {"MAT.NO_VERSION"} <= {r.code for r in cat.related_cross("ProductionVersion")}

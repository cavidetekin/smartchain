"""İlişki haritası (K-146): her ilişki alanının baktığı tablo ve anahtar; zorunlu mu, isteğe bağlı mı; ebeveyn pasifse sınıf.

Tek kaynak docs/03 "İlişki haritası" tablosudur (test ikisini karşılaştırır). Zorunlu: sözleşmede alan zorunludur (ZOR. E). İsteğe bağlı: alan
boş bırakılabilir. İstisna "Zorunlu (doluysa)": rota ve iş emri operasyonundaki kaynak ve kaynak grubu sözleşmede isteğe bağlıdır (biri dolu
olmalı, K-116) ama doluysa ve yoksa Hata: kaynağı boşaltılarak yüklenen operasyon kapasite tüketmez, rota sessizce bozulur. Kaydın anahtarının
parçası olan isteğe bağlı bağlantı da "Zorunlu (doluysa)"dır (Birim dönüşümünün malzemesi, Tahminin müşterisi ve projesi, Stokun sahip alanları):
boş yazılsaydı anahtar değişir, kayıt başka bir kayda dönüşür ya da onunla çakışırdı (K-153). İki yerde kullanılır:
- Validasyon (4.4): referans kuralları (zorunlu → Hata, isteğe bağlı → Uyarı) ve pasif ebeveyn kuralları buradan üretilir.
- Load (5.2): kod `core` Id'sine bu haritayla çevrilir; zorunlu ilişkisi çevrilemeyen satır yüklenmez, isteğe bağlı bağlantı boş yazılır,
  pasif ebeveyne bakan satır yüklenmez.
Lokasyon ilişkisi (`LocationCode` → Lokasyon) her tabloda ortaktır ve burada ayrıca yazılmaz (`ALL.REF_LOCATION`).
Bir ilişki birden çok alanla eşleşebilir (ör. bağlı sipariş: SalesOrderNo, SalesOrderLineNo, SalesOrderLineItemNo); ilk alan doluysa bakılır,
öteki alanlar boşsa eşleşmeyi daraltmaz. Birim alanları referans kontrolüne girmez (K-112).
"""
from dataclasses import dataclass

REQUIRED, OPTIONAL, REQUIRED_IF_FILLED = "Zorunlu", "İsteğe bağlı", "Zorunlu (doluysa)"
WARNING, INFO = "Uyarı", "Bilgi"


@dataclass(frozen=True)
class Reference:
    prefix: str                      # kural kodunun ön eki (tablo)
    key: str                         # kural kodunun ilişki adı: <ÖN EK>.REF_<key>, <ÖN EK>.INACTIVE_<key>
    label: str                       # kullanıcı dilinde ilişki adı: "<label> bulunamadı", "<label> pasif"
    child: str                       # ilişki alanının tablosu
    fields: tuple[str, ...]          # çocuktaki alanlar (ilk alan doluysa bakılır)
    parent: str                      # ebeveyn tablo
    parent_fields: tuple[str, ...]   # ebeveyndeki karşılıkları (aynı sırayla)
    kind: str = REQUIRED             # Zorunlu: yoksa Hata, satır yüklenmez · İsteğe bağlı: doluysa ve yoksa Uyarı, bağlantı boş yazılır ·
                                     # Zorunlu (doluysa): alan boş olabilir, doluysa ve yoksa Hata, satır yüklenmez
    inactive: str | None = None      # ebeveyn pasifse bulgunun sınıfı (yoksa pasif kontrolü yok)
    by_location: bool = True         # LocationCode da eşleşir (lokasyondan bağımsız tablolar: Tedarikçi, Müşteri, Proje…)

    @property
    def is_error(self) -> bool:
        """Bulunamazsa Hata ve satır yüklenmez (Zorunlu ve Zorunlu (doluysa)); değilse Uyarı ve bağlantı boş yazılır."""
        return self.kind != OPTIONAL

    @property
    def child_match(self) -> tuple[str, ...]:
        return (("LocationCode",) if self.by_location else ()) + self.fields

    @property
    def parent_match(self) -> tuple[str, ...]:
        return (("LocationCode",) if self.by_location else ()) + self.parent_fields


R = Reference
SO_LINE = (("SalesOrderNo", "SalesOrderLineNo", "SalesOrderLineItemNo"), "SalesOrderLine", ("OrderNo", "LineNo", "LineItemNo"))

REFERENCES: tuple[Reference, ...] = (
    R("UOM", "MATERIAL", "Malzeme", "UomConversion", ("MaterialCode",), "Material", ("Code",), REQUIRED_IF_FILLED, by_location=False),  # K-112: lokasyondan bağımsız
    R("PV", "MATERIAL", "Malzeme", "ProductionVersion", ("MaterialCode",), "Material", ("Code",), inactive=INFO),
    R("PV", "BOM", "Ürün ağacı", "ProductionVersion", ("BOMCode", "MaterialCode"), "BOM", ("Code", "MaterialCode")),
    R("PV", "ROUTE", "Rota", "ProductionVersion", ("RouteCode",), "Routing", ("RouteCode",)),
    R("BOM", "MATERIAL", "Üretilen malzeme", "BOM", ("MaterialCode",), "Material", ("Code",)),
    R("BOM", "COMPONENT", "Bileşen", "BOM", ("ComponentMaterialCode",), "Material", ("Code",), inactive=WARNING),
    R("RTG", "RESOURCE", "Kaynak", "Routing", ("ResourceCode",), "Resource", ("Code",), REQUIRED_IF_FILLED, inactive=WARNING),
    R("RTG", "RESOURCE_GROUP", "Kaynak grubu", "Routing", ("ResourceGroupCode",), "ResourceGroup", ("Code",), REQUIRED_IF_FILLED),
    R("REF", "MATERIAL", "Benzetilen ürün", "MaterialReference", ("MaterialCode",), "Material", ("Code",)),
    R("REF", "REFERENCE_MATERIAL", "Referans ürün", "MaterialReference", ("ReferenceMaterialCode",), "Material", ("Code",)),
    R("REF", "REFERENCE_VERSION", "Referans versiyon", "MaterialReference", ("ReferenceProductionVersionCode", "ReferenceMaterialCode"), "ProductionVersion",
      ("Code", "MaterialCode"), OPTIONAL),  # boşsa motor seçer
    R("RES", "SUBCONTRACTOR", "Fasoncu", "Resource", ("SubcontractorCode",), "Supplier", ("Code",), OPTIONAL, by_location=False),
    R("RGA", "RESOURCE_GROUP", "Kaynak grubu", "ResourceGroupAssignment", ("ResourceGroupCode",), "ResourceGroup", ("Code",)),
    R("RGA", "RESOURCE", "Kaynak", "ResourceGroupAssignment", ("ResourceCode",), "Resource", ("Code",)),
    R("ABS", "RESOURCE", "Kaynak", "EmployeeAbsence", ("ResourceCode",), "Resource", ("Code",)),
    R("MS", "MATERIAL", "Malzeme", "MaterialSupplier", ("MaterialCode",), "Material", ("Code",)),
    R("MS", "SUPPLIER", "Tedarikçi", "MaterialSupplier", ("SupplierCode",), "Supplier", ("Code",), inactive=WARNING, by_location=False),
    R("PRJ", "PROJECT_GROUP", "Proje grubu", "Project", ("ProjectGroupCode",), "ProjectGroup", ("Code",), OPTIONAL, by_location=False),
    R("SO", "CUSTOMER", "Müşteri", "SalesOrderLine", ("CustomerCode",), "Customer", ("Code",), inactive=WARNING, by_location=False),
    R("SO", "MATERIAL", "Malzeme", "SalesOrderLine", ("MaterialCode",), "Material", ("Code",), inactive=WARNING),
    R("SO", "PROJECT", "Proje", "SalesOrderLine", ("ProjectCode",), "Project", ("Code",), OPTIONAL, by_location=False),
    R("FC", "MATERIAL", "Malzeme", "Forecast", ("MaterialCode",), "Material", ("Code",), inactive=WARNING),
    R("FC", "CUSTOMER", "Müşteri", "Forecast", ("CustomerCode",), "Customer", ("Code",), REQUIRED_IF_FILLED, by_location=False),
    R("FC", "PROJECT", "Proje", "Forecast", ("ProjectCode",), "Project", ("Code",), REQUIRED_IF_FILLED, by_location=False),
    R("STK", "MATERIAL", "Malzeme", "Stock", ("MaterialCode",), "Material", ("Code",), inactive=INFO),
    R("STK", "PROJECT", "Sahip proje", "Stock", ("ProjectCode",), "Project", ("Code",), REQUIRED_IF_FILLED, by_location=False),
    R("STK", "CUSTOMER", "Sahip müşteri", "Stock", ("CustomerCode",), "Customer", ("Code",), REQUIRED_IF_FILLED, by_location=False),
    R("STK", "SALES_ORDER", "Sahip sipariş satırı", "Stock", SO_LINE[0], SO_LINE[1], SO_LINE[2], REQUIRED_IF_FILLED),
    R("BP", "MATERIAL", "Malzeme", "BorrowPayback", ("MaterialCode",), "Material", ("Code",)),
    R("BP", "LENDING_PROJECT", "Ödünç veren proje", "BorrowPayback", ("LendingProjectCode",), "Project", ("Code",), by_location=False),
    R("BP", "BORROWING_PROJECT", "Ödünç alan proje", "BorrowPayback", ("BorrowingProjectCode",), "Project", ("Code",), by_location=False),
    R("WO", "MATERIAL", "Üretilen malzeme", "WorkOrder", ("MaterialCode",), "Material", ("Code",), inactive=WARNING),
    R("WO", "VERSION", "Üretim versiyonu", "WorkOrder", ("ProductionVersionCode", "MaterialCode"), "ProductionVersion", ("Code", "MaterialCode"), OPTIONAL),
    R("WO", "PROJECT", "Proje", "WorkOrder", ("ProjectCode",), "Project", ("Code",), OPTIONAL, by_location=False),
    R("WO", "CUSTOMER", "Müşteri", "WorkOrder", ("CustomerCode",), "Customer", ("Code",), OPTIONAL, by_location=False),
    R("WO", "SALES_ORDER", "Bağlı sipariş satırı", "WorkOrder", SO_LINE[0], SO_LINE[1], SO_LINE[2], OPTIONAL),
    R("WO", "PARENT_WORK_ORDER", "Orijinal iş emri", "WorkOrder", ("ParentWorkOrderNo",), "WorkOrder", ("WorkOrderNo",), OPTIONAL),
    R("WOC", "WORK_ORDER", "İş emri", "WorkOrderComponent", ("WorkOrderNo",), "WorkOrder", ("WorkOrderNo",)),
    R("WOC", "MATERIAL", "Malzeme", "WorkOrderComponent", ("MaterialCode",), "Material", ("Code",)),
    R("WOO", "WORK_ORDER", "İş emri", "WorkOrderOperation", ("WorkOrderNo",), "WorkOrder", ("WorkOrderNo",)),
    R("WOO", "RESOURCE", "Kaynak", "WorkOrderOperation", ("ResourceCode",), "Resource", ("Code",), REQUIRED_IF_FILLED),
    R("WOO", "RESOURCE_GROUP", "Kaynak grubu", "WorkOrderOperation", ("ResourceGroupCode",), "ResourceGroup", ("Code",), REQUIRED_IF_FILLED),
    R("PO", "MATERIAL", "Malzeme", "PurchaseOrderLine", ("MaterialCode",), "Material", ("Code",), inactive=WARNING),
    R("PO", "SUPPLIER", "Tedarikçi", "PurchaseOrderLine", ("SupplierCode",), "Supplier", ("Code",), OPTIONAL, inactive=WARNING, by_location=False),
    R("PO", "PROJECT", "Proje", "PurchaseOrderLine", ("ProjectCode",), "Project", ("Code",), OPTIONAL, by_location=False),
    R("PO", "CUSTOMER", "Müşteri", "PurchaseOrderLine", ("CustomerCode",), "Customer", ("Code",), OPTIONAL, by_location=False),
    R("PO", "SALES_ORDER", "Bağlı sipariş satırı", "PurchaseOrderLine", SO_LINE[0], SO_LINE[1], SO_LINE[2], OPTIONAL),
    R("PO", "WORK_ORDER", "Bağlı iş emri", "PurchaseOrderLine", ("WorkOrderNo",), "WorkOrder", ("WorkOrderNo",), OPTIONAL),
    R("PC", "WORK_ORDER", "İş emri", "ProductionConfirmation", ("WorkOrderNo",), "WorkOrder", ("WorkOrderNo",)),
    R("PC", "MATERIAL", "Malzeme", "ProductionConfirmation", ("MaterialCode",), "Material", ("Code",)),
)

# Uom alanları: malzemenin temel biriminden farklıysa dönüşüm gerekir (K-112); alan → malzeme alanı
UOM_FIELDS: dict[str, tuple[str, str]] = {
    "BOM": ("ComponentUom", "ComponentMaterialCode"),
    "SalesOrderLine": ("Uom", "MaterialCode"),
    "Forecast": ("Uom", "MaterialCode"),
    "Stock": ("Uom", "MaterialCode"),
    "WorkOrder": ("Uom", "MaterialCode"),
    "WorkOrderComponent": ("Uom", "MaterialCode"),
    "PurchaseOrderLine": ("Uom", "MaterialCode"),
}


def of(child: str) -> list[Reference]:
    return [r for r in REFERENCES if r.child == child]

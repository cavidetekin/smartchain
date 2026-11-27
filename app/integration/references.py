"""İlişki haritası (K-146): her ilişki alanının baktığı tablo ve anahtar; zorunlu mu, isteğe bağlı mı; ebeveyn pasifse sınıf.

Tek kaynak docs/03 "İlişki haritası" tablosudur (test ikisini karşılaştırır). Zorunlu: sözleşmede alan zorunludur (ZOR. E). İsteğe bağlı: alan
boş bırakılabilir. Rota ve üretim siparişi operasyonunda kaynak grubu zorunludur (K-180; "kaynak ya da kaynak grubu" istisnası kalktı). İstisna
"Zorunlu (doluysa)": kaydın anahtarının parçası olan isteğe bağlı bağlantı (Birim dönüşümünün malzemesi, Tahminin müşterisi ve projesi):
boş yazılsaydı anahtar değişir, kayıt başka bir kayda dönüşür ya da onunla çakışırdı (K-153). İki yerde kullanılır:
- Validasyon (4.4): referans kuralları (zorunlu → Hata, isteğe bağlı → Uyarı) ve pasif ebeveyn kuralları buradan üretilir.
- Load (5.2): kod `core` Id'sine bu haritayla çevrilir; zorunlu ilişkisi çevrilemeyen satır yüklenmez, isteğe bağlı bağlantı boş yazılır,
  pasif ebeveyne bakan satır yüklenmez.
Lokasyon ilişkisi (`LocationCode` → Lokasyon) her tabloda ortaktır ve burada ayrıca yazılmaz (`ALL.REF_LOCATION`).
Bir ilişki birden çok alanla eşleşebilir (ör. bağlı sipariş: SalesOrderNo, SalesOrderLineNo, SalesOrderLineItemNo); ilk alan doluysa bakılır,
öteki alanlar boşsa eşleşmeyi daraltmaz. Kalemsiz arz (K-198): bağlı siparişte satır no boşsa validasyon sipariş no'nun en az bir satırını arar,
aktarım bağlantıyı (`SalesOrderLineId`) boş yazar (`link_fields`); sipariş no `core`'da ayrı alanda durur. Arzın (stok, üretim siparişi, satın alma
satırı) sahip ilişkileri isteğe bağlıdır (K-198): sahip bulunamazsa Uyarı, satır yüklenir, iç bağ boş kalır; ERP'nin yazdığı kod `core`'da durur ve özel
alokasyon anahtarı ondan kurulur (arz genele düşmez). Birim alanları referans kontrolüne
girmez (K-112).
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
    link_fields: int = 1             # bağlantının yazılması için dolu olması gereken baştaki alan sayısı (bağlı sipariş: sipariş no ve satır no)

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
    R("RTG", "RESOURCE_GROUP", "Kaynak grubu", "Routing", ("ResourceGroupCode",), "ResourceGroup", ("Code",), inactive=WARNING),
    R("REF", "MATERIAL", "Benzetilen ürün", "MaterialReference", ("MaterialCode",), "Material", ("Code",)),
    R("REF", "REFERENCE_MATERIAL", "Referans ürün", "MaterialReference", ("ReferenceMaterialCode",), "Material", ("Code",)),
    R("REF", "REFERENCE_VERSION", "Referans versiyon", "MaterialReference", ("ReferenceProductionVersionCode", "ReferenceMaterialCode"), "ProductionVersion",
      ("Code", "MaterialCode"), OPTIONAL),  # boşsa motor seçer
    R("RG", "SUBCONTRACTOR", "Fasoncu", "ResourceGroup", ("SubcontractorCode",), "Supplier", ("Code",), OPTIONAL, by_location=False),
    R("RGM", "RESOURCE_GROUP", "Kaynak grubu", "ResourceGroupMember", ("ResourceGroupCode",), "ResourceGroup", ("Code",)),
    R("RGM", "RESOURCE", "Kaynak", "ResourceGroupMember", ("ResourceCode",), "Resource", ("Code",)),
    R("ABS", "RESOURCE", "Kaynak", "EmployeeAbsence", ("ResourceCode",), "Resource", ("Code",)),
    R("MS", "MATERIAL", "Malzeme", "MaterialSupplier", ("MaterialCode",), "Material", ("Code",)),
    R("MS", "SUPPLIER", "Tedarikçi", "MaterialSupplier", ("SupplierCode",), "Supplier", ("Code",), inactive=WARNING, by_location=False),
    R("SO", "CUSTOMER", "Müşteri", "SalesOrderLine", ("CustomerCode",), "Customer", ("Code",), inactive=WARNING, by_location=False),
    R("SO", "MATERIAL", "Malzeme", "SalesOrderLine", ("MaterialCode",), "Material", ("Code",), inactive=WARNING),
    R("SO", "PROJECT", "Proje", "SalesOrderLine", ("ProjectCode",), "Project", ("Code",), OPTIONAL, by_location=False),
    R("FC", "MATERIAL", "Malzeme", "Forecast", ("MaterialCode",), "Material", ("Code",), inactive=WARNING),
    R("FC", "CUSTOMER", "Müşteri", "Forecast", ("CustomerCode",), "Customer", ("Code",), REQUIRED_IF_FILLED, by_location=False),
    R("FC", "PROJECT", "Proje", "Forecast", ("ProjectCode",), "Project", ("Code",), REQUIRED_IF_FILLED, by_location=False),
    R("STK", "MATERIAL", "Malzeme", "Stock", ("MaterialCode",), "Material", ("Code",), inactive=INFO),
    R("STK", "PROJECT", "Bağlı proje", "Stock", ("ProjectCode",), "Project", ("Code",), OPTIONAL, by_location=False),
    R("STK", "CUSTOMER", "Bağlı müşteri", "Stock", ("CustomerCode",), "Customer", ("Code",), OPTIONAL, by_location=False),
    R("STK", "SALES_ORDER", "Bağlı sipariş", "Stock", SO_LINE[0], SO_LINE[1], SO_LINE[2], OPTIONAL, link_fields=2),
    R("BP", "MATERIAL", "Malzeme", "BorrowPayback", ("MaterialCode",), "Material", ("Code",)),
    R("BP", "LENDING_PROJECT", "Ödünç veren proje", "BorrowPayback", ("LendingProjectCode",), "Project", ("Code",), by_location=False),
    R("BP", "BORROWING_PROJECT", "Ödünç alan proje", "BorrowPayback", ("BorrowingProjectCode",), "Project", ("Code",), by_location=False),
    R("WO", "MATERIAL", "Üretilen malzeme", "WorkOrder", ("MaterialCode",), "Material", ("Code",), inactive=WARNING),
    R("WO", "VERSION", "Üretim versiyonu", "WorkOrder", ("ProductionVersionCode", "MaterialCode"), "ProductionVersion", ("Code", "MaterialCode"), OPTIONAL),
    R("WO", "PROJECT", "Bağlı proje", "WorkOrder", ("ProjectCode",), "Project", ("Code",), OPTIONAL, by_location=False),
    R("WO", "CUSTOMER", "Bağlı müşteri", "WorkOrder", ("CustomerCode",), "Customer", ("Code",), OPTIONAL, by_location=False),
    R("WO", "SALES_ORDER", "Bağlı sipariş", "WorkOrder", SO_LINE[0], SO_LINE[1], SO_LINE[2], OPTIONAL, link_fields=2),
    R("WO", "PARENT_WORK_ORDER", "Orijinal üretim siparişi", "WorkOrder", ("ParentWorkOrderNo",), "WorkOrder", ("WorkOrderNo",), OPTIONAL),
    R("WOC", "WORK_ORDER", "Üretim siparişi", "WorkOrderComponent", ("WorkOrderNo",), "WorkOrder", ("WorkOrderNo",)),
    R("WOC", "MATERIAL", "Malzeme", "WorkOrderComponent", ("MaterialCode",), "Material", ("Code",)),
    R("WOO", "WORK_ORDER", "Üretim siparişi", "WorkOrderOperation", ("WorkOrderNo",), "WorkOrder", ("WorkOrderNo",)),
    R("WOO", "RESOURCE_GROUP", "Kaynak grubu", "WorkOrderOperation", ("ResourceGroupCode",), "ResourceGroup", ("Code",)),
    R("PO", "MATERIAL", "Malzeme", "PurchaseOrderLine", ("MaterialCode",), "Material", ("Code",), inactive=WARNING),
    R("PO", "SUPPLIER", "Tedarikçi", "PurchaseOrderLine", ("SupplierCode",), "Supplier", ("Code",), OPTIONAL, inactive=WARNING, by_location=False),
    R("PO", "PROJECT", "Bağlı proje", "PurchaseOrderLine", ("ProjectCode",), "Project", ("Code",), OPTIONAL, by_location=False),
    R("PO", "CUSTOMER", "Bağlı müşteri", "PurchaseOrderLine", ("CustomerCode",), "Customer", ("Code",), OPTIONAL, by_location=False),
    R("PO", "SALES_ORDER", "Bağlı sipariş", "PurchaseOrderLine", SO_LINE[0], SO_LINE[1], SO_LINE[2], OPTIONAL, link_fields=2),
    R("PO", "WORK_ORDER", "Bağlı üretim siparişi", "PurchaseOrderLine", ("WorkOrderNo",), "WorkOrder", ("WorkOrderNo",), OPTIONAL),
    R("PC", "WORK_ORDER", "Üretim siparişi", "ProductionConfirmation", ("WorkOrderNo",), "WorkOrder", ("WorkOrderNo",)),
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

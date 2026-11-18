// Ana veri (ekran 03) ve İşlem verisi (ekran 29) sekmeleri ve tabloları (K-168, K-169); sunucudaki sırayla aynı
// (app/api/lists/master_data.py MASTER_TABS, TRANSACTION_TABS). Kayda giden adres de buradan (detay kartı, K-171, K-173).
import { tr } from "../i18n/tr";

export interface TableDef { list: string; slug: string; label: string }
export interface TabDef { key: string; label: string; tables: TableDef[] }
/** Kartın sekmesi: Geçmiş ya da ilişkinin adresteki adı (ör. "uretim-versiyonu"; K-173). */
export type CardTab = string;
export const HISTORY_TAB = "history";

const M = tr.masterData;
const X = tr.transactionData;

export const MASTER_TABS: TabDef[] = [
  { key: "malzeme", label: M.tabs.material, tables: [
    { list: "materials", slug: "malzeme", label: M.tables.material },
    { list: "master-material-reference", slug: "benzetilen-urun", label: M.tables.materialReference }] },
  { key: "urun-agaci-ve-rota", label: M.tabs.bomRouting, tables: [
    { list: "master-production-version", slug: "uretim-versiyonu", label: M.tables.productionVersion },
    { list: "master-bom", slug: "urun-agaci", label: M.tables.bom },
    { list: "master-routing", slug: "rota", label: M.tables.routing }] },
  { key: "kaynak", label: M.tabs.resource, tables: [
    { list: "master-resource", slug: "kaynak", label: M.tables.resource },
    { list: "master-resource-group", slug: "kaynak-grubu", label: M.tables.resourceGroup },
    { list: "master-resource-group-member", slug: "grup-eslesmesi", label: M.tables.groupMember }] },
  { key: "tedarikci-ve-musteri", label: M.tabs.supplierCustomer, tables: [
    { list: "master-supplier", slug: "tedarikci", label: M.tables.supplier },
    { list: "master-material-supplier", slug: "malzeme-tedarikcisi", label: M.tables.materialSupplier },
    { list: "master-customer", slug: "musteri", label: M.tables.customer }] },
  { key: "lokasyon-ve-birim", label: M.tabs.locationUnit, tables: [
    { list: "master-location", slug: "lokasyon", label: M.tables.location },
    { list: "master-unit-of-measure", slug: "birim", label: M.tables.unit },
    { list: "master-uom-conversion", slug: "birim-donusumu", label: M.tables.uomConversion }] },
];

export const TRANSACTION_TABS: TabDef[] = [
  { key: "talep", label: X.tabs.demand, tables: [
    { list: "transaction-sales-order", slug: "satis-siparisi", label: X.tables.salesOrder },
    { list: "transaction-forecast", slug: "tahmin", label: X.tables.forecast },
    { list: "transaction-project", slug: "proje", label: X.tables.project },
    { list: "transaction-project-group", slug: "proje-grubu", label: X.tables.projectGroup }] },
  { key: "stok", label: X.tabs.stock, tables: [
    { list: "transaction-stock", slug: "stok", label: X.tables.stock },
    { list: "transaction-borrow-payback", slug: "odunc-ve-geri-odeme", label: X.tables.borrowPayback }] },
  { key: "uretim", label: X.tabs.production, tables: [
    { list: "transaction-work-order", slug: "is-emri", label: X.tables.workOrder },
    { list: "transaction-work-order-component", slug: "is-emri-bileseni", label: X.tables.workOrderComponent },
    { list: "transaction-work-order-operation", slug: "is-emri-operasyonu", label: X.tables.workOrderOperation },
    { list: "transaction-production-confirmation", slug: "uretim-gerceklesmesi", label: X.tables.productionConfirmation }] },
  { key: "satin-alma", label: X.tabs.purchase, tables: [
    { list: "transaction-purchase-order", slug: "satin-alma-siparisi", label: X.tables.purchaseOrder }] },
  { key: "izin", label: X.tabs.absence, tables: [
    { list: "transaction-employee-absence", slug: "calisan-izni", label: X.tables.employeeAbsence }] },
];

export const DATA_SCREENS = [
  { path: "/veri/ana-veri", tabs: MASTER_TABS },
  { path: "/veri/islem-verisi", tabs: TRANSACTION_TABS },
] as const;

/** Kartın sekmesi adreste (`kart=`): Geçmiş "gecmis", ilişki kendi adıyla. */
const HISTORY_SLUG = "gecmis";
export const cardSlug = (tab: CardTab): string => (tab === HISTORY_TAB ? HISTORY_SLUG : tab);
export const cardOfSlug = (slug: string | null): CardTab | null => (!slug ? null : slug === HISTORY_SLUG ? HISTORY_TAB : slug);

/** İlişkinin adresteki adı: Türkçe karaktersiz, küçük harf, tireli ("Kullanıldığı ağaçlar" → "kullanildigi-agaclar"). */
export function relationSlug(label: string): string {
  const map: Record<string, string> = { ç: "c", ğ: "g", ı: "i", ö: "o", ş: "s", ü: "u", â: "a", î: "i", û: "u" };
  return label.toLocaleLowerCase("tr").replace(/[çğıöşüâîû]/g, (ch) => map[ch]).replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

/** Ekranın adres sorgusu: sekme, çok tablolu sekmede tablo, açık kart (K-171), yalnız bir kaydı gösteren süzgeç (`yalniz`, K-174). */
export function screenQuery(tab: TabDef, table: TableDef, card: { id: string; tab: CardTab } | null, only: string | null = null): string {
  return new URLSearchParams({
    sekme: tab.key, ...(tab.tables.length > 1 ? { tablo: table.slug } : {}),
    ...(card ? { kayit: card.id, kart: cardSlug(card.tab) } : {}),
    ...(only ? { yalniz: only } : {}),
  }).toString();
}

function screenOf(list: string): { path: string; tab: TabDef; table: TableDef } | null {
  for (const screen of DATA_SCREENS) {
    for (const tab of screen.tabs) {
      const table = tab.tables.find((t) => t.list === list);
      if (table) return { path: screen.path, tab, table };
    }
  }
  return null;
}

/** Kaydın kartına giden adres (denetim izinde "Kayda git", ilişkili satırın rozeti; K-173): tablo bütün kayıtlarıyla, kayıt seçili ve kartı açık;
 *  liste bilinmiyorsa null. */
export function recordUrl(list: string, id: string | number, card: CardTab = HISTORY_TAB): string | null {
  const at = screenOf(list);
  return at ? `${at.path}?${screenQuery(at.tab, at.table, { id: String(id), tab: card })}` : null;
}

/** Yalnız o kaydı gösteren adres (Veri kalitesinde "Kayda git", K-174): tablo kaydın Id'siyle süzülü, kart kapalı; liste bilinmiyorsa null. */
export function onlyRecordUrl(list: string, id: string | number): string | null {
  const at = screenOf(list);
  return at ? `${at.path}?${screenQuery(at.tab, at.table, null, String(id))}` : null;
}

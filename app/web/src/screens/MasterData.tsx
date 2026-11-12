// Ana veri (ekran 03, fonksiyon 10; K-168, K-169): beş sekme, aktarılan ana veri, salt okunur. Proje İşlem verisi'nde.
import { tr } from "../i18n/tr";
import { DataScreen, type TabDef } from "./DataScreen";

const T = tr.masterData;

/** Sunucudaki sırayla aynı (app/api/lists/master_data.py MASTER_TABS). */
export const MASTER_TABS: TabDef[] = [
  { key: "malzeme", label: T.tabs.material, tables: [
    { list: "materials", slug: "malzeme", label: T.tables.material },
    { list: "master-material-reference", slug: "benzetilen-urun", label: T.tables.materialReference }] },
  { key: "urun-agaci-ve-rota", label: T.tabs.bomRouting, tables: [
    { list: "master-production-version", slug: "uretim-versiyonu", label: T.tables.productionVersion },
    { list: "master-bom", slug: "urun-agaci", label: T.tables.bom },
    { list: "master-routing", slug: "rota", label: T.tables.routing }] },
  { key: "kaynak", label: T.tabs.resource, tables: [
    { list: "master-resource", slug: "kaynak", label: T.tables.resource },
    { list: "master-resource-group", slug: "kaynak-grubu", label: T.tables.resourceGroup },
    { list: "master-resource-group-assignment", slug: "grup-atamasi", label: T.tables.groupAssignment }] },
  { key: "tedarikci-ve-musteri", label: T.tabs.supplierCustomer, tables: [
    { list: "master-supplier", slug: "tedarikci", label: T.tables.supplier },
    { list: "master-material-supplier", slug: "malzeme-tedarikcisi", label: T.tables.materialSupplier },
    { list: "master-customer", slug: "musteri", label: T.tables.customer }] },
  { key: "lokasyon-ve-birim", label: T.tabs.locationUnit, tables: [
    { list: "master-location", slug: "lokasyon", label: T.tables.location },
    { list: "master-unit-of-measure", slug: "birim", label: T.tables.unit },
    { list: "master-uom-conversion", slug: "birim-donusumu", label: T.tables.uomConversion }] },
];

export function MasterData() {
  return <DataScreen id="masterData" title={T.title} sections={T.sections} tabs={MASTER_TABS} countsUrl="/api/master-data/counts" />;
}

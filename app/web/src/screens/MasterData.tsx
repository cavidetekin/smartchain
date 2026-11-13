// Ana veri (ekran 03, fonksiyon 10; K-168, K-169): beş sekme, aktarılan ana veri, salt okunur. Proje İşlem verisi'nde. Detay kartı: Geçmiş ve
// İlişkili kayıtlar (K-171, K-173).
import { tr } from "../i18n/tr";
import { DataScreen } from "./DataScreen";
import { MASTER_TABS } from "./dataScreenTabs";

export { MASTER_TABS } from "./dataScreenTabs";

export function MasterData() {
  return <DataScreen id="masterData" title={tr.masterData.title} sections={tr.masterData.sections} tabs={MASTER_TABS} countsUrl="/api/master-data/counts" />;
}

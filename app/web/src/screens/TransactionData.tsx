// İşlem verisi (ekran 29, fonksiyon 102; K-169): sekmeler aktarım gruplarıyla aynı (K-150), aktarılan işlem verisi, salt okunur. Detay kartı:
// Geçmiş (K-171, K-173).
import { tr } from "../i18n/tr";
import { DataScreen } from "./DataScreen";
import { TRANSACTION_TABS } from "./dataScreenTabs";

export { TRANSACTION_TABS } from "./dataScreenTabs";

export function TransactionData() {
  return <DataScreen id="transactionData" title={tr.transactionData.title} sections={tr.transactionData.sections} tabs={TRANSACTION_TABS} countsUrl="/api/transaction-data/counts" />;
}

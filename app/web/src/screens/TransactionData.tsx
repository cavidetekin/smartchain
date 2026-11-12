// İşlem verisi (ekran 29, fonksiyon 102; K-169): sekmeler aktarım gruplarıyla aynı (K-150), aktarılan işlem verisi, salt okunur.
import { tr } from "../i18n/tr";
import { DataScreen, type TabDef } from "./DataScreen";

const T = tr.transactionData;

/** Sunucudaki sırayla aynı (app/api/lists/master_data.py TRANSACTION_TABS). */
export const TRANSACTION_TABS: TabDef[] = [
  { key: "talep", label: T.tabs.demand, tables: [
    { list: "transaction-sales-order", slug: "satis-siparisi", label: T.tables.salesOrder },
    { list: "transaction-forecast", slug: "tahmin", label: T.tables.forecast },
    { list: "transaction-project", slug: "proje", label: T.tables.project },
    { list: "transaction-project-group", slug: "proje-grubu", label: T.tables.projectGroup }] },
  { key: "stok", label: T.tabs.stock, tables: [
    { list: "transaction-stock", slug: "stok", label: T.tables.stock },
    { list: "transaction-borrow-payback", slug: "odunc-ve-geri-odeme", label: T.tables.borrowPayback }] },
  { key: "uretim", label: T.tabs.production, tables: [
    { list: "transaction-work-order", slug: "is-emri", label: T.tables.workOrder },
    { list: "transaction-work-order-component", slug: "is-emri-bileseni", label: T.tables.workOrderComponent },
    { list: "transaction-work-order-operation", slug: "is-emri-operasyonu", label: T.tables.workOrderOperation },
    { list: "transaction-production-confirmation", slug: "uretim-gerceklesmesi", label: T.tables.productionConfirmation }] },
  { key: "satin-alma", label: T.tabs.purchase, tables: [
    { list: "transaction-purchase-order", slug: "satin-alma-siparisi", label: T.tables.purchaseOrder }] },
  { key: "izin", label: T.tabs.absence, tables: [
    { list: "transaction-employee-absence", slug: "calisan-izni", label: T.tables.employeeAbsence }] },
];

export function TransactionData() {
  return <DataScreen id="transactionData" title={T.title} sections={T.sections} tabs={TRANSACTION_TABS} countsUrl="/api/transaction-data/counts" />;
}

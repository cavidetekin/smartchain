// Kapasite yönetimi (ekran 30, fonksiyon 24; K-185, docs/12 "Kapasite yönetimi"). 7.9a: Kapasite özeti sekmesi: bütün kaynak grupları × dönem
// (dönem tablosu, K-184; ürünün Standart'ı pivot; salt okunur, girişlerden hesaplanır). Giriş sekmeleri (Kaynak grubu, Kaynak, Çalışma düzeni,
// Bakım ve duruşlar, Verimlilik, Fabrika takvimi, Ek mesai limitleri) 7.9b'de eklenir. Ekran senaryoya bağlıdır: senaryo değişince baştan yüklenir.
import { tr } from "../i18n/tr";
import { DataTable } from "../table/DataTable";
import { OverflowTabs } from "../ui";

const T = tr.capacity;
type Tab = "ozet";
const TABS: { value: Tab; label: string }[] = [{ value: "ozet", label: T.tabs.summary }];

export function CapacityManagement() {
  const lead = <OverflowTabs<Tab> label={T.sections} value="ozet" onChange={() => undefined} options={TABS} />;
  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{T.title}</h1>
      </header>
      <DataTable list="period-resource-group" toolbarLead={lead} />
    </section>
  );
}

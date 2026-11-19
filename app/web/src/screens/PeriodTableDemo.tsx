// Dönem tablosu deneme sayfası (/donem-tablosu, docs/12 "Dönem tablosu standardı", K-184): "Kaynak grubu × dönem (deneme)". Ekran değildir;
// menüde yer almaz. Dönemler bağlam çubuğunda seçili senaryonun ufkundan gelir: senaryo değişince tablo yeniden kurulur. 7.9'da kalkar.
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { DataTable } from "../table/DataTable";

export function PeriodTableDemo() {
  const { scenario } = useShell();
  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{tr.periodDemo.title}</h1>
      </header>
      <DataTable key={scenario?.id ?? 0} list="period-resource-group-demo" />
    </section>
  );
}

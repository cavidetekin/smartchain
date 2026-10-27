// Tablo bileşeni deneme sayfası (/tablo, docs/12): sentetik malzeme listesi. Ekran değildir; menüde yer almaz.
import { tr } from "../i18n/tr";
import { DataTable } from "../table/DataTable";

export function TableDemo() {
  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{tr.demo.title}</h1>
        <p className="sc-muted">{tr.demo.intro}</p>
      </header>
      <DataTable list="materials" />
    </section>
  );
}

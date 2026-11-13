// Veri ekranlarının ortak bileşeni (Ana veri 03, İşlem verisi 29; K-168, K-169): aktarılan veri, salt okunur. Sekmeler; çok tablolu sekmede tablo
// seçimi ortak tablonun araç çubuğunun başında açılır liste (kayıt sayılarıyla), tek tablolu sekmede yok (docs/12 "Bölüm ve tablo seçimi").
// Standart görünümde aktarılan bütün alanlar açık; sığmayan kolonlar için tablo kendi içinde yana kayar. İlk sekme varsayılan; son açılan
// sekme ve her sekmenin son tablosu kullanıcı başına hatırlanır.
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { getJson } from "../api/client";
import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { userPrefs } from "../prefs";
import { useShell } from "../shell/ShellContext";
import { DataTable, type FieldHints } from "../table/DataTable";
import type { ListColumn } from "../table/types";
import { UnsavedGuard } from "../table/useTableEdits";
import { Alert, ConfirmDialog, Segment } from "../ui";
import { useManualValues } from "./useManualValues";

const T = tr.dataScreen;
const MT = tr.manualValues;

export interface TableDef { list: string; slug: string; label: string }
export interface TabDef { key: string; label: string; tables: TableDef[] }

export interface DataCounts {
  data_version: number | null;
  /** Güncel veri versiyonundaki satır; veri yüklenmediyse null. */
  tabs: { key: string; tables: { list: string; label: string; count: number | null }[] }[];
}

/** Kolon genişlikleri: kod ve kısa alanlar dar, uzun başlıklı sayı alanları kesilmesin. */
const HINTS: FieldHints = {
  Code: { width: 9 }, MaterialCode: { width: 9 }, ComponentMaterialCode: { width: 9 }, ReferenceMaterialCode: { width: 9 },
  ReferenceProductionVersionCode: { width: 9 }, ResourceCode: { width: 8 }, ResourceGroupCode: { width: 9 }, SupplierCode: { width: 8 },
  ProjectGroupCode: { width: 9 }, CalendarCode: { width: 8 }, RouteCode: { width: 9 }, BOMCode: { width: 9 }, LocationCode: { width: 8 },
  CustomerCode: { width: 8 }, ProjectCode: { width: 8 }, WorkOrderCode: { width: 9 }, ProductionVersionCode: { width: 9 },
  BaseUom: { width: 7 }, ComponentUom: { width: 7 }, CapacityUnit: { width: 8 }, FromUom: { width: 6 }, ToUom: { width: 6 }, Uom: { width: 7 },
  OperationNo: { width: 7.5 }, SequenceNo: { width: 6 }, LineNo: { width: 6 }, Priority: { width: 6 }, Decimals: { width: 6 }, Quantity: { width: 9 },
  MaterialLevel: { width: 9 }, MaterialGroup: { width: 10 }, DefaultSupplyType: { width: 9 },
  WaitingTimeHours: { width: 11 }, TransferTimeHours: { width: 11 }, FixedLeadTimeDays: { width: 12 }, VariableLeadTimeDays: { width: 12 },
  MinimumOrderQuantity: { width: 13 },
};

interface Choice { tab: string; tables: Record<string, string> }

function initial(saved: { tab: string | null; tables: Record<string, string> }, tabs: TabDef[], search: string): Choice {
  const params = new URLSearchParams(search);
  const fromUrl = tabs.find((t) => t.key === params.get("sekme"));
  const tab = fromUrl ?? tabs.find((t) => t.key === saved.tab) ?? tabs[0];
  const tables = { ...saved.tables };
  const table = tab.tables.find((x) => x.slug === params.get("tablo"));
  if (fromUrl && table) tables[tab.key] = table.list;
  return { tab: tab.key, tables };
}

export function DataScreen({ id, title, sections, tabs, countsUrl }: {
  /** Hatırlanan seçimin anahtarı (ekran başına). */
  id: string;
  title: string;
  /** Sekme grubunun erişilebilir adı. */
  sections: string;
  tabs: TabDef[];
  countsUrl: string;
}) {
  const { userId } = useShell();
  const { search, pathname } = useLocation();
  const navigate = useNavigate();
  const prefs = userPrefs(userId);
  const [choice, setChoice] = useState<Choice>(() => initial(prefs.dataScreen(id), tabs, search));
  const [counts, setCounts] = useState<Map<string, number | null>>(new Map());
  const [columns, setColumns] = useState<ListColumn[] | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [pending, setPending] = useState<Choice | null>(null);  // kaydedilmemiş manuel değerle sekme ya da tablo değişiyor

  useEffect(() => {
    const ctrl = new AbortController();
    getJson<DataCounts>(countsUrl, ctrl.signal)
      .then((r) => setCounts(new Map(r.tabs.flatMap((t) => t.tables.map((x) => [x.list, x.count] as const)))))
      .catch(() => { /* sayılar gelmezse seçimde yalnız adlar görünür */ });
    return () => ctrl.abort();
  }, [countsUrl]);

  const tab = tabs.find((t) => t.key === choice.tab) ?? tabs[0];
  const table = tab.tables.find((x) => x.list === choice.tables[tab.key]) ?? tab.tables[0];
  const manual = useManualValues(table.list, columns, () => setReloadKey((n) => n + 1));  // manuel değer (K-170)
  const choose = (next: Choice) => {
    if (manual.dirty) setPending(next);
    else setChoice(next);
  };

  useEffect(() => {  // adres ve hatırlanan seçim (kullanıcı başına)
    prefs.setDataScreen(id, choice);
    const next = new URLSearchParams({ sekme: tab.key, ...(tab.tables.length > 1 ? { tablo: table.slug } : {}) }).toString();
    if (search.replace(/^\?/, "") !== next) navigate(`${pathname}?${next}`, { replace: true });
  }, [choice]);  // eslint-disable-line react-hooks/exhaustive-deps

  const label = (x: TableDef) => {
    const n = counts.get(x.list);
    return typeof n === "number" ? T.tableWithCount(x.label, formatNumber(n)) : x.label;
  };
  const picker = tab.tables.length > 1 ? (
    <select className="sc-input sc-select sc-viewbar-select" aria-label={T.table} value={table.list}
            onChange={(e) => choose({ ...choice, tables: { ...choice.tables, [tab.key]: e.target.value } })}>
      {tab.tables.map((x) => <option key={x.list} value={x.list}>{label(x)}</option>)}
    </select>
  ) : null;

  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{title}</h1>
      </header>
      <div className="sc-section-switch">
        <Segment<string> label={sections} hideLabel value={tab.key} onChange={(key) => choose({ ...choice, tab: key })}
                         options={tabs.map((t) => ({ value: t.key, label: t.label }))} />
      </div>
      {manual.paste && (
        <Alert tone={manual.paste.rejected ? "risk" : "info"} onClose={manual.closePaste} title={MT.pasteSummary(manual.paste.taken, manual.paste.rejected)}>
          {manual.paste.details.length > 0 && manual.paste.details.join(" ")}
        </Alert>
      )}
      <DataTable key={table.list} list={table.list} fieldHints={HINTS} toolbarLead={picker} fitHeaders onColumns={setColumns} reloadKey={reloadKey}
                 cellRender={manual.cellRender} cellWrap={manual.cellWrap} cellClass={manual.cellClass} toolbarActions={manual.editBar}
                 cellEditing={manual.cellEditing} selection={manual.selection} />
      {manual.cellMenu}
      <UnsavedGuard dirty={manual.dirty} />
      {pending && (
        <ConfirmDialog title={tr.table.unsavedTitle} message={tr.table.unsavedText} confirmLabel={tr.table.unsavedLeave} danger
                       onCancel={() => setPending(null)} onConfirm={() => { manual.discard(); setChoice(pending); setPending(null); }} />
      )}
    </section>
  );
}

// Dünden bugüne (ekran 28, fonksiyon 101; K-159, K-160, K-161). Ana–detay düzeni: üstte tablo başına karşılaştırma, satır seçilince altta Yeni gelenler, Gelmeyenler,
// Güncellenenler. İki tablo da ortak tablo; önceki verisi olmayan tabloda karşılaştırma alanları "—".
import { type HTMLAttributes, useCallback, useMemo, useState } from "react";

import { JOB_VALIDATION } from "../api/client";
import { formatDateTime, formatNumber, formatPercent, serverDate } from "../format";
import { tr } from "../i18n/tr";
import { useJobRefresh } from "../shell/useJobRefresh";
import { type CellRender, DataTable } from "../table/DataTable";
import type { ListFilter, Row } from "../table/types";
import { type DetailTab, MasterDetail, useMasterDetail } from "../ui";

const T = tr.rawCompare;
const READY = "Hazır";
const DASH = "—";
const JOBS = [JOB_VALIDATION] as const;
type Tab = "new" | "missing" | "changed";
interface Selected { id: number; entity: string; name: string; added: number; missing: number; changed: number }

const when = (v: unknown) => (v ? formatDateTime(serverDate(String(v))) : DASH);
const count = (v: unknown) => (v === null || v === undefined ? DASH : formatNumber(Number(v), 0));
const CELLS: CellRender = {
  YesterdayAt: when,
  TodayAt: when,
  TodayLoad: (v) => (v ? String(v) : DASH),
  YesterdayRows: count,
  TodayRows: count,
  ChangePct: (v) => (v === null || v === undefined ? DASH : formatPercent(Number(v), 1)),
  NewCount: count,
  MissingCount: count,
  ChangedCount: count,
};
const listOf = (tab: Tab, entity: string) => (tab === "changed" ? "raw-compare-changes" : `raw-compare-${tab}-${entity}`);
const tabsOf = (s: Selected): DetailTab<Tab>[] => [
  { value: "new", label: T.newTab(formatNumber(s.added, 0)), count: s.added },
  { value: "missing", label: T.missingTab(formatNumber(s.missing, 0)), count: s.missing },
  { value: "changed", label: T.changedTab(formatNumber(s.changed, 0)), count: s.changed },
];
const keyOf = (s: Selected) => s.id;

export function RawCompare() {
  const { selected, tab, toggle, close, setTab } = useMasterDetail<Selected, Tab>(tabsOf, keyOf);
  const [reloadKey, setReloadKey] = useState(0);
  const reload = useCallback(() => setReloadKey((k) => k + 1), []);
  useJobRefresh(JOBS, reload);  // yükleme sonrası hesap tablo validasyon işinde (K-160)

  const rowProps = useCallback((row: Row): HTMLAttributes<HTMLTableRowElement> => {
    if (row.State !== READY) return {};
    const open = () => toggle({ id: Number(row.Id), entity: String(row.Entity), name: String(row.Name), added: Number(row.NewCount ?? 0), missing: Number(row.MissingCount ?? 0),
                                changed: Number(row.ChangedCount ?? 0) });
    return { className: "is-clickable", tabIndex: 0, onClick: open, onKeyDown: (e) => { if (e.key === "Enter") open(); } };
  }, [toggle]);

  const filters = useMemo<ListFilter[] | undefined>(() => (
    selected && tab === "changed" ? [{ field: "EntityName", op: "equals", value: selected.entity }] : undefined
  ), [selected, tab]);

  return (
    <section className="sc-page--fill">
      <header className="sc-page-head"><h1>{T.title}</h1></header>
      <MasterDetail<Tab>
        id="raw-compare"
        master={<DataTable list="raw-compare" cellRender={CELLS} rowProps={rowProps} reloadKey={reloadKey} selectedRowId={selected?.id ?? null} />}
        onClose={close} hideTitle
        detail={selected && tab ? {
          title: selected.name, tabsLabel: T.tabs, tabs: tabsOf(selected), tab, onTab: setTab,
          // Kartın şeridi tablo standardında (K-173): solda sekmeler, sağda tablo düğmeleri, Büyüt ve ✕
          renderBody: ({ tabs, controls }) => (
            <DataTable key={`${selected.entity}:${tab}`} list={listOf(tab, selected.entity)} baseFilters={filters} reloadKey={reloadKey} compact
                       toolbarLead={tabs} toolbarEnd={controls} />
          ),
        } : null} />
    </section>
  );
}

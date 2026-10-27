// Ortak tablo bileşeni (K-81, K-87, docs/12 "Tablo bileşeni"): alan ekle/çıkar (U-6), çoklu sıralama (U-7),
// tipe göre filtre (U-8), sayaç (U-12). Sıralama ve filtre sunucuda (U-21); gövde sanal kaydırmayla çizilir.
// TanStack Table başlık, sıralama ve görünürlük durumunu tutar; satırlar parça önbelleğinden gelir.
import {
  type ColumnVisibilityState, columnVisibilityFeature, createColumnHelper, rowSortingFeature, type SortingState,
  tableFeatures, useTable,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ArrowDown, ArrowUp, Columns3, Funnel } from "lucide-react";
import { type RefObject, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { formatDate, formatDateTime, formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { Alert, Button } from "../ui";
import { FieldPanel } from "./FieldPanel";
import { FilterMenu, valueLabel } from "./filters";
import { listApi, type ListColumn, type ListFilter, type Row } from "./types";
import { type ListRequest, useListQuery } from "./useListQuery";

const T = tr.table;

/** Satır yüksekliği rem cinsinden; tokens.css --row-height ile aynı (testte karşılaştırılır). */
export const ROW_REM = 2.1538;
/** Görünen satırların üstünde ve altında çizilen tampon satır sayısı (docs/12 performans hedefi). */
export const OVERSCAN = 10;

const features = tableFeatures({ rowSortingFeature, columnVisibilityFeature });
const helper = createColumnHelper<typeof features, Row>();
const NO_DATA: Row[] = [];

export function formatCell(col: ListColumn, v: unknown): string {
  if (v === null || v === undefined || v === "") return "";
  switch (col.type) {
    case "number": return formatNumber(Number(v), col.decimals ?? 0);
    case "integer": return formatNumber(Number(v));
    case "bool": return valueLabel(Boolean(v));
    case "date": {
      const [y, m, d] = String(v).split("-").map(Number);
      return formatDate(new Date(y, m - 1, d));
    }
    case "datetime": return formatDateTime(new Date(String(v)));
    default: return String(v);
  }
}

const isNumeric = (c: ListColumn) => c.type === "number" || c.type === "integer";

/** Açık açılır pencereyi Escape ve dışarı tıklamayla kapatır. */
function useDismiss(ref: RefObject<HTMLElement | null>, active: boolean, close: () => void) {
  useEffect(() => {
    if (!active) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [ref, active, close]);
}

export function DataTable({ list }: { list: string }) {
  const { fontSize } = useShell();
  const [columns, setColumns] = useState<ListColumn[] | null>(null);
  const [columnsError, setColumnsError] = useState<ApiError | null>(null);
  const [columnsAttempt, setColumnsAttempt] = useState(0);
  const [visibility, setVisibility] = useState<ColumnVisibilityState>({});
  const [sorting, setSorting] = useState<SortingState>([]);
  const [filters, setFilters] = useState<Record<string, ListFilter>>({});
  const [panelOpen, setPanelOpen] = useState(false);
  const [menu, setMenu] = useState<{ field: string; left: number; top: number } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    listApi(list).columns(ctrl.signal)
      .then((cols) => {
        setColumns(cols);
        setColumnsError(null);
        setVisibility(Object.fromEntries(cols.map((c) => [c.field, c.default_visible])));
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setColumnsError(e instanceof ApiError ? e : new ApiError(0, "network", String(e)));
      });
    return () => ctrl.abort();
  }, [list, columnsAttempt]);

  const byField = useMemo(() => new Map((columns ?? []).map((c) => [c.field, c])), [columns]);
  const defs = useMemo(() => (columns ?? []).map((c) => helper.accessor((r) => r[c.field], { id: c.field, header: c.label })),
    [columns]);
  const table = useTable({
    features, columns: defs, data: NO_DATA,
    state: { sorting, columnVisibility: visibility },
    onSortingChange: setSorting, onColumnVisibilityChange: setVisibility,
    manualSorting: true, enableMultiSort: true, enableSortingRemoval: true, sortDescFirst: false,
    isMultiSortEvent: (e: unknown) => Boolean((e as { shiftKey?: boolean } | undefined)?.shiftKey),
  });
  const visible = table.getVisibleLeafColumns().map((c) => byField.get(c.id)).filter((c): c is ListColumn => Boolean(c));

  const visibleKey = visible.map((c) => c.field).join(",");
  const request: ListRequest | null = useMemo(() => (columns && visibleKey ? {
    fields: visibleKey.split(","),
    sort: sorting.map((s) => ({ field: s.id, dir: s.desc ? "desc" as const : "asc" as const })),
    filters: Object.values(filters),
  } : null), [columns, visibleKey, sorting, filters]);
  const q = useListQuery(list, request);

  const rowPx = Math.round(fontSize * ROW_REM);
  const virtualizer = useVirtualizer({
    count: q.filtered, getScrollElement: () => scrollRef.current, estimateSize: () => rowPx, overscan: OVERSCAN,
  });
  useEffect(() => virtualizer.measure(), [rowPx, virtualizer]);
  const items = virtualizer.getVirtualItems();
  const first = items[0]?.index ?? 0;
  const last = items[items.length - 1]?.index ?? 0;
  const { ensure } = q;
  useEffect(() => {
    if (items.length) ensure(first, last);
  }, [first, last, items.length, ensure]);

  const closeMenu = useCallback(() => setMenu(null), []);
  const closePanel = useCallback(() => setPanelOpen(false), []);
  useDismiss(menuRef, menu !== null, closeMenu);
  useDismiss(panelRef, panelOpen, closePanel);

  const openMenu = (field: string, button: HTMLElement) => {
    if (menu?.field === field) return setMenu(null);
    const root = rootRef.current!.getBoundingClientRect();
    const r = button.getBoundingClientRect();
    setMenu({ field, left: Math.max(0, r.left - root.left), top: r.bottom - root.top });
  };
  const applyFilter = (field: string, f: ListFilter | null) => {
    setFilters((all) => {
      const next = { ...all };
      if (f) next[field] = f;
      else delete next[field];
      return next;
    });
    setMenu(null);
  };
  const others = useMemo(() => Object.values(filters).filter((f) => f.field !== menu?.field), [filters, menu?.field]);

  if (columnsError) {
    return (
      <Alert tone="error" title={T.loadError}>
        {columnsError.message} <Button size="sm" onClick={() => setColumnsAttempt((n) => n + 1)}>{T.retry}</Button>
      </Alert>
    );
  }
  if (!columns) return <p className="sc-muted">{T.loading}</p>;

  const paddingTop = items[0]?.start ?? 0;
  const paddingBottom = items.length ? virtualizer.getTotalSize() - items[items.length - 1].end : 0;
  const menuColumn = menu ? byField.get(menu.field) : undefined;
  const multi = sorting.length > 1;

  return (
    <div className="sc-table" ref={rootRef}>
      <div className="sc-table-toolbar">
        <output className="sc-table-count sc-num" aria-label={T.countLabel}>
          {T.count(formatNumber(q.filtered), formatNumber(q.total))}
        </output>
        <div className="sc-table-anchor" ref={panelRef}>
          <Button size="sm" icon={Columns3} aria-expanded={panelOpen} onClick={() => setPanelOpen((o) => !o)}>
            {T.fields(visible.length, columns.length)}
          </Button>
          {panelOpen && (
            <FieldPanel columns={columns} visibility={visibility}
                        onToggle={(field, on) => setVisibility((v) => ({ ...v, [field]: on }))}
                        onReset={() => setVisibility(Object.fromEntries(columns.map((c) => [c.field, c.default_visible])))} />
          )}
        </div>
      </div>

      {q.status === "error" && (
        <Alert tone="error" title={T.loadError}>
          {q.error?.message} <Button size="sm" onClick={q.retry}>{T.retry}</Button>
        </Alert>
      )}

      <div className="sc-table-scroll" ref={scrollRef} data-testid="table-scroll">
        <table className="sc-table-grid" aria-rowcount={q.filtered + 1} aria-colcount={visible.length}>
          <colgroup>
            {visible.map((c) => <col key={c.field} className={`sc-col--${c.type}`} />)}
          </colgroup>
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id} aria-rowindex={1}>
                {group.headers.map((h) => {
                  const col = byField.get(h.column.id)!;
                  const dir = h.column.getIsSorted();
                  const filtered = Boolean(filters[col.field]);
                  return (
                    <th key={h.id} scope="col" className={isNumeric(col) ? "is-num" : undefined}
                        aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : undefined}>
                      <div className="sc-table-head">
                        <button type="button" className="sc-table-sort" title={T.sortHint}
                                onClick={h.column.getToggleSortingHandler()}>
                          <span className="sc-table-label">{col.label}</span>
                          {dir === "asc" && <ArrowUp aria-hidden="true" />}
                          {dir === "desc" && <ArrowDown aria-hidden="true" />}
                          {dir && multi && (
                            <span className="sc-table-sort-n sc-num" aria-label={T.sortPriority(h.column.getSortIndex() + 1)}>
                              {h.column.getSortIndex() + 1}
                            </span>
                          )}
                        </button>
                        <button type="button" className={`sc-table-filter-btn${filtered ? " is-active" : ""}`}
                                aria-label={T.filterOf(col.label)} aria-pressed={filtered} aria-haspopup="dialog"
                                onClick={(e) => openMenu(col.field, e.currentTarget)}>
                          <Funnel aria-hidden="true" />
                        </button>
                      </div>
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {q.status === "loading" && (
              <tr className="sc-table-state"><td colSpan={visible.length}>{T.loading}</td></tr>
            )}
            {q.status === "ready" && q.filtered === 0 && (
              <tr className="sc-table-state">
                <td colSpan={visible.length}>
                  {T.empty}
                  {Object.keys(filters).length > 0 && (
                    <> · <Button size="sm" variant="ghost" onClick={() => setFilters({})}>{T.clearFilters}</Button></>
                  )}
                </td>
              </tr>
            )}
            {q.status !== "loading" && paddingTop > 0 && <tr aria-hidden="true" className="sc-table-spacer" style={{ height: paddingTop }} />}
            {q.status !== "loading" && items.map((it) => {
              const row = q.row(it.index);
              return (
                <tr key={it.key} aria-rowindex={it.index + 2} className={row ? undefined : "is-placeholder"}>
                  {visible.map((c) => (
                    <td key={c.field} className={isNumeric(c) ? "is-num sc-num" : undefined}>
                      {row ? formatCell(c, row[c.field]) : ""}
                    </td>
                  ))}
                </tr>
              );
            })}
            {q.status !== "loading" && paddingBottom > 0 && <tr aria-hidden="true" className="sc-table-spacer" style={{ height: paddingBottom }} />}
          </tbody>
        </table>
      </div>

      {menu && menuColumn && (
        <div className="sc-table-pop" ref={menuRef} role="dialog" aria-label={T.filterOf(menuColumn.label)}
             style={{ left: menu.left, top: menu.top }}>
          <FilterMenu list={list} column={menuColumn} filter={filters[menuColumn.field]} others={others}
                      onApply={(f) => applyFilter(menuColumn.field, f)} />
        </div>
      )}
    </div>
  );
}

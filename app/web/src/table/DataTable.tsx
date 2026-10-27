// Ortak tablo bileşeni (K-81, K-87, docs/12 "Tablo bileşeni" ve "Görünüm"): alan ekle/çıkar (U-6), çoklu sıralama
// (U-7), tipe göre filtre (U-8), kayıtlı görünüm (U-9), kolon düzeni (U-10), gruplama ve ara toplam (U-11), aktif
// filtre etiketleri ve sayaç (U-12), boş değer (U-13). Sıralama, filtre ve gruplama sunucuda (U-21); gövde sanal.
// Durum tek yerde (TableState, görünüm içeriğiyle birebir); TanStack Table başlık, sıra, sabitleme ve genişliği ondan
// alır. Satırlar parça önbelleğinden (düz) ya da grup başına (gruplu) gelir.
import {
  columnOrderingFeature, columnPinningFeature, columnSizingFeature, columnVisibilityFeature, createColumnHelper,
  rowSortingFeature, type SortingState, tableFeatures, useTable,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  ArrowDown, ArrowUp, ArrowUpDown, ChevronDown, ChevronRight, Columns3, Ellipsis, Funnel, FunnelX, Rows3,
} from "lucide-react";
import {
  type CSSProperties, type DragEvent, type KeyboardEvent, type MouseEvent as ReactMouseEvent, type RefObject,
  useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState,
} from "react";

import { ApiError } from "../api/client";
import { formatDate, formatDateTime, formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { Alert, Button } from "../ui";
import { type Box, placePopover, viewportSize } from "../ui/popover";
import { type ColumnAction, ColumnMenu } from "./ColumnMenu";
import { FieldPanel } from "./FieldPanel";
import { FilterChips } from "./FilterChips";
import { FilterMenu, valueLabel } from "./filters";
import { GroupPanel } from "./GroupPanel";
import { listApi, type GroupNode, type ListColumn, type ListFilter, type Row } from "./types";
import { type DisplayItem, flatten, useGroupedQuery } from "./useGroupedQuery";
import { type ListRequest, useListQuery } from "./useListQuery";
import { useViews, ViewBar } from "./ViewBar";
import {
  clampWidth, DEFAULT_WIDTH_REM, dropField, MAX_WIDTH_REM, MIN_WIDTH_REM, moveField, standardState, type TableState,
  withFilter, withOrder,
} from "./viewState";

const T = tr.table;

/** Satır yüksekliği rem cinsinden; tokens.css --row-height ile aynı (testte karşılaştırılır). */
export const ROW_REM = 2.1538;
/** Görünen satırların üstünde ve altında çizilen tampon satır sayısı (docs/12 performans hedefi). */
export const OVERSCAN = 10;
/** Klavyeyle genişlik adımı (rem). */
export const WIDTH_STEP_REM = 0.5;

const features = tableFeatures({
  rowSortingFeature, columnVisibilityFeature, columnOrderingFeature, columnPinningFeature, columnSizingFeature,
});
const helper = createColumnHelper<typeof features, Row>();
const NO_DATA: Row[] = [];

/** Birim bilinmiyorsa miktar ondalığı (docs/02 UnitOfMeasure.Decimals). */
const DEFAULT_UNIT_DECIMALS = 2;

export function formatCell(col: ListColumn, v: unknown, row?: Row): string {
  if (v === null || v === undefined || v === "") return "";
  switch (col.type) {
    case "number": {
      const unit = row?._unit_decimals;
      const decimals = col.decimals_from_unit ? (typeof unit === "number" ? unit : DEFAULT_UNIT_DECIMALS) : col.decimals ?? 0;
      return formatNumber(Number(v), decimals);
    }
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

/** Grup başlığındaki değer: boş "(Boş)", evet/hayır yazıyla, tarih Türkçe. */
function groupLabel(col: ListColumn | undefined, v: unknown): string {
  if (v === null || v === undefined || v === "") return T.emptyOption;
  return col ? formatCell(col, v) : String(v);
}

/** Ara toplam (K-90): miktarda tek birimin ondalığı; ortalama bir ondalık fazla. */
function formatAggregate(col: ListColumn, node: { aggregates: Record<string, number | null>; unit_decimals: Record<string, number> }) {
  const v = node.aggregates[col.field];
  if (v === null || v === undefined) return "";
  const base = col.decimals_from_unit ? node.unit_decimals[col.field] ?? DEFAULT_UNIT_DECIMALS : col.decimals ?? 0;
  return formatNumber(v, col.aggregate === "avg" ? base + 1 : base);
}

const isNumeric = (c: ListColumn) => c.type === "number" || c.type === "integer";

/** Açık açılır pencereyi Escape ve dışarı tıklamayla kapatır. */
function useDismiss(ref: RefObject<HTMLElement | null>, active: boolean, close: () => void) {
  useEffect(() => {
    if (!active) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) close();
    };
    const onKey = (e: globalThis.KeyboardEvent) => e.key === "Escape" && close();
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [ref, active, close]);
}

const toBox = (el: HTMLElement): Box => {
  const r = el.getBoundingClientRect();
  return { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
};

/** Başlığın sağ kenarındaki genişlik tutamağı (U-10): fareyle sürüklenir, odaktayken ← / → 0,5rem. */
function ResizeHandle({ label, width, remPx, onWidth }: {
  label: string; width: number; remPx: number; onWidth(rem: number): void;
}) {
  const onMouseDown = (e: ReactMouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const [x0, w0] = [e.clientX, width];
    const move = (ev: MouseEvent) => onWidth(clampWidth(w0 + (ev.clientX - x0) / remPx));
    const up = () => {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
    };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  };
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    e.stopPropagation();
    onWidth(clampWidth(width + (e.key === "ArrowRight" ? WIDTH_STEP_REM : -WIDTH_STEP_REM)));
  };
  return (
    <div role="separator" aria-orientation="vertical" aria-label={T.widthOf(label)} tabIndex={0}
         aria-valuenow={Math.round(width * 100) / 100} aria-valuemin={MIN_WIDTH_REM} aria-valuemax={MAX_WIDTH_REM}
         className="sc-table-resize" draggable={false} onDragStart={(e) => e.preventDefault()}
         onMouseDown={onMouseDown} onKeyDown={onKeyDown} onClick={(e) => e.stopPropagation()} />
  );
}

type Pop = { kind: "filter" | "column"; field: string; anchor: Box } | null;

export function DataTable({ list }: { list: string }) {
  const { fontSize, userId } = useShell();
  const [columns, setColumns] = useState<ListColumn[] | null>(null);
  const [chunkSize, setChunkSize] = useState(0);
  const [columnsError, setColumnsError] = useState<ApiError | null>(null);
  const [columnsAttempt, setColumnsAttempt] = useState(0);
  const [state, setState] = useState<TableState | null>(null);
  const [panel, setPanel] = useState<"fields" | "group" | null>(null);
  const [pop, setPop] = useState<Pop>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [drag, setDrag] = useState<{ field: string; over?: string; side?: "before" | "after" } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    listApi(list).columns(ctrl.signal)
      .then(({ columns: cols, chunk_size }) => {
        setColumns(cols);
        setChunkSize(chunk_size);
        setColumnsError(null);
      })
      .catch((e: unknown) => {
        if (!ctrl.signal.aborted) setColumnsError(e instanceof ApiError ? e : new ApiError(0, "network", String(e)));
      });
    return () => ctrl.abort();
  }, [list, columnsAttempt]);

  const views = useViews(list, userId, columns, setState);
  const update = useCallback((fn: (s: TableState) => TableState) => setState((s) => (s ? fn(s) : s)), []);
  const s = state ?? standardState(columns ?? []);
  const byField = useMemo(() => new Map((columns ?? []).map((c) => [c.field, c])), [columns]);

  // TanStack durumu TableState'ten türetilir (genişlikler rem).
  const sorting: SortingState = useMemo(() => s.sort.map((x) => ({ id: x.field, desc: x.dir === "desc" })), [s.sort]);
  const defs = useMemo(() => (columns ?? []).map((c) => helper.accessor((r) => r[c.field], {
    id: c.field, header: c.label, size: DEFAULT_WIDTH_REM[c.type], minSize: MIN_WIDTH_REM, maxSize: MAX_WIDTH_REM,
  })), [columns]);
  const table = useTable({
    features, columns: defs, data: NO_DATA,
    state: {
      sorting,
      columnVisibility: Object.fromEntries((columns ?? []).map((c) => [c.field, s.order.includes(c.field)])),
      columnOrder: [...s.order, ...(columns ?? []).map((c) => c.field).filter((f) => !s.order.includes(f))],
      columnPinning: { start: s.order.slice(0, s.pinned), end: [] },
      columnSizing: Object.fromEntries(s.order.map((f) => [f, s.widths[f] ?? DEFAULT_WIDTH_REM[byField.get(f)?.type ?? "text"]])),
    },
    onSortingChange: (u) => update((st) => {
      const next = typeof u === "function" ? u(st.sort.map((x) => ({ id: x.field, desc: x.dir === "desc" }))) : u;
      return { ...st, sort: next.map((x) => ({ field: x.id, dir: x.desc ? "desc" : "asc" })) };
    }),
    manualSorting: true, enableMultiSort: true, enableSortingRemoval: true, sortDescFirst: false,
    isMultiSortEvent: (e: unknown) => Boolean((e as { shiftKey?: boolean } | undefined)?.shiftKey),
  });
  const visible = s.order.map((f) => byField.get(f)).filter((c): c is ListColumn => Boolean(c));
  const width = (f: string) => s.widths[f] ?? DEFAULT_WIDTH_REM[byField.get(f)?.type ?? "text"];
  const pinStart = (i: number) => visible.slice(0, i).reduce((sum, c) => sum + width(c.field), 0);

  const ready = Boolean(columns && state && views.ready && chunkSize);
  const requestKey = JSON.stringify([s.order, s.sort, s.filters]);
  const request: ListRequest | null = useMemo(() => (ready ? { fields: s.order, sort: s.sort, filters: s.filters } : null),
    [ready, requestKey]); // requestKey alanları, sıralamayı ve filtreleri taşır
  const grouped = s.groupBy.length > 0;
  const flat = useListQuery(list, grouped ? null : request, chunkSize);
  const g = useGroupedQuery(list, grouped ? request : null, s.groupBy, chunkSize);
  const groupKey = JSON.stringify([s.groupBy, s.filters]);
  useEffect(() => setCollapsed(new Set()), [groupKey]);
  const display: DisplayItem[] | null = useMemo(
    () => (grouped && g.tree ? flatten(g.tree.groups, s.groupBy, collapsed) : null),
    [grouped, g.tree, s.groupBy, collapsed]);

  const count = grouped ? display?.length ?? 0 : flat.filtered;
  const status = grouped ? g.status : flat.status;
  const error = grouped ? g.error : flat.error;
  const filtered = grouped ? g.tree?.filtered ?? 0 : flat.filtered;
  const total = grouped ? g.tree?.total ?? 0 : flat.total;

  const rowPx = Math.round(fontSize * ROW_REM);
  const virtualizer = useVirtualizer({
    count, getScrollElement: () => scrollRef.current, estimateSize: () => rowPx, overscan: OVERSCAN,
  });
  useEffect(() => virtualizer.measure(), [rowPx, virtualizer]);
  const items = virtualizer.getVirtualItems();
  const first = items[0]?.index ?? 0;
  const last = items[items.length - 1]?.index ?? 0;
  const { ensure: ensureFlat } = flat;
  const { ensure: ensureGroup } = g;
  useEffect(() => {
    if (!items.length) return;
    if (!grouped) {
      ensureFlat(first, last);
      return;
    }
    if (!display) return;
    const leaves = new Map<string, { keys: DisplayItem & { kind: "row" }; lo: number; hi: number }>();
    for (let i = first; i <= last && i < display.length; i++) {
      const it = display[i];
      if (it.kind !== "row") continue;
      const cur = leaves.get(it.leaf);
      leaves.set(it.leaf, cur ? { ...cur, hi: it.index } : { keys: it, lo: it.index, hi: it.index });
    }
    leaves.forEach(({ keys, lo, hi }) => ensureGroup(keys.leaf, keys.keys, lo, hi));
  }, [first, last, items.length, grouped, display, ensureFlat, ensureGroup]);

  const closePop = useCallback(() => setPop(null), []);
  const closePanel = useCallback(() => setPanel(null), []);
  useDismiss(popRef, pop !== null, closePop);
  useDismiss(panelRef, panel !== null, closePanel);

  const openPop = (kind: "filter" | "column", field: string, anchor: HTMLElement) =>
    setPop((p) => (p?.kind === kind && p.field === field ? null : { kind, field, anchor: toBox(anchor) }));
  // Açılır pencere görünür alana sığar (docs/12): ölçülür, ekran koordinatında yerleştirilir, köke göre yazılır.
  useLayoutEffect(() => {
    const el = popRef.current;
    if (!pop || !el || !rootRef.current) return;
    el.style.left = "0px";  // genişlik konumdan bağımsız ölçülsün
    el.style.top = "0px";
    const at = placePopover(pop.anchor, el.getBoundingClientRect(), viewportSize());
    const root = rootRef.current.getBoundingClientRect();
    el.style.left = `${at.left - root.left}px`;
    el.style.top = `${at.top - root.top}px`;
  }, [pop]);

  const setFilter = (field: string, f: ListFilter | null) => {
    update((st) => ({ ...st, filters: withFilter(st.filters, field, f) }));
    setPop(null);
  };
  const others = useMemo(() => s.filters.filter((f) => f.field !== pop?.field), [s.filters, pop?.field]);
  const filterOf = (field: string) => s.filters.find((f) => f.field === field);

  const columnAction = (field: string, action: ColumnAction) => {
    update((st) => {
      const i = st.order.indexOf(field);
      switch (action) {
        case "left": return { ...st, order: moveField(st.order, field, -1) };
        case "right": return { ...st, order: moveField(st.order, field, 1) };
        case "pin": return { ...st, pinned: i + 1 };
        case "unpin": return { ...st, pinned: 0 };
        case "group": return { ...st, groupBy: [...st.groupBy, field] };
        case "hide": return withOrder(st, st.order.filter((f) => f !== field));
        case "resetWidth": {
          const widths = { ...st.widths };
          delete widths[field];
          return { ...st, widths };
        }
      }
    });
    setPop(null);
  };
  const onHeaderKey = (field: string, e: KeyboardEvent) => {
    if (!e.altKey || (e.key !== "ArrowLeft" && e.key !== "ArrowRight")) return;
    e.preventDefault();
    update((st) => ({ ...st, order: moveField(st.order, field, e.key === "ArrowLeft" ? -1 : 1) }));
  };
  const dragOver = (field: string, e: DragEvent<HTMLTableCellElement>) => {
    if (!drag || drag.field === field) return;
    e.preventDefault();
    const r = e.currentTarget.getBoundingClientRect();
    const side = e.clientX < r.left + r.width / 2 ? "before" : "after";
    if (drag.over !== field || drag.side !== side) setDrag({ ...drag, over: field, side });
  };
  const drop = (field: string, e: DragEvent) => {
    e.preventDefault();
    if (drag && drag.field !== field) {
      update((st) => ({ ...st, order: dropField(st.order, drag.field, field, drag.side ?? "before") }));
    }
    setDrag(null);
  };
  const allGroupIds = useMemo(() => {
    const ids: string[] = [];
    const walk = (nodes: GroupNode[]) => nodes.forEach((n) => { ids.push(JSON.stringify(n.key)); if (n.children) walk(n.children); });
    walk(g.tree?.groups ?? []);
    return ids;
  }, [g.tree]);
  const toggleGroup = (id: string) => setCollapsed((c) => {
    const next = new Set(c);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });

  if (columnsError) {
    return (
      <Alert tone="error" title={T.loadError}>
        {columnsError.message} <Button size="sm" onClick={() => setColumnsAttempt((n) => n + 1)}>{T.retry}</Button>
      </Alert>
    );
  }
  if (!columns || !state) return <p className="sc-muted">{T.loading}</p>;

  const paddingTop = items[0]?.start ?? 0;
  const paddingBottom = items.length ? virtualizer.getTotalSize() - items[items.length - 1].end : 0;
  const popColumn = pop ? byField.get(pop.field) : undefined;
  const multi = s.sort.length > 1;
  const pinnedCell = (i: number): { className: string; style?: CSSProperties } =>
    i < s.pinned ? { className: `is-pinned${i === s.pinned - 1 ? " is-pinned-last" : ""}`, style: { left: `${pinStart(i)}rem` } }
                 : { className: "" };
  const cellClass = (c: ListColumn, i: number) =>
    [isNumeric(c) ? "is-num sc-num" : "", pinnedCell(i).className].filter(Boolean).join(" ") || undefined;

  const renderRow = (key: string | number | bigint, index: number, row: Row | undefined) => (
    <tr key={String(key)} aria-rowindex={index + 2} className={row ? undefined : "is-placeholder"}>
      {visible.map((c, i) => (
        <td key={c.field} className={cellClass(c, i)} style={pinnedCell(i).style}>
          {row ? formatCell(c, row[c.field], row) : ""}
        </td>
      ))}
    </tr>
  );
  // Grup adı, ara toplamı olmayan baştaki kolonları kaplar (kesilmesin); sabit kolon varsa sabit bölgeyi aşmaz.
  const leading = Math.max(1, visible.findIndex((c) => c.aggregate) === -1 ? visible.length : visible.findIndex((c) => c.aggregate));
  const labelSpan = s.pinned > 0 ? Math.min(leading, s.pinned) : leading;
  const renderGroup = (key: string | number | bigint, index: number, it: DisplayItem & { kind: "group" }) => {
    const open = !collapsed.has(it.id);
    const field = s.groupBy[it.depth];
    return (
      <tr key={String(key)} aria-rowindex={index + 2} aria-level={it.depth + 1} aria-expanded={open} tabIndex={0}
          className="sc-table-group" onClick={() => toggleGroup(it.id)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              toggleGroup(it.id);
            }
          }}>
        <td colSpan={labelSpan} className={labelSpan === s.pinned ? "is-pinned is-pinned-last" : pinnedCell(0).className || undefined}
            style={pinnedCell(0).style}>
          <span className="sc-tgroup-head" style={{ paddingLeft: `${it.depth * 1.2308}rem` }}>
            {open ? <ChevronDown aria-hidden="true" /> : <ChevronRight aria-hidden="true" />}
            <span className="sc-tgroup-value">{groupLabel(byField.get(field), it.node.key[it.depth])}</span>
            <span className="sc-muted sc-num">· {T.groupRows(formatNumber(it.node.count))}</span>
          </span>
        </td>
        {visible.slice(labelSpan).map((c, j) => (
          <td key={c.field} className={cellClass(c, j + labelSpan)} style={pinnedCell(j + labelSpan).style}>
            {it.node.mixed_units.includes(c.field) ? (
              <span className="sc-muted" title={T.mixedUnits} aria-label={T.mixedUnits}>—</span>
            ) : c.aggregate ? formatAggregate(c, it.node) : ""}
          </td>
        ))}
      </tr>
    );
  };

  return (
    <div className="sc-table" ref={rootRef}>
      <div className="sc-table-toolbar">
        <ViewBar views={views} state={s} />
        <div className="sc-table-tools" ref={panelRef}>
          <div className="sc-table-anchor">
            <Button size="sm" icon={Rows3} aria-expanded={panel === "group"} onClick={() => setPanel((p) => (p === "group" ? null : "group"))}>
              {T.group(s.groupBy.length)}
            </Button>
            {panel === "group" && (
              <GroupPanel columns={columns} groupBy={s.groupBy} onChange={(groupBy) => update((st) => ({ ...st, groupBy }))} />
            )}
          </div>
          <div className="sc-table-anchor">
            <Button size="sm" icon={Columns3} aria-expanded={panel === "fields"} onClick={() => setPanel((p) => (p === "fields" ? null : "fields"))}>
              {T.fields(visible.length, columns.length)}
            </Button>
            {panel === "fields" && (
              <FieldPanel columns={columns} visibility={Object.fromEntries(columns.map((c) => [c.field, s.order.includes(c.field)]))}
                          onToggle={(field, on) => update((st) => withOrder(st, on ? [...st.order, field] : st.order.filter((f) => f !== field)))}
                          onReset={() => update((st) => withOrder(st, standardState(columns).order))} />
            )}
          </div>
        </div>
      </div>

      <div className="sc-table-status">
        <output className="sc-table-count sc-num" aria-label={T.countLabel}>
          {T.count(formatNumber(filtered), formatNumber(total))}
        </output>
        <FilterChips filters={s.filters} byField={byField} onRemove={(f) => setFilter(f, null)}
                     onEdit={(f, el) => openPop("filter", f, el)} />
        {s.filters.length > 0 && (
          <Button size="sm" variant="ghost" icon={FunnelX} onClick={() => update((st) => ({ ...st, filters: [] }))}>{T.clearFilters}</Button>
        )}
        {s.sort.length > 0 && (
          <Button size="sm" variant="ghost" icon={ArrowUpDown} onClick={() => update((st) => ({ ...st, sort: [] }))}>{T.clearSort}</Button>
        )}
        {grouped && (
          <span className="sc-table-grouped">
            {T.groupedBy(s.groupBy.map((f) => byField.get(f)?.label ?? f).join(" › "))}
            <Button size="sm" variant="ghost" onClick={() => setCollapsed(new Set(allGroupIds))}>{T.collapseAll}</Button>
            <Button size="sm" variant="ghost" onClick={() => setCollapsed(new Set())}>{T.expandAll}</Button>
          </span>
        )}
      </div>

      {views.error && <Alert tone="risk">{views.error}</Alert>}
      {views.warnings.length > 0 && (
        <Alert tone="info" title={T.viewWarnings} onClose={views.dismissWarnings}>{views.warnings.join(" ")}</Alert>
      )}
      {status === "error" && (
        <Alert tone="error" title={T.loadError}>
          {error?.message} <Button size="sm" onClick={grouped ? g.retry : flat.retry}>{T.retry}</Button>
        </Alert>
      )}

      <div className="sc-table-scroll" ref={scrollRef} data-testid="table-scroll">
        <table className="sc-table-grid" aria-rowcount={count + 1} aria-colcount={visible.length}
               style={{ width: `${visible.reduce((sum, c) => sum + width(c.field), 0)}rem` }}>
          <colgroup>
            {visible.map((c) => <col key={c.field} style={{ width: `${width(c.field)}rem` }} />)}
          </colgroup>
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id} aria-rowindex={1}>
                {group.headers.map((h) => {
                  const col = byField.get(h.column.id)!;
                  const i = s.order.indexOf(col.field);
                  const dir = h.column.getIsSorted();
                  const isFiltered = Boolean(filterOf(col.field));
                  const pin = pinnedCell(i);
                  const dropClass = drag?.over === col.field ? ` is-drop-${drag.side}` : "";
                  return (
                    <th key={h.id} scope="col" style={pin.style} draggable
                        className={[isNumeric(col) ? "is-num" : "", pin.className, dropClass.trim()].filter(Boolean).join(" ") || undefined}
                        aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : undefined}
                        onDragStart={(e) => { e.dataTransfer?.setData("text/plain", col.field); setDrag({ field: col.field }); }}
                        onDragOver={(e) => dragOver(col.field, e)} onDrop={(e) => drop(col.field, e)}
                        onDragEnd={() => setDrag(null)}>
                      <div className="sc-table-head">
                        <button type="button" className="sc-table-sort" title={`${T.sortHint}. ${T.moveHint}`}
                                onClick={h.column.getToggleSortingHandler()} onKeyDown={(e) => onHeaderKey(col.field, e)}>
                          <span className="sc-table-label">{col.label}</span>
                          {dir === "asc" && <ArrowUp aria-hidden="true" />}
                          {dir === "desc" && <ArrowDown aria-hidden="true" />}
                          {dir && multi && (
                            <span className="sc-table-sort-n sc-num" aria-label={T.sortPriority(h.column.getSortIndex() + 1)}>
                              {h.column.getSortIndex() + 1}
                            </span>
                          )}
                        </button>
                        <button type="button" className={`sc-table-filter-btn${isFiltered ? " is-active" : ""}`}
                                aria-label={T.filterOf(col.label)} aria-pressed={isFiltered} aria-haspopup="dialog"
                                onClick={(e) => openPop("filter", col.field, e.currentTarget)}>
                          <Funnel aria-hidden="true" />
                        </button>
                        <button type="button" className="sc-table-filter-btn" aria-label={T.columnMenu(col.label)}
                                aria-haspopup="menu" onClick={(e) => openPop("column", col.field, e.currentTarget)}>
                          <Ellipsis aria-hidden="true" />
                        </button>
                      </div>
                      <ResizeHandle label={col.label} width={width(col.field)} remPx={fontSize}
                                    onWidth={(rem) => update((st) => ({ ...st, widths: { ...st.widths, [col.field]: rem } }))} />
                    </th>
                  );
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {status === "loading" && (
              <tr className="sc-table-state"><td colSpan={visible.length}>{T.loading}</td></tr>
            )}
            {status === "ready" && filtered === 0 && (
              <tr className="sc-table-state">
                <td colSpan={visible.length}>
                  {T.empty}
                  {s.filters.length > 0 && (
                    <> · <Button size="sm" variant="ghost" onClick={() => update((st) => ({ ...st, filters: [] }))}>{T.clearFilters}</Button></>
                  )}
                </td>
              </tr>
            )}
            {status !== "loading" && paddingTop > 0 && <tr aria-hidden="true" className="sc-table-spacer" style={{ height: paddingTop }} />}
            {status !== "loading" && items.map((it) => {
              if (!grouped) return renderRow(it.key, it.index, flat.row(it.index));
              const d = display?.[it.index];
              if (!d) return null;
              return d.kind === "group" ? renderGroup(it.key, it.index, d) : renderRow(it.key, it.index, g.row(d.leaf, d.index));
            })}
            {status !== "loading" && paddingBottom > 0 && <tr aria-hidden="true" className="sc-table-spacer" style={{ height: paddingBottom }} />}
          </tbody>
        </table>
      </div>

      {pop && popColumn && (
        <div className={pop.kind === "filter" ? "sc-table-pop" : "sc-table-pop sc-table-pop--menu"} ref={popRef}
             role={pop.kind === "filter" ? "dialog" : undefined}
             aria-label={pop.kind === "filter" ? T.filterOf(popColumn.label) : undefined}>
          {pop.kind === "filter" ? (
            <FilterMenu list={list} column={popColumn} filter={filterOf(popColumn.field)} others={others}
                        onApply={(f) => setFilter(popColumn.field, f)} />
          ) : (
            <ColumnMenu column={popColumn} state={s} onAction={(a) => columnAction(popColumn.field, a)} />
          )}
        </div>
      )}
    </div>
  );
}

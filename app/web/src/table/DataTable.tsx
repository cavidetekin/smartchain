// Ortak tablo bileşeni (K-81, K-87, docs/12 "Tablo bileşeni" ve "Görünüm"): alan ekle/çıkar (U-6), çoklu sıralama
// (U-7), tipe göre filtre (U-8), kayıtlı görünüm (U-9), kolon düzeni (U-10), gruplama ve ara toplam (U-11), aktif
// filtre etiketleri ve sayaç (U-12), boş değer (U-13), Excel'e aktarım (U-14), koşullu biçim (U-24, K-95). Sıralama, filtre ve gruplama sunucuda (U-21); gövde sanal.
// Durum tek yerde (TableState, görünüm içeriğiyle birebir); TanStack Table başlık, sıra, sabitleme ve genişliği ondan
// alır. Satırlar parça önbelleğinden (düz) ya da grup başına (gruplu) gelir.
import {
  columnOrderingFeature, columnPinningFeature, columnSizingFeature, columnVisibilityFeature, createColumnHelper,
  rowSortingFeature, type SortingState, tableFeatures, useTable,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import {
  ArrowDown, ArrowUp, ChevronDown, ChevronRight, Columns3, Ellipsis, FileSpreadsheet, FoldVertical, Funnel,
  FunnelX,
  ListCollapse, Rows3, UnfoldVertical,
} from "lucide-react";
import {
  type CSSProperties, type DragEvent, type KeyboardEvent, memo, type MouseEvent as ReactMouseEvent, type RefObject,
  useCallback, useEffect, useMemo, useRef, useState,
} from "react";

import { ApiError, saveBlob } from "../api/client";
import { formatDate, formatDateTime, formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { Alert, Button } from "../ui";
import { useFloating } from "../ui/popover";
import { type ColumnAction, ColumnMenu } from "./ColumnMenu";
import { ExportDialog } from "./ExportDialog";
import { FieldPanel } from "./FieldPanel";
import { FilterChips } from "./FilterChips";
import { FilterMenu, valueLabel } from "./filters";
import { GroupPanel } from "./GroupPanel";
import { RuleDialog } from "./RuleDialog";
import { RuledValue } from "./RuleIcon";
import {
  activeRules, cellFormat, describeRule, formatStyle, newRuleId, RULE_OPS, ruleKind, toRequestRule,
} from "./rules";
import { RulesPanel } from "./RulesPanel";
import {
  type AggSpec, type ExportInfo, type ExportScope, type FormatRule, listApi, type GroupNode, type ListColumn, type ListFilter,
  MAX_RULES, type Row,
} from "./types";
import { type DisplayItem, flatten, useGroupedQuery } from "./useGroupedQuery";
import { type ListRequest, useListQuery } from "./useListQuery";
import { useViews, ViewBar } from "./ViewBar";
import {
  aggregateOf, clampWidth, DEFAULT_WIDTH_REM, dropField, MAX_WIDTH_REM, MIN_WIDTH_REM, moveField, requestAggregates,
  standardState, type TableState, withAggregate, withFilter, withOrder,
} from "./viewState";

const T = tr.table;

/** Satır yüksekliği rem cinsinden; tokens.css --row-height ile aynı (testte karşılaştırılır). */
export const ROW_REM = 2.1538;
/** Görünen satırların üstünde ve altında çizilen tampon satır sayısı (docs/12 performans hedefi). */
export const OVERSCAN = 10;
/** Grup düzeyi başına girinti ve grup okunun (ikon + boşluk) genişliği (rem); veri satırı hizası bunlardan. */
export const GROUP_INDENT_REM = 1.2308;
export const GROUP_ARROW_REM = 1.3077;
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

/** Ara toplam (K-90): miktarda tek birimin ondalığı; ortalamalar bir ondalık fazla, sayı ondalıksız. */
function formatAggregate(col: ListColumn, spec: AggSpec,
                         node: { aggregates: Record<string, number | null>; unit_decimals: Record<string, number> }) {
  const v = node.aggregates[col.field];
  if (v === null || v === undefined) return "";
  if (spec.fn === "count") return formatNumber(v, 0);
  const base = col.decimals_from_unit ? node.unit_decimals[col.field] ?? DEFAULT_UNIT_DECIMALS : col.decimals ?? 0;
  return formatNumber(v, ["avg", "avg_nonzero", "wavg"].includes(spec.fn) ? base + 1 : base);
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

type Pop = { kind: "filter" | "column"; field: string; anchor: HTMLElement } | null;

/** Hücrenin kolon düzeninden gelen sabit kısmı (sınıf, sabitleme konumu, girinti): düzen değişmedikçe aynı nesne. */
interface CellSpec {
  col: ListColumn;
  className?: string;
  style?: CSSProperties;
  numeric: boolean;
}

/**
 * Veri satırı. Belleğe alınır (memo): kaydırmada yalnız yeni giren ya da değişen satırlar çizilir; koşullu biçim
 * (K-95) yalnız onlarda hesaplanır. Her kaydırmada görünen bütün satırları yeniden çizmek, özellikle kurallar
 * varken ve geliştirme modunda tabloyu yavaşlatıyordu (1.6 ölçümü, docs/12).
 */
const DataRow = memo(function DataRow({ index, row, cells, selected, onSelect, active, ruleText }: {
  index: number;
  row: Row | undefined;
  cells: CellSpec[];
  selected: boolean;
  onSelect(id: number): void;
  active: FormatRule[];
  ruleText: Map<string, string>;
}) {
  return (
    <tr aria-rowindex={index + 2} aria-current={selected || undefined}
        className={row ? `sc-table-row${selected ? " is-selected" : ""}` : "is-placeholder"}
        onClick={row ? () => onSelect(row.Id) : undefined}>
      {cells.map(({ col, className, style, numeric }) => {
        const cf = row ? cellFormat(active, row, col.field) : null;
        return (
          <td key={col.field} className={className} style={cf ? { ...style, ...formatStyle(cf.format) } : style}
              title={cf ? T.ruleCellHint(cf.rules.map((r) => ruleText.get(r.id)).join("; ")) : undefined}>
            {row ? <RuledValue format={cf?.format} numeric={numeric}>{formatCell(col, row[col.field], row)}</RuledValue> : ""}
          </td>
        );
      })}
    </tr>
  );
});

export function DataTable({ list }: { list: string }) {
  const { fontSize, userId, trackExport } = useShell();
  const [columns, setColumns] = useState<ListColumn[] | null>(null);
  const [chunkSize, setChunkSize] = useState(0);
  const [exportInfo, setExportInfo] = useState<ExportInfo | null>(null);
  const [exporting, setExporting] = useState(false);
  const [columnsError, setColumnsError] = useState<ApiError | null>(null);
  const [columnsAttempt, setColumnsAttempt] = useState(0);
  const [state, setState] = useState<TableState | null>(null);
  const [panel, setPanel] = useState<"fields" | "group" | "rules" | null>(null);
  /** Kural penceresi; from: liste panelinden açıldıysa kapanınca panel geri açılır. */
  const [editing, setEditing] = useState<{ rule: FormatRule; isNew: boolean; from: "panel" | "menu" } | null>(null);
  /** Kural listesi kolon menüsünden açılır: o kolonun "⋯" düğmesinin yanında; "Kural ekle" o kolonla başlar. */
  const [rulesFrom, setRulesFrom] = useState<{ anchor: HTMLElement; field: string } | null>(null);
  const [pop, setPop] = useState<Pop>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [drag, setDrag] = useState<{ field: string; over?: string; side?: "before" | "after" } | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const groupBtnRef = useRef<HTMLButtonElement>(null);
  const fieldsBtnRef = useRef<HTMLButtonElement>(null);
  const panelPopRef = useRef<HTMLDivElement>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    listApi(list).columns(ctrl.signal)
      .then(({ columns: cols, chunk_size, export: info }) => {
        setColumns(cols);
        setChunkSize(chunk_size);
        setExportInfo(info);
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
  const visible = useMemo(() => s.order.map((f) => byField.get(f)).filter((c): c is ListColumn => Boolean(c)),
    [s.order, byField]);
  const width = (f: string) => s.widths[f] ?? DEFAULT_WIDTH_REM[byField.get(f)?.type ?? "text"];
  const pinStart = (i: number) => visible.slice(0, i).reduce((sum, c) => sum + width(c.field), 0);

  const ready = Boolean(columns && state && views.ready && chunkSize);
  // Koşullu biçim (K-95): ekrana uygulanan kurallar aktif, alanı görünen ve karşılaştırılan alanı listede olanlar.
  const known = useMemo(() => new Set((columns ?? []).map((c) => c.field)), [columns]);
  const active = useMemo(() => activeRules(s.rules, s.order, known), [s.rules, s.order, known]);
  /** Kural özetleri kural başına bir kez (hücre ipucunda her çizimde yeniden kurulmasın). */
  const ruleText = useMemo(() => new Map(active.map((r) => [r.id, describeRule(r, byField)])), [active, byField]);
  // Satır hücrelerinin sabit kısmı; kolon düzeni (sıra, genişlik, sabitleme, gruplu girinti) değişmedikçe aynı.
  // Gruplu görünümde veri satırının ilk hücresi, en alt grubun adıyla aynı hizada başlar (girinti + ok + boşluk).
  const groupDepth = s.groupBy.length;
  const cellSpecs: CellSpec[] = useMemo(() => {
    const widthOf = (f: string) => s.widths[f] ?? DEFAULT_WIDTH_REM[byField.get(f)?.type ?? "text"];
    const cols = s.order.map((f) => byField.get(f)).filter((c): c is ListColumn => Boolean(c));
    const indent = groupDepth ? `calc(var(--space-2) + ${(groupDepth - 1) * GROUP_INDENT_REM + GROUP_ARROW_REM}rem)` : undefined;
    let left = 0;
    return cols.map((col, i) => {
      const pinned = i < s.pinned;
      const style: CSSProperties | undefined = pinned ? { left: `${left}rem` } : undefined;
      left += widthOf(col.field);
      const className = [isNumeric(col) ? "is-num sc-num" : "",
                         pinned ? `is-pinned${i === s.pinned - 1 ? " is-pinned-last" : ""}` : ""].filter(Boolean).join(" ") || undefined;
      return { col, numeric: isNumeric(col), className, style: i === 0 && indent ? { ...style, paddingLeft: indent } : style };
    });
  }, [s.order, s.widths, s.pinned, groupDepth, byField]);
  const requestKey = JSON.stringify([s.order, s.sort, s.filters, active.map(toRequestRule)]);
  const request: ListRequest | null = useMemo(() => (ready ? {
    fields: s.order, sort: s.sort, filters: s.filters, ...(active.length ? { rules: active.map(toRequestRule) } : {}),
  } : null), [ready, requestKey]); // requestKey alanları, sıralamayı, filtreleri ve kuralları taşır
  const grouped = s.groupBy.length > 0;
  const flat = useListQuery(list, grouped ? null : request, chunkSize);
  const aggKey = JSON.stringify(requestAggregates(columns ?? [], s));
  const aggregates = useMemo(() => JSON.parse(aggKey) as Record<string, AggSpec>, [aggKey]);
  const g = useGroupedQuery(list, grouped ? request : null, s.groupBy, chunkSize, aggregates);
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
    setPop((p) => (p?.kind === kind && p.field === field ? null : { kind, field, anchor }));
  // Bütün açılır öğeler ortak yerleşimle görünür alana sığar (docs/12, ui/popover).
  useFloating(popRef, pop?.anchor ?? null, pop !== null);
  useFloating(panelPopRef, panel === "group" ? groupBtnRef : panel === "rules" ? rulesFrom?.anchor ?? null : fieldsBtnRef, panel !== null);

  const openRule = (field: string, from: "panel" | "menu") => {
    const col = byField.get(field) ?? columns?.[0];
    if (!col) return;
    setEditing({ rule: { id: newRuleId(s.rules), field: col.field, enabled: true, condition: { op: RULE_OPS[ruleKind(col)][0] },
                         format: {} }, isNew: true, from });
    setPanel(null);
  };
  const closeRule = (from: "panel" | "menu") => {
    setEditing(null);
    if (from === "panel") setPanel("rules");
  };

  const setFilter = (field: string, f: ListFilter | null) => {
    update((st) => ({ ...st, filters: withFilter(st.filters, field, f) }));
    setPop(null);
  };
  const others = useMemo(() => s.filters.filter((f) => f.field !== pop?.field), [s.filters, pop?.field]);
  const filterOf = (field: string) => s.filters.find((f) => f.field === field);

  const columnAction = (field: string, action: ColumnAction) => {
    if (action === "ruleAdd" || action === "ruleManage") {
      if (pop) setRulesFrom({ anchor: pop.anchor, field });
      setPop(null);
      if (action === "ruleAdd") openRule(field, "menu");
      else setPanel("rules");
      return;
    }
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
        default:
          return st;
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
  /** Düzey başına grup kimlikleri (toplu daralt / aç, Alt+tıklama). */
  const idsByLevel = useMemo(() => {
    const levels: string[][] = [];
    const walk = (nodes: GroupNode[], depth: number) => nodes.forEach((n) => {
      (levels[depth] ??= []).push(JSON.stringify(n.key));
      if (n.children) walk(n.children, depth + 1);
    });
    walk(g.tree?.groups ?? [], 0);
    return levels;
  }, [g.tree]);
  const allGroupIds = idsByLevel.flat();
  /** Alt+tıklama: bu düzeydeki bütün gruplar, tıklanan grubun tersi duruma geçer (U-11). */
  const toggleLevel = (depth: number, id: string) => setCollapsed((c) => {
    const close = !c.has(id);
    const next = new Set(c);
    (idsByLevel[depth] ?? []).forEach((x) => (close ? next.add(x) : next.delete(x)));
    return next;
  });
  const toggleGroup = (id: string) => setCollapsed((c) => {
    const next = new Set(c);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    return next;
  });

  /** Ekrandaki görünüm durumu + kapsam (K-91): anlık dosya iner, arka plandaki iş bildirimle izlenir. */
  const runExport = async (scope: ExportScope) => {
    const result = await listApi(list).export({
      fields: s.order, widths: s.widths, sort: s.sort, filters: s.filters, group_by: s.groupBy, aggregates, scope,
      rules: active,
    });
    if (result.kind === "file") saveBlob(result.blob, result.fileName);
    else trackExport({ jobId: result.job_id, title: exportInfo?.title ?? list, fileName: result.file_name, rows: result.rows });
    setExporting(false);
  };

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
    <DataRow key={String(key)} index={index} row={row} cells={cellSpecs} selected={Boolean(row) && row!.Id === selectedId}
             onSelect={setSelectedId} active={active} ruleText={ruleText} />
  );
  // Grup adı, ara toplamı olmayan baştaki kolonları kaplar (kesilmesin); sabit kolon varsa sabit bölgeyi aşmaz.
  const firstAgg = visible.findIndex((c) => aggregateOf(c, s).fn !== "none");
  const leading = Math.max(1, firstAgg === -1 ? visible.length : firstAgg);
  const aggCell = (c: ListColumn, node: GroupNode) => {
    const spec = aggregateOf(c, s);
    if (spec.fn === "none") return "";
    if (node.mixed_units.includes(c.field)) {
      return <span className="sc-muted" title={T.mixedUnits} aria-label={T.mixedUnits}>—</span>;
    }
    const label = spec.fn === "wavg" ? T.weightedBy(byField.get(spec.weight ?? "")?.label ?? "") : T.aggFns[spec.fn];
    const value = formatAggregate(c, spec, node);
    return value && <span title={label}><span className="sc-agg-fn">{T.aggShort[spec.fn]}</span>{value}</span>;
  };
  const labelSpan = s.pinned > 0 ? Math.min(leading, s.pinned) : leading;
  const renderGroup = (key: string | number | bigint, index: number, it: DisplayItem & { kind: "group" }) => {
    const open = !collapsed.has(it.id);
    const field = s.groupBy[it.depth];
    return (
      <tr key={String(key)} aria-rowindex={index + 2} aria-level={it.depth + 1} aria-expanded={open} tabIndex={0}
          className={`sc-table-group sc-table-group--${it.depth === 0 ? 1 : 2}`} title={T.groupToggleHint}
          onClick={(e) => (e.altKey ? toggleLevel(it.depth, it.id) : toggleGroup(it.id))}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              if (e.altKey) toggleLevel(it.depth, it.id);
              else toggleGroup(it.id);
            }
          }}>
        <td colSpan={labelSpan} className={labelSpan === s.pinned ? "is-pinned is-pinned-last" : pinnedCell(0).className || undefined}
            style={pinnedCell(0).style}>
          <span className="sc-tgroup-head" style={{ paddingLeft: `${it.depth * GROUP_INDENT_REM}rem` }}>
            {open ? <ChevronDown aria-hidden="true" /> : <ChevronRight aria-hidden="true" />}
            <span className="sc-tgroup-value">{groupLabel(byField.get(field), it.node.key[it.depth])}</span>
            <span className="sc-muted sc-num">· {T.groupRows(formatNumber(it.node.count))}</span>
          </span>
        </td>
        {visible.slice(labelSpan).map((c, j) => (
          <td key={c.field} className={cellClass(c, j + labelSpan)} style={pinnedCell(j + labelSpan).style}>
            {aggCell(c, it.node)}
          </td>
        ))}
      </tr>
    );
  };

  return (
    <div className="sc-table" ref={rootRef}>
      {views.error && <Alert tone="risk">{views.error}</Alert>}
      {views.warnings.length > 0 && (
        <Alert tone="info" title={T.viewWarnings} onClose={views.dismissWarnings}>{views.warnings.join(" ")}</Alert>
      )}
      {status === "error" && (
        <Alert tone="error" title={T.loadError}>
          {error?.message} <Button size="sm" onClick={grouped ? g.retry : flat.retry}>{T.retry}</Button>
        </Alert>
      )}

      {/* Araç çubuğu ve filtre / gruplama satırı sayfa zemininde; tablo çerçevesi başlık satırından başlar (U-22, docs/12) */}
      <div className="sc-table-toolbar">
        <div className="sc-table-toolbar-main">
          <ViewBar views={views} state={s} onClearSort={() => update((st) => ({ ...st, sort: [] }))} />
          <output className="sc-table-count sc-num" aria-label={T.countLabel}>
            {T.count(formatNumber(filtered), formatNumber(total))}
          </output>
        </div>
        <div className="sc-table-tools" ref={panelRef}>
          <Button size="sm" icon={Rows3} ref={groupBtnRef} aria-expanded={panel === "group"}
                  onClick={() => setPanel((p) => (p === "group" ? null : "group"))}>
            {T.group(s.groupBy.length)}
          </Button>
          {grouped && (
            <div className="sc-btn-group" role="group" aria-label={T.groupToggles}>
              <button type="button" className="sc-tool-btn" aria-label={T.collapseAll} title={T.collapseAll}
                      onClick={() => setCollapsed(new Set(allGroupIds))}><FoldVertical aria-hidden="true" /></button>
              <button type="button" className="sc-tool-btn" aria-label={T.expandAll} title={T.expandAll}
                      onClick={() => setCollapsed(new Set())}><UnfoldVertical aria-hidden="true" /></button>
              {s.groupBy.length >= 2 && (
                <button type="button" className="sc-tool-btn" aria-label={T.expandLevel1} title={T.expandLevel1}
                        onClick={() => setCollapsed(new Set(idsByLevel.slice(1).flat()))}><ListCollapse aria-hidden="true" /></button>
              )}
            </div>
          )}
          <Button size="sm" icon={Columns3} ref={fieldsBtnRef} aria-expanded={panel === "fields"}
                  onClick={() => setPanel((p) => (p === "fields" ? null : "fields"))}>
            {T.fields(visible.length, columns.length)}
          </Button>
          {exportInfo && (
            <Button size="sm" icon={FileSpreadsheet} onClick={() => setExporting(true)}>{T.exportButton}</Button>
          )}
          {panel === "group" && (
            <GroupPanel ref={panelPopRef} columns={columns} groupBy={s.groupBy}
                        onChange={(groupBy) => update((st) => ({ ...st, groupBy }))} />
          )}
          {panel === "rules" && (
            <RulesPanel ref={panelPopRef} rules={s.rules} columns={columns} visible={s.order}
                        onChange={(rules) => update((st) => ({ ...st, rules }))}
                        onEdit={(rule) => { setEditing({ rule, isNew: false, from: "panel" }); setPanel(null); }}
                        onAdd={() => openRule(rulesFrom?.field ?? s.order[0], "panel")} />
          )}
          {panel === "fields" && (
            <FieldPanel ref={panelPopRef} columns={columns}
                        visibility={Object.fromEntries(columns.map((c) => [c.field, s.order.includes(c.field)]))}
                        onToggle={(field, on) => update((st) => withOrder(st, on ? [...st.order, field] : st.order.filter((f) => f !== field)))}
                        onReset={() => update((st) => withOrder(st, standardState(columns).order))} />
          )}
        </div>
      </div>

      {(s.filters.length > 0 || grouped) && (
        <div className="sc-table-status">
          <FilterChips filters={s.filters} byField={byField} onRemove={(f) => setFilter(f, null)}
                       onEdit={(f, el) => openPop("filter", f, el)} />
          {s.filters.length > 0 && (
            <Button size="sm" variant="ghost" icon={FunnelX} onClick={() => update((st) => ({ ...st, filters: [] }))}>{T.clearFilters}</Button>
          )}
          {grouped && (
            <span className="sc-table-grouped">{T.groupedBy(s.groupBy.map((f) => byField.get(f)?.label ?? f).join(" › "))}</span>
          )}
        </div>
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
                        <span className={`sc-table-head-tools${isFiltered ? " has-filter" : ""}`}>
                          <button type="button" className={`sc-table-filter-btn${isFiltered ? " is-active" : ""}`}
                                  aria-label={T.filterOf(col.label)} aria-pressed={isFiltered} aria-haspopup="dialog"
                                  onClick={(e) => openPop("filter", col.field, e.currentTarget)}>
                            <Funnel aria-hidden="true" />
                          </button>
                          <button type="button" className="sc-table-filter-btn sc-table-menu-btn" aria-label={T.columnMenu(col.label)}
                                  aria-haspopup="menu" onClick={(e) => openPop("column", col.field, e.currentTarget)}>
                            <Ellipsis aria-hidden="true" />
                          </button>
                        </span>
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

      {editing && (
        <RuleDialog rule={editing.rule} isNew={editing.isNew} columns={columns}
                    onClose={() => closeRule(editing.from)}
                    onSave={(rule) => {
                      update((st) => ({ ...st, rules: editing.isNew ? [...st.rules, rule]
                        : st.rules.map((x) => (x.id === rule.id ? rule : x)) }));
                      closeRule(editing.from);
                    }} />
      )}

      {exporting && exportInfo && (
        <ExportDialog info={exportInfo} filtered={filtered} total={total} visibleColumns={visible.length}
                      allColumns={columns.length} hasFilters={s.filters.length > 0}
                      onClose={() => setExporting(false)} onExport={runExport} />
      )}

      {pop && popColumn && (
        <div className={pop.kind === "filter" ? "sc-table-pop sc-floating" : "sc-table-pop sc-table-pop--menu sc-floating"} ref={popRef}
             role={pop.kind === "filter" ? "dialog" : undefined}
             aria-label={pop.kind === "filter" ? T.filterOf(popColumn.label) : undefined}>
          {pop.kind === "filter" ? (
            <FilterMenu list={list} column={popColumn} filter={filterOf(popColumn.field)} others={others}
                        onApply={(f) => setFilter(popColumn.field, f)} />
          ) : (
            <ColumnMenu column={popColumn} columns={columns} state={s} ruleLimit={s.rules.length >= MAX_RULES}
                        onAction={(a) => columnAction(popColumn.field, a)}
                        onAggregate={(spec) => { update((st) => withAggregate(st, popColumn, spec)); setPop(null); }} />
          )}
        </div>
      )}
    </div>
  );
}

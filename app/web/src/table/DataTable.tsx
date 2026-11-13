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
  ArrowDown, ArrowUp, ChevronDown, ChevronRight, Columns3, Download, Ellipsis, FoldVertical, Funnel,
  FunnelX,
  ListCollapse, Rows3, UnfoldVertical,
} from "lucide-react";
import {
  type CSSProperties, type DragEvent, type HTMLAttributes, type KeyboardEvent, memo, type MouseEvent as ReactMouseEvent, type ReactNode, type RefObject,
  useCallback, useEffect, useMemo, useRef, useState,
} from "react";

import { ApiError, emitNotice, saveBlob } from "../api/client";
import { formatDate, formatDateTime, formatNumber, formatPercent } from "../format";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { Alert, Button } from "../ui";
import { type MenuAction, MenuActions, RowPopMenu } from "../ui/PopMenu";
import { userPrefs } from "../prefs";
import { useFloating } from "../ui/popover";
import { type ColumnAction, ColumnMenu } from "./ColumnMenu";
import { ExportDialog } from "./ExportDialog";
import { FieldPanel } from "./FieldPanel";
import { FilterChips } from "./FilterChips";
import { FilterMenu, valueLabel } from "./filters";
import { GroupPanel } from "./GroupPanel";
import { RuleDialog } from "./RuleDialog";
import { RuledValue } from "./RuleIcon";
import { type CellEditing, type EditorSpec, type PasteCell, parseClipboard } from "./cellEditing";
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

export type CellRender = Record<string, (value: unknown, row: Row) => ReactNode>;
/** Bütün kolonlarda hücre içeriğini saran işlev (ör. kuralla değişen hücrenin izi, K-140); Excel düz metin kalır. */
export type CellWrap = (field: string, row: Row, content: ReactNode) => ReactNode;
/** Kolon ipucu (ör. veri kurallarının Sıra kolonu, K-145): varsayılan genişlik (rem; kullanıcı değiştirince onunki) ve sola hizalama. */
export type FieldHints = Record<string, { width?: number; left?: boolean }>;
/** Hücrenin ek sınıfı (ör. kuralla değişen hücrenin lila zemini, K-143). */
export type CellClass = (field: string, row: Row) => string | undefined;
/** Satırın ek özellikleri (ör. sürükle-bırak, K-143): olay işleyicileri ve ek sınıf. */
export type RowProps = (row: Row) => HTMLAttributes<HTMLTableRowElement>;
/** Çoklu seçim (K-171): seçili satırların kimlikleri; rows() yüklü olmayanları da okur (ör. manuel değerleri kaldırmak için). */
export interface Selection { ids: string[]; rows(): Promise<Row[]> }

/** Satır sonundaki ⋯ menüsü (K-171): bütün tablolarda standart; detay görünümü olan tabloda ilk seçenek "Detay". Sağ tık aynı menüyü açar,
 *  hücreye özgü seçenekler (extra: Kopyala, Manuel değeri kaldır) menünün başına eklenir. */
export interface RowMenuSpec {
  label(row: Row): string;
  onOpen(row: Row, anchor: HTMLElement, extra?: MenuAction[]): void;
}

/** "⋯" kolonunun genişliği (rem). */
const ROW_MENU_REM = 2.5;

/** Hücre menüsünün ek öğesi (ör. manuel değeri kaldır, K-171). */
export type CellMenuItem = MenuAction;

/** Hücrenin ekrandaki metni panoya (K-173): navigator.clipboard yalnız HTTPS'te ya da localhost'ta; yoksa geçici alandan. */
async function copyCell(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // izin yoksa aşağıdaki yol denenir
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.append(area);
  area.select();
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    area.remove();
  }
}

/** Satır seçim kutusu kolonu (rem; toplu işlem, K-172). */
const SELECT_REM = 2.3077;

const features = tableFeatures({
  rowSortingFeature, columnVisibilityFeature, columnOrderingFeature, columnPinningFeature, columnSizingFeature,
});
const helper = createColumnHelper<typeof features, Row>();
/** fitHeaders: başlığın harf başına genişliği ve sıralama, filtre düğmeleriyle iç boşluk (rem; 13 px'te ölçüldü). */
const HEADER_CHAR_REM = 0.56;
const HEADER_PAD_REM = 3.6;
const NO_DATA: Row[] = [];

/** Birim bilinmiyorsa miktar ondalığı (docs/02 UnitOfMeasure.Decimals). */
const DEFAULT_UNIT_DECIMALS = 2;

export function formatCell(col: ListColumn, v: unknown, row?: Row): string {
  if (v === null || v === undefined || v === "") return "";
  switch (col.type) {
    case "number": {
      if (col.percent) return formatPercent(Number(v), col.decimals ?? 2);
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
  const digits = ["avg", "avg_nonzero", "wavg"].includes(spec.fn) ? base + 1 : base;
  return col.percent ? formatPercent(v, digits) : formatNumber(v, digits);
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
/** Satırın düzenleme durumu (K-172): imleç ve açık düzenleyici yalnız ilgili satıra verilir (öteki satırlar yeniden çizilmesin). */
interface RowEditing {
  spec: CellEditing;
  cursorField: string | null;
  open: { field: string; initial: string | null } | null;
  onCell(index: number, field: string): void;
  onStart(index: number, field: string): void;
  onDone(index: number, field: string, result: { text: string; move: Move } | null): void;
}
type Move = "down" | "right" | "left" | null;

/** Hücreyi kaplayan düzenleyici: Enter ve Tab taslağa alır, sonraki hücreye geçer; Esc vazgeçer; odak kaybı taslağa alır. */
function CellEditorBox({ spec, label, initial, onDone }: {
  spec: EditorSpec; label: string; initial: string | null; onDone(result: { text: string; move: Move } | null): void;
}) {
  const [text, setText] = useState(initial !== null && spec.kind === "text" ? initial : spec.text);
  const done = useRef(false);
  const box = useRef<HTMLInputElement & HTMLSelectElement>(null);
  useEffect(() => {  // odak kaydırmasız (tablo kaymasın); metinde imleç sona
    const el = box.current;
    if (!el) return;
    el.focus({ preventScroll: true });
    if (el instanceof HTMLInputElement) el.setSelectionRange(el.value.length, el.value.length);
  }, []);
  const finish = (result: { text: string; move: Move } | null) => {
    if (done.current) return;
    done.current = true;
    onDone(result);
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement | HTMLSelectElement>) => {
    if (e.key === "Enter") finish({ text, move: "down" });
    else if (e.key === "Tab") finish({ text, move: e.shiftKey ? "left" : "right" });
    else if (e.key === "Escape") finish(null);
    else return;
    e.preventDefault();
    e.stopPropagation();
  };
  const stop = (e: ReactMouseEvent) => e.stopPropagation();
  if (spec.kind === "select") {
    return (
      <select ref={box} className="sc-cell-editor" aria-label={label} value={text} onChange={(e) => setText(e.target.value)} onKeyDown={onKey}
              onBlur={() => finish({ text, move: null })} onClick={stop} onDoubleClick={stop}>
        {(spec.options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    );
  }
  return (
    <input ref={box} className="sc-cell-editor" aria-label={label} value={text} placeholder={spec.placeholder} onChange={(e) => setText(e.target.value)}
           onKeyDown={onKey} onBlur={() => finish({ text, move: null })} onClick={stop} onDoubleClick={stop} />
  );
}

/** Hücreyi en az kaydırmayla görünür yapar: yapışkan başlığın altında ve sabit kolonların sağında kalsın (tarayıcının odak kaydırması
 *  bunları hesaba katmaz, K-172). */
function revealCell(box: HTMLElement, el: HTMLElement) {
  const b = box.getBoundingClientRect();
  const r = el.getBoundingClientRect();
  const head = box.querySelector("thead")?.getBoundingClientRect().height ?? 0;
  const pinned = el.classList.contains("is-pinned") ? b.left
    : Math.max(b.left, ...[...box.querySelectorAll<HTMLElement>("thead th.is-pinned")].map((th) => th.getBoundingClientRect().right));
  if (r.top < b.top + head) box.scrollTop -= b.top + head - r.top;
  else if (r.bottom > b.bottom) box.scrollTop += r.bottom - b.bottom;
  if (r.left < pinned) box.scrollLeft -= pinned - r.left;
  else if (r.right > b.right) box.scrollLeft += r.right - b.right;
}

const DataRow = memo(function DataRow({ index, row, cells, selected, picked, onSelect, active, ruleText, cellRender, cellWrap, cellClass, rowProps, rowMenu, measure, edit, check, onMenu, onPick }: {
  index: number;
  row: Row | undefined;
  cells: CellSpec[];
  selected: boolean;
  /** Çoklu seçimde seçili (K-171): açık indigo. */
  picked?: boolean;
  /** Tıklama: Ctrl / Shift ile çoklu seçim (true dönerse satırın kendi tıklaması çalışmaz). */
  onSelect(index: number, row: Row, e: ReactMouseEvent): boolean;
  active: FormatRule[];
  ruleText: Map<string, string>;
  cellRender?: CellRender;
  cellWrap?: CellWrap;
  cellClass?: CellClass;
  rowProps?: RowProps;
  rowMenu?: RowMenuSpec;
  /** Pencere kipinde satır yüksekliği ölçülür (alt satıra kayan metin, sanal kaydırma kaymasın). */
  measure?: (el: HTMLTableRowElement | null) => void;
  edit?: RowEditing;
  /** Satır seçim kutusu (toplu işlem): işaretli mi, değişince. */
  check?: { checked: boolean; label: string; onChange(next: boolean): void };
  /** Hücre menüsü (sağ tık, K-173) ve kopyalanacak hücrenin seçimi (tıklama). */
  onMenu?: (index: number, col: ListColumn, row: Row, anchor: HTMLElement) => void;
  onPick?: (index: number, field: string) => void;
}) {
  const extra = row && rowProps ? rowProps(row) : {};  // satırın onClick'i seçimden sonra çalışır (ör. Veri aktarım raporu, K-156)
  return (
    <tr ref={measure} data-index={index} aria-rowindex={index + 2} aria-current={selected || undefined} {...extra}
        className={row ? [`sc-table-row${selected ? " is-selected" : ""}${picked ? " is-picked" : ""}`, extra.className].filter(Boolean).join(" ") : "is-placeholder"}
        aria-selected={row && check ? Boolean(picked) : undefined}
        onMouseDown={row ? (e) => { if (e.shiftKey || e.ctrlKey || e.metaKey) e.preventDefault(); } : undefined}
        onClick={row ? (e) => { if (!onSelect(index, row, e)) extra.onClick?.(e); } : undefined}>
      {check && (
        <td className="sc-table-check is-pinned" style={{ left: 0 }} onClick={(e) => e.stopPropagation()}>
          {row && <input type="checkbox" aria-label={check.label} checked={check.checked} onChange={(e) => check.onChange(e.target.checked)} />}
        </td>
      )}
      {cells.map(({ col, className, style, numeric }) => {
        const cf = row ? cellFormat(active, row, col.field) : null;
        const editable = Boolean(row && edit?.spec.canEdit(col, row));
        const isCursor = edit?.cursorField === col.field;
        const open = row && edit?.open?.field === col.field ? edit.open : null;
        const content = row ? (cellRender?.[col.field] ? cellRender[col.field](row[col.field], row) : formatCell(col, row[col.field], row)) : null;
        const classes = [className, row && cellClass?.(col.field, row), editable ? "is-editable" : "", isCursor ? "is-cursor" : "", open ? "is-editing" : ""];
        return (
          <td key={col.field} className={classes.filter(Boolean).join(" ") || undefined} style={cf ? { ...style, ...formatStyle(cf.format) } : style}
              title={cf ? T.ruleCellHint(cf.rules.map((r) => ruleText.get(r.id)).join("; ")) : undefined}
              {...(edit || onMenu ? { "data-cell": `${index}|${col.field}` } : {})}
              {...(edit ? {
                tabIndex: isCursor ? 0 : -1,
                onClick: () => edit.onCell(index, col.field),
                onDoubleClick: editable ? () => edit.onStart(index, col.field) : undefined,
              } : onPick ? { onClick: () => onPick(index, col.field) } : {})}
              onContextMenu={row && onMenu ? (e: ReactMouseEvent<HTMLTableCellElement>) => {  // hücrenin tamamında (metnin dışında da)
                e.preventDefault();
                edit?.onCell(index, col.field);
                onPick?.(index, col.field);
                onMenu(index, col, row, e.currentTarget);
              } : undefined}>
            {row && open ? (
              <CellEditorBox spec={edit!.spec.editor(col, row)} label={edit!.spec.label(col, row)} initial={open.initial}
                             onDone={(result) => edit!.onDone(index, col.field, result)} />
            ) : row ? (
              <RuledValue format={cf?.format} numeric={numeric}>
                {cellWrap ? cellWrap(col.field, row, content) : content}
              </RuledValue>
            ) : ""}
          </td>
        );
      })}
      {rowMenu && <RowMenuCell row={row} menu={rowMenu} />}
    </tr>
  );
});

/** Taslak sıra (K-142): yüklü satırlar Id'ye göre verilen sırayla; sırada olmayan satır sona. Sıra yoksa null. */
function orderedRows(order: readonly string[] | null, count: number, rowAt: (i: number) => Row | undefined): (Row | undefined)[] | null {
  if (!order) return null;
  const byId = new Map<string, Row>();
  const rest: Row[] = [];
  for (let i = 0; i < count; i++) {
    const r = rowAt(i);
    if (r) byId.set(String(r.Id), r);
  }
  const out: (Row | undefined)[] = order.map((id) => byId.get(id));
  for (const [id, r] of byId) if (!order.includes(id)) rest.push(r);
  return [...out, ...rest];
}

/** Sağda sabit "⋯" hücresi (2.3): alan paneline, görünüme ve Excel'e girmez. */
function RowMenuCell({ row, menu }: { row: Row | undefined; menu: RowMenuSpec }) {
  return (
    <td className="sc-table-rowmenu">
      {row && (
        <button type="button" className="sc-table-filter-btn" aria-haspopup="menu" aria-label={menu.label(row)}
                onClick={(e) => { e.stopPropagation(); menu.onOpen(row, e.currentTarget); }}>
          <Ellipsis aria-hidden="true" />
        </button>
      )}
    </td>
  );
}

export function DataTable({ list, cellRender, cellWrap, cellClass, rowProps, fieldHints, rowMenu, reloadKey = 0, baseFilters, toolbarLead, toolbarEnd, compact = false, toolbarActions, fit = false, fitHeaders = false, onColumns, cellEditing, wrapFields, rowOrder, selectedRowId, cellMenu, onSelection, selectionMenu }: {
  list: string;
  /** Alana göre hücre içeriği (ör. rozet); Excel düz metin kalır. */
  cellRender?: CellRender;
  cellWrap?: CellWrap;
  cellClass?: CellClass;
  rowProps?: RowProps;
  fieldHints?: FieldHints;
  /** Satır işlemleri: sağda sabit "⋯" kolonu. */
  rowMenu?: RowMenuSpec;
  /** Artınca (işlemden sonra) satırlar yeniden okunur. */
  reloadKey?: number;
  /** Sabit filtre (ör. tek parti, K-129): her sorguya eklenir, etiketlerde görünmez, kaldırılamaz; Excel de yalnız bu satırları alır. */
  baseFilters?: ListFilter[];
  /** Şeridin solunda: ekranın sekmeleri ve tablo seçimi (K-168, K-173). */
  toolbarLead?: ReactNode;
  /** Araç çubuğunun başında (ör. tablo içi düzenlemenin Kaydet ve Vazgeç'i, K-132). */
  toolbarActions?: ReactNode;
  /** Varsayılan genişlik en az başlığı sığdırır (K-169; veri ekranları: tablo yana kayar, başlık kesilmez). Kullanıcının genişliği önce gelir. */
  fitHeaders?: boolean;
  /** Hücre düzenleme standardı (K-172): imleç, ok tuşları, düzenleyici, yapıştırma. */
  cellEditing?: CellEditing;
  /** Çoklu seçim değişince (K-171; ör. detay kartı seçili kayıtların hepsini gösterir). */
  onSelection?: (ids: string[]) => void;
  /** Seçili satıra sağ tıkta "Seçili n satır" grubunun toplu işlemleri (K-171); boşsa grup yok. */
  selectionMenu?: (selection: Selection) => MenuAction[];
  /** Kolonlar yüklenince (ör. manuel değer düzenleyicileri kolon tipini bilsin, K-170). */
  onColumns?: (columns: ListColumn[]) => void;
  /** Pencere kipi (docs/12): tablo pencereye sığar, kolon genişliği içerikten; sabitleme ve genişlik ayarı yok. */
  fit?: boolean;
  /** Pencere kipinde kalan genişliği alıp alt satıra kayan uzun metin kolonları (ör. Sorun). */
  wrapFields?: readonly string[];
  /** Taslak satır sırası (Id listesi; ör. veri kurallarının sırası, K-142): verilirse ve gruplama yoksa satırlar bu sırayla çizilir.
   *  Bütün satırların yüklü olduğu küçük listeler içindir. */
  rowOrder?: readonly string[] | null;
  /** Seçili satırı dışarıdan verir (ana–detay düzeni, K-161): detay kapanınca işaret kalkar; verilmezse tıklanan satır işaretli kalır. */
  selectedRowId?: number | string | null;
  /** Hücreye özgü sağ tık seçenekleri (K-171): Kopyala'nın ardından. Sağ tık her tabloda açılır; satır menüsü varsa onu bu seçenekler başta
   *  olarak açar, yoksa yalnız bunlar. Ctrl+C seçili hücreyi kopyalar. */
  cellMenu?: (col: ListColumn, row: Row) => CellMenuItem[];
  /** Şeridin en sağında (ör. detay kartında Büyüt ve ✕, K-173). */
  toolbarEnd?: ReactNode;
  /** Alçak şerit (detay kartı, K-173). */
  compact?: boolean;
}) {
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
  // Çoklu seçim (K-171): kimlikler; kolon ⚙ menüsünden, kullanıcı ve tablo başına
  const [multiOn, setMultiOn] = useState(() => userPrefs(userId).multiSelect(list));
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set());
  const anchorRef = useRef<number | null>(null);
  const plainRef = useRef(false);  // son tıklama düz tık mıydı: ilk Ctrl tıklamada o satır da seçime girer
  const rowClickRef = useRef<(index: number, row: Row, e: ReactMouseEvent) => boolean>(() => false);
  const onRowSelect = useCallback((index: number, row: Row, e: ReactMouseEvent) => rowClickRef.current(index, row, e), []);
  /** Hücre imleci ve açık düzenleyici (K-172): satır sırası (index) ve alan. */
  const [cursor, setCursor] = useState<{ index: number; field: string } | null>(null);
  const [openCell, setOpenCell] = useState<{ index: number; field: string; initial: string | null } | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    listApi(list).columns(ctrl.signal)
      .then(({ columns: cols, chunk_size, export: info }) => {
        setColumns(cols);
        onColumns?.(cols);
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
  /** Kolonun varsayılan genişliği (rem): ipucu ya da tipin varsayılanı; fitHeaders'ta başlık (sıralama ve filtre düğmeleriyle) kesilmesin. */
  const baseWidth = (f: string): number => {
    const c = byField.get(f);
    const w = fieldHints?.[f]?.width ?? DEFAULT_WIDTH_REM[c?.type ?? "text"];
    return fitHeaders && c ? Math.max(w, clampWidth(c.label.length * HEADER_CHAR_REM + HEADER_PAD_REM)) : w;
  };

  // TanStack durumu TableState'ten türetilir (genişlikler rem).
  const sorting: SortingState = useMemo(() => s.sort.map((x) => ({ id: x.field, desc: x.dir === "desc" })), [s.sort]);
  const defs = useMemo(() => (columns ?? []).map((c) => helper.accessor((r) => r[c.field], {
    id: c.field, header: c.label, size: baseWidth(c.field), minSize: MIN_WIDTH_REM, maxSize: MAX_WIDTH_REM,
  })), [columns]);
  const table = useTable({
    features, columns: defs, data: NO_DATA,
    state: {
      sorting,
      columnVisibility: Object.fromEntries((columns ?? []).map((c) => [c.field, s.order.includes(c.field)])),
      columnOrder: [...s.order, ...(columns ?? []).map((c) => c.field).filter((f) => !s.order.includes(f))],
      columnPinning: { start: s.order.slice(0, s.pinned), end: [] },
      columnSizing: Object.fromEntries(s.order.map((f) => [f, s.widths[f] ?? baseWidth(f)])),
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
  const width = (f: string) => s.widths[f] ?? baseWidth(f);
  const pinnedCount = fit ? 0 : s.pinned;
  const selRem = multiOn && !s.groupBy.length && !fit ? SELECT_REM : 0;
  const wrapKey = (wrapFields ?? []).join(",");
  const pinStart = (i: number) => selRem + visible.slice(0, i).reduce((sum, c) => sum + width(c.field), 0);

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
    const widthOf = (f: string) => s.widths[f] ?? baseWidth(f);
    const cols = s.order.map((f) => byField.get(f)).filter((c): c is ListColumn => Boolean(c));
    const indent = groupDepth ? `calc(var(--space-2) + ${(groupDepth - 1) * GROUP_INDENT_REM + GROUP_ARROW_REM}rem)` : undefined;
    let left = selRem;
    return cols.map((col, i) => {
      const pinned = i < pinnedCount;
      const style: CSSProperties | undefined = pinned ? { left: `${left}rem` } : undefined;
      left += widthOf(col.field);
      const className = [isNumeric(col) ? (fieldHints?.[col.field]?.left ? "sc-num" : "is-num sc-num") : "",
                         pinned ? `is-pinned${i === pinnedCount - 1 ? " is-pinned-last" : ""}` : "",
                         wrapKey.split(",").includes(col.field) ? "is-wrap" : ""].filter(Boolean).join(" ") || undefined;
      return { col, numeric: isNumeric(col), className, style: i === 0 && indent ? { ...style, paddingLeft: indent } : style };
    });
  }, [s.order, s.widths, pinnedCount, wrapKey, groupDepth, byField, selRem]);
  const baseKey = JSON.stringify(baseFilters ?? []);
  const fixed = useMemo(() => JSON.parse(baseKey) as ListFilter[], [baseKey]);
  const requestKey = JSON.stringify([s.order, s.sort, s.filters, fixed, active.map(toRequestRule)]);
  const request: ListRequest | null = useMemo(() => (ready ? {
    fields: s.order, sort: s.sort, filters: [...fixed, ...s.filters], ...(active.length ? { rules: active.map(toRequestRule) } : {}),
  } : null), [ready, requestKey]); // requestKey alanları, sıralamayı, filtreleri ve kuralları taşır
  const grouped = s.groupBy.length > 0;
  const flat = useListQuery(list, grouped ? null : request, chunkSize);
  const aggKey = JSON.stringify(requestAggregates(columns ?? [], s));
  const aggregates = useMemo(() => JSON.parse(aggKey) as Record<string, AggSpec>, [aggKey]);
  const g = useGroupedQuery(list, grouped ? request : null, s.groupBy, chunkSize, aggregates);
  const shownReload = useRef(reloadKey);
  const reload = grouped ? g.retry : flat.refresh;
  useEffect(() => {
    if (shownReload.current === reloadKey) return;
    shownReload.current = reloadKey;
    reload();
  }, [reloadKey, reload]);
  const pickKey = JSON.stringify([list, fixed, s.filters]);
  useEffect(() => setPicked(new Set()), [pickKey]);
  const onSelectionRef = useRef(onSelection);
  onSelectionRef.current = onSelection;
  useEffect(() => onSelectionRef.current?.([...picked]), [picked]);
  // Esc önce seçimi temizler (K-171): pencere, menü ya da düzenleyici açıksa onlar kapanır; seçim yoksa kartın Esc'i çalışır
  useEffect(() => {
    if (!picked.size) return undefined;
    const key = (e: globalThis.KeyboardEvent) => {
      if (e.key !== "Escape" || document.querySelector("[role=dialog], [role=menu], .sc-cell-editor")) return;
      e.stopPropagation();
      setPicked(new Set());
    };
    window.addEventListener("keydown", key, true);
    return () => window.removeEventListener("keydown", key, true);
  }, [picked]);
  const groupKey = JSON.stringify([s.groupBy, s.filters]);
  useEffect(() => setCollapsed(new Set()), [groupKey]);
  const display: DisplayItem[] | null = useMemo(
    () => (grouped && g.tree ? flatten(g.tree.groups, s.groupBy, collapsed) : null),
    [grouped, g.tree, s.groupBy, collapsed]);

  const count = grouped ? display?.length ?? 0 : flat.filtered;
  const ordered = orderedRows(grouped ? null : rowOrder ?? null, count, flat.row);
  const status = grouped ? g.status : flat.status;
  const rowAtIndex = useCallback((i: number) => (ordered ? ordered[i] : flat.row(i)), [ordered, flat]);
  // Hücre imleci yalnız düzenlenebilir kolonu olan tabloda (K-172): öteki tabloda yalnız satır vurgusu
  const gridOn = Boolean(cellEditing) && !grouped && (columns ?? []).some((c) => cellEditing!.editableColumn(c));
  /** İmleç klavyeyle (ya da düzenleyiciden) taşındı: görünür alana getirilir. Fareyle kaydırma imleci geri çekmez (K-172). */
  const reveal = useRef(false);
  const startEdit = useCallback((index: number, field: string, initial: string | null) => {
    const row = rowAtIndex(index);
    const col = byField.get(field);
    if (!cellEditing || !row || !col || !cellEditing.canEdit(col, row)) return;
    reveal.current = true;
    setCursor({ index, field });
    setOpenCell({ index, field, initial });
  }, [cellEditing, rowAtIndex, byField]);
  const moveCursor = useCallback((from: { index: number; field: string }, di: number, dj: number) => {
    const j = visible.findIndex((c) => c.field === from.field);
    const index = Math.min(Math.max(from.index + di, 0), Math.max(count - 1, 0));
    const field = visible[Math.min(Math.max(j + dj, 0), visible.length - 1)]?.field ?? from.field;
    reveal.current = true;
    setCursor({ index, field });
  }, [visible, count]);
  const finishEdit = useCallback((index: number, field: string, result: { text: string; move: Move } | null) => {
    const row = rowAtIndex(index);
    const col = byField.get(field);
    if (result && row && col && cellEditing) cellEditing.commit(col, row, result.text);
    setOpenCell(null);
    if (result?.move) moveCursor({ index, field }, result.move === "down" ? 1 : 0, result.move === "right" ? 1 : result.move === "left" ? -1 : 0);
  }, [rowAtIndex, byField, cellEditing, moveCursor]);
  /** Klavye ve yapıştırma yalnız hücreden ya da tablo kutusundan (imleç hücresi kaydırmayla çizimden çıkınca odak kutuda kalır). */
  // Hücre menüsü ve kopyalama (K-173): imleçli tabloda imleç hücresi, ötekinde son tıklanan hücre
  const menuOn = true;  // sağ tık ve Ctrl+C her tabloda (K-171)
  const [menu, setMenu] = useState<{ anchor: HTMLElement; items: MenuAction[] } | null>(null);
  const [pick, setPick] = useState<{ index: number; field: string } | null>(null);
  const pickedRef = useRef(picked);
  pickedRef.current = picked;
  const selectionRef = useRef<Selection | null>(null);
  const onMenu = useCallback((_index: number, col: ListColumn, row: Row, anchor: HTMLElement) => {
    const text = (anchor.textContent ?? "").trim();
    const sel = selectionRef.current;
    // Seçili satırda "Seçili n satır" grubu başta (K-171)
    const bulk = sel && pickedRef.current.has(String(row.Id)) ? selectionMenu?.(sel) ?? [] : [];
    const items: MenuAction[] = [
      ...(bulk.length ? [{ kind: "heading" as const, label: T.pickedRows(formatNumber(sel!.ids.length)) }, ...bulk, { kind: "separator" as const, label: "" }] : []),
      { label: T.copy, onClick: () => void copyText(text) },
      ...(cellMenu?.(col, row) ?? []),
    ];
    if (rowMenu) rowMenu.onOpen(row, anchor, items);  // ekranın satır menüsü, hücre seçenekleri başta
    else setMenu({ anchor, items });
  }, [rowMenu, cellMenu, selectionMenu]);
  const onPick = useCallback((index: number, field: string) => setPick({ index, field }), []);
  // Kopyalamada bildirim yok (K-171); yalnız pano kullanılamazsa
  async function copyText(text: string) {
    if (!(await copyCell(text))) emitNotice(T.copyFailed);
  }
  const selectAll = async () => {
    try {
      const r = await listApi(list).ids([...fixed, ...s.filters]);
      setPicked(new Set(r.ids));
      if (r.truncated) emitNotice(T.selectionMax);
    } catch (e) {
      emitNotice(e instanceof ApiError ? e.message : T.loadError);
    }
  };
  const onSelectKey = (e: KeyboardEvent<HTMLDivElement>): boolean => {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "a" || openCell) return false;
    const el = e.target as HTMLElement;
    if (el !== scrollRef.current && (!el.closest?.("td[data-cell]") || el.closest("input, select, textarea"))) return false;
    e.preventDefault();
    void selectAll();
    return true;
  };
  const onCopyKey = (e: KeyboardEvent<HTMLDivElement>): boolean => {
    if (!menuOn || !(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "c" || window.getSelection()?.toString()) return false;
    const target = gridOn ? cursor : pick;
    const el = target && scrollRef.current?.querySelector<HTMLElement>(`td[data-cell="${target.index}|${target.field}"]`);
    if (!el) return false;
    e.preventDefault();
    void copyText((el.textContent ?? "").trim());
    return true;
  };
  const fromGrid = (target: EventTarget) => target === scrollRef.current || Boolean((target as HTMLElement).closest?.("td[data-cell]"))
    && !(target as HTMLElement).closest("button, input, select, a, textarea");
  const onGridKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!gridOn || !cursor || openCell || !fromGrid(e.target)) return;
    const j = visible.findIndex((c) => c.field === cursor.field);
    switch (e.key) {
      case "ArrowUp": moveCursor(cursor, -1, 0); break;
      case "ArrowDown": moveCursor(cursor, 1, 0); break;
      case "ArrowLeft": moveCursor(cursor, 0, -1); break;
      case "ArrowRight": moveCursor(cursor, 0, 1); break;
      case "Tab":
        if ((e.shiftKey && j <= 0) || (!e.shiftKey && j >= visible.length - 1)) return;  // sınırda odak tablodan çıkar
        moveCursor(cursor, 0, e.shiftKey ? -1 : 1);
        break;
      case "Enter": case "F2": startEdit(cursor.index, cursor.field, null); break;
      case "Delete": {  // seçili hücrenin değerini kaldırma (manuel değer, K-172); düzenleyiciyi açmaz
        const row = rowAtIndex(cursor.index);
        const col = byField.get(cursor.field);
        if (!row || !col || !cellEditing?.clear?.(col, row)) return;
        break;
      }
      default:
        if (e.key.length !== 1 || e.ctrlKey || e.metaKey || e.altKey) return;
        startEdit(cursor.index, cursor.field, e.key);  // yazmaya başlamak düzenleyiciyi açar
    }
    e.preventDefault();
  };
  const onGridPaste = (e: React.ClipboardEvent<HTMLDivElement>) => {
    if (!gridOn || !cursor || openCell || !cellEditing?.paste || !fromGrid(e.target)) return;
    const text = e.clipboardData.getData("text/plain");
    if (!text) return;
    e.preventDefault();
    const j = visible.findIndex((c) => c.field === cursor.field);
    const cells: PasteCell[] = [];
    parseClipboard(text).forEach((line, r) => line.forEach((value, c) => {
      const index = cursor.index + r;
      cells.push({ row: index < count ? rowAtIndex(index) : undefined, col: visible[j + c], text: value });
    }));
    cellEditing.paste(cells);
  };
  const error = grouped ? g.error : flat.error;
  const filtered = grouped ? g.tree?.filtered ?? 0 : flat.filtered;
  const total = grouped ? g.tree?.total ?? 0 : flat.total;

  const rowPx = Math.round(fontSize * ROW_REM);
  const virtualizer = useVirtualizer({
    count, getScrollElement: () => scrollRef.current, estimateSize: () => rowPx, overscan: OVERSCAN,
    ...(fit ? { measureElement: (el: Element) => el.getBoundingClientRect().height || rowPx } : {}),
  });
  useEffect(() => virtualizer.measure(), [rowPx, virtualizer]);
  const items = virtualizer.getVirtualItems();
  // İmleç hücresine odak. Yalnız klavyeyle taşınan imleç görünür alana getirilir (reveal); fareyle kaydırırken imleç hücresi çizimden
  // çıkarsa odak tablo kutusuna geçer (klavye çalışmaya devam eder), kaydırma geri çekilmez (K-172). Odak tablonun dışındaysa (ör. açık
  // pencere, araç çubuğu) ya da tablodaki bir düğme ve kutudaysa alınmaz.
  useEffect(() => {
    if (!cursor || openCell || !gridOn) return;
    const box = scrollRef.current;
    if (!box) return;
    const el = box.querySelector<HTMLElement>(`td[data-cell="${cursor.index}|${cursor.field}"]`);
    const activeEl = document.activeElement;
    const ours = activeEl === document.body || activeEl === box || Boolean(activeEl?.matches("td[data-cell]") && box.contains(activeEl));
    if (!el) {
      if (reveal.current) virtualizer.scrollToIndex(cursor.index);
      else if (activeEl === document.body) box.focus({ preventScroll: true });
      return;
    }
    if (!ours) {
      reveal.current = false;
      return;
    }
    if (activeEl !== el) el.focus({ preventScroll: true });
    if (reveal.current) {
      reveal.current = false;
      revealCell(box, el);
    }
  }, [cursor, openCell, gridOn, items, virtualizer]);
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
  const others = useMemo(() => [...fixed, ...s.filters.filter((f) => f.field !== pop?.field)], [fixed, s.filters, pop?.field]);
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
      fields: s.order, widths: s.widths, sort: s.sort, filters: [...fixed, ...s.filters], group_by: s.groupBy, aggregates,
      scope: fixed.length ? { ...scope, rows: "filtered" } : scope,  // "Tümü" sabit filtreyi aşmaz
      rules: active,
    });
    if (result.kind === "file") saveBlob(result.blob, result.fileName);
    else trackExport({ jobId: result.job_id, title: exportInfo?.title ?? list, fileName: result.file_name, rows: result.rows });
    setExporting(false);
  };

  // Kolonlar gelmeden (yükleniyor, hata) de şeridin solu ve sağ ucu çizilir: sekmeler ve kartın Büyüt / ✕'i kaybolmaz (K-173)
  const bareStrip = (toolbarLead || toolbarEnd) ? (
    <div className={`sc-table-toolbar${compact ? " sc-table-toolbar--compact" : ""}`}>
      <div className="sc-table-toolbar-main">{toolbarLead}</div>
      <div className="sc-table-tools">{toolbarEnd}</div>
    </div>
  ) : null;
  if (columnsError) {
    return (
      <>
        {bareStrip}
        <Alert tone="error" title={T.loadError}>
          {columnsError.message} <Button size="sm" onClick={() => setColumnsAttempt((n) => n + 1)}>{T.retry}</Button>
        </Alert>
      </>
    );
  }
  if (!columns || !state) return <>{bareStrip}<p className="sc-muted">{T.loading}</p></>;

  const paddingTop = items[0]?.start ?? 0;
  const extraCols = (rowMenu ? 1 : 0) + (selRem ? 1 : 0);
  /** Başlıktaki kutu: yüklü satırların hepsi (parça parça yüklenir; filtrelenmiş liste kaydırdıkça gelir). */
  const loadedRows = (): Row[] => {
    const rows: Row[] = [];
    for (let i = 0; i < count; i++) {
      const r = rowAtIndex(i);
      if (r) rows.push(r);
    }
    return rows;
  };
  const allPicked = picked.size > 0 && picked.size >= filtered;
  const somePicked = picked.size > 0 && !allPicked;
  const togglePick = (id: string, on?: boolean) => setPicked((p) => {
    const next = new Set(p);
    if (on ?? !next.has(id)) next.add(id);
    else next.delete(id);
    return next;
  });
  /** Satır tıklaması (K-171): Ctrl ekler ya da çıkarır (ilk Ctrl tıklamada son tıklanan satır da girer), Shift aralığı seçer; düz tık seçimi temizler. */
  const onRowClick = (index: number, row: Row, e: ReactMouseEvent): boolean => {
    const id = String(row.Id);
    if (e.ctrlKey || e.metaKey) {
      const anchorRow = plainRef.current && anchorRef.current !== null && !grouped ? rowAtIndex(anchorRef.current) : undefined;  // güncelleyiciden önce
      setPicked((p) => {
        const next = new Set(p);
        if (!next.size && anchorRow && String(anchorRow.Id) !== id) next.add(String(anchorRow.Id));
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
      anchorRef.current = index;
      plainRef.current = false;
      return true;
    }
    if (e.shiftKey && anchorRef.current !== null && !grouped) {
      const [lo, hi] = [Math.min(anchorRef.current, index), Math.max(anchorRef.current, index)];
      setPicked((p) => {
        const next = new Set(p);
        for (let i = lo; i <= hi; i++) {
          const r = rowAtIndex(i);
          if (r) next.add(String(r.Id));
        }
        return next;
      });
      return true;
    }
    anchorRef.current = index;
    plainRef.current = true;
    if (picked.size) setPicked(new Set());
    setSelectedId(row.Id);
    return false;
  };
  rowClickRef.current = onRowClick;
  // Seçili satırlar (yüklü olmayanlar da): Id süzgeciyle parça parça okunur
  selectionRef.current = picked.size ? {
    ids: [...picked],
    rows: async () => {
      const have = new Map(loadedRows().map((r) => [String(r.Id), r]));
      const missing = [...picked].filter((id) => !have.has(id));
      for (let i = 0; i < missing.length; i += chunkSize) {
        const part = missing.slice(i, i + chunkSize);
        const r = await listApi(list).query({ fields: s.order, sort: [], filters: [...fixed, { field: "Id", op: "in", values: part }], offset: 0, limit: chunkSize });
        r.rows.forEach((row) => have.set(String(row.Id), row));
      }
      return [...picked].map((id) => have.get(id)).filter((r): r is Row => Boolean(r));
    },
  } : null;
  const paddingBottom = items.length ? virtualizer.getTotalSize() - items[items.length - 1].end : 0;
  const popColumn = pop ? byField.get(pop.field) : undefined;
  const multi = s.sort.length > 1;
  const pinnedCell = (i: number): { className: string; style?: CSSProperties } =>
    i < pinnedCount ? { className: `is-pinned${i === pinnedCount - 1 ? " is-pinned-last" : ""}`, style: { left: `${pinStart(i)}rem` } }
                 : { className: "" };
  const colClass = (c: ListColumn, i: number) =>
    [isNumeric(c) ? (fieldHints?.[c.field]?.left ? "sc-num" : "is-num sc-num") : "", pinnedCell(i).className].filter(Boolean).join(" ") || undefined;

  const renderRow = (key: string | number | bigint, index: number, row: Row | undefined) => (
    <DataRow key={String(key)} index={index} row={row} cells={cellSpecs} selected={Boolean(row) && row!.Id === (selectedRowId !== undefined ? selectedRowId : selectedId)}
             picked={Boolean(row) && picked.has(String(row!.Id))} onSelect={onRowSelect} active={active} ruleText={ruleText} cellRender={cellRender} cellWrap={cellWrap} cellClass={cellClass} rowProps={rowProps} rowMenu={rowMenu}
             measure={fit ? virtualizer.measureElement : undefined}
             edit={gridOn && cellEditing ? {
               spec: cellEditing, cursorField: cursor?.index === index ? cursor.field : null,
               open: openCell?.index === index ? openCell : null,
               onCell: (i, f) => setCursor({ index: i, field: f }), onStart: (i, f) => startEdit(i, f, null), onDone: finishEdit,
             } : undefined}
             onMenu={menuOn ? onMenu : undefined} onPick={menuOn && !gridOn ? onPick : undefined}
             check={selRem && row ? {
               checked: picked.has(String(row.Id)), label: T.selectRow,
               onChange: (next) => { togglePick(String(row.Id), next); anchorRef.current = index; },
             } : selRem ? { checked: false, label: "", onChange: () => {} } : undefined} />
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
  const labelSpan = pinnedCount > 0 ? Math.min(leading, pinnedCount) : leading;
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
        <td colSpan={labelSpan} className={labelSpan === pinnedCount ? "is-pinned is-pinned-last" : pinnedCell(0).className || undefined}
            style={pinnedCell(0).style}>
          <span className="sc-tgroup-head" style={{ paddingLeft: `${it.depth * GROUP_INDENT_REM}rem` }}>
            {open ? <ChevronDown aria-hidden="true" /> : <ChevronRight aria-hidden="true" />}
            <span className="sc-tgroup-value">{groupLabel(byField.get(field), it.node.key[it.depth])}</span>
            <span className="sc-muted sc-num">· {T.groupRows(formatNumber(it.node.count))}</span>
          </span>
        </td>
        {visible.slice(labelSpan).map((c, j) => (
          <td key={c.field} className={colClass(c, j + labelSpan)} style={pinnedCell(j + labelSpan).style}>
            {aggCell(c, it.node)}
          </td>
        ))}
        {rowMenu && <td className="sc-table-rowmenu" />}
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
      <div className={`sc-table-toolbar${compact ? " sc-table-toolbar--compact" : ""}`}>
        <div className="sc-table-toolbar-main">{toolbarLead}</div>
        <div className="sc-table-tools" ref={panelRef}>
          {toolbarActions}
          <ViewBar views={views} state={s} onClearSort={() => update((st) => ({ ...st, sort: [] }))}
                   multi={fit ? undefined : { on: multiOn, toggle: () => { const next = !multiOn; setMultiOn(next); userPrefs(userId).setMultiSelect(list, next); } }}>
            <button type="button" className={`sc-tool-btn${s.groupBy.length ? " has-mark" : ""}`} ref={groupBtnRef} aria-expanded={panel === "group"}
                    aria-label={T.group(s.groupBy.length)} title={T.group(s.groupBy.length)}
                    onClick={() => setPanel((p) => (p === "group" ? null : "group"))}><Rows3 aria-hidden="true" /></button>
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
            <button type="button" className="sc-tool-btn" ref={fieldsBtnRef} aria-expanded={panel === "fields"}
                    aria-label={T.fields(visible.length, columns.length)} title={T.fields(visible.length, columns.length)}
                    onClick={() => setPanel((p) => (p === "fields" ? null : "fields"))}><Columns3 aria-hidden="true" /></button>
            {exportInfo && (
              <button type="button" className="sc-tool-btn" aria-label={T.exportButton} title={T.exportButton}
                      onClick={() => setExporting(true)}><Download aria-hidden="true" /></button>
            )}
          </ViewBar>
          {toolbarEnd}
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

      {menu && (
        <RowPopMenu label={T.cellMenu} anchor={menu.anchor} onClose={() => setMenu(null)}>
          <MenuActions items={menu.items} onDone={() => setMenu(null)} end={false} />
        </RowPopMenu>
      )}
      <div className="sc-table-scroll" ref={scrollRef} data-testid="table-scroll" tabIndex={-1}
           onKeyDown={(e) => { if (!onSelectKey(e) && !onCopyKey(e) && gridOn) onGridKey(e); }} onPaste={gridOn ? onGridPaste : undefined}>
        <table className={`sc-table-grid${fit ? " sc-table-grid--fit" : ""}`} aria-rowcount={count + 1} aria-colcount={visible.length + extraCols}
               style={fit ? undefined : { width: `${visible.reduce((sum, c) => sum + width(c.field), (rowMenu ? ROW_MENU_REM : 0) + selRem)}rem` }}>
          {!fit && (
            <colgroup>
              {selRem > 0 && <col style={{ width: `${SELECT_REM}rem` }} />}
              {visible.map((c) => <col key={c.field} style={{ width: `${width(c.field)}rem` }} />)}
              {rowMenu && <col style={{ width: `${ROW_MENU_REM}rem` }} />}
            </colgroup>
          )}
          <thead>
            {table.getHeaderGroups().map((group) => (
              <tr key={group.id} aria-rowindex={1}>
                {selRem > 0 && (
                  <th scope="col" className="sc-table-check is-pinned" style={{ left: 0 }}>
                    <input type="checkbox" aria-label={T.selectAll} checked={allPicked} ref={(el) => { if (el) el.indeterminate = somePicked; }}
                           onChange={() => (picked.size ? setPicked(new Set()) : void selectAll())} />
                  </th>
                )}
                {group.headers.map((h) => {
                  const col = byField.get(h.column.id)!;
                  const i = s.order.indexOf(col.field);
                  const dir = h.column.getIsSorted();
                  const isFiltered = Boolean(filterOf(col.field));
                  const pin = pinnedCell(i);
                  const dropClass = drag?.over === col.field ? ` is-drop-${drag.side}` : "";
                  return (
                    <th key={h.id} scope="col" style={pin.style} draggable
                        className={[isNumeric(col) && !fieldHints?.[col.field]?.left ? "is-num" : "", pin.className, dropClass.trim()].filter(Boolean).join(" ") || undefined}
                        aria-sort={dir === "asc" ? "ascending" : dir === "desc" ? "descending" : undefined}
                        onDragStart={(e) => { e.dataTransfer?.setData("text/plain", col.field); setDrag({ field: col.field }); }}
                        onDragOver={(e) => dragOver(col.field, e)} onDrop={(e) => drop(col.field, e)}
                        onDragEnd={() => setDrag(null)}>
                      <div className="sc-table-head">
                        <button type="button" className="sc-table-sort" title={col.note ?? undefined}
                                onClick={h.column.getToggleSortingHandler()} onKeyDown={(e) => onHeaderKey(col.field, e)}>
                          <span className="sc-table-label">{col.label}</span>
                          {gridOn && cellEditing!.editableColumn(col) && <span className="sc-table-edit-mark" title={T.editableColumn} aria-label={T.editableColumn}>✎</span>}
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
                      {!fit && (
                        <ResizeHandle label={col.label} width={width(col.field)} remPx={fontSize}
                                      onWidth={(rem) => update((st) => ({ ...st, widths: { ...st.widths, [col.field]: rem } }))} />
                      )}
                    </th>
                  );
                })}
                {rowMenu && <th scope="col" className="sc-table-rowmenu" aria-label={T.rowActions} />}
              </tr>
            ))}
          </thead>
          <tbody>
            {status === "loading" && (
              <tr className="sc-table-state"><td colSpan={visible.length + extraCols}>{T.loading}</td></tr>
            )}
            {status === "ready" && filtered === 0 && (
              <tr className="sc-table-state">
                <td colSpan={visible.length + extraCols}>
                  {T.empty}
                  {s.filters.length > 0 && (
                    <> · <Button size="sm" variant="ghost" onClick={() => update((st) => ({ ...st, filters: [] }))}>{T.clearFilters}</Button></>
                  )}
                </td>
              </tr>
            )}
            {status !== "loading" && paddingTop > 0 && <tr aria-hidden="true" className="sc-table-spacer" style={{ height: paddingTop }} />}
            {status !== "loading" && items.map((it) => {
              if (!grouped) return renderRow(it.key, it.index, ordered ? ordered[it.index] : flat.row(it.index));
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
        <ExportDialog info={exportInfo} filtered={filtered} total={fixed.length ? filtered : total} visibleColumns={visible.length}
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

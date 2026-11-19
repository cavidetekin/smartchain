// Pivot ızgarası (K-183, docs/12 "Pivot standardı"): katlı sütun başlıkları, sabit satır başlıkları, sanal kaydırma. Satırlar sunucudan
// parça parça gelir (satır sınırı yok); toplam satırları da sunucunun satırlarıdır (kayıtlardan hesaplanmış). Sütun ekseni tek seferde gelir.
import { useVirtualizer } from "@tanstack/react-virtual";
import { Funnel } from "lucide-react";
import { type CSSProperties, type KeyboardEvent, type MouseEvent as ReactMouseEvent, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { tr } from "../i18n/tr";
import { formatStyle } from "./rules";
import { useShell } from "../shell/ShellContext";
import { Alert, Button } from "../ui";
import { type ChartSelection } from "../ui/chart/chartModel";
import { bucketLabel } from "../ui/chart/chartOption";
import { valueLabel as boolLabel } from "./filters";
import {
  formatPivotCell, PIVOT_VALUE_WIDTH, type PivotAxisInfo, type PivotCell, type PivotColumn, type PivotConfig, type PivotData, pivotReady, pivotRequest, type PivotRow,
  valueDisplay, valueName,
} from "./pivotModel";
import { listApi, type ListColumn, type ListFilter } from "./types";
import { clampWidth, MAX_WIDTH_REM, MIN_WIDTH_REM } from "./viewState";

const T = tr.pivot;
export const PIVOT_ROW_REM = 2.1538;      // tablonun satır yüksekliği
const HEAD_REM = 11;                       // satır başlık kolonu: en az; alan adı kesilmeyecek kadar genişler (K-186)
const VALUE_ROW_REM = 3.2308;              // değerler sütunlardayken son başlık satırı (iki satırlı değer adı)
const WIDTH_STEP_REM = 0.5;
const HEAD_EXTRA_REM = 3.6;                // başlıkta huni ve iç boşluk
const FIT_PAD_REM = 1.4;
const VALUE_HEAD_REM = 14;                 // "Değer" kolonu (değerler satırlarda): en az; uzun değer adında genişler
const MAX_VALUE_HEAD_REM = 26;
const CELL_REM = 8.4615;                   // değer hücresi
const MAX_CELL_REM = 18;
const HEADER_CHAR_REM = 0.56;
const DEBOUNCE_MS = 250;
const OVERSCAN = 10;

type Key = string | number | boolean | null;

/** Sunucunun reddettiği pivotun nedeni: genel mesajın yanında hangi alanın ya da ayarın geçersiz olduğu. */
export function reasonOf(e: ApiError): string {
  const problems = [...new Set(e.details.map((d) => (d as { problem?: string }).problem).filter((p): p is string => Boolean(p)))];
  return problems.length ? problems.join(" · ") : e.message;
}

function keyLabel(v: Key, info: PivotAxisInfo | undefined): string {
  if (v === null || v === undefined || v === "") return T.empty;
  if (info?.bucket) return bucketLabel(String(v), info.bucket);
  return typeof v === "boolean" ? boolLabel(v) : String(v);
}

/** En dıştaki sütun alanının her grubunun (ve sağdaki "Toplam" grubunun) ilk sütunu: solunda ince dikey ayraç çizilir. */
export function groupStarts(columns: PivotColumn[]): boolean[] {
  return columns.map((c, i) => {
    if (i === 0) return false;
    const previous = columns[i - 1];
    return c.level === 0 || previous.level === 0 || c.key[0] !== previous.key[0];
  });
}

/** Sütun, bu kattaki başlığıyla üst kattaki başlığın tek alt sütunu mu ve yazıları aynı mı (K-186): öyleyse üstteki hücreyle birleşir
 *  (ör. Ay › Dönem'de aylık dönem: "Ara 2026" altında yine "Ara 2026"). */
function mergedUp(columns: PivotColumn[], i: number, level: number, fields: PivotAxisInfo[]): boolean {
  const c = columns[i];
  if (level === 0 || c.level <= level || c.empty) return false;
  const sibling = (o: PivotColumn | undefined) => Boolean(o && o.level >= level && o.key.slice(0, level).every((v, j) => v === c.key[j]));
  if (sibling(columns[i - 1]) || sibling(columns[i + 1])) return false;
  return keyLabel(c.key[level], fields[level]) === keyLabel(c.key[level - 1], fields[level - 1]);
}

/** Satır alanı hücrelerinin birleşmesi (K-186): görüntü satırının `j`. satır alanındaki hücresinin grubu. Aynı gruptaki ardışık satırlar tek
 *  hücredir: aynı öneki (ilk j + 1 anahtar) paylaşan satırlar; ara toplam satırı dış düzeylerin grubundadır, adını taşıdığı kolon ve sağındakiler
 *  ile genel toplam satırın kendisine aittir (değerler satırlardayken satırın değer satırları boyunca yine birleşir). */
export function rowGroup(row: PivotRow, d: number, j: number): string {
  const inside = j < (row.total ? row.level - 1 : row.key.length);
  return inside ? `k${JSON.stringify(row.key.slice(0, j + 1))}` : `#${d}`;
}

/** Bir başlık katının hücreleri: aynı üst değeri paylaşan sütunlar birleşir; ara toplam sütunu kendi katında başlar ve alta kadar uzanır. */
export function headerCells(columns: PivotColumn[], level: number, depth: number, span: number, fields: PivotAxisInfo[]) {
  const out: { label: string; colSpan: number; rowSpan: number; total: boolean; key: string; start: boolean }[] = [];
  const starts = groupStarts(columns);
  let i = 0;
  while (i < columns.length) {
    const c = columns[i];
    if (c.level > level) {
      let n = 1;
      while (i + n < columns.length && columns[i + n].level > level && columns[i + n].key.slice(0, level + 1).every((v, j) => v === c.key[j])) n += 1;
      const blank = c.empty && level > 0;  // verisiz dönemin alt başlığı boş
      if (n === 1 && mergedUp(columns, i, level, fields)) { i += n; continue; }   // üstteki aynı yazılı başlıkla birleşti
      let down = 1;
      while (n === 1 && level + down < depth && mergedUp(columns, i, level + down, fields)) down += 1;
      out.push({ label: blank ? "" : keyLabel(c.key[level], fields[level]), colSpan: n * span, rowSpan: down, total: false, key: `${i}`, start: starts[i] });
      i += n;
    } else {
      if (c.level === level) out.push({ label: T.total, colSpan: span, rowSpan: depth - level, total: true, key: `${i}`, start: starts[i] });
      i += 1;
    }
  }
  return out;
}

/** Satır başlığı kolonunun genişlik tutamağı (K-186): sürükleme, ok tuşları, çift tıklayınca içeriğe sığdırma. */
function WidthHandle({ label, width, remPx, onWidth, onFit }: { label: string; width: number; remPx: number; onWidth(rem: number): void; onFit(): void }) {
  const onMouseDown = (e: ReactMouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const [x0, w0] = [e.clientX, width];
    const move = (ev: MouseEvent) => onWidth(clampWidth(w0 + (ev.clientX - x0) / remPx));
    const up = () => { document.removeEventListener("mousemove", move); document.removeEventListener("mouseup", up); };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  };
  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    onWidth(clampWidth(width + (e.key === "ArrowRight" ? WIDTH_STEP_REM : -WIDTH_STEP_REM)));
  };
  return (
    <div role="separator" aria-orientation="vertical" aria-label={tr.table.widthOf(label)} tabIndex={0} title={T.fitWidth}
         aria-valuenow={Math.round(width * 100) / 100} aria-valuemin={MIN_WIDTH_REM} aria-valuemax={MAX_WIDTH_REM}
         className="sc-table-resize" onMouseDown={onMouseDown} onKeyDown={onKeyDown} onClick={(e) => e.stopPropagation()}
         onDoubleClick={(e) => { e.stopPropagation(); onFit(); }} />
  );
}

export function PivotGrid({ list, columns, pivot, filters, selection, chunkSize, reloadKey, onFilter, isFiltered, onWidths, style }: {
  list: string;
  /** Bilinen kolonlar (etiket için). */
  columns: ListColumn[];
  pivot: PivotConfig;
  filters: ListFilter[];
  selection?: ChartSelection | null;
  chunkSize: number;
  reloadKey?: unknown;
  /** Başlıktaki huni: tablonun filtre penceresi. */
  onFilter(field: string, anchor: HTMLElement): void;
  isFiltered(field: string): boolean;
  /** Satır başlığı kolonunun genişliği değişti (görünümle saklanır). Verilmezse genişlik ayarlanamaz. */
  onWidths?(widths: Record<string, number>): void;
  style?: CSSProperties;
}) {
  const { scenario, fontSize } = useShell();
  const byField = useMemo(() => new Map(columns.map((c) => [c.field, c])), [columns]);
  const ready = pivotReady(pivot);
  const baseKey = useMemo(() => JSON.stringify(pivotRequest(pivot, filters, selection, scenario?.id, 0, chunkSize)),
    [pivot.rows, pivot.columns, pivot.values, pivot.totals, pivot.sort, filters, selection, scenario?.id, chunkSize]);
  const [meta, setMeta] = useState<PivotData | null>(null);
  const [chunks, setChunks] = useState<Map<number, PivotRow[]>>(new Map());
  const [error, setError] = useState<string | null>(null);
  const [shownKey, setShownKey] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const pending = useRef(new Set<number>());
  const generation = useRef(0);
  const first = useRef(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ready) return undefined;
    const ctrl = new AbortController();
    generation.current += 1;
    const gen = generation.current;
    const run = () => {
      listApi(list).pivot(JSON.parse(baseKey), ctrl.signal)
        .then((d) => {
          if (gen !== generation.current) return;
          pending.current = new Set();
          setMeta(d);
          setChunks(new Map([[0, d.rows]]));
          setError(null);
          setShownKey(baseKey);
          if (scrollRef.current) scrollRef.current.scrollTop = 0;
        })
        .catch((e: unknown) => {
          if (ctrl.signal.aborted) return;
          setError(e instanceof ApiError ? reasonOf(e) : T.failed);
          setShownKey(baseKey);
        });
    };
    const timer = window.setTimeout(run, first.current ? 0 : DEBOUNCE_MS);
    first.current = false;
    return () => { window.clearTimeout(timer); ctrl.abort(); };
  }, [list, baseKey, reloadKey, attempt, ready]);

  const loadChunk = (n: number) => {
    if (shownKey !== baseKey || chunks.has(n) || pending.current.has(n)) return;
    pending.current.add(n);
    const gen = generation.current;
    listApi(list).pivot({ ...JSON.parse(baseKey), offset: n * chunkSize })
      .then((d) => { if (gen === generation.current) setChunks((m) => new Map(m).set(n, d.rows)); })
      .catch(() => { pending.current.delete(n); });
  };

  const stale = shownKey !== baseKey;
  const data = error ? null : meta;
  const valuesOnRows = pivot.values_on === "rows";
  const V = data?.values.length ?? 0;
  const per = valuesOnRows ? Math.max(V, 1) : 1;
  const count = (data?.row_count ?? 0) * per;
  const rowPx = Math.round(fontSize * PIVOT_ROW_REM);
  const virtualizer = useVirtualizer({ count, getScrollElement: () => scrollRef.current, estimateSize: () => rowPx, overscan: OVERSCAN });
  useEffect(() => virtualizer.measure(), [rowPx, virtualizer]);
  const items = virtualizer.getVirtualItems();
  const firstIndex = items[0]?.index ?? 0;
  const lastIndex = items[items.length - 1]?.index ?? 0;
  useEffect(() => {
    if (!data || !count) return;
    const from = Math.floor(Math.floor(firstIndex / per) / chunkSize);
    const to = Math.floor(Math.floor(lastIndex / per) / chunkSize);
    for (let n = from; n <= to; n += 1) loadChunk(n);
  }, [firstIndex, lastIndex, data, count, per, chunkSize, shownKey]);

  if (!ready) return <div className="sc-pivot sc-pivot--empty" style={style}><p className="sc-muted">{T.setup}</p></div>;
  if (error) {
    return (
      <div className="sc-pivot sc-pivot--empty" style={style}>
        <Alert tone="risk">{error} <Button size="sm" onClick={() => setAttempt((n) => n + 1)}>{tr.table.retry}</Button></Alert>
      </div>
    );
  }
  if (!data) return <div className="sc-pivot sc-pivot--empty" style={style}><p className="sc-muted">{tr.table.loading}</p></div>;
  if (data.row_count === 0) return <div className="sc-pivot sc-pivot--empty" style={style}><p className="sc-muted">{T.noData}</p></div>;

  const R = data.row_fields.length;
  const C = data.column_fields.length;
  const leftCols = R + (valuesOnRows ? 1 : 0);
  const span = valuesOnRows ? 1 : V;
  const configured = data.values.map((v) => {
    const own = pivot.values.find((x) => x.id === v.id);
    return { field: v.field, weight: v.weight, fn: v.fn === "calc" ? "sum" as const : v.fn, kind: v.fn === "calc" ? "calc" as const : undefined, name: own?.name ?? null };
  });
  const labels = configured.map((v) => valueName(v, byField));
  const shown = configured.map((v) => valueDisplay(v, byField));
  const starts = groupStarts(data.columns);
  const overrides = data.values.map((v) => pivot.values.find((x) => x.id === v.id)?.decimals ?? null);
  // satırdaki `formats` istekte gönderilen (etkin) kuralların sırasını taşır
  const ruleFormats = data.values.map((v) => (pivot.values.find((x) => x.id === v.id)?.rules ?? []).filter((r) => r.enabled).map((r) => r.format));
  // Değerler sütunlardayken hücre, değerin adı kesilmeden sığacak kadar geniştir (üst sınırla)
  const cellRem = (k: number) => (valuesOnRows ? CELL_REM
    : Math.min(MAX_CELL_REM, Math.max(CELL_REM, Math.max(shown[k].top.length, shown[k].bottom?.length ?? 0) * HEADER_CHAR_REM + 1.6)));
  const groupRem = valuesOnRows ? CELL_REM : labels.reduce((sum, _, k) => sum + cellRem(k), 0);
  // değer adı kesilmesin: en uzun ada göre (dönem tablosunda "Verimlilik · Ağırlıklı ortalama (Toplam kapasite)" gibi adlar)
  const valueHeadRem = Math.min(MAX_VALUE_HEAD_REM, Math.max(VALUE_HEAD_REM, Math.max(0, ...labels.map((l) => l.length)) * HEADER_CHAR_REM + 1.6));
  const fieldLabel = (field: string) => byField.get(field)?.label ?? field;
  // Satır başlığı kolonları (K-186): ayarlanmış genişlik; yoksa alan adı (ve huni) kesilmeyecek kadar
  const headRem = data.row_fields.map((f) => pivot.widths?.[f.field] ?? clampWidth(Math.max(HEAD_REM, fieldLabel(f.field).length * HEADER_CHAR_REM + HEAD_EXTRA_REM)));
  const valueRem = pivot.widths?.[PIVOT_VALUE_WIDTH] ?? valueHeadRem;
  const leftRem = (j: number) => headRem.slice(0, j).reduce((sum, w) => sum + w, 0);
  const widthRem = leftRem(R) + (valuesOnRows ? valueRem : 0) + data.columns.length * groupRem;
  const setWidth = (key: string, rem: number) => onWidths?.({ ...(pivot.widths ?? {}), [key]: clampWidth(rem) });
  /** İçeriğe sığdır: başlık ve yüklü satırlardaki en uzun yazı (ölçülemiyorsa karakter sayısından). */
  const fit = (key: string, j: number | null) => {
    const texts = j === null ? [T.value, ...labels] : [fieldLabel(data.row_fields[j].field)];
    if (j !== null) {
      for (const rows of chunks.values()) {
        for (const r of rows) {
          if (r.total) {
            if (j === Math.max(r.level - 1, 0)) texts.push(r.level === 0 ? T.grandTotal : T.totalOf(keyLabel(r.key[r.level - 1], data.row_fields[r.level - 1])));
          } else if (j < r.key.length) texts.push(keyLabel(r.key[j], data.row_fields[j]));
        }
      }
    }
    const el = scrollRef.current;
    let ctx: CanvasRenderingContext2D | null = null;
    try { ctx = document.createElement("canvas").getContext("2d"); } catch { ctx = null; }
    if (ctx && el) ctx.font = getComputedStyle(el).font;
    const measure = (t: string) => (ctx && el ? ctx.measureText(t).width / fontSize : t.length * HEADER_CHAR_REM);
    const widest = Math.max(0, ...[...new Set(texts)].map(measure));
    const head = j === null ? 0 : measure(fieldLabel(data.row_fields[j].field)) + HEAD_EXTRA_REM;
    setWidth(key, Math.max(widest + FIT_PAD_REM, head));
  };
  const handle = (key: string, label: string, width: number, j: number | null) => onWidths && (
    <WidthHandle label={label} width={width} remPx={fontSize} onWidth={(rem) => setWidth(key, rem)} onFit={() => fit(key, j)} />
  );
  // Değerin satır biçimi (K-186): değerler satırlardayken satırına, sütunlardayken sütunlarına; kural tutan hücrede kural kazanır
  const rowFormats = data.values.map((v) => {
    const f = pivot.values.find((x) => x.id === v.id)?.format;
    return f && (f.fill || f.color || f.bold) ? formatStyle(f) : undefined;
  });
  const headerRem = C * PIVOT_ROW_REM + (valuesOnRows ? PIVOT_ROW_REM : VALUE_ROW_REM);   // yapışkan satır yazısının duracağı yer: başlığın altı
  const rowAt = (d: number): PivotRow | undefined => chunks.get(Math.floor(d / chunkSize))?.[d % chunkSize];
  const funnel = (field: string) => (
    <button type="button" className={`sc-table-filter-btn${isFiltered(field) ? " is-active" : ""}`} aria-label={tr.table.filterOf(fieldLabel(field))}
            aria-pressed={isFiltered(field)} aria-haspopup="dialog" onClick={(e) => onFilter(field, e.currentTarget)}>
      <Funnel aria-hidden="true" />
    </button>
  );
  const top = (level: number): CSSProperties => ({ top: `${level * PIVOT_ROW_REM}rem` });
  const before = items.length ? items[0].start : 0;
  const after = items.length ? virtualizer.getTotalSize() - items[items.length - 1].end : 0;
  const totalCols = leftCols + data.columns.length * span;

  const cell = (row: PivotRow, k: number, s: number, c: PivotColumn) => {
    const value: PivotCell = row.cells[k]?.[s] ?? null;
    const mixed = typeof value === "object" && value !== null && "mixed" in value;
    const hit = row.formats?.[String(k)]?.[s];
    const format = hit == null ? undefined : ruleFormats[k]?.[hit];
    const own = rowFormats[k];
    return (
      <td key={`${s}-${k}`} className={`sc-num${row.total || c.total ? " is-total" : ""}${mixed ? " is-mixed" : ""}${starts[s] && (valuesOnRows || k === 0) ? " is-group-start" : ""}${format ? " is-ruled" : ""}${own ? " is-formatted" : ""}`}
          title={mixed ? tr.table.mixedUnits : undefined} style={format || own ? { ...own, ...(format ? formatStyle(format) : {}) } : undefined}>
        {formatPivotCell(value, data.values[k], overrides[k])}
      </td>
    );
  };

  return (
    <div className={`sc-pivot${stale ? " is-stale" : ""}`} style={style} ref={scrollRef} data-testid="pivot-scroll" tabIndex={-1}>
      <table className="sc-pivot-grid" style={{ width: `${widthRem}rem` }} aria-rowcount={count} aria-label={T.pivot}>
        <colgroup>
          {data.row_fields.map((f, j) => <col key={f.field} style={{ width: `${headRem[j]}rem` }} />)}
          {valuesOnRows && <col style={{ width: `${valueRem}rem` }} />}
          {data.columns.flatMap((_, s) => Array.from({ length: span }, (__, k) => <col key={`${s}-${k}`} style={{ width: `${cellRem(k)}rem` }} />))}
        </colgroup>
        <thead>
          {data.column_fields.map((f, level) => (
            <tr key={f.field}>
              <th className="sc-pivot-corner is-pinned" colSpan={leftCols} style={{ left: 0, ...top(level) }}>
                <div className="sc-pivot-corner-field"><span title={fieldLabel(f.field)}>{fieldLabel(f.field)}</span>{funnel(f.field)}</div>
              </th>
              {headerCells(data.columns, level, C, span, data.column_fields).map((h) => (
                <th key={h.key} scope="colgroup" colSpan={h.colSpan} rowSpan={h.rowSpan} className={`sc-pivot-col${h.total ? " is-total" : ""}${h.start ? " is-group-start" : ""}`}
                    style={top(level)} title={h.label}>{h.label}</th>
              ))}
            </tr>
          ))}
          <tr>
            {data.row_fields.map((f, j) => (
              <th key={f.field} scope="col" className="sc-pivot-rowhead is-pinned" style={{ left: `${leftRem(j)}rem`, ...top(C) }}>
                <div className="sc-pivot-corner-field"><span title={fieldLabel(f.field)}>{fieldLabel(f.field)}</span>{funnel(f.field)}</div>
                {handle(f.field, fieldLabel(f.field), headRem[j], j)}
              </th>
            ))}
            {valuesOnRows && (
              <th scope="col" aria-label={T.value} className="sc-pivot-rowhead is-pinned is-pinned-last" style={{ left: `${leftRem(R)}rem`, ...top(C) }}>
                <span className="sc-pivot-rowhead-text">{T.value}</span>
                {handle(PIVOT_VALUE_WIDTH, T.value, valueRem, null)}
              </th>
            )}
            {data.columns.flatMap((c, s) => (valuesOnRows
              ? [<th key={s} className={`sc-pivot-col${c.total ? " is-total" : ""}${starts[s] ? " is-group-start" : ""}`} style={top(C)} />]
              : shown.map((name, k) => (
                <th key={`${s}-${k}`} scope="col" aria-label={labels[k]} title={name.full}
                    className={`sc-pivot-col sc-pivot-value${c.total ? " is-total" : ""}${starts[s] && k === 0 ? " is-group-start" : ""}`} style={top(C)}>
                  <span className="sc-pivot-value-top">{name.top}</span>
                  {name.bottom !== null && <span className="sc-pivot-calc">{name.bottom}</span>}
                </th>
              ))))}
          </tr>
        </thead>
        <tbody>
          {before > 0 && <tr aria-hidden="true"><td colSpan={totalCols} style={{ height: before, padding: 0, border: 0 }} /></tr>}
          {items.map((it, p) => {
            const d = Math.floor(it.index / per);
            const k = it.index % per;
            const row = rowAt(d);
            if (!row) {
              return <tr key={it.index} aria-rowindex={it.index + 1} style={{ height: rowPx }}><td colSpan={totalCols} className="sc-pivot-wait" /></tr>;
            }
            // ekrandaki (sanal) satırlar içinde hücrenin grubu: üstteki satır aynı gruptaysa hücre çizilmez, ilk satırdaki hücre grubu boyunca uzanır
            const groupAt = (q: number, j: number): string | null => {
              const other = items[q];
              if (!other) return null;
              const od = Math.floor(other.index / per);
              const orow = rowAt(od);
              return orow ? rowGroup(orow, od, j) : null;
            };
            const previous = d > 0 ? rowAt(d - 1) : undefined;
            // en dıştaki satır grubunun başı (K-186): gruplar arasında ince yatay çizgi; grup yoksa (tek alan, değerler sütunlarda) çizgi yok
            const outer = (r: PivotRow) => (r.total && r.level === 0 ? "#" : JSON.stringify(r.key[0]));   // ara toplam grubunun içindedir; genel toplam ayrı
            const outerStart = (R > 1 || valuesOnRows) && k === 0 && d > 0 && (!previous || outer(previous) !== outer(row));
            return (
              <tr key={it.index} aria-rowindex={it.index + 1} className={`${row.total ? "is-total" : ""}${outerStart ? " is-row-group-start" : ""}`.trim() || undefined}
                  style={{ height: rowPx }}>
                {data.row_fields.map((f, j) => {
                  const group = rowGroup(row, d, j);
                  if (p > 0 && groupAt(p - 1, j) === group) return null;   // üstteki hücrenin devamı
                  let rows = 1;
                  while (groupAt(p + rows, j) === group) rows += 1;
                  let text = "";
                  if (row.total) {
                    if (j === Math.max(row.level - 1, 0)) text = row.level === 0 ? T.grandTotal : T.totalOf(keyLabel(row.key[row.level - 1], data.row_fields[row.level - 1]));
                    else if (j < row.level - 1) text = keyLabel(row.key[j], f);
                  } else {
                    text = keyLabel(row.key[j], f);
                  }
                  return (
                    <th key={f.field} scope="row" rowSpan={rows > 1 ? rows : undefined}
                        className={`sc-pivot-rowkey is-pinned${!valuesOnRows && j === R - 1 ? " is-pinned-last" : ""}`}
                        style={{ left: `${leftRem(j)}rem` }} title={text || undefined}>
                      <span className="sc-pivot-rowkey-text" style={{ top: `${headerRem}rem` }}>{text}</span>
                    </th>
                  );
                })}
                {valuesOnRows && (
                  <th scope="row" className={`sc-pivot-rowkey sc-pivot-value is-pinned is-pinned-last${rowFormats[k] ? " is-formatted" : ""}`}
                      style={{ left: `${leftRem(R)}rem`, ...rowFormats[k] }} title={labels[k]}>
                    <span className="sc-pivot-rowkey-text">{labels[k]}</span>
                  </th>
                )}
                {data.columns.flatMap((c, s) => (valuesOnRows ? [cell(row, k, s, c)] : data.values.map((_, kk) => cell(row, kk, s, c))))}
              </tr>
            );
          })}
          {after > 0 && <tr aria-hidden="true"><td colSpan={totalCols} style={{ height: after, padding: 0, border: 0 }} /></tr>}
        </tbody>
      </table>
    </div>
  );
}

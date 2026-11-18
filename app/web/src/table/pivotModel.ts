// Pivot (K-183, docs/12 "Pivot standardı"): satırlar × sütunlar × değerler. Ayarlar görünümle saklanır (`pivot`); hesap sunucuda
// (`POST /api/<liste>/pivot`), satırlar parça parça gelir. Saf işlevler: varsayılanlar, uyarlama, istek, etiket ve biçim.
import { formatDate, formatDateTime, formatNumber, formatPercent } from "../format";
import { tr } from "../i18n/tr";
import type { ChartBucket, ChartSelection } from "../ui/chart/chartModel";
import type { ColumnType, ListColumn, ListFilter } from "./types";

export type PivotFn = "sum" | "avg" | "min" | "max" | "count" | "distinct" | "wavg";
export const PIVOT_FNS: PivotFn[] = ["sum", "avg", "min", "max", "count", "distinct", "wavg"];
export const PIVOT_MAX_AXIS = 3;
export const PIVOT_MAX_VALUES = 8;
export const PIVOT_MAX_DISTINCT = 3;

export interface PivotAxis { field: string; bucket?: ChartBucket | null }
export interface PivotValue {
  id: string;
  /** "Say"da alan yok. */
  field?: string | null;
  fn: PivotFn;
  /** Ağırlıklı ortalamanın ağırlık alanı. */
  weight?: string | null;
  /** Gösterim ondalığı; boşsa alanın (miktarda birimin) ondalığı. */
  decimals?: number | null;
}
export interface PivotTotals { rows: boolean; columns: boolean; subtotals: boolean }
export interface PivotSort { by: string; dir: "asc" | "desc" }
export interface PivotConfig {
  v: 1;
  open: boolean;
  rows: PivotAxis[];
  columns: PivotAxis[];
  values: PivotValue[];
  values_on: "columns" | "rows";
  totals: PivotTotals;
  sort: PivotSort;
}

/** Hücre: sayı, boş, birimi karışık, biriminin ondalığıyla sayı ya da tarih (En erken · En geç; ISO metin). */
export type PivotCell = number | string | null | { mixed: true } | { v: number; d: number };
export interface PivotColumn { key: (string | number | boolean | null)[]; level: number; total: boolean; empty?: boolean }
export interface PivotRow { key: (string | number | boolean | null)[]; level: number; total: boolean; cells: PivotCell[][] }
export interface PivotAxisInfo { field: string; type: ColumnType; bucket: ChartBucket | null }
export interface PivotValueInfo {
  id: string; fn: PivotFn; field: string | null; weight: string | null; decimals: number; percent: boolean; from_unit: boolean;
  /** Sonucun tipi: sayı; tarih alanında En erken · En geç için tarih. */
  type?: "number" | "date" | "datetime";
}
export interface PivotData {
  row_fields: PivotAxisInfo[];
  column_fields: PivotAxisInfo[];
  columns: PivotColumn[];
  values: PivotValueInfo[];
  rows: PivotRow[];
  offset: number;
  row_count: number;
  week_start: string;
}
export interface PivotRequest {
  filters: ListFilter[];
  chart_selection?: ChartSelection;
  rows: PivotAxis[];
  columns: PivotAxis[];
  values: { id: string; field?: string | null; fn: PivotFn; weight?: string | null }[];
  totals: PivotTotals;
  sort: PivotSort;
  scenario_id?: number;
  offset: number;
  limit: number;
}

const DATE: ColumnType[] = ["date", "datetime"];
const NUMERIC: ColumnType[] = ["number", "integer"];
export const isDate = (c: ListColumn | undefined) => Boolean(c && DATE.includes(c.type));
export const isNumeric = (c: ListColumn | undefined) => Boolean(c && NUMERIC.includes(c.type));
/** Satır ve sütun alanı: kategori ya da tarih; ondalıklı sayı olamaz. */
export const isAxisField = (c: ListColumn) => c.type !== "number";

export const emptyPivot = (): PivotConfig => ({
  v: 1, open: true, rows: [], columns: [], values: [], values_on: "columns", totals: { rows: false, columns: false, subtotals: false },
  sort: { by: "name", dir: "asc" },
});

/** Kayıtlı içerik: eksik anahtarlar varsayılanla. */
export function normalizePivot(raw: Partial<PivotConfig> | null | undefined): PivotConfig | null {
  if (!raw) return null;
  const base = emptyPivot();
  return {
    v: 1, open: raw.open ?? true,
    rows: (raw.rows ?? []).map((a) => ({ field: a.field, bucket: a.bucket ?? null })),
    columns: (raw.columns ?? []).map((a) => ({ field: a.field, bucket: a.bucket ?? null })),
    values: (raw.values ?? []).map((v) => ({ id: v.id, field: v.field ?? null, fn: v.fn ?? "sum", weight: v.weight ?? null, decimals: v.decimals ?? null })),
    values_on: raw.values_on ?? "columns",
    totals: { ...base.totals, ...(raw.totals ?? {}) },
    sort: { ...base.sort, ...(raw.sort ?? {}) },
  };
}

/** Bugünkü kolonlara uydurur: alanı olmayan satır, sütun ve değer atılır. */
export function fitPivot(pivot: PivotConfig | null, columns: ListColumn[]): PivotConfig | null {
  if (!pivot) return null;
  const known = new Set(columns.map((c) => c.field));
  const values = pivot.values.filter((v) => (!v.field || known.has(v.field)) && (!v.weight || known.has(v.weight)));
  return {
    ...pivot, rows: pivot.rows.filter((a) => known.has(a.field)), columns: pivot.columns.filter((a) => known.has(a.field)), values,
    sort: pivot.sort.by === "name" || values.some((v) => v.id === pivot.sort.by) ? pivot.sort : { by: "name", dir: "asc" },
  };
}

/** Çizilebilir mi: en az bir satır alanı ve bir değer; değerler tam. */
export const pivotReady = (p: PivotConfig) =>
  p.rows.length > 0 && p.values.length > 0 && p.values.every((v) => v.fn === "count" || (v.field && (v.fn !== "wavg" || v.weight)));

export function nextValueId(values: PivotValue[]): string {
  const used = new Set(values.map((v) => v.id));
  for (let i = 1; ; i += 1) if (!used.has(`d${i}`)) return `d${i}`;
}

/** Eklenen alanın ilk hesaplaması: sayıda Toplam, tarihte En erken, öteki alanda Benzersiz say. */
export const defaultFn = (c: ListColumn): PivotFn => (isNumeric(c) ? "sum" : isDate(c) ? "min" : "distinct");
/** Alana uyan hesaplamalar: sayıda hepsi; tarihte En erken · En geç · Say · Benzersiz say; metinde Say · Benzersiz say. */
export const fnsFor = (c: ListColumn | undefined): PivotFn[] =>
  (!c ? ["count"] : isNumeric(c) ? PIVOT_FNS : isDate(c) ? ["min", "max", "count", "distinct"] : ["count", "distinct"]);
/** Hesaplamanın adı: tarih alanında "En düşük · En yüksek" yerine "En erken · En geç". */
export const fnLabel = (fn: PivotFn, c: ListColumn | undefined): string =>
  (isDate(c) && (fn === "min" || fn === "max") ? tr.pivot.fnDate[fn] : tr.pivot.fn[fn]);

/** Değerin iki parçası: alan ve hesaplama ("Say"da alan yok; ağırlıklı ortalamada ağırlık alanı parantezde). */
export function valueParts(v: Pick<PivotValue, "field" | "fn" | "weight">, byField: Map<string, ListColumn>): { field: string | null; calc: string } {
  if (v.fn === "count") return { field: null, calc: tr.pivot.fn.count };
  const col = byField.get(v.field ?? "");
  const calc = v.fn === "wavg" ? `${tr.pivot.fn.wavg} (${byField.get(v.weight ?? "")?.label ?? v.weight ?? ""})` : fnLabel(v.fn, col);
  return { field: col?.label ?? v.field ?? "", calc };
}

export function pivotRequest(p: PivotConfig, filters: ListFilter[], selection: ChartSelection | null | undefined, scenarioId: number | undefined,
                             offset: number, limit: number): PivotRequest {
  const weekly = [...p.rows, ...p.columns].some((a) => a.bucket === "week");
  return {
    filters, ...(selection ? { chart_selection: selection } : {}),
    rows: p.rows.map((a) => ({ field: a.field, ...(a.bucket ? { bucket: a.bucket } : {}) })),
    columns: p.columns.map((a) => ({ field: a.field, ...(a.bucket ? { bucket: a.bucket } : {}) })),
    values: p.values.map((v) => ({ id: v.id, fn: v.fn, ...(v.fn === "count" ? {} : { field: v.field }), ...(v.fn === "wavg" ? { weight: v.weight } : {}) })),
    totals: p.totals, sort: p.sort, ...(weekly && scenarioId ? { scenario_id: scenarioId } : {}), offset, limit,
  };
}

/** Değerin adı: "Alan · Hesaplama"; ağırlıklı ortalamada "(ağırlık alanı)"; "Say" alansız. */
export function valueLabel(v: Pick<PivotValue, "field" | "fn" | "weight">, byField: Map<string, ListColumn>): string {
  const { field, calc } = valueParts(v, byField);
  return field === null ? calc : `${field} · ${calc}`;
}

const RATIO: PivotFn[] = ["avg", "wavg"];

/** Hücrenin yazısı: boş hücre boş; sonuç 0 ise "0". Ondalık: ayar, yoksa birimin ya da alanın ondalığı; ortalamalarda bir fazla. */
export function formatPivotCell(cell: PivotCell, info: PivotValueInfo, override: number | null | undefined): string {
  if (cell === null || cell === undefined) return "";
  if (typeof cell === "object" && "mixed" in cell) return "—";
  if (typeof cell === "string") {  // En erken · En geç
    if (info.type === "datetime") return formatDateTime(new Date(cell));
    const [y, m, d] = cell.slice(0, 10).split("-").map(Number);
    return formatDate(new Date(y, m - 1, d));
  }
  const value = typeof cell === "number" ? cell : cell.v;
  const base = typeof cell === "number" ? info.decimals : cell.d;
  const digits = override ?? (base + (RATIO.includes(info.fn) ? 1 : 0));
  return info.percent ? formatPercent(value, digits) : formatNumber(value, digits);
}

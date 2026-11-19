// Pivot (K-183, docs/12 "Pivot standardı"): satırlar × sütunlar × değerler. Ayarlar görünümle saklanır (`pivot`); hesap sunucuda
// (`POST /api/<liste>/pivot`), satırlar parça parça gelir. Saf işlevler: varsayılanlar, uyarlama, istek, etiket ve biçim.
import { formatDate, formatDateTime, formatNumber, formatPercent } from "../format";
import { tr } from "../i18n/tr";
import type { ChartBucket, ChartSelection } from "../ui/chart/chartModel";
import type { ColumnType, ListColumn, ListFilter, RuleCondition, RuleFormat } from "./types";

export type PivotFn = "sum" | "avg" | "min" | "max" | "count" | "distinct" | "wavg" | "first" | "last";
/** İlk · Son dönem değeri (K-184): yalnız dönem tablosunda; zaman içinde ilk (son) dönemin değeri, kayıtlar arasında toplanır. */
export const PERIOD_FNS: PivotFn[] = ["first", "last"];
export const PIVOT_FNS: PivotFn[] = ["sum", "avg", "min", "max", "count", "distinct", "wavg"];
export const PIVOT_MAX_AXIS = 3;
export const PIVOT_MAX_VALUES = 8;
export const PIVOT_MAX_DISTINCT = 3;

export const PIVOT_MAX_RULES = 5;
export type PivotOp = "div" | "mul" | "add" | "sub";
export const PIVOT_OPS: PivotOp[] = ["div", "mul", "add", "sub"];
/** Değerin koşullu biçim kuralı: pivot hücresindeki hesaplanmış değere bakar (yalnız sayı koşulları). */
export interface PivotRule { id: string; enabled: boolean; condition: RuleCondition; format: RuleFormat }
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
  /** Kullanıcının verdiği ad (ör. "Sipariş sayısı"); boşsa otomatik ad. Başlıkta, panelde ve sıralama listesinde kullanılır. */
  name?: string | null;
  /** Hesaplanan değer (toplamlardan): a op b; a ve b pivotun alan değerlerinin kimlikleri. */
  kind?: "field" | "calc";
  a?: string | null;
  op?: PivotOp | null;
  b?: string | null;
  /** Hesaplanan değerde yüzde gösterim. */
  percent?: boolean;
  rules?: PivotRule[];
  /** Kurallar toplam satır ve sütunlarına da uygulanır (varsayılan kapalı). */
  rules_on_totals?: boolean;
  /** Değerin satır biçimi (K-186): zemin, yazı rengi, kalın. Değerler satırlardayken satırına, sütunlardayken sütunlarına uygulanır. */
  format?: PivotRowFormat;
}
export type PivotRowFormat = Pick<RuleFormat, "fill" | "color" | "bold">;
/** "Değer" kolonunun genişlik anahtarı (değerler satırlardayken). */
export const PIVOT_VALUE_WIDTH = "__value";
/** Boş biçim saklanmaz: yalnız dolu özellikler; hiçbiri yoksa undefined. */
export function cleanRowFormat(f: PivotRowFormat | null | undefined): PivotRowFormat | undefined {
  const out: PivotRowFormat = { ...(f?.fill ? { fill: f.fill } : {}), ...(f?.color ? { color: f.color } : {}), ...(f?.bold ? { bold: true } : {}) };
  return Object.keys(out).length ? out : undefined;
}
export const isCalc = (v: Pick<PivotValue, "kind">) => v.kind === "calc";
/** Hesaplanan değerin işleneni olabilir mi: alan değeri ve sonucu sayı (tarihte En erken · En geç olamaz). */
export const isOperand = (v: PivotValue, byField: Map<string, ListColumn>) =>
  !isCalc(v) && !(isDate(byField.get(v.field ?? "")) && (v.fn === "min" || v.fn === "max"));
/** Değere kural konabilir mi: sonucu sayı olan her değer. */
export const canRule = (v: PivotValue, byField: Map<string, ListColumn>) => isCalc(v) || isOperand(v, byField);
/** İşleneni kalmayan ya da işleneni artık sayı vermeyen hesaplanan değerler düşer; sıralama da ada döner. */
export function dropOrphans(p: PivotConfig, byField: Map<string, ListColumn>): PivotConfig {
  const ok = new Set(p.values.filter((v) => isOperand(v, byField)).map((v) => v.id));
  const values = p.values.filter((v) => !isCalc(v) || (ok.has(v.a ?? "") && ok.has(v.b ?? "")));
  if (values.length === p.values.length) return p;
  return { ...p, values, sort: values.some((v) => v.id === p.sort.by) || p.sort.by === "name" ? p.sort : { by: "name", dir: "asc" } };
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
  /** Satır başlığı kolonlarının genişliği (rem; K-186): satır alanı → genişlik; "Değer" kolonu `PIVOT_VALUE_WIDTH`. Yalnız gösterim. */
  widths?: Record<string, number>;
}

/** Hücre: sayı, boş, birimi karışık, biriminin ondalığıyla sayı ya da tarih (En erken · En geç; ISO metin). */
export type PivotCell = number | string | null | { mixed: true } | { v: number; d: number };
export interface PivotColumn { key: (string | number | boolean | null)[]; level: number; total: boolean; empty?: boolean }
export interface PivotRow {
  key: (string | number | boolean | null)[]; level: number; total: boolean; cells: PivotCell[][];
  /** Kuralı tutan hücreler: değer sırası → sütun sırasına göre (etkin) kuralın sırası ya da null. */
  formats?: Record<string, (number | null)[]>;
}
export interface PivotAxisInfo { field: string; type: ColumnType; bucket: ChartBucket | null }
export interface PivotValueInfo {
  id: string; fn: PivotFn | "calc"; field: string | null; weight: string | null; decimals: number; percent: boolean; from_unit: boolean;
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
  values: { id: string; kind?: "calc"; field?: string | null; fn?: PivotFn; weight?: string | null; a?: string | null; op?: PivotOp | null; b?: string | null;
            percent?: boolean; rules?: PivotRule[]; rules_on_totals?: boolean }[];
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
/** Pivotun bütün seçicilerinin (satır, sütun, değer) tek kuralı: "Manuel değer" kolonu ve sistem alanları sunulmaz (sunucunun `pivot` işareti). */
export const isPivotField = (c: ListColumn) => c.pivot !== false;
/** Satır ve sütun alanı: kategori ya da tarih; ondalıklı sayı olamaz. */
export const isAxisField = (c: ListColumn) => isPivotField(c) && c.type !== "number";

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
    values: (raw.values ?? []).map((v) => ({
      id: v.id, field: v.field ?? null, fn: v.fn ?? "sum", weight: v.weight ?? null, decimals: v.decimals ?? null, name: v.name?.trim() ? v.name.trim() : null,
      ...(v.kind === "calc" ? { kind: "calc" as const, a: v.a ?? null, op: v.op ?? "div", b: v.b ?? null, percent: Boolean(v.percent) } : {}),
      ...(v.rules?.length ? { rules: v.rules } : {}), ...(v.rules_on_totals ? { rules_on_totals: true } : {}),
      ...(cleanRowFormat(v.format) ? { format: cleanRowFormat(v.format) } : {}),
    })),
    values_on: raw.values_on ?? "columns",
    totals: { ...base.totals, ...(raw.totals ?? {}) },
    sort: { ...base.sort, ...(raw.sort ?? {}) },
    ...(raw.widths && Object.keys(raw.widths).length ? { widths: { ...raw.widths } } : {}),
  };
}

/** Bugünkü kolonlara uydurur: alanı olmayan satır, sütun ve değer atılır. */
export function fitPivot(pivot: PivotConfig | null, columns: ListColumn[]): PivotConfig | null {
  if (!pivot) return null;
  const known = new Set(columns.map((c) => c.field));
  const fields = pivot.values.filter((v) => !isCalc(v) && (!v.field || known.has(v.field)) && (!v.weight || known.has(v.weight)));
  const ids = new Set(fields.map((v) => v.id));
  // hesaplanan değer işlenenleriyle yaşar: biri giderse o da gider
  const values = pivot.values.filter((v) => (isCalc(v) ? ids.has(v.a ?? "") && ids.has(v.b ?? "") : ids.has(v.id)));
  const { widths, ...rest } = pivot;
  const kept = Object.fromEntries(Object.entries(widths ?? {}).filter(([f]) => f === PIVOT_VALUE_WIDTH || known.has(f)));
  return {
    ...rest, rows: pivot.rows.filter((a) => known.has(a.field)), columns: pivot.columns.filter((a) => known.has(a.field)), values,
    sort: pivot.sort.by === "name" || values.some((v) => v.id === pivot.sort.by) ? pivot.sort : { by: "name", dir: "asc" },
    ...(Object.keys(kept).length ? { widths: kept } : {}),
  };
}

/** Çizilebilir mi: en az bir satır alanı ve bir değer; değerler tam. */
export const pivotReady = (p: PivotConfig) =>
  p.rows.length > 0 && p.values.length > 0
  && p.values.every((v) => (isCalc(v) ? Boolean(v.a && v.b && v.op) : v.fn === "count" || (v.field && (v.fn !== "wavg" || v.weight))));

export function nextValueId(values: PivotValue[]): string {
  const used = new Set(values.map((v) => v.id));
  for (let i = 1; ; i += 1) if (!used.has(`d${i}`)) return `d${i}`;
}

/** Eklenen alanın ilk hesaplaması: liste tanımındaki varsayılan (K-183); yoksa sayıda Toplam, tarihte En erken, öteki alanda Benzersiz say. */
export function defaultFn(c: ListColumn): PivotFn {
  if (isNumeric(c)) {
    const a = c.aggregate;
    if (a === "sum" || a === "avg" || a === "min" || a === "max") return a;
    if (a === "avg_nonzero") return "avg";
    if (a === "wavg" && c.aggregate_weight) return "wavg";
    if (a === "first" || a === "last") return a;
    return "sum";
  }
  return isDate(c) ? "min" : "distinct";
}
/** Alana uyan hesaplamalar: sayıda hepsi; tarihte En erken · En geç · Say · Benzersiz say; metinde Say · Benzersiz say. */
export const fnsFor = (c: ListColumn | undefined, periodTable = false): PivotFn[] =>
  (!c ? ["count"] : isNumeric(c) ? (periodTable ? [...PIVOT_FNS, ...PERIOD_FNS] : PIVOT_FNS) : isDate(c) ? ["min", "max", "count", "distinct"] : ["count", "distinct"]);
/** Hesaplamanın adı: tarih alanında "En düşük · En yüksek" yerine "En erken · En geç". */
export const fnLabel = (fn: PivotFn, c: ListColumn | undefined): string =>
  (isDate(c) && (fn === "min" || fn === "max") ? tr.pivot.fnDate[fn] : tr.pivot.fn[fn]);

/** Değerin iki parçası: alan ve hesaplama ("Say"da alan yok; ağırlıklı ortalamada ağırlık alanı parantezde). */
export function valueParts(v: Pick<PivotValue, "field" | "fn" | "weight" | "kind" | "name">, byField: Map<string, ListColumn>): { field: string | null; calc: string } {
  if (v.kind === "calc") return { field: v.name?.trim() || tr.pivot.calcName, calc: tr.pivot.fromTotals };   // hesap yolu etikette: "Ad · Toplamlardan"
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
    values: p.values.map((v) => ({
      id: v.id,
      ...(isCalc(v) ? { kind: "calc" as const, a: v.a, op: v.op, b: v.b, percent: Boolean(v.percent) }
        : { fn: v.fn, ...(v.fn === "count" ? {} : { field: v.field }), ...(v.fn === "wavg" ? { weight: v.weight } : {}) }),
      ...(v.rules?.some((r) => r.enabled) ? { rules: v.rules.filter((r) => r.enabled), ...(v.rules_on_totals ? { rules_on_totals: true } : {}) } : {}),
    })),
    totals: p.totals, sort: p.sort, ...(weekly && scenarioId ? { scenario_id: scenarioId } : {}), offset, limit,
  };
}

/** Değerin adı: "Alan · Hesaplama"; ağırlıklı ortalamada "(ağırlık alanı)"; "Say" alansız. */
export function valueLabel(v: Pick<PivotValue, "field" | "fn" | "weight" | "kind" | "name">, byField: Map<string, ListColumn>): string {
  const { field, calc } = valueParts(v, byField);
  return field === null ? calc : `${field} · ${calc}`;
}

/** Değerin gösterimi: iki satır. Özel ad varsa tek satır o addır (otomatik ad ipucunda); yoksa üstte alan, altta hesaplama. */
export function valueDisplay(v: Pick<PivotValue, "field" | "fn" | "weight" | "name" | "kind">, byField: Map<string, ListColumn>): { top: string; bottom: string | null; full: string } {
  const full = valueLabel(v, byField);
  if (v.name?.trim() && v.kind !== "calc") return { top: v.name.trim(), bottom: null, full };
  const { field, calc } = valueParts(v, byField);
  return field === null ? { top: calc, bottom: null, full } : { top: field, bottom: calc, full };
}

/** Değerin tek satırlık adı (sıralama listesi, "Değer" kolonu): özel ad ya da otomatik ad. */
export const valueName = (v: Pick<PivotValue, "field" | "fn" | "weight" | "name" | "kind">, byField: Map<string, ListColumn>): string =>
  (v.name?.trim() && v.kind !== "calc" ? v.name.trim() : valueLabel(v, byField));

/** Excel'e aktarım isteği: pivot isteği (parçasız), değerlerin yeri, ekrandaki değer adları ve ondalık ayarları. */
export function pivotExportRequest(p: PivotConfig, filters: ListFilter[], selection: ChartSelection | null | undefined, scenarioId: number | undefined,
                                   byField: Map<string, ListColumn>) {
  const { offset: _o, limit: _l, values, ...rest } = pivotRequest(p, filters, selection, scenarioId, 0, 1);
  return {
    ...rest, values_on: p.values_on,
    values: values.map((v, i) => ({ ...v, ...(p.values[i].decimals != null ? { decimals: p.values[i].decimals } : {}), ...(p.values[i].name ? { name: p.values[i].name } : {}),
                                    ...(cleanRowFormat(p.values[i].format) ? { format: cleanRowFormat(p.values[i].format) } : {}) })),
    ...(p.widths && Object.keys(p.widths).length ? { widths: p.widths } : {}),
    names: Object.fromEntries(p.values.map((v) => [v.id, valueName(v, byField)])),
  };
}

const RATIO: string[] = ["avg", "wavg"];

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

// Grafik ayar modeli (K-178, docs/12 "Grafik standardı"): görünümdeki `chart` anahtarıyla birebir (docs/08). Saf işlevler: varsayılanlar, ilk açılış
// kuralı, alan seçenekleri, sunucu isteği. Çizim kütüphanesinden bağımsızdır.
import type { ColumnType, ListColumn, ListFilter } from "../../table/types";

export type ChartBucket = "day" | "week" | "month" | "quarter" | "year";   // saat kırılımı yok
export type ChartFn = "sum" | "avg" | "min" | "max" | "count";
export type SeriesType = "bar" | "line" | "smooth" | "step" | "area";   // smooth: eğimli (monoton) çizgi
export type AxisSide = "primary" | "secondary";
export type BarMode = "group" | "stack" | "percent";
export type RefKind = "value" | "avg" | "min" | "max";
export type LegendPosition = "top" | "bottom" | "right";
export type TitleAlign = "left" | "center" | "right";
export type TitleSize = "small" | "medium" | "large";
export type BarWidth = "thin" | "medium" | "thick";

export interface ChartSeries {
  id: string;
  /** "count" (satır sayısı) alan istemez. */
  field: string | null;
  fn: ChartFn;
  type: SeriesType;
  axis: AxisSide;
  /** Boşsa paletten sırayla. */
  color: string | null;
  /** zero: "Sıfır değerleri göster"; kapalıyken 0 değerinin etiketi çıkmaz. */
  labels: { show: boolean; decimals: number; zero: boolean };
  /** line: "Eşik çizgisini göster"; kapalıyken yalnız eşik üstü renk uygulanır. */
  threshold: { value: number; color: string; line: boolean } | null;
}

export interface ValueAxis { title: string; min: number | null; max: number | null; unit: string; grid: boolean }
export interface RefLine { id: string; kind: RefKind; value: number | null; series: string | null; name: string; color: string | null; show_name: boolean; show_value: boolean }

export interface ChartConfig {
  v: 1;
  open: boolean;
  layout: "split" | "full";
  /** Bölünmüş görünümde grafiğin payı (0,15–0,85). */
  height: number;
  x: { field: string; bucket: ChartBucket | null };
  split: string | null;
  order: "value" | "name";
  /** Kategori ekseninde gösterilecek değer sayısı (en büyükler; kalanı "Diğer"). */
  limit: number;
  series: ChartSeries[];
  /** totals: yığılmışta çubuğun üstünde toplam. width: çubuk genişliği, bütün çubuk serileri için ortak. */
  bars: { mode: BarMode; horizontal: boolean; totals: boolean; width: BarWidth };
  axes: { x: { title: string }; primary: ValueAxis; secondary: ValueAxis };
  ref_lines: RefLine[];
  legend: { show: boolean; position: LegendPosition };
  title: string;
  title_align: TitleAlign;
  title_size: TitleSize;
}

/** Sunucunun cevabı (`POST /api/<liste>/chart`). */
export interface ChartKey { key: string | number | boolean | null; label: string | null }
export interface ChartData {
  x: { kind: "date" | "category"; bucket: ChartBucket | null; values: ChartKey[]; other: boolean };
  split: { field: string; values: ChartKey[]; other: boolean } | null;
  /** data: kırılım × yatay eksen; birim karışıksa null. */
  series: { id: string; data: (number | null)[][] | null; mixed_units: boolean }[];
  rows: number;
  week_start: string;
}

export const OTHER_KEY = "__other__";
export const MAX_SERIES = 8;
export const MAX_REF_LINES = 6;
export const MIN_HEIGHT = 0.15;
export const MAX_HEIGHT = 0.85;
export const DEFAULT_HEIGHT = 0.45;
export const BUCKETS: ChartBucket[] = ["day", "week", "month", "quarter", "year"];
export const FNS: ChartFn[] = ["sum", "avg", "min", "max", "count"];
export const SERIES_TYPES: SeriesType[] = ["bar", "line", "smooth", "step", "area"];
export const MAX_CATEGORIES = 30;
export const CATEGORY_LIMITS = [5, 10, 15, 20, 30];

const DATE_TYPES: ColumnType[] = ["date", "datetime"];
const CATEGORY_TYPES: ColumnType[] = ["text", "bool", "integer"];
const NUMERIC_TYPES: ColumnType[] = ["number", "integer"];

export const isDateField = (c: ListColumn | undefined) => Boolean(c && DATE_TYPES.includes(c.type));
export const isNumericField = (c: ListColumn | undefined) => Boolean(c && NUMERIC_TYPES.includes(c.type));
/** Yatay eksen olabilen alanlar: tarih (dönemle) ve kategori. */
export const xFields = (columns: ListColumn[]) => columns.filter((c) => DATE_TYPES.includes(c.type) || CATEGORY_TYPES.includes(c.type));
export const splitFields = (columns: ListColumn[], x: string) => columns.filter((c) => CATEGORY_TYPES.includes(c.type) && c.field !== x);
export const numericFields = (columns: ListColumn[]) => columns.filter((c) => NUMERIC_TYPES.includes(c.type));

export const clampHeight = (ratio: number) => Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, Math.round(ratio * 1000) / 1000));

const valueAxis = (grid: boolean): ValueAxis => ({ title: "", min: null, max: null, unit: "", grid });

export function newSeries(id: string, field: string | null, fn: ChartFn, type: SeriesType = "bar"): ChartSeries {
  return { id, field, fn, type, axis: "primary", color: null, labels: { show: false, decimals: 0, zero: false }, threshold: null };
}

/** Kullanılmayan kısa kimlik: s1, s2… (r1… referans çizgisi). */
export function nextId(prefix: string, used: string[]): string {
  for (let i = 1; ; i++) if (!used.includes(`${prefix}${i}`)) return `${prefix}${i}`;
}

/** İlk açılış (K-178): grafik boş gelmez. Yatay eksen görünür ilk tarih alanı (dönem Ay), yoksa görünür ilk kategori alanı; seri görünür ilk
 *  sayısal alanın toplamı, çubuk; sayısal alan yoksa adet. Görünür alanlarda yoksa listenin bütün alanlarına bakılır. Çizilecek eksen yoksa null. */
export function defaultChart(columns: ListColumn[], order: string[]): ChartConfig | null {
  const byField = new Map(columns.map((c) => [c.field, c]));
  const visible = order.map((f) => byField.get(f)).filter((c): c is ListColumn => Boolean(c));
  const isCategory = (c: ListColumn) => c.type === "text" || c.type === "bool";
  const axis = (from: ListColumn[]) => from.find(isDateField) ?? from.find(isCategory) ?? from.find((c) => c.type === "integer");
  const x = axis(visible) ?? axis(columns);  // önce görünür alanlar (tarih, yoksa kategori); hiçbiri yoksa listenin öteki alanları
  if (!x) return null;
  const number = (from: ListColumn[]) => from.find((c) => c.type === "number") ?? from.find((c) => c.type === "integer" && c.field !== x.field);
  const value = number(visible) ?? number(columns);
  return {
    v: 1, open: true, layout: "split", height: DEFAULT_HEIGHT,
    x: { field: x.field, bucket: isDateField(x) ? "month" : null }, split: null, order: "value", limit: MAX_CATEGORIES,
    series: [value ? newSeries("s1", value.field, "sum") : newSeries("s1", null, "count")],
    bars: { mode: "group", horizontal: false, totals: false, width: "medium" },
    axes: { x: { title: "" }, primary: valueAxis(true), secondary: valueAxis(false) },
    ref_lines: [], legend: { show: true, position: "top" }, title: "", title_align: "left", title_size: "medium",
  };
}

/** Kayıtlı içerik tam biçime getirilir (eksik anahtarlar varsayılanla); karşılaştırma ve çizim hep bu biçimle. */
export function normalizeChart(raw: Partial<ChartConfig> & Pick<ChartConfig, "x" | "series">): ChartConfig {
  const axis = (a: Partial<ValueAxis> | undefined, grid: boolean): ValueAxis => ({
    title: a?.title ?? "", min: a?.min ?? null, max: a?.max ?? null, unit: a?.unit ?? "", grid: a?.grid ?? grid });
  return {
    v: 1, open: raw.open ?? true, layout: raw.layout === "full" ? "full" : "split", height: clampHeight(raw.height ?? DEFAULT_HEIGHT),
    x: { field: raw.x.field, bucket: raw.x.bucket ?? null }, split: raw.split ?? null, order: raw.order === "name" ? "name" : "value",
    limit: Math.min(MAX_CATEGORIES, Math.max(1, raw.limit ?? MAX_CATEGORIES)),
    series: raw.series.map((s) => ({
      id: s.id, field: s.field ?? null, fn: s.fn, type: s.type ?? "bar", axis: s.axis ?? "primary", color: s.color ?? null,
      labels: { show: s.labels?.show ?? false, decimals: s.labels?.decimals ?? 0, zero: s.labels?.zero ?? false },
      threshold: s.threshold ? { value: s.threshold.value, color: s.threshold.color, line: s.threshold.line ?? false } : null })),
    bars: { mode: raw.bars?.mode ?? "group", horizontal: raw.bars?.horizontal ?? false, totals: raw.bars?.totals ?? false, width: raw.bars?.width ?? "medium" },
    axes: { x: { title: raw.axes?.x?.title ?? "" }, primary: axis(raw.axes?.primary, true), secondary: axis(raw.axes?.secondary, false) },
    ref_lines: (raw.ref_lines ?? []).map((r) => ({ id: r.id, kind: r.kind, value: r.value ?? null, series: r.series ?? null, name: r.name ?? "", color: r.color ?? null,
                                                    show_name: r.show_name ?? true, show_value: r.show_value ?? true })),
    legend: { show: raw.legend?.show ?? true, position: raw.legend?.position ?? "top" },
    title: raw.title ?? "", title_align: raw.title_align ?? "left", title_size: raw.title_size ?? "medium",
  };
}

/** Listede artık olmayan alanlara bağlı parçalar atılır (sunucu da açılışta aynısını yapar); çizilecek bir şey kalmazsa null. */
export function fitChart(chart: ChartConfig, columns: ListColumn[]): ChartConfig | null {
  const known = new Set(columns.map((c) => c.field));
  if (!known.has(chart.x.field)) return null;
  const series = chart.series.filter((s) => s.fn === "count" || (s.field !== null && known.has(s.field)));
  if (!series.length) return null;
  const ids = new Set(series.map((s) => s.id));
  return { ...chart, series, split: chart.split && known.has(chart.split) ? chart.split : null,
           ref_lines: chart.ref_lines.filter((r) => r.kind === "value" || (r.series !== null && ids.has(r.series))) };
}

export interface ChartRequest {
  filters: ListFilter[];
  x: { field: string; bucket: ChartBucket | null };
  split: string | null;
  order: "value" | "name";
  series: { id: string; field: string | null; fn: ChartFn }[];
  limit: number;
  scenario_id?: number;
}

/** Sunucu isteği: yalnız veriyi değiştiren ayarlar (tip, renk, etiket, eksen sınırı gibi görünüş ayarları istek atmaz). */
export function chartRequest(chart: ChartConfig, filters: ListFilter[], scenarioId?: number): ChartRequest {
  return {
    filters, x: chart.x, split: chart.split, order: chart.order,
    series: chart.series.map((s) => ({ id: s.id, field: s.fn === "count" ? null : s.field, fn: s.fn })),
    limit: chart.limit,
    ...(scenarioId !== undefined && chart.x.bucket === "week" ? { scenario_id: scenarioId } : {}),
  };
}

/** Yatay eksen alanı değişince dönem alanın tipine uyar: tarihte dönem (varsayılan Ay), kategoride yok; kırılım eksenle aynı kalamaz. */
export function withXField(chart: ChartConfig, col: ListColumn): ChartConfig {
  return { ...chart, x: { field: col.field, bucket: isDateField(col) ? chart.x.bucket ?? "month" : null },
           split: chart.split === col.field ? null : chart.split };
}

/** Toplama değişince alan uyar: "adet" alansızdır; ötekilerde sayısal alan gerekir. */
export function withSeriesFn(s: ChartSeries, fn: ChartFn, columns: ListColumn[]): ChartSeries {
  if (fn === "count") return { ...s, fn, field: null };
  const field = s.field ?? numericFields(columns)[0]?.field ?? null;
  return field === null ? s : { ...s, fn, field };
}

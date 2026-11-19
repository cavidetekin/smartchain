// Grafik ayar modeli (K-178, docs/12 "Grafik standardı"): görünümdeki `chart` anahtarıyla birebir (docs/08). Saf işlevler: varsayılanlar, ilk açılış
// kuralı, alan seçenekleri, sunucu isteği. Çizim kütüphanesinden bağımsızdır.
import type { ColumnType, ListColumn, ListFilter } from "../../table/types";

export type ChartBucket = "day" | "week" | "month" | "quarter" | "year";   // saat kırılımı yok
/** count: "Say" (satır sayısı; alan istemez). distinct: "Benzersiz say" (alandaki farklı değer sayısı; listenin bütün alanları; K-179). */
export type ChartFn = "sum" | "avg" | "min" | "max" | "count" | "distinct";
export type LineStyle = "solid" | "dashed";
export type SeriesType = "bar" | "line" | "smooth" | "step" | "area";   // smooth: eğimli (monoton) çizgi
export type AxisSide = "primary" | "secondary";
export type BarMode = "group" | "stack" | "percent";
export type RefKind = "value" | "avg" | "min" | "max";
export type LegendPosition = "top" | "bottom" | "right";
export type TitleAlign = "left" | "center" | "right";
export type TitleSize = "small" | "medium" | "large";
export type BarWidth = "thin" | "medium" | "thick";
/** Grafik türü (K-179): çubuk ve çizgi, pasta, halka, dağılım. */
export type ChartKind = "xy" | "pie" | "donut" | "scatter";
export type PieLabel = "value" | "percent" | "none";
export type FacetScale = "shared" | "own";
/** Dağılım: iki sayısal alan, satır başına nokta; isteğe bağlı renk kırılımı. point_color: renk kırılımı yokken noktaların rengi (boşsa paletten). */
export interface ScatterConfig { x: string; y: string; color: string | null; point_color: string | null }

export interface ChartSeries {
  id: string;
  /** "count" (satır sayısı) alan istemez. */
  field: string | null;
  fn: ChartFn;
  type: SeriesType;
  /** Çizgi biçimi (K-179): çizgi ve alan tiplerinde. */
  line: LineStyle;
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
  kind: ChartKind;
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
  /** x.zoom: yakınlaştırma kaydırıcısı (yalnız zaman ekseninde; konumu saklanmaz). */
  axes: { x: { title: string; zoom: boolean }; primary: ValueAxis; secondary: ValueAxis };
  ref_lines: RefLine[];
  legend: { show: boolean; position: LegendPosition };
  title: string;
  title_align: TitleAlign;
  title_size: TitleSize;
  /** Küçük grafiklere böl (K-179): kategori alanı; en büyük 12 değer + "Diğer". */
  facet: string | null;
  facet_scale: FacetScale;
  pie: { label: PieLabel };
  scatter: ScatterConfig | null;
}

/** Sunucunun cevabı (`POST /api/<liste>/chart`). */
export interface ChartKey { key: string | number | boolean | null; label: string | null }
export interface ChartData {
  x: { kind: "date" | "category"; bucket: ChartBucket | null; values: ChartKey[]; other: boolean };
  split: { field: string; values: ChartKey[]; other: boolean } | null;
  /** Küçük grafikler (K-179); yoksa null. */
  facets?: { field: string; values: ChartKey[]; other: boolean } | null;
  /** data: kırılım × yatay eksen (küçük grafik varsa küçük grafik × kırılım × yatay eksen); birim karışıksa null. */
  series: { id: string; data: (number | null)[][] | (number | null)[][][] | null; mixed_units: boolean }[];
  rows: number;
  week_start: string;
}

/** Dağılımın noktaları (`POST /api/<liste>/chart/points`): [x, y, renk sırası, kayıt adı]. */
export interface PointsData {
  points: [number, number, number, string | null][];
  colors: { field: string; values: ChartKey[]; other: boolean } | null;
  /** rows: eşleşen kayıt; shown: gösterilen nokta (sınır aşılırsa eşit aralıklı örnekleme). */
  rows: number;
  shown: number;
  mixed_units: { x: boolean; y: boolean };
  label_field: string | null;
}
export interface PointsRequest { filters: ListFilter[]; x: string; y: string; color: string | null; limit: number }
export const MAX_POINTS = 2000;
export const KINDS: ChartKind[] = ["xy", "pie", "donut", "scatter"];

export const OTHER_KEY = "__other__";
export const MAX_SERIES = 8;
export const MAX_REF_LINES = 6;
export const MIN_HEIGHT = 0.15;
export const MAX_HEIGHT = 0.85;
export const DEFAULT_HEIGHT = 0.45;
export const BUCKETS: ChartBucket[] = ["day", "week", "month", "quarter", "year"];
export const FNS: ChartFn[] = ["sum", "avg", "min", "max", "count", "distinct"];
export const MAX_DISTINCT = 3;
export const MAX_SELECTION = 200;
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
/** Küçük grafiklere bölen alanlar: kategori; yatay eksen ve kırılım dışında. */
export const facetFields = (columns: ListColumn[], x: string, split: string | null) => columns.filter((c) => CATEGORY_TYPES.includes(c.type) && c.field !== x && c.field !== split);
export const colorFields = (columns: ListColumn[]) => columns.filter((c) => CATEGORY_TYPES.includes(c.type));
export const isPie = (chart: Pick<ChartConfig, "kind">) => chart.kind === "pie" || chart.kind === "donut";
export const numericFields = (columns: ListColumn[]) => columns.filter((c) => NUMERIC_TYPES.includes(c.type));

export const clampHeight = (ratio: number) => Math.min(MAX_HEIGHT, Math.max(MIN_HEIGHT, Math.round(ratio * 1000) / 1000));

const valueAxis = (grid: boolean): ValueAxis => ({ title: "", min: null, max: null, unit: "", grid });

export function newSeries(id: string, field: string | null, fn: ChartFn, type: SeriesType = "bar"): ChartSeries {
  return { id, field, fn, type, line: "solid", axis: "primary", color: null, labels: { show: false, decimals: 0, zero: false }, threshold: null };
}

/** Kullanılmayan kısa kimlik: s1, s2… (r1… referans çizgisi). */
export function nextId(prefix: string, used: string[]): string {
  for (let i = 1; ; i++) if (!used.includes(`${prefix}${i}`)) return `${prefix}${i}`;
}

/** İlk açılış (K-178): grafik boş gelmez. Yatay eksen görünür ilk tarih alanı (dönem Ay), yoksa görünür ilk kategori alanı; seri görünür ilk
 *  sayısal alanın toplamı (liste tanımı alanı verdiyse o), çubuk; sayısal alan yoksa adet. Görünür alanlarda yoksa listenin bütün alanlarına bakılır. Çizilecek eksen yoksa null. */
export function defaultChart(columns: ListColumn[], order: string[], preferred?: string): ChartConfig | null {
  const byField = new Map(columns.map((c) => [c.field, c]));
  const visible = order.map((f) => byField.get(f)).filter((c): c is ListColumn => Boolean(c));
  const isCategory = (c: ListColumn) => c.type === "text" || c.type === "bool";
  const axis = (from: ListColumn[]) => from.find(isDateField) ?? from.find(isCategory) ?? from.find((c) => c.type === "integer");
  const x = axis(visible) ?? axis(columns);  // önce görünür alanlar (tarih, yoksa kategori); hiçbiri yoksa listenin öteki alanları
  if (!x) return null;
  const number = (from: ListColumn[]) => from.find((c) => c.type === "number") ?? from.find((c) => c.type === "integer" && c.field !== x.field);
  // liste tanımı grafiğin ilk değer alanını verebilir (K-186; ör. Kapasite özeti'nde Kullanılabilir kapasite)
  const value = (preferred ? columns.find((c) => c.field === preferred && NUMERIC_TYPES.includes(c.type)) : undefined) ?? number(visible) ?? number(columns);
  return {
    v: 1, open: true, kind: "xy", layout: "split", height: DEFAULT_HEIGHT,
    x: { field: x.field, bucket: isDateField(x) ? "month" : null }, split: null, order: "value", limit: MAX_CATEGORIES,
    series: [value ? newSeries("s1", value.field, "sum") : newSeries("s1", null, "count")],
    bars: { mode: "group", horizontal: false, totals: false, width: "medium" },
    axes: { x: { title: "", zoom: false }, primary: valueAxis(true), secondary: valueAxis(false) },
    ref_lines: [], legend: { show: true, position: "top" }, title: "", title_align: "left", title_size: "medium",
    facet: null, facet_scale: "shared", pie: { label: "percent" }, scatter: null,
  };
}

/** Kayıtlı içerik tam biçime getirilir (eksik anahtarlar varsayılanla); karşılaştırma ve çizim hep bu biçimle. */
export function normalizeChart(raw: Partial<ChartConfig> & Pick<ChartConfig, "x" | "series">): ChartConfig {
  const axis = (a: Partial<ValueAxis> | undefined, grid: boolean): ValueAxis => ({
    title: a?.title ?? "", min: a?.min ?? null, max: a?.max ?? null, unit: a?.unit ?? "", grid: a?.grid ?? grid });
  return {
    v: 1, open: raw.open ?? true, kind: KINDS.includes(raw.kind as ChartKind) && (raw.kind !== "scatter" || raw.scatter) ? raw.kind as ChartKind : "xy",
    layout: raw.layout === "full" ? "full" : "split", height: clampHeight(raw.height ?? DEFAULT_HEIGHT),
    x: { field: raw.x.field, bucket: raw.x.bucket ?? null }, split: raw.split ?? null, order: raw.order === "name" ? "name" : "value",
    limit: Math.min(MAX_CATEGORIES, Math.max(1, raw.limit ?? MAX_CATEGORIES)),
    series: raw.series.map((s) => ({
      id: s.id, field: s.field ?? null, fn: s.fn, type: s.type ?? "bar", line: s.line === "dashed" ? "dashed" : "solid", axis: s.axis ?? "primary", color: s.color ?? null,
      labels: { show: s.labels?.show ?? false, decimals: s.labels?.decimals ?? 0, zero: s.labels?.zero ?? false },
      threshold: s.threshold ? { value: s.threshold.value, color: s.threshold.color, line: s.threshold.line ?? false } : null })),
    bars: { mode: raw.bars?.mode ?? "group", horizontal: raw.bars?.horizontal ?? false, totals: raw.bars?.totals ?? false, width: raw.bars?.width ?? "medium" },
    axes: { x: { title: raw.axes?.x?.title ?? "", zoom: raw.axes?.x?.zoom ?? false }, primary: axis(raw.axes?.primary, true), secondary: axis(raw.axes?.secondary, false) },
    ref_lines: (raw.ref_lines ?? []).map((r) => ({ id: r.id, kind: r.kind, value: r.value ?? null, series: r.series ?? null, name: r.name ?? "", color: r.color ?? null,
                                                    show_name: r.show_name ?? true, show_value: r.show_value ?? true })),
    legend: { show: raw.legend?.show ?? true, position: raw.legend?.position ?? "top" },
    title: raw.title ?? "", title_align: raw.title_align ?? "left", title_size: raw.title_size ?? "medium",
    facet: raw.facet ?? null, facet_scale: raw.facet_scale === "own" ? "own" : "shared", pie: { label: raw.pie?.label ?? "percent" },
    scatter: raw.scatter ? { x: raw.scatter.x, y: raw.scatter.y, color: raw.scatter.color ?? null, point_color: raw.scatter.point_color ?? null } : null,
  };
}

/** Listede artık olmayan alanlara bağlı parçalar atılır (sunucu da açılışta aynısını yapar); çizilecek bir şey kalmazsa null. */
export function fitChart(chart: ChartConfig, columns: ListColumn[]): ChartConfig | null {
  const known = new Set(columns.map((c) => c.field));
  if (!known.has(chart.x.field)) return null;
  const series = chart.series.filter((s) => s.fn === "count" || (s.field !== null && known.has(s.field)));
  if (!series.length) return null;
  const ids = new Set(series.map((s) => s.id));
  const sc = chart.scatter && known.has(chart.scatter.x) && known.has(chart.scatter.y)
    ? { ...chart.scatter, color: chart.scatter.color && known.has(chart.scatter.color) ? chart.scatter.color : null } : null;
  return { ...chart, series, split: chart.split && known.has(chart.split) ? chart.split : null,
           facet: chart.facet && known.has(chart.facet) ? chart.facet : null, scatter: sc, kind: chart.kind === "scatter" && !sc ? "xy" : chart.kind,
           ref_lines: chart.ref_lines.filter((r) => r.kind === "value" || (r.series !== null && ids.has(r.series))) };
}

export interface ChartRequest {
  filters: ListFilter[];
  x: { field: string; bucket: ChartBucket | null };
  split: string | null;
  order: "value" | "name";
  series: { id: string; field: string | null; fn: ChartFn }[];
  limit: number;
  /** İniş (K-179): yalnız bu dönem(ler)in satırları. */
  within?: { bucket: ChartBucket; keys: string[] }[];
  /** Küçük grafiklere böl (K-179). */
  facet?: string;
  scenario_id?: number;
}

/** Grafikte seçilen öğe (K-179): yatay eksen değeri (dönemin ilk günü ya da kategori; null boş), kırılım varsa parça, küçük grafik varsa değeri. */
export interface PickItem { x: string | number | boolean | null; p?: string | number | boolean | null; f?: string | number | boolean | null }
/** İniş adımı: `bucket` düzeyindeki `keys` dönem(ler)inin içine, `to` dönemiyle inildi (birden fazla dönem seçiliyken de inilir). */
export interface DrillStep { bucket: ChartBucket; keys: string[]; to: ChartBucket }
/** Grafik seçimi ve iniş: geçicidir, görünüme kaydedilmez. */
export interface ChartPick { items: PickItem[]; drill: DrillStep[] }
export const NO_PICK: ChartPick = { items: [], drill: [] };
export const hasPick = (pick: ChartPick) => pick.items.length > 0 || pick.drill.length > 0;
export const samePick = (a: PickItem, b: PickItem) => a.x === b.x && (a.p ?? null) === (b.p ?? null) && (a.f ?? null) === (b.f ?? null);

/** Bulunulan dönemden ince dönemler (iniş; ara düzey atlanabilir): Yıl → Çeyrek → Ay → Hafta → Gün. */
export function finerBuckets(bucket: ChartBucket | null): ChartBucket[] {
  const order: ChartBucket[] = ["year", "quarter", "month", "week", "day"];
  return bucket ? order.slice(order.indexOf(bucket) + 1) : [];
}

/** İnişle geçerli dönem: son iniş adımının dönemi; iniş yoksa görünümün kayıtlı dönemi. */
export const effectiveBucket = (chart: ChartConfig, pick: ChartPick): ChartBucket | null =>
  (pick.drill.length ? pick.drill[pick.drill.length - 1].to : chart.x.bucket);

/** Tablo sorgularına eklenen grafik seçimi (docs/08 `chart_selection`); seçim ve iniş yoksa undefined. */
export interface ChartSelection {
  x: { field: string; bucket: ChartBucket | null };
  split: string | null;
  facet?: string;
  items: PickItem[];
  within: { bucket: ChartBucket; keys: string[] }[];
  scenario_id?: number;
}
export function chartSelection(chart: ChartConfig | null, pick: ChartPick, scenarioId?: number): ChartSelection | undefined {
  if (!chart || !chart.open || chart.kind === "scatter" || !hasPick(pick)) return undefined;
  const bucket = effectiveBucket(chart, pick);
  const weekly = bucket === "week" || pick.drill.some((d) => d.bucket === "week");
  const split = isPie(chart) ? null : chart.split;  // pasta ve halkada kırılım kullanılmaz
  return {
    x: { field: chart.x.field, bucket }, split, ...(chart.facet ? { facet: chart.facet } : {}),
    items: pick.items.map((i) => ({ x: i.x, ...(split ? { p: i.p ?? null } : {}), ...(chart.facet ? { f: i.f ?? null } : {}) })),
    within: pick.drill.map((d) => ({ bucket: d.bucket, keys: d.keys })),
    ...(scenarioId !== undefined && weekly ? { scenario_id: scenarioId } : {}),
  };
}

/** Sunucu isteği: yalnız veriyi değiştiren ayarlar (tip, renk, etiket, eksen sınırı gibi görünüş ayarları istek atmaz). */
export function chartRequest(chart: ChartConfig, filters: ListFilter[], scenarioId?: number, drill: DrillStep[] = []): ChartRequest {
  const bucket = drill.length ? drill[drill.length - 1].to : chart.x.bucket;
  const weekly = bucket === "week" || drill.some((d) => d.bucket === "week");
  const pie = isPie(chart);
  return {
    filters, x: { field: chart.x.field, bucket }, split: pie ? null : chart.split, order: chart.order,
    series: (pie ? chart.series.slice(0, 1) : chart.series).map((s) => ({ id: s.id, field: s.fn === "count" ? null : s.field, fn: s.fn })),  // pasta yalnız ilk seriyi çizer
    limit: chart.limit,
    ...(drill.length ? { within: drill.map((d) => ({ bucket: d.bucket, keys: d.keys })) } : {}),
    ...(chart.facet ? { facet: chart.facet } : {}),
    ...(scenarioId !== undefined && weekly ? { scenario_id: scenarioId } : {}),
  };
}

/** Yatay eksen alanı değişince dönem alanın tipine uyar: tarihte dönem (varsayılan Ay), kategoride yok; kırılım eksenle aynı kalamaz. */
export function withXField(chart: ChartConfig, col: ListColumn): ChartConfig {
  return { ...chart, x: { field: col.field, bucket: isDateField(col) ? chart.x.bucket ?? "month" : null },
           split: chart.split === col.field ? null : chart.split, facet: chart.facet === col.field ? null : chart.facet,
           kind: isDateField(col) && isPie(chart) ? "xy" : chart.kind };  // pasta ve halka yalnız kategori ekseninde
}

/** Dağılım isteği: iki sayısal alan ve (varsa) renk kırılımı; tablonun filtresiyle. */
export function pointsRequest(chart: ChartConfig, filters: ListFilter[]): PointsRequest {
  const sc = chart.scatter!;
  return { filters, x: sc.x, y: sc.y, color: sc.color, limit: MAX_POINTS };
}

/** Tür değişince ayar uyar: dağılımda iki sayısal alan seçilir (yoksa tür değişmez); pasta ve halka tarih ekseninde seçilemez. */
export function withKind(chart: ChartConfig, kind: ChartKind, columns: ListColumn[]): ChartConfig {
  if (kind === "scatter") {
    const all = numericFields(columns);
    const numeric = [...all.filter((c) => c.type === "number"), ...all.filter((c) => c.type !== "number")];  // önce ölçü alanları (ondalıklı), sonra tam sayılar
    if (!numeric.length) return chart;
    return { ...chart, kind, scatter: chart.scatter ?? { x: numeric[0].field, y: (numeric[1] ?? numeric[0]).field, color: null, point_color: null } };
  }
  if ((kind === "pie" || kind === "donut") && chart.x.bucket !== null) return chart;
  return { ...chart, kind };
}

/** Hesaplama değişince alan uyar: "Say" alansızdır; "Benzersiz say" her alanda çalışır; ötekilerde sayısal alan gerekir. */
export function withSeriesFn(s: ChartSeries, fn: ChartFn, columns: ListColumn[]): ChartSeries {
  if (fn === "count") return { ...s, fn, field: null };
  if (fn === "distinct") {
    const field = s.field ?? columns[0]?.field ?? null;
    return field === null ? s : { ...s, fn, field };
  }
  const numeric = numericFields(columns);
  const field = numeric.some((c) => c.field === s.field) ? s.field : numeric[0]?.field ?? null;
  return field === null ? s : { ...s, fn, field };
}

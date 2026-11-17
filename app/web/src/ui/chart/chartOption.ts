// Ayar + veri → çizim seçenekleri (K-178, K-179; docs/12 "Grafik standardı"). Saf işlev: grafiğin bütün kuralları burada (renk sırası, eksen, etiket,
// ipucu, gösterge, eşik, referans çizgisi, köşe yuvarlağı, küçük grafik ızgarası, pasta ve halka, dağılım); kütüphane yalnız çizer. Sayı ve tarihler
// Türkçe, rakamlar Inter. Saat hiçbir yerde yazılmaz.
import { formatDate, formatNumber } from "../../format";
import { tr } from "../../i18n/tr";
import type { ListColumn } from "../../table/types";
import { suggestText } from "../contrast";
import { tokenColor } from "../palette";
import {
  type AxisSide, type ChartBucket, type ChartConfig, type ChartData, type ChartKey, type ChartSeries, OTHER_KEY, type PickItem, type PointsData, samePick,
} from "./chartModel";

const T = tr.chart;

/** Seri renk sırası (U-5, K-85): indigo, petrol, hardal, kurşun, erik, kahve; sonra aynı sıranın açık tonları. Kırmızı ve kiremit yok. */
export const PALETTE: string[] = Array.from({ length: 12 }, (_, i) => tokenColor(`chart-${i + 1}`));
/** Eşik üstü rengin varsayılanı: açık kiremit (durum anlamı). */
export const THRESHOLD_COLOR = tokenColor("status-over-bg");
export const NUM_FONT = "Inter, system-ui, sans-serif";
export const TEXT_FONT = '"Instrument Sans", system-ui, sans-serif';
const TEXT = tokenColor("lead-600");
const STRONG = tokenColor("lead-900");
const LINE = tokenColor("lead-300");
const GRID = tokenColor("lead-100");
/** Görselin zemini (PNG dışa aktarımı) ve etiket kenarlığı. */
export const SURFACE = tokenColor("surface");
const BAND = tokenColor("lead-50");  // üstüne gelinen dönemin bandı: çok açık gri
const RADIUS = 3;  // çubuğun üst köşesi (px)
const ZOOM_FILL = tokenColor("indigo-100");  // kaydırıcıda seçili aralık
const ZOOM_SIZE = 24;  // kaydırıcının kalınlığı (px): içindeki veri silueti seçilecek kadar belirgin
const DIM = 0.35;  // seçim varken seçilmeyenlerin saydamlığı (K-179)
const TITLE_SCALE = { small: 1, medium: 1.15, large: 1.4 } as const;
/** Çubuk genişliği (K-178): kategori aralığında bırakılan boşluk ve üst sınır (yazı boyutunun katı). Genişlik kategori sayısıyla ölçeklenir; kademe oranı belirler. */
export const BAR_WIDTH = { thin: { gap: "55%", max: 5 }, medium: { gap: "34%", max: 8 }, thick: { gap: "16%", max: 12 } } as const;
/** Ölçü bilinmiyorsa (ilk çizim, test) varsayılan grafik kutusu (px). */
const DEFAULT_BOX = { width: 900, height: 400 };
/** Küçük grafiğin en küçük yüksekliği (px; başlığıyla). */
const FACET_MIN = { xy: 165, pie: 185 };
/** Küçük grafiğin kutusu (K-179): iç boşluk, kutular arası boşluk ve köşe yuvarlağı (px). */
const FACET_BOX = { pad: 8, gapX: 12, gapY: 12, radius: 6 };

const esc = (text: string) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const isoDate = (key: string) => { const [y, m, d] = key.split("-").map(Number); return new Date(y, m - 1, d); };

/** Hafta numarası: haftanın dördüncü gününün ISO haftası (hafta Pazartesi başlıyorsa ISO ile aynı; başka günde de kararlı). */
function weekNo(start: Date): { week: number; year: number } {
  const t = new Date(Date.UTC(start.getFullYear(), start.getMonth(), start.getDate() + 3));  // UTC: yaz saati gün sayısını kaydırmasın
  t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));                                    // o günün ISO haftasının Perşembesi
  const year = t.getUTCFullYear();
  return { week: Math.ceil(((t.getTime() - Date.UTC(year, 0, 1)) / 86400000 + 1) / 7), year };
}

/** Dönem etiketi: "16.11.2026" · "H47 2026" · "Kas 2026" · "Ç4 2026" · "2026". */
export function bucketLabel(key: string, bucket: ChartBucket): string {
  const d = isoDate(key);
  if (bucket === "day") return formatDate(d);
  if (bucket === "week") { const w = weekNo(d); return `H${w.week} ${w.year}`; }
  if (bucket === "month") return `${T.months[d.getMonth()]} ${d.getFullYear()}`;
  if (bucket === "quarter") return `Ç${Math.floor(d.getMonth() / 3) + 1} ${d.getFullYear()}`;
  return String(d.getFullYear());
}

export function keyLabel(v: ChartKey, bucket: ChartBucket | null = null): string {
  if (v.key === OTHER_KEY) return T.other;
  if (v.key === null) return T.empty;
  if (bucket && typeof v.key === "string") return bucketLabel(v.key, bucket);
  return v.label ?? String(v.key);
}

export function seriesLabel(s: Pick<ChartSeries, "field" | "fn">, byField: Map<string, ListColumn>): string {
  if (s.fn === "count") return T.fn.count;
  return `${byField.get(s.field ?? "")?.label ?? s.field} · ${T.fn[s.fn]}`;
}

/** Serinin ondalığı: alanınki (birimden ondalıklıda 2); ortalamada bir fazla; adette 0. */
export function seriesDecimals(s: Pick<ChartSeries, "field" | "fn">, byField: Map<string, ListColumn>): number {
  if (s.fn === "count" || s.fn === "distinct") return 0;
  const col = byField.get(s.field ?? "");
  const base = col?.type === "integer" ? 0 : col?.decimals ?? 2;
  return s.fn === "avg" ? Math.min(4, base + 1) : base;
}

export const isEmptyData = (data: ChartData) => data.rows === 0 || data.x.values.length === 0;

/** Küçük grafik ızgarası (K-179): alana göre 1–4 sütun; dar alanda sütun azalır. */
export function facetColumns(count: number, width: number): number {
  const most = width < 560 ? 1 : width < 900 ? 2 : width < 1300 ? 3 : 4;
  return Math.max(1, Math.min(count, most));
}

/** Ortak ölçekte eksenin ucu: değerin üstündeki "yuvarlak" sayı (1, 2, 2,5, 5, 10 × 10ⁿ). */
export function niceCeil(v: number): number {
  if (!(v > 0)) return 0;
  const pow = 10 ** Math.floor(Math.log10(v));
  const f = v / pow;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * pow;
}

interface Drawn { s: ChartSeries; name: string; color: string; raw: (number | null)[]; shown: (number | null)[]; decimals: number; bar: boolean; p: ChartKey | null }
interface LayoutParams { rect: { width: number; height: number }; labelRect: { width: number; height: number } }
interface Box { left: number; top: number; width: number; height: number }
export interface BuildOptions {
  narrow?: boolean; fontSize?: number; selected?: PickItem[];
  /** Grafik kutusunun ölçüsü (px): küçük grafik ızgarası ve pasta yerleşimi bununla hesaplanır. */
  width?: number; height?: number;
}

export interface BuiltChart {
  option: Record<string, unknown>;
  /** Birimi karışık olduğu için çizilmeyen serilerin adları. */
  mixed: string[];
  /** Grafiğin altındaki uyarılar (ör. negatif dilim, örnekleme). */
  notes: string[];
  /** Küçük grafiklerde çizimin en küçük yüksekliği (px): alan bundan kısaysa grafik bölmesi kaydırılır, küçük grafikler ezilmez. */
  minHeight?: number;
  /** Tıklanan parçanın öğesi (K-179): yatay eksen değeri, kırılım varsa parça, küçük grafik varsa değeri; "Diğer" için "other" (seçilemez), öbür
   *  parçalar (toplam etiketi, dağılım noktası) için null. */
  hit(seriesIndex: number, dataIndex: number): PickItem | "other" | null;
}

/** Ortak parçalar: başlık, gösterge ve bunların kapladığı yer. */
function frame(config: ChartConfig, names: string[], opts: BuildOptions) {
  const size = Math.round((opts.fontSize ?? 13) * 0.92);
  const titleSize = Math.round(size * TITLE_SCALE[config.title_size]);
  const titleRoom = config.title ? titleSize * 1.9 : 0;
  const legendAt = config.legend.position === "right" && opts.narrow ? "bottom" : config.legend.position;
  const legend = {
    show: config.legend.show && names.length > 0, type: "scroll", data: names,
    textStyle: { color: STRONG, fontFamily: TEXT_FONT, fontSize: size }, itemWidth: 14, itemHeight: 10,
    ...(legendAt === "right" ? { orient: "vertical", right: 4, top: "middle" } : legendAt === "bottom" ? { bottom: 0, left: "center" } : { top: titleRoom, left: "center" }),
  };
  const title = { show: Boolean(config.title), text: config.title, top: 0, left: config.title_align,
                  textStyle: { color: STRONG, fontFamily: TEXT_FONT, fontSize: titleSize, fontWeight: 600 } };
  const withLegend = legend.show;
  return {
    size, title, titleRoom, legend, legendAt, withLegend,
    base: { animation: false, color: PALETTE, textStyle: { fontFamily: TEXT_FONT, fontSize: size } },
    room: { top: titleRoom + (withLegend && legendAt === "top" ? size * 2.2 : 0), bottom: withLegend && legendAt === "bottom" ? size * 2.4 : 0,
            right: withLegend && legendAt === "right" ? 150 : 0 },
  };
}

/** Küçük grafiklerin kutuları ve başlıkları: ortak başlık ve göstergeden kalan alan ızgaraya bölünür. */
function facetLayout(count: number, room: { top: number; bottom: number; right: number }, size: number, opts: BuildOptions, minCell: number) {
  const W = opts.width && opts.width > 0 ? opts.width : DEFAULT_BOX.width;
  const cols = facetColumns(count, W);
  const rows = Math.ceil(count / cols);
  const { pad, gapX, gapY } = FACET_BOX;
  const left = 8, right = room.right + 8, top = room.top + 6, bottom = room.bottom + 6;
  // her küçük grafik en az minCell yüksekliğinde: sığmıyorsa çizim uzar (bölme kaydırılır)
  const minHeight = Math.ceil(top + bottom + rows * minCell + gapY * (rows - 1));
  const H = Math.max(opts.height && opts.height > 0 ? opts.height : DEFAULT_BOX.height, minHeight);
  const cellW = Math.max(40, (W - left - right - gapX * (cols - 1)) / cols);
  const cellH = Math.max(40, (H - top - bottom - gapY * (rows - 1)) / rows);
  const head = Math.round(size * 1.7);
  // Her küçük grafik kendi kutusunda: çerçeve (frames) hücrenin tamamı; başlık ve çizim kutunun iç boşluğunda
  const frames: Box[] = [];
  const boxes: (Box & { titleTop: number })[] = Array.from({ length: count }, (_, i) => {
    const x = left + (i % cols) * (cellW + gapX);
    const y = top + Math.floor(i / cols) * (cellH + gapY);
    frames.push({ left: Math.round(x) + 0.5, top: Math.round(y) + 0.5, width: Math.round(cellW) - 1, height: Math.round(cellH) - 1 });
    return { left: Math.round(x + pad), titleTop: Math.round(y + pad - 1), top: Math.round(y + pad + head), width: Math.round(cellW - 2 * pad),
             height: Math.round(Math.max(20, cellH - head - 2 * pad)) };
  });
  return { boxes, frames, cols, rows, minHeight, height: H };
}

/** Küçük grafiklerin kutuları: çok açık gri ince çerçeve, hafif yuvarlak köşe; çizimin arkasında, tıklamayı almaz. */
const facetFrames = (frames: Box[]) => frames.map((f) => ({
  type: "rect", silent: true, z: 0, shape: { x: f.left, y: f.top, width: f.width, height: f.height, r: FACET_BOX.radius },
  style: { fill: "none", stroke: GRID, lineWidth: 1 } }));

/** Küçük grafiğin başlığı: çubuk ve çizgide kutunun sol üstünde; pasta ve halkada (center) kutunun üstünde ortalı. */
const facetTitle = (text: string, box: Box & { titleTop: number }, size: number, center = false) => ({
  text, ...(center ? { left: Math.round(box.left + box.width / 2), textAlign: "center" } : { left: box.left }), top: box.titleTop, textStyle: { color: STRONG, fontFamily: TEXT_FONT, fontSize: size, fontWeight: 600, width: box.width, overflow: "truncate" } });

export function buildOption(config: ChartConfig, data: ChartData, columns: ListColumn[], opts: BuildOptions = {}): BuiltChart {
  return config.kind === "pie" || config.kind === "donut" ? buildPie(config, data, columns, opts) : buildXY(config, data, columns, opts);
}

function buildXY(config: ChartConfig, data: ChartData, columns: ListColumn[], opts: BuildOptions): BuiltChart {
  const byField = new Map(columns.map((c) => [c.field, c]));
  const horizontal = config.bars.horizontal;
  const percent = config.bars.mode === "percent";
  const stacked = config.bars.mode !== "group";
  const cats = data.x.values.map((v) => keyLabel(v, data.x.bucket));
  const splits: (ChartKey | null)[] = data.split ? data.split.values : [null];
  const facets: (ChartKey | null)[] = data.facets ? data.facets.values : [null];
  const faceted = data.facets !== null && data.facets !== undefined;
  const mixed: string[] = [];
  const usable = config.series.filter((s) => {
    const got = data.series.find((d) => d.id === s.id);
    if (!got) return false;
    if (got.mixed_units || !got.data) { mixed.push(seriesLabel(s, byField)); return false; }
    return true;
  });
  const sides = (["primary", "secondary"] as AxisSide[]).filter((side) => side === "primary" || usable.some((s) => s.axis === side));
  const sideOf = (side: AxisSide) => Math.max(0, sides.indexOf(side));
  const where = (v: number) => (horizontal ? { xAxis: v } : { yAxis: v });
  const corner = horizontal ? [0, RADIUS, RADIUS, 0] : [RADIUS, RADIUS, 0, 0];

  // Panel başına çizilen seriler (küçük grafik yoksa tek panel): seri × kırılım
  const panelDrawn = (fi: number): Drawn[] => {
    const drawn: Drawn[] = [];
    config.series.forEach((s, si) => {
      if (!usable.includes(s)) return;
      const got = data.series.find((d) => d.id === s.id)!;
      const grid = (faceted ? (got.data as (number | null)[][][])[fi] : got.data as (number | null)[][]) ?? [];
      const label = seriesLabel(s, byField);
      splits.forEach((p, pi) => {
        const raw = grid[pi] ?? [];
        const name = p === null ? label : config.series.length > 1 ? `${keyLabel(p)} · ${label}` : keyLabel(p);
        const color = p === null ? s.color ?? PALETTE[si % PALETTE.length] : PALETTE[drawn.length % PALETTE.length];
        drawn.push({ s, name, color, raw, shown: raw, decimals: seriesDecimals(s, byField), bar: s.type === "bar", p });
      });
    });
    // %100: aynı eksendeki çubuklar kategori başına yüzdeye çevrilir (ipucu gerçek değeri de yazar)
    if (percent) {
      for (const side of ["primary", "secondary"] as AxisSide[]) {
        const bars = drawn.filter((d) => d.bar && d.s.axis === side);
        cats.forEach((_, j) => {
          const total = bars.reduce((sum, d) => sum + Math.abs(d.raw[j] ?? 0), 0);
          bars.forEach((d) => { if (d.shown === d.raw) d.shown = [...d.raw]; d.shown[j] = d.raw[j] === null || !total ? d.raw[j] === null ? null : 0 : (d.raw[j]! / total) * 100; });
        });
      }
    }
    return drawn;
  };
  const panels = facets.map((f, fi) => ({ f, drawn: panelDrawn(fi) }));
  const first = panels[0]?.drawn ?? [];
  const names = first.map((d) => d.name);
  const F = frame(config, names, opts);
  const size = F.size;
  const bar = BAR_WIDTH[config.bars.width];
  const barSize = { barMaxWidth: size * bar.max, barCategoryGap: bar.gap };
  const sidePercent = (side: AxisSide) => percent && first.some((d) => d.bar && d.s.axis === side);
  const sideDecimals = (side: AxisSide) => Math.max(0, ...first.filter((d) => d.s.axis === side).map((d) => d.decimals));
  const lineLabel = (text: string, color: string) => ({ show: Boolean(text), formatter: text, color, position: "insideEndTop", fontFamily: NUM_FONT, fontSize: size });

  // Seçim (K-179): seçilenler canlı, ötekiler soluk; grafik daralmaz
  const selected = opts.selected ?? [];
  const itemOf = (d: Drawn, j: number, f: ChartKey | null): PickItem | null => {
    const x = data.x.values[j];
    if (!x || x.key === OTHER_KEY || d.p?.key === OTHER_KEY || f?.key === OTHER_KEY) return null;  // "Diğer" seçilemez
    return { x: x.key, ...(d.p === null ? {} : { p: d.p.key }), ...(f === null ? {} : { f: f.key }) };
  };
  const faded = (d: Drawn, j: number, f: ChartKey | null) => {
    if (!selected.length) return false;
    const item = itemOf(d, j, f);
    return !item || !selected.some((s) => samePick(s, item));
  };

  const series: Record<string, unknown>[] = [];
  const flat: ({ d: Drawn; f: ChartKey | null; g: number } | null)[] = [];  // seri sırası → çizilen parça (toplam etiketi null)
  panels.forEach(({ f, drawn }, g) => {
    const valueAxis = (side: AxisSide) => g * sides.length + sideOf(side);
    const panelAxis = faceted ? { [horizontal ? "yAxisIndex" : "xAxisIndex"]: g } : {};  // küçük grafikte kategori ekseni panelin kendi ekseni
    const stackOf = (side: AxisSide) => (faceted ? `${g}:${side}` : side);
    // Yığılmışta yalnız en üst parçanın köşesi yuvarlak: kategori başına son dolu çubuk
    const top = new Map<string, number>();
    if (stacked) drawn.forEach((d, i) => { if (d.bar) cats.forEach((_, j) => { if ((d.shown[j] ?? 0) > 0) top.set(`${d.s.axis}:${j}`, i); }); });
    const refs = config.ref_lines.map((r) => {
      const host = drawn.findIndex((d) => (r.kind === "value" ? true : d.s.id === r.series));
      if (host < 0) return null;
      let value = r.value;
      if (r.kind !== "value") {
        const all = drawn.filter((d) => d.s.id === r.series).flatMap((d) => d.raw).filter((v): v is number => v !== null);
        if (!all.length) return null;
        value = r.kind === "avg" ? all.reduce((a, b) => a + b, 0) / all.length : r.kind === "min" ? Math.min(...all) : Math.max(...all);
      }
      if (value === null) return null;
      const color = r.color ?? TEXT;
      const number = formatNumber(value, r.kind === "avg" && drawn[host].decimals === 0 ? 1 : drawn[host].decimals);
      // "Adı göster" ve "Değeri göster" ayrı ayrı; ikisi de kapalıysa yalnız çizgi
      const text = [r.show_name ? r.name || T.refKind[r.kind] : "", r.show_value ? number : ""].filter(Boolean).join(" ");
      return { host, item: { ...where(value), name: text, lineStyle: { color, type: "dashed", width: 1.5 }, label: lineLabel(text, color) } };
    }).filter((r): r is NonNullable<typeof r> => r !== null);

    drawn.forEach((d, i) => {
      const th = d.s.threshold;
      const above = (j: number) => th !== null && d.raw[j] !== null && d.raw[j]! > th.value;
      const lines: Record<string, unknown>[] = refs.filter((r) => r.host === i).map((r) => r.item);
      const firstOfSeries = drawn.findIndex((x) => x.s.id === d.s.id) === i;
      if (th && th.line && firstOfSeries && !(percent && d.bar)) {  // "Eşik çizgisini göster": kapalıyken yalnız eşik üstü renk
        const text = `${T.threshold} ${formatNumber(th.value, d.decimals)}`;
        lines.push({ ...where(th.value), name: text, lineStyle: { color: TEXT, type: "dotted", width: 1 }, label: lineLabel(text, TEXT) });
      }
      const inside = d.bar && stacked;  // yığılmışta etiket parçanın içinde: sade yazı, sığmazsa yok
      const text = (j: number) => {
        const v = d.raw[j];
        if (v === null || (v === 0 && !d.s.labels.zero)) return "";  // "Sıfır değerleri göster" kapalıyken 0'ın etiketi çıkmaz
        return formatNumber(v, d.s.labels.decimals);
      };
      const label = {
        show: d.s.labels.show, fontFamily: NUM_FONT, fontSize: size, formatter: (p: { dataIndex: number }) => text(p.dataIndex),
        ...(inside
          ? { position: "inside", color: suggestText(d.color, STRONG), padding: [1, 3] }
          : { position: d.bar ? (horizontal ? "right" : "top") : "top", color: STRONG, padding: [3, 5], distance: d.bar ? 2 : 4,
              textBorderColor: SURFACE, textBorderWidth: 2.5 }),  // çizginin ya da çubuğun üstüne düşen etiket okunur kalır
      };
      const labelLayout = inside
        ? (p: LayoutParams) => ({ hideOverlap: true, ...(p.labelRect.width > p.rect.width || p.labelRect.height > p.rect.height ? { fontSize: 0 } : {}) })
        : { hideOverlap: true };
      const common = {
        name: d.name, color: d.color, [horizontal ? "xAxisIndex" : "yAxisIndex"]: valueAxis(d.s.axis), ...panelAxis, label, labelLayout,
        emphasis: { focus: "none" },
        ...(lines.length ? { markLine: { silent: true, symbol: "none", animation: false, data: lines } } : {}),
      };
      flat.push({ d, f, g });
      if (d.bar) {
        series.push({
          ...common, type: "bar", ...barSize, barGap: "8%", ...(stacked ? { stack: stackOf(d.s.axis) } : {}),
          data: d.shown.map((v, j) => ({
            value: v,
            itemStyle: { ...(above(j) ? { color: th!.color } : {}), borderRadius: !stacked || top.get(`${d.s.axis}:${j}`) === i ? corner : 0,
                         ...(faded(d, j, f) ? { opacity: DIM } : {}) },
            ...(inside && above(j) ? { label: { color: suggestText(th!.color, STRONG) } } : {}),
          })),
        });
        return;
      }
      series.push({
        ...common, type: "line",
        ...(d.s.type === "smooth" ? { smooth: true, smoothMonotone: "x" } : { smooth: false }),  // eğimli çizgi monoton: veri aralığının dışına taşmaz
        ...(d.s.type === "step" ? { step: "end" } : {}), ...(d.s.type === "area" ? { areaStyle: { opacity: 0.2 } } : {}),
        lineStyle: { width: 2, type: d.s.line === "dashed" ? "dashed" : "solid" }, symbol: "circle", symbolSize: selected.length ? 7 : 5, connectNulls: false,
        data: d.shown.map((v, j) => ({
          value: v,
          ...(above(j) ? { symbolSize: 9, itemStyle: { color: th!.color, borderColor: d.color, borderWidth: 2, ...(faded(d, j, f) ? { opacity: DIM } : {}) } }
            : faded(d, j, f) ? { itemStyle: { opacity: DIM } } : {}),
        })),
      });
    });

    // Yığılmışta "Toplamı göster": yığının üstünde toplam (görünmez sıfır yükseklikli parça taşır; göstergede ve ipucunda yer almaz)
    if (config.bars.totals && config.bars.mode === "stack") {
      for (const side of sides) {
        const bars = drawn.filter((d) => d.bar && d.s.axis === side && d.s.fn !== "distinct");  // Benzersiz say toplanmaz (K-179)
        if (!bars.length) continue;
        const totals = cats.map((_, j) => bars.reduce((sum, d) => sum + (d.raw[j] ?? 0), 0));
        const dec = Math.max(0, ...bars.map((d) => d.s.labels.decimals));  // toplam, seri etiketlerinin ondalığıyla
        flat.push(null);
        series.push({
          type: "bar", stack: stackOf(side), name: "", silent: true, [horizontal ? "xAxisIndex" : "yAxisIndex"]: valueAxis(side), ...panelAxis,
          data: totals.map(() => 0), itemStyle: { color: "transparent" }, tooltip: { show: false }, ...barSize,
          label: { show: true, position: horizontal ? "right" : "top", color: STRONG, fontFamily: NUM_FONT, fontSize: size, fontWeight: 600,
                   formatter: (p: { dataIndex: number }) => (totals[p.dataIndex] === 0 ? "" : formatNumber(totals[p.dataIndex], dec)) },
          labelLayout: { hideOverlap: true },
        });
      }
    }
  });

  // Ortak ölçek (küçük grafiklerde varsayılan): bütün panellerin aralığı; yığılmışta kategori toplamı
  const extent = (side: AxisSide): { min: number; max: number } => {
    let lo = 0, hi = 0;
    for (const { drawn } of panels) {
      const mine = drawn.filter((d) => d.s.axis === side);
      cats.forEach((_, j) => {
        let pos = 0, neg = 0;
        for (const d of mine) {
          const v = d.shown[j] ?? 0;
          if (d.bar && stacked) { if (v > 0) pos += v; else neg += v; } else { hi = Math.max(hi, v); lo = Math.min(lo, v); }
        }
        hi = Math.max(hi, pos); lo = Math.min(lo, neg);
      });
    }
    return { min: lo < 0 ? -niceCeil(-lo) : 0, max: niceCeil(hi) };
  };
  const shared = faceted && config.facet_scale === "shared";
  const layout = faceted ? facetLayout(panels.length, F.room, size, opts, FACET_MIN.xy) : null;
  const zoom = !faceted && config.axes.x.zoom && data.x.kind === "date";  // yakınlaştırma kaydırıcısı yalnız zaman ekseninde (K-179); küçük grafiklerde yok

  const categoryAxis = (g: number) => ({
    type: "category", data: cats, inverse: horizontal, ...(faceted ? { gridIndex: g } : {}),
    ...(faceted ? {} : { name: config.axes.x.title, nameLocation: "middle", nameGap: horizontal ? 8 : size * 2.4,
                         nameTextStyle: { color: TEXT, fontFamily: TEXT_FONT, fontSize: size } }),  // küçük grafiklerde eksen başlığı yazılmaz
    axisLabel: { color: TEXT, fontFamily: data.x.kind === "date" ? NUM_FONT : TEXT_FONT, fontSize: size, hideOverlap: true },
    axisLine: { lineStyle: { color: LINE } }, axisTick: { alignWithLabel: true, lineStyle: { color: LINE } },
  });
  const valueAxes = (g: number) => sides.map((side) => {
    const ax = config.axes[side];
    const pct = sidePercent(side);
    const dec = sideDecimals(side);
    const range = shared && !pct ? extent(side) : null;
    return {
      type: "value", ...(faceted ? { gridIndex: g } : {}), position: horizontal ? (side === "primary" ? "bottom" : "top") : side === "primary" ? "left" : "right",
      ...(faceted ? {} : {
        name: [ax.title, ax.unit ? `(${ax.unit})` : ""].filter(Boolean).join(" "),
        nameTextStyle: { color: TEXT, fontFamily: TEXT_FONT, fontSize: size, ...(horizontal ? {} : { align: side === "primary" ? "left" : "right" }) } }),
      min: pct ? 0 : ax.min ?? range?.min ?? undefined, max: pct ? 100 : ax.max ?? (range && range.max > 0 ? range.max : undefined),
      ...(dec === 0 && !pct ? { minInterval: 1 } : {}),  // tam sayılı eksende adım tam sayı: aynı sayı iki kez yazılmaz
      splitLine: { show: ax.grid, lineStyle: { color: GRID } }, axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: TEXT, fontFamily: NUM_FONT, fontSize: size, hideOverlap: true,
                   formatter: (v: number) => (pct ? `%${formatNumber(v, 0)}` : formatNumber(v, Number.isInteger(v) ? 0 : Math.max(1, dec))) },
    };
  });
  const categories = panels.map((_, g) => categoryAxis(g));
  const values = panels.flatMap((_, g) => valueAxes(g));
  const named = !faceted && values.some((v) => "name" in v && v.name);

  const tooltip = {
    trigger: "axis", confine: true, transitionDuration: 0,  // ipucu fareyi gecikmesiz izler: bantla aynı dönemi gösterir
    axisPointer: { type: "shadow", animation: false, shadowStyle: { color: BAND, opacity: 0.7 } },
    textStyle: { color: STRONG, fontFamily: TEXT_FONT, fontSize: size },
    formatter: (params: { dataIndex: number; seriesIndex: number; marker: string }[]) => {
      const rows = params.filter((p) => flat[p.seriesIndex]);
      if (!rows.length) return "";
      const j = rows[0].dataIndex;
      const key = data.x.values[j];
      const f = flat[rows[0].seriesIndex]!.f;
      const week = data.x.bucket === "week" && typeof key?.key === "string" && key.key !== OTHER_KEY ? `<div>${esc(T.weekOf(formatDate(isoDate(key.key))))}</div>` : "";
      const lines = rows.map((p) => {
        const d = flat[p.seriesIndex]!.d;
        const raw = d.raw[j];
        const value = raw === null ? "–" : formatNumber(raw, d.decimals) + (percent && d.bar && d.shown[j] !== null ? ` (%${formatNumber(d.shown[j]!, 1)})` : "");
        return `<div>${p.marker} ${esc(d.name)}: <span style="font-family:${NUM_FONT};font-variant-numeric:tabular-nums">${value}</span></div>`;
      });
      return `<div style="font-weight:600">${esc(f === null ? cats[j] : `${keyLabel(f)} · ${cats[j]}`)}</div>${week}${lines.join("")}`;
    },
  };
  const grid = layout
    ? layout.boxes.map((b) => ({ containLabel: true, left: b.left, top: b.top, width: b.width, height: b.height }))
    : {
        containLabel: true, left: 8, right: (F.room.right || 16) + (zoom && horizontal ? ZOOM_SIZE + 8 : 0),
        top: F.room.top + (named ? size * 1.8 : 8) + 4,
        bottom: F.room.bottom + (config.axes.x.title && !horizontal ? size * 1.6 : 0) + 6 + (zoom && !horizontal ? ZOOM_SIZE + 10 : 0),
      };
  const option = {
    ...F.base,
    title: layout ? [F.title, ...layout.boxes.map((b, g) => facetTitle(keyLabel(panels[g].f!), b, size))] : F.title,
    grid, legend: F.legend, tooltip, ...(layout ? { graphic: facetFrames(layout.frames) } : {}),
    xAxis: horizontal ? values : (faceted ? categories : categories[0]),
    yAxis: horizontal ? (faceted ? categories : categories[0]) : values,
    series,
    ...(zoom ? { dataZoom: [{ type: "slider", [horizontal ? "yAxisIndex" : "xAxisIndex"]: 0, showDetail: false, brushSelect: false, filterMode: "empty", throttle: 30,  // "empty": dikey eksen bütün verinin aralığında sabit kalır
                              ...(horizontal ? { right: 4, width: ZOOM_SIZE } : { bottom: F.withLegend && F.legendAt === "bottom" ? size * 2.4 : 4, height: ZOOM_SIZE }),
                              dataBackground: { lineStyle: { color: TEXT, width: 1, opacity: 1 }, areaStyle: { color: LINE, opacity: 1 } },
                              selectedDataBackground: { lineStyle: { color: PALETTE[0], width: 1, opacity: 1 }, areaStyle: { color: PALETTE[0], opacity: 0.55 } },
                              borderColor: LINE, fillerColor: `${ZOOM_FILL}73`, backgroundColor: SURFACE, /* dolgu yarı saydam: alttaki veri silueti görünür */
                              handleStyle: { color: SURFACE, borderColor: PALETTE[0] }, moveHandleSize: 4 }] } : {}),
  };
  return {
    option, mixed, notes: [], minHeight: layout?.minHeight,
    hit: (seriesIndex, dataIndex) => { const at = flat[seriesIndex]; return at ? itemOf(at.d, dataIndex, at.f) ?? "other" : null; },
  };
}

/** Pasta ve halka (K-179): yalnız ilk seri; dilimler yatay eksenin değerleri ("Diğer" dahil); küçük grafiklerde yan yana pastalar. Negatif değerli
 *  dilim çizilmez (uyarı); sıfır değerli dilim yalnız "Sıfır değerleri göster" açıkken yer alır. Kırılım kullanılmaz. */
function buildPie(config: ChartConfig, data: ChartData, columns: ListColumn[], opts: BuildOptions): BuiltChart {
  const byField = new Map(columns.map((c) => [c.field, c]));
  const s = config.series[0];
  const got = data.series.find((d) => d.id === s.id);
  const label = seriesLabel(s, byField);
  const mixed = !got || got.mixed_units || !got.data ? [label] : [];
  const cats = data.x.values.map((v) => keyLabel(v, data.x.bucket));
  const facets: (ChartKey | null)[] = data.facets ? data.facets.values : [null];
  const faceted = data.facets !== null && data.facets !== undefined;
  const decimals = seriesDecimals(s, byField);
  const colorOf = (j: number) => (data.x.values[j].key === OTHER_KEY ? LINE : PALETTE[j % PALETTE.length]);
  const selected = opts.selected ?? [];
  const F = frame(config, mixed.length ? [] : cats, opts);
  const size = F.size;
  const W = opts.width && opts.width > 0 ? opts.width : DEFAULT_BOX.width;
  const H = opts.height && opts.height > 0 ? opts.height : DEFAULT_BOX.height;
  const layout = faceted ? facetLayout(facets.length, F.room, size, opts, FACET_MIN.pie) : null;
  const boxes: Box[] = layout ? layout.boxes : [{ left: 8, top: F.room.top + 6, width: W - 16 - F.room.right, height: H - F.room.top - F.room.bottom - 12 }];
  const mode = config.pie.label;
  const outside = mode !== "none";
  let negative = 0;
  const index: number[][] = [];  // seri → dilim sırası → yatay eksen sırası
  const titleTops: number[] = [];  // küçük grafikte başlık pastanın hemen üstünde durur (kutu yüksekse de aralarında boş alan kalmaz)

  const itemOf = (j: number, f: ChartKey | null): PickItem | null => {
    const x = data.x.values[j];
    if (!x || x.key === OTHER_KEY || f?.key === OTHER_KEY) return null;
    return { x: x.key, ...(f === null ? {} : { f: f.key }) };
  };
  const series = mixed.length ? [] : facets.map((f, fi) => {
    const row = ((faceted ? (got!.data as (number | null)[][][])[fi] : got!.data as (number | null)[][]) ?? [])[0] ?? [];
    const kept: number[] = [];
    row.forEach((v, j) => {
      if (v === null) return;
      if (v < 0) { negative += 1; return; }
      if (v === 0 && !s.labels.zero) return;
      kept.push(j);
    });
    index.push(kept);
    const total = kept.reduce((sum, j) => sum + (row[j] ?? 0), 0);
    const box = boxes[fi];
    // küçük grafikte pasta kutuyu doldurur: başlıkla arasında boş alan kalmaz (etiketler yanlara açılır)
    const r = Math.max(12, faceted ? Math.min(box.width / 2 * (outside ? 0.6 : 0.9), box.height / 2 * (outside ? 0.84 : 0.94))
      : Math.min(box.width, box.height) / 2 * (outside ? 0.66 : 0.9));
    if (layout) {
      const head = Math.round(size * 1.7) + (outside ? Math.round(size * 1.3) : 4);  // başlık ve (varsa) üstteki etiketin yeri
      titleTops.push(Math.max(layout.boxes[fi].titleTop, Math.round(box.top + box.height / 2 - r - head)));
    }
    const text = (j: number) => (mode === "value" ? formatNumber(row[j] ?? 0, s.labels.decimals) : `%${formatNumber(total ? ((row[j] ?? 0) / total) * 100 : 0, 1)}`);
    return {
      type: "pie", name: f === null ? label : keyLabel(f), center: [Math.round(box.left + box.width / 2), Math.round(box.top + box.height / 2)],
      radius: config.kind === "donut" ? [Math.round(r * 0.58), Math.round(r)] : [0, Math.round(r)],
      avoidLabelOverlap: true, minShowLabelAngle: 2, emphasis: { scale: true, scaleSize: 3 },
      itemStyle: { borderColor: SURFACE, borderWidth: 1 },
      label: { show: outside, color: STRONG, fontFamily: NUM_FONT, fontSize: size,
               formatter: (p: { dataIndex: number }) => (F.withLegend ? text(kept[p.dataIndex]) : `${cats[kept[p.dataIndex]]} ${text(kept[p.dataIndex])}`) },
      labelLine: { show: outside, length: 8, length2: 6, lineStyle: { color: LINE } },
      data: kept.map((j) => {
        const item = itemOf(j, f);
        const dim = selected.length > 0 && (!item || !selected.some((x) => samePick(x, item)));
        return { name: cats[j], value: row[j], itemStyle: { color: colorOf(j), ...(dim ? { opacity: DIM } : {}) } };
      }),
      _total: total, _row: row,
    };
  });
  const tooltip = {
    trigger: "item", confine: true, transitionDuration: 0, textStyle: { color: STRONG, fontFamily: TEXT_FONT, fontSize: size },
    formatter: (p: { seriesIndex: number; dataIndex: number; marker: string }) => {
      const sr = series[p.seriesIndex];
      if (!sr) return "";
      const j = index[p.seriesIndex][p.dataIndex];
      const f = facets[p.seriesIndex];
      const v = sr._row[j] ?? 0;
      const head = f === null ? label : `${keyLabel(f)} · ${label}`;
      return `<div style="font-weight:600">${esc(head)}</div><div>${p.marker} ${esc(cats[j])}: <span style="font-family:${NUM_FONT};font-variant-numeric:tabular-nums">`
        + `${formatNumber(v, decimals)} (%${formatNumber(sr._total ? (v / sr._total) * 100 : 0, 1)})</span></div>`;
    },
  };
  const option = {
    ...F.base,
    title: layout ? [F.title, ...layout.boxes.map((b, g) => facetTitle(keyLabel(facets[g]!), { ...b, titleTop: titleTops[g] ?? b.titleTop }, size, true))] : F.title,
    legend: F.legend, tooltip, ...(layout ? { graphic: facetFrames(layout.frames) } : {}),
    series: series.map(({ _total, _row, ...rest }) => { void _total; void _row; return rest; }),
  };
  return {
    option, mixed, notes: negative > 0 ? [T.pieNegative(negative)] : [], minHeight: layout?.minHeight,
    hit: (seriesIndex, dataIndex) => {
      const j = index[seriesIndex]?.[dataIndex];
      return j === undefined ? null : itemOf(j, facets[seriesIndex]) ?? "other";
    },
  };
}

/** Dağılım (K-179): satır başına nokta; renk kırılımı varsa değer başına seri (en büyük 11 + "Diğer"). Seçim, iniş, yakınlaştırma, referans çizgisi
 *  ve eşik yoktur. Bir eksendeki alanın birimi karışıksa çizilmez (uyarı); sınır aşılmışsa örnekleme uyarısı çıkar. */
export function buildScatter(config: ChartConfig, data: PointsData, columns: ListColumn[], opts: BuildOptions = {}): BuiltChart {
  const byField = new Map(columns.map((c) => [c.field, c]));
  const sc = config.scatter!;
  const xCol = byField.get(sc.x), yCol = byField.get(sc.y);
  const dec = (c: ListColumn | undefined) => (c?.type === "integer" ? 0 : c?.decimals ?? 2);
  const xName = xCol?.label ?? sc.x, yName = yCol?.label ?? sc.y;
  const colors = data.colors ? data.colors.values.map((v) => keyLabel(v)) : [];
  const F = frame(config, colors, opts);
  const size = F.size;
  const mixedAxes = [...new Set([data.mixed_units.x ? xName : null, data.mixed_units.y ? yName : null].filter((n): n is string => n !== null))];
  const groups: number[][] = colors.length ? colors.map(() => []) : [[]];
  data.points.forEach((p, i) => { (groups[colors.length ? Math.min(p[2], colors.length - 1) : 0] ?? groups[0]).push(i); });
  const ax = config.axes.primary;
  const valueAxis = (name: string, d: number, extra: Record<string, unknown>) => ({
    type: "value", scale: true, name, nameTextStyle: { color: TEXT, fontFamily: TEXT_FONT, fontSize: size },
    axisLine: { lineStyle: { color: LINE } }, axisTick: { lineStyle: { color: LINE } }, splitLine: { show: ax.grid, lineStyle: { color: GRID } },
    axisLabel: { color: TEXT, fontFamily: NUM_FONT, fontSize: size, hideOverlap: true, formatter: (v: number) => formatNumber(v, Number.isInteger(v) ? 0 : Math.max(1, d)) },
    ...extra,
  });
  const series = groups.map((members, g) => ({
    type: "scatter", name: colors[g] ?? T.kinds.scatter, symbolSize: 7, large: false,
    itemStyle: { color: colors.length ? (data.colors!.values[g].key === OTHER_KEY ? LINE : PALETTE[g % PALETTE.length]) : sc.point_color ?? PALETTE[0], opacity: 0.75 },
    emphasis: { focus: "none", scale: 1.4 },
    data: members.map((i) => [data.points[i][0], data.points[i][1], i]),
  }));
  const number = (v: number, d: number) => `<span style="font-family:${NUM_FONT};font-variant-numeric:tabular-nums">${formatNumber(v, d)}</span>`;
  const option = {
    ...F.base, title: F.title, legend: F.legend,
    grid: { containLabel: true, left: 8, right: (F.room.right || 16) + 8, top: F.room.top + size * 1.8 + 4, bottom: F.room.bottom + size * 1.6 + 6 },
    tooltip: {
      trigger: "item", confine: true, transitionDuration: 0, textStyle: { color: STRONG, fontFamily: TEXT_FONT, fontSize: size },
      formatter: (p: { seriesIndex: number; data: number[]; marker: string }) => {
        const point = data.points[p.data[2]];
        if (!point) return "";
        const head = point[3] === null || point[3] === "" ? "" : `<div style="font-weight:600">${esc(String(point[3]))}</div>`;
        const color = colors.length ? `<div>${p.marker} ${esc(colors[Math.min(point[2], colors.length - 1)])}</div>` : "";
        return `${head}${color}<div>${esc(xName)}: ${number(point[0], dec(xCol))}</div><div>${esc(yName)}: ${number(point[1], dec(yCol))}</div>`;
      },
    },
    xAxis: valueAxis(config.axes.x.title || xName, dec(xCol), { nameLocation: "middle", nameGap: size * 2.2 }),
    yAxis: valueAxis([ax.title || yName, ax.unit ? `(${ax.unit})` : ""].filter(Boolean).join(" "), dec(yCol),
                     { min: ax.min ?? undefined, max: ax.max ?? undefined, nameTextStyle: { color: TEXT, fontFamily: TEXT_FONT, fontSize: size, align: "left" } }),
    series,
  };
  const notes = [
    ...(mixedAxes.length ? [T.scatterMixed(mixedAxes.join(", "))] : []),
    ...(!mixedAxes.length && data.shown < data.rows ? [T.sampled(formatNumber(data.rows, 0), formatNumber(data.shown, 0))] : []),
  ];
  return { option, mixed: [], notes, hit: () => null };
}

// Ayar + veri → çizim seçenekleri (K-178, docs/12 "Grafik standardı"). Saf işlev: grafiğin bütün kuralları burada (renk sırası, eksen, etiket, ipucu,
// gösterge, eşik, referans çizgisi, köşe yuvarlağı); kütüphane yalnız çizer. Sayı ve tarihler Türkçe, rakamlar Inter. Saat hiçbir yerde yazılmaz.
import { formatDate, formatNumber } from "../../format";
import { tr } from "../../i18n/tr";
import type { ListColumn } from "../../table/types";
import { suggestText } from "../contrast";
import { tokenColor } from "../palette";
import { type AxisSide, type ChartBucket, type ChartConfig, type ChartData, type ChartKey, type ChartSeries, OTHER_KEY } from "./chartModel";

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
const SURFACE = tokenColor("surface");
const BAND = tokenColor("lead-50");  // üstüne gelinen dönemin bandı: çok açık gri
const RADIUS = 3;  // çubuğun üst köşesi (px)
const TITLE_SCALE = { small: 1, medium: 1.15, large: 1.4 } as const;
/** Çubuk genişliği (K-178): kategori aralığında bırakılan boşluk ve üst sınır (yazı boyutunun katı). Genişlik kategori sayısıyla ölçeklenir; kademe oranı belirler. */
export const BAR_WIDTH = { thin: { gap: "55%", max: 5 }, medium: { gap: "34%", max: 8 }, thick: { gap: "16%", max: 12 } } as const;

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
  if (s.fn === "count") return 0;
  const col = byField.get(s.field ?? "");
  const base = col?.type === "integer" ? 0 : col?.decimals ?? 2;
  return s.fn === "avg" ? Math.min(4, base + 1) : base;
}

export const isEmptyData = (data: ChartData) => data.rows === 0 || data.x.values.length === 0;

interface Drawn { s: ChartSeries; name: string; color: string; raw: (number | null)[]; shown: (number | null)[]; decimals: number; bar: boolean }
interface LayoutParams { rect: { width: number; height: number }; labelRect: { width: number; height: number } }

export interface BuiltChart {
  option: Record<string, unknown>;
  /** Birimi karışık olduğu için çizilmeyen serilerin adları. */
  mixed: string[];
}

export function buildOption(config: ChartConfig, data: ChartData, columns: ListColumn[], opts: { narrow?: boolean; fontSize?: number } = {}): BuiltChart {
  const byField = new Map(columns.map((c) => [c.field, c]));
  const size = Math.round((opts.fontSize ?? 13) * 0.92);
  const horizontal = config.bars.horizontal;
  const percent = config.bars.mode === "percent";
  const stacked = config.bars.mode !== "group";
  const cats = data.x.values.map((v) => keyLabel(v, data.x.bucket));
  const splits: (ChartKey | null)[] = data.split ? data.split.values : [null];
  const mixed: string[] = [];

  const drawn: Drawn[] = [];
  config.series.forEach((s, si) => {
    const got = data.series.find((d) => d.id === s.id);
    const label = seriesLabel(s, byField);
    if (!got) return;
    if (got.mixed_units || !got.data) { mixed.push(label); return; }
    splits.forEach((p, pi) => {
      const raw = got.data![pi] ?? [];
      const name = p === null ? label : config.series.length > 1 ? `${keyLabel(p)} · ${label}` : keyLabel(p);
      const color = p === null ? s.color ?? PALETTE[si % PALETTE.length] : PALETTE[drawn.length % PALETTE.length];
      drawn.push({ s, name, color, raw, shown: raw, decimals: seriesDecimals(s, byField), bar: s.type === "bar" });
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
  // Yığılmışta yalnız en üst parçanın köşesi yuvarlak: kategori başına son dolu çubuk
  const top = new Map<string, number>();
  if (stacked) drawn.forEach((d, i) => { if (d.bar) cats.forEach((_, j) => { if ((d.shown[j] ?? 0) > 0) top.set(`${d.s.axis}:${j}`, i); }); });
  const corner = horizontal ? [0, RADIUS, RADIUS, 0] : [RADIUS, RADIUS, 0, 0];
  const bar = BAR_WIDTH[config.bars.width];
  const barSize = { barMaxWidth: size * bar.max, barCategoryGap: bar.gap };

  const sides = (["primary", "secondary"] as AxisSide[]).filter((side) => side === "primary" || drawn.some((d) => d.s.axis === side));
  const axisIndex = (side: AxisSide) => Math.max(0, sides.indexOf(side));
  const sidePercent = (side: AxisSide) => percent && drawn.some((d) => d.bar && d.s.axis === side);
  const sideDecimals = (side: AxisSide) => Math.max(0, ...drawn.filter((d) => d.s.axis === side).map((d) => d.decimals));
  const where = (v: number) => (horizontal ? { xAxis: v } : { yAxis: v });
  const lineLabel = (text: string, color: string) => ({ show: Boolean(text), formatter: text, color, position: "insideEndTop", fontFamily: NUM_FONT, fontSize: size });

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

  const series: Record<string, unknown>[] = drawn.map((d, i) => {
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
      name: d.name, color: d.color, [horizontal ? "xAxisIndex" : "yAxisIndex"]: axisIndex(d.s.axis), label, labelLayout,
      emphasis: { focus: "none" },
      ...(lines.length ? { markLine: { silent: true, symbol: "none", animation: false, data: lines } } : {}),
    };
    if (d.bar) {
      return {
        ...common, type: "bar", ...barSize, barGap: "8%", ...(stacked ? { stack: d.s.axis } : {}),
        data: d.shown.map((v, j) => ({
          value: v,
          itemStyle: { ...(above(j) ? { color: th!.color } : {}), borderRadius: !stacked || top.get(`${d.s.axis}:${j}`) === i ? corner : 0 },
          ...(inside && above(j) ? { label: { color: suggestText(th!.color, STRONG) } } : {}),
        })),
      };
    }
    return {
      ...common, type: "line",
      ...(d.s.type === "smooth" ? { smooth: true, smoothMonotone: "x" } : { smooth: false }),  // eğimli çizgi monoton: veri aralığının dışına taşmaz
      ...(d.s.type === "step" ? { step: "end" } : {}), ...(d.s.type === "area" ? { areaStyle: { opacity: 0.2 } } : {}),
      lineStyle: { width: 2 }, symbol: "circle", symbolSize: 5, connectNulls: false,
      data: d.shown.map((v, j) => (above(j) ? { value: v, symbolSize: 9, itemStyle: { color: th!.color, borderColor: d.color, borderWidth: 2 } } : { value: v })),
    };
  });

  // Yığılmışta "Toplamı göster": yığının üstünde toplam (görünmez sıfır yükseklikli parça taşır; göstergede ve ipucunda yer almaz)
  if (config.bars.totals && config.bars.mode === "stack") {
    for (const side of sides) {
      const bars = drawn.filter((d) => d.bar && d.s.axis === side);
      if (!bars.length) continue;
      const totals = cats.map((_, j) => bars.reduce((sum, d) => sum + (d.raw[j] ?? 0), 0));
      const dec = Math.max(0, ...bars.map((d) => d.s.labels.decimals));  // toplam, seri etiketlerinin ondalığıyla
      series.push({
        type: "bar", stack: side, name: "", silent: true, [horizontal ? "xAxisIndex" : "yAxisIndex"]: axisIndex(side), data: totals.map(() => 0),
        itemStyle: { color: "transparent" }, tooltip: { show: false }, ...barSize,
        label: { show: true, position: horizontal ? "right" : "top", color: STRONG, fontFamily: NUM_FONT, fontSize: size, fontWeight: 600,
                 formatter: (p: { dataIndex: number }) => (totals[p.dataIndex] === 0 ? "" : formatNumber(totals[p.dataIndex], dec)) },
        labelLayout: { hideOverlap: true },
      });
    }
  }

  const category = {
    type: "category", data: cats, inverse: horizontal, name: config.axes.x.title, nameLocation: "middle", nameGap: horizontal ? 8 : size * 2.4,
    nameTextStyle: { color: TEXT, fontFamily: TEXT_FONT, fontSize: size },
    axisLabel: { color: TEXT, fontFamily: data.x.kind === "date" ? NUM_FONT : TEXT_FONT, fontSize: size, hideOverlap: true },
    axisLine: { lineStyle: { color: LINE } }, axisTick: { alignWithLabel: true, lineStyle: { color: LINE } },
  };
  const values = sides.map((side) => {
    const ax = config.axes[side];
    const pct = sidePercent(side);
    const dec = sideDecimals(side);
    return {
      type: "value", position: horizontal ? (side === "primary" ? "bottom" : "top") : side === "primary" ? "left" : "right",
      name: [ax.title, ax.unit ? `(${ax.unit})` : ""].filter(Boolean).join(" "),
      nameTextStyle: { color: TEXT, fontFamily: TEXT_FONT, fontSize: size, ...(horizontal ? {} : { align: side === "primary" ? "left" : "right" }) },
      min: pct ? 0 : ax.min ?? undefined, max: pct ? 100 : ax.max ?? undefined,
      ...(dec === 0 && !pct ? { minInterval: 1 } : {}),  // tam sayılı eksende adım tam sayı: aynı sayı iki kez yazılmaz
      splitLine: { show: ax.grid, lineStyle: { color: GRID } }, axisLine: { show: false }, axisTick: { show: false },
      axisLabel: { color: TEXT, fontFamily: NUM_FONT, fontSize: size, hideOverlap: true,
                   formatter: (v: number) => (pct ? `%${formatNumber(v, 0)}` : formatNumber(v, Number.isInteger(v) ? 0 : Math.max(1, dec))) },
    };
  });

  const titleSize = Math.round(size * TITLE_SCALE[config.title_size]);
  const titleRoom = config.title ? titleSize * 1.9 : 0;
  const legendAt = config.legend.position === "right" && opts.narrow ? "bottom" : config.legend.position;
  const legend = {
    show: config.legend.show && drawn.length > 0, type: "scroll", data: drawn.map((d) => d.name),
    textStyle: { color: STRONG, fontFamily: TEXT_FONT, fontSize: size }, itemWidth: 14, itemHeight: 10,
    ...(legendAt === "right" ? { orient: "vertical", right: 4, top: "middle" } : legendAt === "bottom" ? { bottom: 0, left: "center" } : { top: titleRoom, left: "center" }),
  };
  const withLegend = legend.show;
  const tooltip = {
    trigger: "axis", confine: true, transitionDuration: 0,  // ipucu fareyi gecikmesiz izler: bantla aynı dönemi gösterir
    axisPointer: { type: "shadow", animation: false, shadowStyle: { color: BAND, opacity: 0.7 } },
    textStyle: { color: STRONG, fontFamily: TEXT_FONT, fontSize: size },
    formatter: (params: { dataIndex: number; seriesIndex: number; marker: string }[]) => {
      const rows = params.filter((p) => p.seriesIndex < drawn.length);
      if (!rows.length) return "";
      const j = rows[0].dataIndex;
      const key = data.x.values[j];
      const week = data.x.bucket === "week" && typeof key?.key === "string" && key.key !== OTHER_KEY ? `<div>${esc(T.weekOf(formatDate(isoDate(key.key))))}</div>` : "";
      const lines = rows.map((p) => {
        const d = drawn[p.seriesIndex];
        const raw = d.raw[j];
        const value = raw === null ? "–" : formatNumber(raw, d.decimals) + (percent && d.bar && d.shown[j] !== null ? ` (%${formatNumber(d.shown[j]!, 1)})` : "");
        return `<div>${p.marker} ${esc(d.name)}: <span style="font-family:${NUM_FONT};font-variant-numeric:tabular-nums">${value}</span></div>`;
      });
      return `<div style="font-weight:600">${esc(cats[j])}</div>${week}${lines.join("")}`;
    },
  };
  const option = {
    animation: false, color: PALETTE, textStyle: { fontFamily: TEXT_FONT, fontSize: size },
    title: { show: Boolean(config.title), text: config.title, top: 0, left: config.title_align,
             textStyle: { color: STRONG, fontFamily: TEXT_FONT, fontSize: titleSize, fontWeight: 600 } },
    grid: {
      containLabel: true, left: 8, right: withLegend && legendAt === "right" ? 150 : 16,
      top: titleRoom + (withLegend && legendAt === "top" ? size * 2.2 : 0) + (values.some((v) => v.name) ? size * 1.8 : 8) + 4,
      bottom: (withLegend && legendAt === "bottom" ? size * 2.4 : 0) + (config.axes.x.title && !horizontal ? size * 1.6 : 0) + 6,
    },
    legend, tooltip,
    xAxis: horizontal ? values : category, yAxis: horizontal ? category : values,
    series,
  };
  return { option, mixed };
}

// Grafik standardı (K-178, docs/12): ayar + veri → çizim seçenekleri. Kütüphane çizmeden, üretilen seçenek nesnesi sınanır.
import { describe, expect, it } from "vitest";

import { col, COLUMNS } from "../../table/testBackend";
import {
  type ChartConfig, type ChartData, chartRequest, chartSelection, defaultChart, effectiveBucket, finerBuckets, fitChart, newSeries, normalizeChart, OTHER_KEY,
  withSeriesFn, withXField,
} from "./chartModel";
import { bucketLabel, buildOption, isEmptyData, keyLabel, PALETTE, seriesLabel, THRESHOLD_COLOR } from "./chartOption";

type Opt = Record<string, any>;  // eslint-disable-line @typescript-eslint/no-explicit-any
const base = (patch: Partial<ChartConfig> = {}): ChartConfig => ({ ...defaultChart(COLUMNS, ["MaterialLevel", "StockCoverageDays"])!, ...patch });
const data = (patch: Partial<ChartData> = {}): ChartData => ({
  x: { kind: "category", bucket: null, values: ["A", "B", "C"].map((key) => ({ key, label: key })), other: false }, split: null,
  series: [{ id: "s1", data: [[10, 20, 30]], mixed_units: false }], rows: 60, week_start: "Pazartesi", ...patch });
const build = (config: ChartConfig, d: ChartData = data(), opts = {}) => buildOption(config, d, COLUMNS, opts).option as Opt;
const two = (patch: Partial<ChartConfig> = {}) => base({ series: [newSeries("s1", "SafetyStock", "sum"), newSeries("s2", "StockCoverageDays", "avg")], ...patch });
const twoData = data({ series: [{ id: "s1", data: [[10, 20, 30]], mixed_units: false }, { id: "s2", data: [[30, 20, 0]], mixed_units: false }] });

describe("ayar modeli", () => {
  it("ilk açılış: görünür ilk tarih alanı aylık, ilk sayısal alan toplam ve çubuk; tarih yoksa ilk kategori; sayı yoksa adet", () => {
    const c = defaultChart(COLUMNS, ["Code", "Name", "SafetyStock", "UpdatedAt"])!;
    expect([c.x, c.series.map((s) => [s.field, s.fn, s.type]), c.open, c.layout]).toEqual([{ field: "UpdatedAt", bucket: "month" }, [["SafetyStock", "sum", "bar"]], true, "split"]);
    const texts = defaultChart(COLUMNS, ["Name", "Code"])!;                                                         // görünürde tarih yoksa görünür ilk kategori
    expect([texts.x, texts.series[0].field]).toEqual([{ field: "Name", bucket: null }, "SafetyStock"]);                // sayı görünürde yoksa listenin alanlarından
    const plain = defaultChart([col("Code", "Kod", "text", "text"), col("Name", "Ad", "text", "text")], ["Name", "Code"])!;
    expect([plain.x, plain.series[0].fn, plain.series[0].field]).toEqual([{ field: "Name", bucket: null }, "count", null]);
    expect(defaultChart([col("Qty", "Miktar", "number", "number")], ["Qty"])).toBeNull();                         // eksen olacak alan yok
  });

  it("kayıtlı içerik tam biçime gelir; alanı kalkan seri, kırılım ve ona bağlı çizgi atılır; eksen gitmişse grafik de", () => {
    const n = normalizeChart({ x: { field: "MaterialLevel", bucket: null }, series: [{ id: "a", field: null, fn: "count" } as never] });
    expect(n.series[0]).toEqual({ id: "a", field: null, fn: "count", type: "bar", line: "solid", axis: "primary", color: null, labels: { show: false, decimals: 0, zero: false }, threshold: null });
    expect([n.height, n.bars, n.legend, n.axes.secondary.grid]).toEqual([0.45, { mode: "group", horizontal: false, totals: false, width: "medium" }, { show: true, position: "top" }, false]);
    expect([n.limit, n.title_align, n.title_size]).toEqual([30, "left", "medium"]);                                    // yeni ayarların varsayılanları; panel durumu modelde yok
    expect(Object.keys(n)).not.toContain("panel");
    const c = two({ split: "Eski", ref_lines: [{ id: "r1", kind: "avg", value: null, series: "s2", name: "", color: null, show_name: true, show_value: true }, { id: "r2", kind: "value", value: 5, series: null, name: "", color: null, show_name: true, show_value: true }] });
    const fitted = fitChart(c, COLUMNS.filter((x) => x.field !== "StockCoverageDays"))!;
    expect([fitted.series.map((s) => s.id), fitted.split, fitted.ref_lines.map((r) => r.id)]).toEqual([["s1"], null, ["r2"]]);
    expect(fitChart(c, COLUMNS.filter((x) => x.field !== "MaterialLevel"))).toBeNull();
  });

  it("istek yalnız veriyi değiştiren ayarları taşır; senaryo yalnız haftalık dönemde gider; eksen ve toplama değişince alanlar uyar", () => {
    const c = two({ split: "MaterialGroup", order: "name" });
    const req = chartRequest(c, [{ field: "Name", op: "contains", value: "mil" }], 7);
    expect(req).toEqual({ filters: [{ field: "Name", op: "contains", value: "mil" }], x: { field: "MaterialLevel", bucket: null }, split: "MaterialGroup", order: "name",
                          series: [{ id: "s1", field: "SafetyStock", fn: "sum" }, { id: "s2", field: "StockCoverageDays", fn: "avg" }], limit: 30 });
    expect(chartRequest({ ...c, limit: 10 }, [], 7).limit).toBe(10);                                                 // gösterilecek değer sayısı isteğe gider
    const look = { ...c, bars: { mode: "stack" as const, horizontal: true, totals: true, width: "medium" as const }, title: "x", series: c.series.map((s) => ({ ...s, type: "line" as const, color: "#112233" })) };
    expect(JSON.stringify(chartRequest(look, req.filters, 7))).toBe(JSON.stringify(req));                           // görünüş ayarı isteği değiştirmez
    const weekly = withXField({ ...c, x: { field: "MaterialLevel", bucket: null } }, COLUMNS.find((x) => x.field === "UpdatedAt")!);
    expect(weekly.x).toEqual({ field: "UpdatedAt", bucket: "month" });
    expect(chartRequest({ ...weekly, x: { ...weekly.x, bucket: "week" } }, [], 7).scenario_id).toBe(7);
    expect(withXField(c, COLUMNS.find((x) => x.field === "MaterialGroup")!).split).toBeNull();                     // kırılım eksenle aynı kalamaz
    expect(withSeriesFn(c.series[0], "count", COLUMNS).field).toBeNull();
    expect(withSeriesFn(newSeries("s9", null, "count"), "max", COLUMNS)).toMatchObject({ fn: "max", field: "SafetyStock" });
  });
});

describe("seçim ve iniş (K-179)", () => {
  const monthly = (): ChartConfig => ({ ...base(), x: { field: "UpdatedAt", bucket: "month" } });

  it("ince dönemler: ara düzey atlanabilir; günden aşağısı yok; kategori ekseninde iniş yok", () => {
    expect([finerBuckets("year"), finerBuckets("month"), finerBuckets("week"), finerBuckets("day"), finerBuckets(null)])
      .toEqual([["quarter", "month", "week", "day"], ["week", "day"], ["day"], [], []]);
  });

  it("iniş geçerli dönemi değiştirir, görünümün dönemini değil; grafik isteği inilen dönemi taşır; senaryo haftada gider", () => {
    const c = monthly();
    const drill = [{ bucket: "month" as const, keys: ["2026-11-01"], to: "week" as const }];
    expect(effectiveBucket(c, { items: [], drill })).toBe("week");
    expect(c.x.bucket).toBe("month");
    const req = chartRequest(c, [], 7, drill);
    expect([req.x, req.within, req.scenario_id]).toEqual([{ field: "UpdatedAt", bucket: "week" }, [{ bucket: "month", keys: ["2026-11-01"] }], 7]);
    expect(chartRequest(c, [], 7).within).toBeUndefined();
    const deep = chartRequest(c, [], 7, [...drill, { bucket: "week" as const, keys: ["2026-11-16"], to: "day" as const }]);
    expect([deep.x.bucket, deep.within, deep.scenario_id]).toEqual(["day", [{ bucket: "month", keys: ["2026-11-01"] }, { bucket: "week", keys: ["2026-11-16"] }], 7]);
  });

  it("tablo sorgusuna giden seçim: öğeler ve inilen dönem; kırılımda parça; seçim yoksa ya da grafik kapalıysa yok", () => {
    const c = monthly();
    expect(chartSelection(c, { items: [], drill: [] }, 7)).toBeUndefined();
    expect(chartSelection({ ...c, open: false }, { items: [{ x: "2026-11-01" }], drill: [] }, 7)).toBeUndefined();
    expect(chartSelection(null, { items: [{ x: "2026-11-01" }], drill: [] }, 7)).toBeUndefined();
    expect(chartSelection(c, { items: [{ x: "2026-11-01" }, { x: null }], drill: [] }, 7))
      .toEqual({ x: { field: "UpdatedAt", bucket: "month" }, split: null, items: [{ x: "2026-11-01" }, { x: null }], within: [] });
    expect(chartSelection({ ...c, split: "MaterialGroup" }, { items: [{ x: "2026-11-01", p: "Çubuk" }], drill: [] }, 7)?.items).toEqual([{ x: "2026-11-01", p: "Çubuk" }]);
    const drilled = chartSelection(c, { items: [], drill: [{ bucket: "month", keys: ["2026-11-01"], to: "week" }] }, 7)!;
    expect(drilled).toEqual({ x: { field: "UpdatedAt", bucket: "week" }, split: null, items: [], within: [{ bucket: "month", keys: ["2026-11-01"] }], scenario_id: 7 });
  });

  it("seçilenler canlı, ötekiler soluk; seçim yokken hiçbiri soluk değil; tıklanan parça öğesine çevrilir, Diğer seçilemez", () => {
    const d = data({ x: { kind: "category", bucket: null, values: [{ key: "A", label: "A" }, { key: null, label: null }, { key: OTHER_KEY, label: null }], other: true } });
    const plain = buildOption(base(), d, COLUMNS);
    expect((plain.option as Opt).series[0].data.map((p: Opt) => p.itemStyle.opacity)).toEqual([undefined, undefined, undefined]);
    expect([plain.hit(0, 0), plain.hit(0, 1), plain.hit(0, 2), plain.hit(5, 0)]).toEqual([{ x: "A" }, { x: null }, "other", null]);   // (Boş) seçilir, Diğer seçilmez
    const picked = buildOption(base(), d, COLUMNS, { selected: [{ x: null }] });
    expect((picked.option as Opt).series[0].data.map((p: Opt) => p.itemStyle.opacity)).toEqual([0.35, undefined, 0.35]);
    const line = buildOption(base({ series: [newSeries("s1", "StockCoverageDays", "sum", "line")] }), d, COLUMNS, { selected: [{ x: "A" }] });
    expect((line.option as Opt).series[0].data.map((p: Opt) => p.itemStyle?.opacity)).toEqual([undefined, 0.35, 0.35]);   // çizgide nokta da seçilir
    const split = data({ split: { field: "MaterialGroup", values: [{ key: "Çubuk", label: "Çubuk" }, { key: OTHER_KEY, label: null }], other: true },
                         series: [{ id: "s1", data: [[1, 2, 3], [4, 5, 6]], mixed_units: false }] });
    const parts = buildOption(base({ split: "MaterialGroup" }), split, COLUMNS, { selected: [{ x: "B", p: "Çubuk" }] });
    expect([parts.hit(0, 1), parts.hit(1, 1)]).toEqual([{ x: "B", p: "Çubuk" }, "other"]);
    expect((parts.option as Opt).series[0].data.map((p: Opt) => p.itemStyle.opacity)).toEqual([0.35, undefined, 0.35]);
  });
});

describe("Say, Benzersiz say, çizgi biçimi, yakınlaştırma (K-179)", () => {
  it("Say eski Adet'tir (kayıttaki değer count); Benzersiz say her alanda, ondalıksız; hesaplama değişince alan uyar", () => {
    const byField = new Map(COLUMNS.map((c) => [c.field, c]));
    expect([seriesLabel({ field: null, fn: "count" }, byField), seriesLabel({ field: "Name", fn: "distinct" }, byField)]).toEqual(["Say", "Malzeme adı · Benzersiz say"]);
    expect(normalizeChart({ x: { field: "MaterialLevel", bucket: null }, series: [{ id: "a", field: null, fn: "count" } as never] }).series[0].fn).toBe("count");  // eski kayıt
    expect(withSeriesFn(newSeries("s1", null, "count"), "distinct", COLUMNS)).toMatchObject({ fn: "distinct", field: "Code" });
    expect(withSeriesFn(newSeries("s1", "Name", "distinct"), "sum", COLUMNS)).toMatchObject({ fn: "sum", field: "SafetyStock" });   // metin alanı toplanamaz
    const d = data({ series: [{ id: "s1", data: [[3, 2, 2]], mixed_units: false }] });
    const o = build(base({ series: [{ ...newSeries("s1", "Name", "distinct"), labels: { show: true, decimals: 0, zero: false } }] }), d);
    expect([o.series[0].name, o.yAxis[0].minInterval, o.series[0].label.formatter({ dataIndex: 0 })]).toEqual(["Malzeme adı · Benzersiz say", 1, "3"]);
  });

  it("Toplamı göster Benzersiz say serilerini toplamaz", () => {
    const c = base({ bars: { mode: "stack", horizontal: false, totals: true, width: "medium" },
                     series: [newSeries("s1", "StockCoverageDays", "sum"), newSeries("s2", "Name", "distinct")] });
    const o = build(c, twoData);
    expect([0, 1, 2].map((i) => o.series[2].label.formatter({ dataIndex: i }))).toEqual(["10", "20", "30"]);        // yalnız birinci seri
    const only = build(base({ bars: { mode: "stack", horizontal: false, totals: true, width: "medium" }, series: [newSeries("s1", "Name", "distinct")] }));
    expect(only.series).toHaveLength(1);                                                                            // toplanacak seri yok: toplam etiketi de yok
  });

  it("çizgi biçimi: düz ya da kesikli; çubukta etkisiz", () => {
    const o = build(base({ series: [{ ...newSeries("s1", "StockCoverageDays", "sum", "line"), line: "dashed" }, { ...newSeries("s2", "StockCoverageDays", "avg", "area") },
                                    { ...newSeries("s3", null, "count"), line: "dashed" }] }),
                    data({ series: ["s1", "s2", "s3"].map((id) => ({ id, data: [[1, 2, 3]], mixed_units: false })) }));
    expect([o.series[0].lineStyle.type, o.series[1].lineStyle.type, o.series[2].lineStyle]).toEqual(["dashed", "solid", undefined]);
  });

  it("yakınlaştırma kaydırıcısı: yalnız zaman ekseninde; yatay çubukta dikey; kapalıyken yok", () => {
    const dated = data({ x: { kind: "date", bucket: "day", values: ["2026-11-16", "2026-11-17", "2026-11-18"].map((key) => ({ key, label: null })), other: false } });
    const zoomed = (patch: Partial<ChartConfig> = {}) => ({ ...base(patch), x: { field: "UpdatedAt", bucket: "day" as const }, axes: { ...base().axes, x: { title: "", zoom: true } } });
    const o = build(zoomed(), dated);
    expect(o.dataZoom).toHaveLength(1);
    expect([o.dataZoom[0].type, o.dataZoom[0].xAxisIndex, o.dataZoom[0].showDetail]).toEqual(["slider", 0, false]);
    expect(o.dataZoom[0].filterMode).toBe("empty");                                    // kaydırırken dikey eksen sınırları değişmez
    expect(o.dataZoom[0].dataBackground.areaStyle.opacity).toBe(1);                    // veri silueti belirgin
    expect(o.dataZoom[0].height).toBeGreaterThanOrEqual(24);
    expect(build(zoomed({ bars: { mode: "group", horizontal: true, totals: false, width: "medium" } }), dated).dataZoom[0].yAxisIndex).toBe(0);
    expect(build({ ...base(), axes: { ...base().axes, x: { title: "", zoom: true } } }).dataZoom).toBeUndefined();   // kategori ekseni
    expect(build({ ...zoomed(), axes: base().axes }, dated).dataZoom).toBeUndefined();
  });
});

describe("etiketler", () => {
  it("dönem etiketleri: gün, hafta, ay, çeyrek, yıl; saat yok", () => {
    expect([bucketLabel("2026-11-16", "day"), bucketLabel("2026-11-16", "week"), bucketLabel("2026-11-01", "month"), bucketLabel("2026-10-01", "quarter"), bucketLabel("2026-01-01", "year")])
      .toEqual(["16.11.2026", "H47 2026", "Kas 2026", "Ç4 2026", "2026"]);
    expect(bucketLabel("2026-11-14", "week")).toBe("H47 2026");   // hafta Cumartesi başlasa da aynı hafta numarası
  });

  it("Diğer, boş, Evet/Hayır; seri adı alan · toplama, adet alansız", () => {
    expect([keyLabel({ key: OTHER_KEY, label: null }), keyLabel({ key: null, label: null }), keyLabel({ key: true, label: "Evet" }), keyLabel({ key: 5, label: "5" })])
      .toEqual(["Diğer", "(Boş)", "Evet", "5"]);
    const byField = new Map(COLUMNS.map((c) => [c.field, c]));
    expect([seriesLabel({ field: "SafetyStock", fn: "sum" }, byField), seriesLabel({ field: null, fn: "count" }, byField)]).toEqual(["Güvenlik stoğu · Toplam", "Say"]);                     // eski adı "Adet" (K-179)
  });
});

describe("çizim seçenekleri", () => {
  it("palet: indigo, petrol, hardal, kurşun, erik, kahve ve açık tonları; kırmızı ve kiremit yok; eşik önerileri açık kiremit ve açık hardal", () => {
    expect(PALETTE.slice(0, 6)).toEqual(["#4f5bd5", "#2e7d7a", "#b8860b", "#5a606b", "#8e4585", "#8a6440"]);
    expect(PALETTE).toHaveLength(12);
    const reddish = (hex: string) => { const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)); return r > 170 && g < 110 && b < 110; };
    expect(PALETTE.filter(reddish)).toEqual([]);
    expect(THRESHOLD_COLOR).toBe("#f7dcd5");                                                                          // eşik üstü rengin varsayılanı açık kiremit
  });

  it("varsayılan: çubuk, canlandırma yok, üst köşeler yuvarlak, renk paletten sırayla, eksen etiketleri Inter ve Türkçe sayı", () => {
    const o = build(two(), twoData);
    expect(o.animation).toBe(false);
    expect(o.series.map((s: Opt) => [s.type, s.color, s.stack])).toEqual([["bar", PALETTE[0], undefined], ["bar", PALETTE[1], undefined]]);
    expect(o.series[0].data[0]).toEqual({ value: 10, itemStyle: { borderRadius: [3, 3, 0, 0] } });
    expect(o.xAxis.data).toEqual(["A", "B", "C"]);
    expect(o.yAxis).toHaveLength(1);
    expect(o.yAxis[0].axisLabel.fontFamily).toContain("Inter");
    expect([o.yAxis[0].axisLabel.formatter(12345.5), o.yAxis[0].axisLabel.formatter(2000)]).toEqual(["12.345,50", "2.000"]);
    expect(o.series[0].labelLayout).toEqual({ hideOverlap: true });                                                // etiketler çakışmaz
    expect([o.series[0].barCategoryGap, o.series[0].barMaxWidth]).toEqual(["34%", 96]);                            // çubuk genişliği kategori sayısına göre dengeli
    expect([o.tooltip.transitionDuration, o.tooltip.axisPointer.animation, o.tooltip.axisPointer.shadowStyle.color]).toEqual([0, false, "#f4f5f7"]);  // ipucu ve bant gecikmesiz; bant çok açık gri
    expect(o.xAxis.axisLabel.hideOverlap).toBe(true);
  });

  it("tipler birleşir: çizgi düz (eğimsiz), kademeli, alan; ikincil eksen yalnız kullanılınca; serbest renk", () => {
    const c = base({ series: [newSeries("s1", "SafetyStock", "sum"), { ...newSeries("s2", "StockCoverageDays", "avg", "line"), axis: "secondary", color: "#112233" },
                              newSeries("s3", null, "count", "step"), newSeries("s4", null, "count", "area")] });
    const d = data({ series: ["s1", "s2", "s3", "s4"].map((id) => ({ id, data: [[1, 2, 3]], mixed_units: false })) });
    const o = build(c, d);
    expect(o.series.map((s: Opt) => [s.type, s.smooth, s.step, Boolean(s.areaStyle), s.yAxisIndex])).toEqual([
      ["bar", undefined, undefined, false, 0], ["line", false, undefined, false, 1], ["line", false, "end", false, 0], ["line", false, undefined, true, 0]]);
    const smooth = build(base({ series: [newSeries("s1", "StockCoverageDays", "sum", "smooth")] }));
    expect([smooth.series[0].type, smooth.series[0].smooth, smooth.series[0].smoothMonotone]).toEqual(["line", true, "x"]);  // eğimli çizgi monoton: veri aralığının dışına taşmaz
    expect(o.series[1].color).toBe("#112233");
    expect(o.yAxis.map((a: Opt) => a.position)).toEqual(["left", "right"]);
    expect(o.yAxis[1].splitLine.show).toBe(false);                                                                 // kılavuz yalnız birincil eksenden
  });

  it("yığılmış: yalnız en üst parça yuvarlak; %100: yüzdeye çevrilir, eksen %0–%100, ipucu gerçek değeri ve yüzdeyi yazar", () => {
    const stacked = build(two({ bars: { mode: "stack", horizontal: false, totals: false, width: "medium" } }), twoData);
    expect(stacked.series.map((s: Opt) => s.stack)).toEqual(["primary", "primary"]);
    expect(stacked.series[0].data.map((p: Opt) => p.itemStyle.borderRadius)).toEqual([0, 0, [3, 3, 0, 0]]);        // C'de ikinci seri 0: üst parça ilk seri
    expect(stacked.series[1].data.map((p: Opt) => p.itemStyle.borderRadius)).toEqual([[3, 3, 0, 0], [3, 3, 0, 0], 0]);
    const pct = build(two({ bars: { mode: "percent", horizontal: false, totals: false, width: "medium" } }), twoData);
    expect(pct.series[0].data.map((p: Opt) => p.value)).toEqual([25, 50, 100]);
    expect([pct.yAxis[0].min, pct.yAxis[0].max, pct.yAxis[0].axisLabel.formatter(50)]).toEqual([0, 100, "%50"]);
    const tip = pct.tooltip.formatter([{ dataIndex: 0, seriesIndex: 0, marker: "•" }, { dataIndex: 0, seriesIndex: 1, marker: "•" }]);
    expect(tip).toContain("Güvenlik stoğu · Toplam");
    expect(tip).toMatch(/10,00 \(%25,0\)/);
    expect(tip).toMatch(/30,0 \(%75,0\)/);
  });

  it("yığılmışta etiket parçanın içinde ve sade: çevre çizgisi yok, yazı rengi parçaya göre, sığmayan gösterilmez; yan yanada çevre çizgili", () => {
    const labelled = (mode: "group" | "stack" | "percent") => build(two({ bars: { mode, horizontal: false, totals: false, width: "medium" },
      series: [{ ...newSeries("s1", "SafetyStock", "sum"), labels: { show: true, decimals: 0, zero: false } }, { ...newSeries("s2", "StockCoverageDays", "avg"), color: "#f7ebc4", labels: { show: true, decimals: 0, zero: false } }] }), twoData);
    for (const mode of ["stack", "percent"] as const) {
      const [dark, light] = labelled(mode).series;
      expect([dark.label.position, dark.label.textBorderWidth, dark.label.color]).toEqual(["inside", undefined, "#ffffff"]);   // koyu parçada beyaz yazı
      expect([light.label.position, light.label.textBorderWidth, light.label.color]).toEqual(["inside", undefined, "#1f2329"]); // açık parçada koyu yazı
      expect(dark.labelLayout({ rect: { width: 40, height: 30 }, labelRect: { width: 20, height: 14 } })).toEqual({ hideOverlap: true });
      expect(dark.labelLayout({ rect: { width: 40, height: 8 }, labelRect: { width: 20, height: 14 } })).toEqual({ hideOverlap: true, fontSize: 0 });   // parçaya sığmıyor
      expect(dark.labelLayout({ rect: { width: 12, height: 30 }, labelRect: { width: 20, height: 14 } })).toMatchObject({ fontSize: 0 });
    }
    const side = labelled("group").series[0];
    expect([side.label.position, side.label.textBorderWidth, side.labelLayout]).toEqual(["top", 2.5, { hideOverlap: true }]);
  });

  it("yığılmışta Toplamı göster: yığının üstünde toplam; göstergede ve ipucunda yer almaz; %100'de ve yan yanada yok", () => {
    const o = build(two({ bars: { mode: "stack", horizontal: false, totals: true, width: "medium" } }), twoData);
    expect(o.series).toHaveLength(3);
    const total = o.series[2];
    expect([total.stack, total.name, total.data, total.label.position]).toEqual(["primary", "", [0, 0, 0], "top"]);
    expect([0, 1, 2].map((i) => total.label.formatter({ dataIndex: i }))).toEqual(["40", "40", "30"]);                  // seri etiketlerinin ondalığıyla
    expect(o.legend.data).toEqual(["Güvenlik stoğu · Toplam", "Stok gün kapsamı · Ortalama"]);
    expect(o.tooltip.formatter([{ dataIndex: 0, seriesIndex: 2, marker: "" }])).toBe("");
    expect(build(two({ bars: { mode: "percent", horizontal: false, totals: true, width: "medium" } }), twoData).series).toHaveLength(2);
    expect(build(two({ bars: { mode: "group", horizontal: false, totals: true, width: "medium" } }), twoData).series).toHaveLength(2);
  });

  it("tam sayılı eksende adım tam sayıdır (aynı sayı iki kez yazılmaz); ondalıklı ve yüzde ekseninde serbest", () => {
    const counts = build(base({ series: [newSeries("s1", null, "count")] }));
    expect(counts.yAxis[0].minInterval).toBe(1);
    expect(build(two(), twoData).yAxis[0].minInterval).toBeUndefined();
    expect(build(base({ series: [newSeries("s1", null, "count")], bars: { mode: "percent", horizontal: false, totals: false, width: "medium" } })).yAxis[0].minInterval).toBeUndefined();
  });

  it("çubuk genişliği: İnce · Orta · Kalın bütün çubuk serileri için ortak; kategori aralığının oranı ve üst sınır kademeyle değişir", () => {
    const sized = (width: "thin" | "medium" | "thick") => build(two({ bars: { mode: "group", horizontal: false, totals: false, width } }), twoData).series;
    expect(sized("thin").map((s: Opt) => [s.barCategoryGap, s.barMaxWidth])).toEqual([["55%", 60], ["55%", 60]]);
    expect(sized("medium").map((s: Opt) => [s.barCategoryGap, s.barMaxWidth])).toEqual([["34%", 96], ["34%", 96]]);
    expect(sized("thick").map((s: Opt) => [s.barCategoryGap, s.barMaxWidth])).toEqual([["16%", 144], ["16%", 144]]);
    const total = build(two({ bars: { mode: "stack", horizontal: false, totals: true, width: "thick" } }), twoData).series[2];
    expect([total.barCategoryGap, total.barMaxWidth]).toEqual(["16%", 144]);                                       // toplam etiketi de aynı genişlikte
    expect(normalizeChart({ x: { field: "MaterialLevel", bucket: null }, series: [{ id: "a", field: null, fn: "count" } as never] }).bars.width).toBe("medium");
  });

  it("yatay çubuk: eksenler yer değiştirir, kategori yukarıdan aşağı, köşe sağda", () => {
    const o = build(base({ bars: { mode: "group", horizontal: true, totals: false, width: "medium" } }));
    expect([o.yAxis.type, o.yAxis.inverse, o.xAxis[0].type, o.series[0].xAxisIndex]).toEqual(["category", true, "value", 0]);
    expect(o.series[0].data[0].itemStyle.borderRadius).toEqual([0, 3, 3, 0]);
  });

  it("eşik: aşan çubuk eşik üstü renkte, çizgide nokta işaretli; eşik çizgisi adıyla", () => {
    const th = { value: 15, color: "#F7DCD5", line: true };
    const bar = build(base({ series: [{ ...newSeries("s1", "StockCoverageDays", "sum"), threshold: th }] }));
    expect(bar.series[0].data.map((p: Opt) => p.itemStyle.color)).toEqual([undefined, "#F7DCD5", "#F7DCD5"]);
    expect(bar.series[0].markLine.data[0]).toMatchObject({ yAxis: 15, name: "Eşik 15" });
    const quiet = build(base({ series: [{ ...newSeries("s1", "StockCoverageDays", "sum"), threshold: { ...th, line: false } }] }));
    expect(quiet.series[0].markLine).toBeUndefined();                                                              // "Eşik çizgisini göster" kapalı: çizgi ve adı yok
    expect(quiet.series[0].data.map((p: Opt) => p.itemStyle.color)).toEqual([undefined, "#F7DCD5", "#F7DCD5"]);    // eşik üstü renk yine uygulanır
    const line = build(base({ series: [{ ...newSeries("s1", "StockCoverageDays", "sum", "line"), threshold: th }] }));
    expect(line.series[0].data.map((p: Opt) => p.itemStyle?.color)).toEqual([undefined, "#F7DCD5", "#F7DCD5"]);
    expect(line.series[0].data[1].symbolSize).toBeGreaterThan(line.series[0].symbolSize);
  });

  it("referans çizgisi: sabit değer ve serinin ortalaması, en düşüğü, en yükseği; adı ve değeri ucunda, kesikli", () => {
    const c = base({ ref_lines: [{ id: "r1", kind: "avg", value: null, series: "s1", name: "", color: null, show_name: true, show_value: true }, { id: "r2", kind: "value", value: 25, series: null, name: "Hedef", color: "#2E7D7A", show_name: true, show_value: true },
                                 { id: "r3", kind: "max", value: null, series: "s1", name: "Tepe", color: null, show_name: true, show_value: true }] });
    const lines = build(c).series[0].markLine.data;
    expect(lines.map((l: Opt) => [l.yAxis, l.name, l.lineStyle.type])).toEqual([[20, "Ortalama 20,0", "dashed"], [25, "Hedef 25", "dashed"], [30, "Tepe 30", "dashed"]]);
    expect(lines[1].lineStyle.color).toBe("#2E7D7A");
    const show = (show_name: boolean, show_value: boolean) => build(base({ ref_lines: [{ id: "r2", kind: "value", value: 25, series: null, name: "Hedef", color: null, show_name, show_value }] }))
      .series[0].markLine.data[0];
    expect([show(true, false).name, show(false, true).name, show(false, false).name, show(false, false).label.show]).toEqual(["Hedef", "25", "", false]);  // adı ve değeri ayrı ayrı
  });

  it("veri etiketi: seri başına açılır, ondalığıyla; kapalıyken yok", () => {
    const o = build(base({ series: [{ ...newSeries("s1", "StockCoverageDays", "sum"), labels: { show: true, decimals: 1, zero: false } }] }));
    expect([o.series[0].label.show, o.series[0].label.formatter({ dataIndex: 1 }), o.series[0].label.fontFamily.includes("Inter")]).toEqual([true, "20,0", true]);
    expect(build(base()).series[0].label.show).toBe(false);
    const zeros = data({ series: [{ id: "s1", data: [[0, 20, null]], mixed_units: false }] });
    const label = (zero: boolean) => build(base({ series: [{ ...newSeries("s1", "StockCoverageDays", "sum"), labels: { show: true, decimals: 0, zero } }] }), zeros).series[0].label.formatter;
    expect([0, 1, 2].map((i) => label(false)({ dataIndex: i }))).toEqual(["", "20", ""]);                          // "Sıfır değerleri göster" kapalı: 0'ın etiketi yok
    expect([0, 1, 2].map((i) => label(true)({ dataIndex: i }))).toEqual(["0", "20", ""]);
  });

  it("kırılım: her seri kırılım değerlerine bölünür, renkler sırayla; Diğer ve boş adlarıyla", () => {
    const d = data({ split: { field: "MaterialGroup", values: [{ key: "Çubuk", label: "Çubuk" }, { key: null, label: null }, { key: OTHER_KEY, label: null }], other: true },
                     series: [{ id: "s1", data: [[1, 2, 3], [4, 5, 6], [7, 8, 9]], mixed_units: false }] });
    const o = build(base({ split: "MaterialGroup" }), d);
    expect(o.series.map((s: Opt) => [s.name, s.color])).toEqual([["Çubuk", PALETTE[0]], ["(Boş)", PALETTE[1]], ["Diğer", PALETTE[2]]]);
    expect(o.series[2].data.map((p: Opt) => p.value)).toEqual([7, 8, 9]);
  });

  it("tarih ekseni: dönem etiketleri; haftada ipucunda haftanın ilk günü; saat hiçbir yerde yok", () => {
    const d = data({ x: { kind: "date", bucket: "week", values: [{ key: "2026-11-16", label: null }, { key: "2026-11-23", label: null }, { key: null, label: null }], other: false } });
    const o = build(base({ x: { field: "UpdatedAt", bucket: "week" } }), d);
    expect(o.xAxis.data).toEqual(["H47 2026", "H48 2026", "(Boş)"]);
    const tip = o.tooltip.formatter([{ dataIndex: 0, seriesIndex: 0, marker: "" }]);
    expect(tip).toContain("16.11.2026 haftası");
    expect(tip).not.toMatch(/\d\d:\d\d/);
    expect(o.xAxis.axisLabel.fontFamily).toContain("Inter");
  });

  it("gösterge: açık ya da kapalı, konum; dar alanda Sağda alta iner; göstergeden gizleme kütüphanenin işidir; başlık ve eksen adı birimle", () => {
    expect(build(base()).legend).toMatchObject({ show: true, left: "center" });
    expect(build(base({ legend: { show: true, position: "right" } })).legend).toMatchObject({ orient: "vertical" });
    expect(build(base({ legend: { show: true, position: "right" } }), data(), { narrow: true }).legend).toMatchObject({ bottom: 0 });
    expect(build(base({ legend: { show: false, position: "top" } })).legend.show).toBe(false);
    const c = base({ title: "Açık miktar", axes: { x: { title: "Hafta", zoom: false }, primary: { title: "Miktar", unit: "adet", min: 0, max: 100, grid: false }, secondary: { title: "", unit: "", min: null, max: null, grid: false } } });
    const o = build(c);
    expect([o.title.text, o.title.show, o.xAxis.name, o.yAxis[0].name, o.yAxis[0].min, o.yAxis[0].max, o.yAxis[0].splitLine.show]).toEqual(["Açık miktar", true, "Hafta", "Miktar (adet)", 0, 100, false]);
    expect([o.title.left, o.title.textStyle.fontSize]).toEqual(["left", 14]);                                       // varsayılan: sol, orta
    const big = build({ ...c, title_align: "center", title_size: "large" });
    expect([big.title.left, big.title.textStyle.fontSize]).toEqual(["center", 17]);
    expect(build({ ...c, title_align: "right", title_size: "small" }).title).toMatchObject({ left: "right", textStyle: { fontSize: 12 } });
  });

  it("karışık birim: seri çizilmez, adı uyarıya girer; öteki seriler çizilir; ipucu veritabanından gelen metni kaçışlar", () => {
    const d = data({ series: [{ id: "s1", data: null, mixed_units: true }, { id: "s2", data: [[1, 2, 3]], mixed_units: false }] });
    const built = buildOption(two(), d, COLUMNS);
    expect(built.mixed).toEqual(["Güvenlik stoğu · Toplam"]);
    expect((built.option as Opt).series.map((s: Opt) => s.name)).toEqual(["Stok gün kapsamı · Ortalama"]);
    const evil = data({ x: { kind: "category", bucket: null, values: [{ key: "<b>x</b>", label: "<b>x</b>" }], other: false }, series: [{ id: "s1", data: [[1]], mixed_units: false }] });
    expect(build(base(), evil).tooltip.formatter([{ dataIndex: 0, seriesIndex: 0, marker: "" }])).toContain("&lt;b&gt;x&lt;/b&gt;");
  });

  it("boş veri", () => {
    expect(isEmptyData(data({ rows: 0 }))).toBe(true);
    expect(isEmptyData(data())).toBe(false);
  });
});

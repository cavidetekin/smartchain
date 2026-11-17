// Tablonun grafiği (K-178, docs/12 "Grafik standardı"): şerit simgesi, bölünmüş ve tam ekran, ayar paneli, veri isteği, görünümle kaydetme, hâller.
// Çizim kütüphanesi sahtelenir; ona verilen seçenek nesnesi sınanır.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { calls, chartData, openTable, savedView, useTableTestSetup } from "./testBackend";

const drawn = vi.hoisted(() => ({ options: [] as Record<string, any>[], disposed: 0 }));  // eslint-disable-line @typescript-eslint/no-explicit-any
vi.mock("../ui/chart/echarts", () => ({
  createChart: () => ({ setOption: (o: Record<string, unknown>) => { drawn.options.push(o); }, resize: () => {}, dispose: () => { drawn.disposed += 1; } }),
}));

useTableTestSetup();
beforeEach(() => { drawn.options.length = 0; drawn.disposed = 0; });

const last = () => drawn.options[drawn.options.length - 1];
const lastChart = () => calls.charts[calls.charts.length - 1];
const pane = () => screen.getByTestId("chart-pane");
const chartButton = () => screen.getByRole("button", { name: "Grafik" });
const section = (name: string) => within(screen.getByRole("complementary", { name: "Grafik ayarları" })).getByRole("button", { name: new RegExp(`^${name}`) });
const CHART = {
  v: 1 as const, open: true, layout: "split" as const, height: 0.6, x: { field: "MaterialLevel", bucket: null }, split: null, order: "name" as const, limit: 30,
  series: [{ id: "s1", field: "StockCoverageDays", fn: "avg" as const, type: "line" as const, axis: "primary" as const, color: "#2E7D7A", labels: { show: true, decimals: 1, zero: false }, threshold: null }],
  bars: { mode: "group" as const, horizontal: false, totals: false, width: "medium" as const }, axes: { x: { title: "" }, primary: { title: "", min: null, max: null, unit: "", grid: true }, secondary: { title: "", min: null, max: null, unit: "", grid: false } },
  ref_lines: [], legend: { show: true, position: "top" as const }, title: "Seviye", title_align: "left" as const, title_size: "medium" as const,
};
const settings = () => within(pane()).getByRole("button", { name: "Grafik ayarları" });
/** Ayar panelini açar (her açılışta kapalı gelir) ve istenen bölümleri genişletir (hepsi kapalı gelir). */
async function openPanel(user: ReturnType<typeof userEvent.setup>, ...sections: string[]) {
  if (!screen.queryByRole("complementary", { name: "Grafik ayarları" })) await user.click(settings());
  for (const name of sections) if (section(name).getAttribute("aria-expanded") !== "true") await user.click(section(name));
  return screen.getByRole("complementary", { name: "Grafik ayarları" });
}

async function openChart(opts?: Parameters<typeof openTable>[0]) {
  const user = userEvent.setup();
  await openTable(opts);
  await user.click(chartButton());
  await screen.findByTestId("chart-pane");
  return user;
}

describe("tablonun grafiği (K-178)", () => {
  it("şeritte ⚙'nın solunda Grafik simgesi; açılınca indigo, boş gelmez: ilk tarih alanı aylık, ilk sayısal alan toplam; tablo altta kalır", async () => {
    const user = userEvent.setup();
    await openTable();
    const tools = document.querySelector(".sc-table-tools") as HTMLElement;
    const names = within(tools).getAllByRole("button").map((b) => b.getAttribute("aria-label"));
    expect(names.slice(-2)).toEqual(["Grafik", "Tablo ayarları"]);
    expect(chartButton()).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByTestId("chart-pane")).toBeNull();
    await user.click(chartButton());
    await waitFor(() => expect(calls.charts).toHaveLength(1));
    expect(lastChart()).toEqual({ filters: [], x: { field: "UpdatedAt", bucket: "month" }, split: null, order: "value", series: [{ id: "s1", field: "SafetyStock", fn: "sum" }], limit: 30 });
    expect(screen.queryByRole("complementary", { name: "Grafik ayarları" })).toBeNull();                              // grafik her açılışta panel kapalı gelir
    expect(settings()).toHaveAttribute("aria-pressed", "false");
    expect(chartButton()).toHaveAttribute("aria-pressed", "true");
    expect(chartButton().className).toContain("is-on");
    await waitFor(() => expect(last()?.xAxis.data).toEqual(["Eyl 2026", "Eki 2026", "Kas 2026"]));
    expect(last().series.map((s: { type: string; name: string }) => [s.type, s.name])).toEqual([["bar", "Güvenlik stoğu · Toplam"]]);
    const root = document.querySelector(".sc-table")!;
    const order = [...root.children].map((c) => c.getAttribute("data-testid") ?? c.getAttribute("role") ?? c.className.split(" ")[0]);
    expect(order.slice(-3)).toEqual(["chart-pane", "separator", "table-scroll"]);                                    // üstte grafik, tutamaç, altta tablo
    expect(screen.getByRole("img", { name: "Grafik" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Kaydedilmemiş değişiklik" })).toBeInTheDocument();                   // grafik görünümün parçası
  });

  it("tutamaç yüksekliği değiştirir; ⤢ tam ekran tabloyu kaplar ve geri döner; ✕ kapatır, görünümde grafik yoksa iz kalmaz", async () => {
    const user = await openChart();
    const split = screen.getByRole("separator", { name: "Grafik ve tablo arasındaki ayraç" });
    expect(split).toHaveAttribute("aria-valuenow", "45");
    fireEvent.keyDown(split, { key: "ArrowDown" });
    expect(screen.getByRole("separator", { name: "Grafik ve tablo arasındaki ayraç" })).toHaveAttribute("aria-valuenow", "50");
    expect(pane().style.flex).toBe("0.5 1 0px");
    await user.click(within(pane()).getByRole("button", { name: "Tam ekran" }));
    expect(screen.getByTestId("table-scroll")).not.toBeVisible();
    expect(screen.queryByRole("separator", { name: "Grafik ve tablo arasındaki ayraç" })).toBeNull();
    await user.click(within(pane()).getByRole("button", { name: "Bölünmüş görünüm" }));
    expect(screen.getByTestId("table-scroll")).toBeVisible();
    await user.click(within(pane()).getByRole("button", { name: "Grafiği kapat" }));
    expect(screen.queryByTestId("chart-pane")).toBeNull();
    expect(chartButton()).toHaveAttribute("aria-pressed", "false");
    expect(screen.queryByRole("img", { name: "Kaydedilmemiş değişiklik" })).toBeNull();
  });

  it("ayar paneli: ☰ ile açılır, altı bölüm de kapalı gelir, Kaydet yok; veri ayarı yeniden sorar (hafta senaryoyla), görünüş ayarı sormaz ve anında yansır", async () => {
    const user = await openChart();
    await user.click(settings());
    const panel = screen.getByRole("complementary", { name: "Grafik ayarları" });
    expect(within(panel).getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(["Veri", "Seriler1", "Çubuklar", "Eksenler", "Referans çizgileri", "Görünüm"]);
    expect(within(panel).getAllByRole("heading", { level: 3 }).map((h) => within(h).getByRole("button").getAttribute("aria-expanded"))).toEqual(Array(6).fill("false"));  // hepsi daraltılmış
    expect(within(panel).queryByRole("combobox")).toBeNull();
    expect(within(panel).queryByRole("button", { name: "Kaydet" })).toBeNull();
    await openPanel(user, "Veri");
    expect(within(within(panel).getByRole("combobox", { name: "Dönem" })).getAllByRole("option").map((o) => o.textContent)).toEqual(["Gün", "Hafta", "Ay", "Çeyrek", "Yıl"]);  // saat yok
    await waitFor(() => expect(calls.charts).toHaveLength(1));
    await user.selectOptions(within(panel).getByRole("combobox", { name: "Dönem" }), "week");
    await waitFor(() => expect(calls.charts).toHaveLength(2));
    expect(lastChart().x).toEqual({ field: "UpdatedAt", bucket: "week" });
    expect(lastChart().scenario_id).toBe(1);                                                                       // hafta başlangıcı seçili senaryodan
    await openPanel(user, "Çubuklar");
    expect(within(panel).queryByRole("switch", { name: "Toplamı göster" })).toBeNull();                             // yalnız yığılmışta
    await user.click(within(panel).getByRole("radio", { name: "Yığılmış" }));
    await waitFor(() => expect(last().series[0].stack).toBe("primary"));
    await user.click(within(panel).getByRole("switch", { name: "Toplamı göster" }));
    await waitFor(() => expect(last().series).toHaveLength(2));
    await user.click(within(panel).getByRole("switch", { name: "Yatay çubuk" }));
    await waitFor(() => expect(last().yAxis.type).toBe("category"));
    const width = within(panel).getByRole("radiogroup", { name: "Çubuk genişliği" });
    expect(within(width).getAllByRole("radio").map((r) => [r.textContent, r.getAttribute("aria-checked")])).toEqual([["İnce", "false"], ["Orta", "true"], ["Kalın", "false"]]);
    await user.click(within(width).getByRole("radio", { name: "Kalın" }));
    await waitFor(() => expect(last().series[0].barCategoryGap).toBe("16%"));
    await openPanel(user, "Görünüm");
    await user.type(within(panel).getByRole("textbox", { name: "Başlık" }), "Stok");
    await user.click(within(within(panel).getByRole("radiogroup", { name: "Başlık hizası" })).getByRole("radio", { name: "Orta" }));
    await user.click(within(within(panel).getByRole("radiogroup", { name: "Başlık boyutu" })).getByRole("radio", { name: "Büyük" }));
    await waitFor(() => expect([last().title.text, last().title.left, last().title.textStyle.fontSize]).toEqual(["Stok", "center", 17]));
    await new Promise((r) => setTimeout(r, 350));
    expect(calls.charts).toHaveLength(2);                                                                          // görünüş ayarı istek atmaz
    await user.click(settings());
    expect(screen.queryByRole("complementary", { name: "Grafik ayarları" })).toBeNull();
    expect(Object.keys(window.localStorage).filter((k) => k.toLowerCase().includes("chart"))).toEqual([]);         // panelin durumu hiçbir yerde saklanmaz
  });

  it("seriler: ekle (çizgi olarak), ayarla (Hesaplama, tip listesi, eksen, renk seçici, etiket ve sıfırlar, eşik ve eşik çizgisi), sil; sıra, değer sayısı, kırılım; referans çizgisi", async () => {
    const user = await openChart();
    const panel = await openPanel(user, "Veri", "Seriler");
    await user.selectOptions(within(panel).getByRole("combobox", { name: "Yatay eksen" }), "MaterialLevel");
    expect(within(panel).queryByRole("combobox", { name: "Dönem" })).toBeNull();
    await user.click(within(panel).getByRole("radio", { name: "Ada göre" }));
    expect(within(within(panel).getByRole("combobox", { name: "Gösterilecek değer sayısı" })).getAllByRole("option").map((o) => o.textContent)).toEqual(["5", "10", "15", "20", "30"]);
    expect(within(panel).getByRole("combobox", { name: "Gösterilecek değer sayısı" })).toHaveValue("30");
    await user.selectOptions(within(panel).getByRole("combobox", { name: "Gösterilecek değer sayısı" }), "10");
    await user.selectOptions(within(panel).getByRole("combobox", { name: "Kırılım" }), "MaterialGroup");
    await waitFor(() => expect(lastChart()).toMatchObject({ x: { field: "MaterialLevel", bucket: null }, order: "name", split: "MaterialGroup", limit: 10 }));
    await waitFor(() => expect(last().series.map((s: { name: string }) => s.name)).toEqual(["Çubuk", "Levha"]));
    await user.selectOptions(within(panel).getByRole("combobox", { name: "Kırılım" }), "");
    await user.click(within(panel).getByRole("button", { name: "Seri ekle" }));
    await waitFor(() => expect(lastChart().series).toEqual([{ id: "s1", field: "SafetyStock", fn: "sum" }, { id: "s2", field: "StockCoverageDays", fn: "sum" }]));
    expect(within(panel).queryByRole("combobox", { name: "Toplama" })).toBeNull();                                  // alanın adı "Hesaplama"
    expect(within(within(panel).getByRole("combobox", { name: "Hesaplama" })).getAllByRole("option").map((o) => o.textContent)).toEqual(["Toplam", "Ortalama", "En düşük", "En yüksek", "Adet"]);
    await user.selectOptions(within(panel).getByRole("combobox", { name: "Hesaplama" }), "avg");
    const type = within(panel).getByRole("combobox", { name: "Tip" });                                              // tek satır: açılır liste
    expect(within(type).getAllByRole("option").map((o) => o.textContent)).toEqual(["Çubuk", "Çizgi", "Eğimli çizgi", "Kademeli çizgi", "Alan"]);
    await user.selectOptions(type, "smooth");
    await waitFor(() => expect(last().series[1]).toMatchObject({ type: "line", smooth: true, smoothMonotone: "x" }));
    await user.selectOptions(type, "step");
    await user.click(within(panel).getByRole("radio", { name: "İkincil" }));
    // renk: koşullu biçimlendirmedeki renk seçici (ürün renkleri, tema renkleri, standart renkler, Diğer renk)
    await user.click(within(panel).getByRole("button", { name: /^Renk/ }));
    const picker = screen.getByRole("dialog", { name: "Renk" });
    expect(within(picker).getAllByRole("group").map((g) => g.getAttribute("aria-label"))).toEqual(["Ürün renkleri", "Tema renkleri", "Standart renkler"]);
    await user.click(within(within(picker).getByRole("group", { name: "Standart renkler" })).getAllByRole("button")[0]);
    await user.click(within(panel).getByRole("switch", { name: "Veri etiketi" }));
    expect(within(panel).getByRole("switch", { name: "Sıfır değerleri göster" })).not.toBeChecked();                // varsayılan kapalı
    await user.type(within(panel).getByRole("textbox", { name: "Eşik" }), "20{Enter}");
    await waitFor(() => expect(last().series[1]).toMatchObject({ type: "line", step: "end", yAxisIndex: 1, label: { show: true } }));
    expect(last().series[1].color).toMatch(/^#[0-9a-f]{6}$/);
    expect(last().series[1].color).not.toBe("#2e7d7a");
    expect(within(panel).getByRole("button", { name: /^Eşik üstü renk/ })).toBeInTheDocument();                    // aynı renk seçici
    expect(within(panel).getByRole("switch", { name: "Eşik çizgisini göster" })).not.toBeChecked();                 // varsayılan kapalı
    expect(last().series[1].markLine).toBeUndefined();
    await user.click(within(panel).getByRole("switch", { name: "Eşik çizgisini göster" }));
    await waitFor(() => expect(last().series[1].markLine.data[0]).toMatchObject({ yAxis: 20, name: "Eşik 20,0" }));
    await openPanel(user, "Referans çizgileri");
    await user.click(within(panel).getByRole("button", { name: "Çizgi ekle" }));
    await waitFor(() => expect(last().series[0].markLine.data[0].name).toBe("Ortalama 20,00"));
    await user.click(within(panel).getByRole("switch", { name: "Adı göster" }));
    await waitFor(() => expect(last().series[0].markLine.data[0].name).toBe("20,00"));
    await user.click(within(panel).getByRole("switch", { name: "Değeri göster" }));
    await waitFor(() => expect(last().series[0].markLine.data[0].label.show).toBe(false));
    await user.click(within(panel).getByRole("button", { name: "Stok gün kapsamı · Ortalama serisini sil" }));
    await waitFor(() => expect(lastChart().series).toHaveLength(1));
    expect(within(panel).getByRole("button", { name: "Güvenlik stoğu · Toplam serisini sil" })).toBeDisabled();     // son seri silinmez
  });

  it("grafik görünümle kaydedilir ve görünümle açılır: düzen, yükseklik, ayarlar; tablonun filtresi isteğe aynen gider", async () => {
    const filters = [{ field: "Name", op: "contains" as const, value: "mil" }];
    const user = userEvent.setup();
    await openTable({ views: { views: [savedView(7, "Seviye grafiği", { filters, chart: CHART })], default_view_id: 7 } });
    await screen.findByTestId("chart-pane");
    await waitFor(() => expect(lastChart()).toEqual({ filters, x: { field: "MaterialLevel", bucket: null }, split: null, order: "name", series: [{ id: "s1", field: "StockCoverageDays", fn: "avg" }], limit: 30 }));
    expect(screen.queryByRole("complementary", { name: "Grafik ayarları" })).toBeNull();                              // kaydedilen görünüm paneli açık getirmez
    expect(screen.getByRole("separator", { name: "Grafik ve tablo arasındaki ayraç" })).toHaveAttribute("aria-valuenow", "60");  // kaydedilen yükseklik
    await waitFor(() => expect(last().title.text).toBe("Seviye"));
    expect(last().series[0]).toMatchObject({ type: "line", color: "#2E7D7A" });
    expect(screen.queryByRole("img", { name: "Kaydedilmemiş değişiklik" })).toBeNull();
    await user.click(within(pane()).getByRole("button", { name: "Tam ekran" }));
    expect(screen.getByRole("img", { name: "Kaydedilmemiş değişiklik" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Tablo ayarları" }));
    await user.click(within(screen.getByRole("menu", { name: "Tablo ayarları" })).getByRole("menuitem", { name: "Kaydet" }));
    await waitFor(() => expect(calls.views.some((c) => c.method === "PUT")).toBe(true));
    const body = calls.views.find((c) => c.method === "PUT")!.body as { definition: { chart: typeof CHART } };
    expect(body.definition.chart).toEqual({ ...CHART, layout: "full" });
    expect(JSON.stringify(body.definition)).not.toContain("panel");                                                 // panelin durumu görünüme yazılmaz
    // ✕: görünümde grafik var, kapalı olarak saklanır (ayarlar durur)
    await user.click(within(pane()).getByRole("button", { name: "Grafiği kapat" }));
    expect(screen.queryByTestId("chart-pane")).toBeNull();
    await user.click(chartButton());
    await waitFor(() => expect(last().title.text).toBe("Seviye"));
  });

  it("ilk açılışta birimler karışıksa seri Adet'e döner: grafik boş gelmez; kullanıcının sonradan seçtiği seri uyarıyla kalır", async () => {
    await openChart({ chart: (req) => ({ body: chartData(req, { series: req.series.map((s) => ({ id: s.id, data: s.fn === "count" ? [[4, 5, 6]] : null, mixed_units: s.fn !== "count" })) }) }) });
    await waitFor(() => expect(lastChart().series).toEqual([{ id: "s1", field: null, fn: "count" }]));
    await waitFor(() => expect(last()?.series.map((s: { name: string }) => s.name)).toEqual(["Adet"]));
    expect(within(pane()).queryByText(/Farklı birimler toplanamaz/)).toBeNull();
    const user = userEvent.setup();
    const panel = await openPanel(user, "Seriler");
    await user.click(within(panel).getByRole("button", { name: "AdetÇubuk" }));
    await user.selectOptions(within(panel).getByRole("combobox", { name: "Hesaplama" }), "sum");
    expect(await within(pane()).findByText(/Farklı birimler toplanamaz: Güvenlik stoğu · Toplam/)).toBeInTheDocument();
    expect(lastChart().series).toEqual([{ id: "s1", field: "SafetyStock", fn: "sum" }]);   // yeniden Adet'e çevrilmez
  });

  it("hâller: boş veri, hata ve Yeniden dene, karışık birim uyarısı", async () => {
    let reply: "empty" | "error" | "mixed" = "empty";
    await openChart({ chart: (req) => (reply === "error"
      ? { status: 422, body: { error: { code: "too_many_periods", message: "Dönem sayısı çok fazla; daha büyük bir dönem seçin.", trace_id: "x" } } }
      : { body: chartData(req, reply === "empty" ? { rows: 0, x: { kind: "date", bucket: "month", values: [], other: false } }
        : { series: [{ id: "s1", data: null, mixed_units: true }] }) }) });
    const user = userEvent.setup();
    expect(await within(pane()).findByText("Bu görünümde çizilecek veri yok.")).toBeInTheDocument();
    reply = "error";
    const panel = await openPanel(user, "Veri");
    await user.selectOptions(within(panel).getByRole("combobox", { name: "Dönem" }), "day");
    expect(await within(pane()).findByText(/Dönem sayısı çok fazla/)).toBeInTheDocument();
    expect(within(pane()).getByText("Grafik çizilemedi.")).toBeInTheDocument();
    reply = "mixed";
    const before = calls.charts.length;
    await user.click(within(pane()).getByRole("button", { name: "Yeniden dene" }));
    await waitFor(() => expect(calls.charts.length).toBe(before + 1));
    expect(await within(pane()).findByText("Farklı birimler toplanamaz: Güvenlik stoğu · Toplam. Birime göre filtreleyin ya da toplamayı Adet yapın.")).toBeInTheDocument();
  });
});

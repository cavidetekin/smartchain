// Dönem tablosu (K-184, docs/12 "Dönem tablosu standardı"): ürünün Standart'ı pivot (panel kapalı), isteklerde senaryo, dönem sütunları sunucu
// sırasıyla, İlk · Son dönem değeri yalnız dönem tablosunda, hazır hesaplanan değerler, gruplamada varsayılan ara toplam. Tablo, Kapasite yönetimi
// ekranının (ekran 30, K-185) "Kapasite özeti" sekmesidir: menüdeki yeri, sekme şeridi, End user'ın salt okunur görmesi.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { meAs, mockApi, renderApp } from "../test/helpers";
import { defaultFn, fnsFor, type PivotData, type PivotRequest, valueLabel } from "./pivotModel";
import { col, useTableTestSetup } from "./testBackend";
import { defaultChart } from "../ui/chart/chartModel";
import { aggregateOf, standardState } from "./viewState";

useTableTestSetup();

const LIST = "/api/period-resource-group";
const PATH = "/parametre/kapasite-yonetimi";
const ORDER = { order_by: "PeriodStart" };
const COLUMNS = [
  col("ResourceGroupCode", "Kaynak grubu", "text", "list", { values_from_server: true }), col("CapacityUnit", "Kapasite birimi", "text", "list"),
  col("PeriodType", "Dönem tipi", "text", "list", ORDER), col("Period", "Dönem", "text", "list", ORDER), col("PeriodStart", "Dönem başı", "date", "date"),
  col("Month", "Ay", "text", "list", ORDER), col("PeriodDays", "Dönem takvim günü", "integer", "number"),
  col("ResourceCount", "Kaynak sayısı", "integer", "number", { aggregate: "last" }), col("TotalCapacity", "Toplam kapasite", "number", "number", { aggregate: "sum", decimals: 2 }),
  col("AvailableCapacity", "Kullanılabilir kapasite", "number", "number", { aggregate: "sum", decimals: 2 }),
  col("Efficiency", "Verimlilik", "number", "number", { aggregate: "wavg", aggregate_weight: "TotalCapacity", percent: true, decimals: 1 }),
];
const byField = new Map(COLUMNS.map((c) => [c.field, c]));
const STANDARD = {
  v: 1, open: true, rows: [{ field: "ResourceGroupCode" }], columns: [{ field: "Period" }], values_on: "rows",
  values: [{ id: "d1", field: "ResourceCount", fn: "last" }, { id: "d2", field: "TotalCapacity", fn: "sum" },
           { id: "d3", field: "Efficiency", fn: "wavg", weight: "TotalCapacity" }],
  totals: { rows: false, columns: false, subtotals: false }, sort: { by: "name", dir: "asc" },
};
const READY = [{ name: "Kullanılabilirlik", a: { field: "AvailableCapacity", fn: "sum" }, op: "div", b: { field: "TotalCapacity", fn: "sum" }, percent: true, decimals: 2 }];
// Sunucunun sırası: dönem başına göre (alfabetik olsaydı "Ara 2026" başa gelirdi)
const PERIODS = ["H47 2026", "H48 2026", "Ara 2026", "Oca 2027"];

function data(req: PivotRequest): PivotData {
  const columns = req.columns.length ? PERIODS.map((p) => ({ key: [p], level: 1, total: false })) : [{ key: [], level: 0, total: false }];
  return {
    row_fields: req.rows.map((a) => ({ field: a.field, type: "text", bucket: null })), column_fields: req.columns.map((a) => ({ field: a.field, type: "text", bucket: null })),
    columns, values: req.values.map((v) => ({ id: v.id, fn: v.kind === "calc" ? "calc" as const : v.fn ?? "sum", field: v.field ?? null, weight: v.weight ?? null, decimals: 0,
                                             percent: false, from_unit: false })),
    rows: ["KG-1", "KG-2"].map((g, i) => ({ key: [g], level: 1, total: false, cells: req.values.map((_, k) => columns.map((_c, s) => (i + 1) * 10 + k + s)) })),
    offset: 0, row_count: 2, week_start: "Pazartesi",
  };
}

function backend(scenario = { id: 7, name: "Kısıtsız kapasite", is_base: false, is_active: true }) {
  const bodies: Record<string, Record<string, unknown>[]> = { pivot: [], query: [], groups: [], values: [] };
  const post = (name: string, reply: (body: Record<string, unknown>) => unknown) => (_url: string, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    bodies[name].push(body);
    return { body: reply(body) };
  };
  mockApi({
    "/api/scenarios/current": { body: scenario },
    "/api/scenarios/options": { body: { scenarios: [{ id: 1, name: "Baz", is_base: true }, { id: scenario.id, name: scenario.name, is_base: false }] } },
    [`${LIST}/columns`]: { body: { chunk_size: 100, columns: COLUMNS, relations: [{ path: "ResourceGroupId", label: "Kaynak grubu" }], period_table: true,
                                   standard_pivot: STANDARD, calculated_values: READY,
                                   export: { title: "Kaynak grubu × dönem", file_slug: "kaynak-grubu-donem", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    [`${LIST}/views`]: { body: { views: [], default_view_id: null } },
    [`${LIST}/values`]: post("values", () => PERIODS.map((value) => ({ value, count: 2 }))),
    [`${LIST}/query`]: post("query", () => ({ rows: [{ Id: 7001, ResourceGroupCode: "KG-1", Period: "H47 2026", ResourceCount: 3 }], filtered: 1, total: 1 })),
    [`${LIST}/groups`]: post("groups", () => ({ groups: [], leaf_groups: 0, filtered: 0, total: 0, aggregate_specs: {} })),
    [`${LIST}/pivot`]: post("pivot", (body) => data(body as unknown as PivotRequest)),
  });
  return bodies;
}

async function open() {
  const user = userEvent.setup();
  const bodies = backend();
  renderApp(PATH, meAs("Key user"));
  const table = await screen.findByRole("table", { name: "Pivot" }, { timeout: 5000 });
  await within(table).findByText("KG-1");
  return { user, bodies, table };
}

describe("dönem tablosu modeli (K-184)", () => {
  it("Standart'ta pivot; İlk · Son dönem değeri yalnız dönem tablosunda; gruplamada varsayılan ara toplam değil", () => {
    expect(standardState(COLUMNS).pivot).toBeNull();
    const state = standardState(COLUMNS, STANDARD);
    expect(state.pivot).toMatchObject({ open: true, values_on: "rows", rows: [{ field: "ResourceGroupCode" }], columns: [{ field: "Period" }] });
    expect(state.pivot!.values.map((v) => v.fn)).toEqual(["last", "sum", "wavg"]);
    const count = byField.get("ResourceCount")!;
    expect(fnsFor(count)).not.toContain("last");
    expect(fnsFor(count, true).slice(-2)).toEqual(["first", "last"]);
    expect(defaultFn(count)).toBe("last");
    expect(valueLabel({ field: "ResourceCount", fn: "last" }, byField)).toBe("Kaynak sayısı · Son dönem değeri");
    expect(valueLabel({ field: "ResourceCount", fn: "first" }, byField)).toBe("Kaynak sayısı · İlk dönem değeri");
    expect(aggregateOf(count, state)).toEqual({ fn: "none" });                     // tablodaki gruplamada ara toplam yok sayılır
    // varsayılanı ağırlıklı ortalama olan alan ağırlık alanıyla birlikte gider (7.8 demo bulgusu: ağırlıksız istek 422 veriyordu)
    expect(aggregateOf(byField.get("Efficiency")!, state)).toEqual({ fn: "wavg", weight: "TotalCapacity" });
    expect(aggregateOf({ ...byField.get("Efficiency")!, aggregate_weight: null }, state)).toEqual({ fn: "none" });
    expect(aggregateOf(byField.get("TotalCapacity")!, state)).toEqual({ fn: "sum" });
  });

  it("grafik ilk açılışta liste tanımının verdiği değerle gelir (K-186); verilmezse görünür ilk sayı alanı", () => {
    const order = COLUMNS.map((c) => c.field);
    expect(defaultChart(COLUMNS, order, "AvailableCapacity")!.series.map((x) => [x.field, x.fn])).toEqual([["AvailableCapacity", "sum"]]);
    expect(defaultChart(COLUMNS, order)!.series[0].field).toBe("TotalCapacity");
    expect(defaultChart(COLUMNS, order, "Yok")!.series[0].field).toBe("TotalCapacity");   // bilinmeyen alan yok sayılır
  });
});

describe("ekran 30 · Kapasite yönetimi · Kapasite özeti (K-184, K-185)", () => {
  it("pivot açık gelir, ayar paneli kapalı, görünüm değişmiş sayılmaz; sütunlar sunucunun sırasıyla; istekler seçili senaryoyu taşır", async () => {
    const { bodies, table } = await open();
    expect(screen.getByRole("heading", { level: 1, name: "Kapasite yönetimi" })).toBeInTheDocument();
    // sekme şeridi: ilk sekme Kapasite özeti (giriş sekmeleri CapacityManagement.test'te)
    const tabs = within(screen.getByRole("radiogroup", { name: "Kapasite yönetimi bölümleri" })).getAllByRole("radio");
    expect(tabs[0]).toHaveTextContent("Kapasite özeti");
    expect(tabs[0]).toHaveAttribute("aria-checked", "true");
    // menüde Parametre grubunda, Parametreler ile Senaryolar arasında
    const links = screen.getAllByRole("link").map((l) => l.textContent);
    const at = links.indexOf("Kapasite yönetimi");
    expect(links.slice(at - 1, at + 2)).toEqual(["Parametreler", "Kapasite yönetimi", "Senaryolar"]);
    expect(screen.queryByRole("complementary", { name: "Pivot ayarları" })).toBeNull();
    expect(screen.getByRole("button", { name: "Tablo ayarları" })).toHaveAttribute("title", "Tablo ayarları");   // kaydedilmemiş değişiklik sayılmaz
    const heads = within(table).getAllByRole("columnheader").map((h) => h.textContent);
    expect(heads.filter((h) => PERIODS.includes(h ?? ""))).toEqual(PERIODS);                              // istemci yeniden sıralamaz
    const sent = bodies.pivot[bodies.pivot.length - 1];
    expect(sent).toMatchObject({ scenario_id: 7, rows: [{ field: "ResourceGroupCode" }], columns: [{ field: "Period" }] });
    expect((sent.values as { fn: string }[]).map((v) => v.fn)).toEqual(["last", "sum", "wavg"]);
    expect(within(table).getAllByText("Kaynak sayısı · Son dönem değeri").length).toBe(2);              // her kaynak grubunda bir değer satırı
  });

  it("panelde İlk · Son dönem değeri ve hazır hesaplanan değer; hazır değer işlenenleriyle eklenir", async () => {
    const { user, bodies } = await open();
    await user.click(screen.getByRole("button", { name: /^Tablo ayarları/ }));
    await user.click(within(screen.getByRole("menu")).getByText("Pivot ayarları"));
    const panel = screen.getByRole("complementary", { name: "Pivot ayarları" });
    await user.click(within(panel).getByRole("button", { name: /^Değerler\d*$/ }));
    await user.click(within(panel).getByRole("button", { name: "Kaynak sayısı · Son dönem değeri" }));
    const options = within(within(panel).getByRole("combobox", { name: "Hesaplama" })).getAllByRole("option").map((o) => o.textContent);
    expect(options.slice(-2)).toEqual(["İlk dönem değeri", "Son dönem değeri"]);
    await user.selectOptions(within(panel).getByRole("combobox", { name: "Hesaplama" }), "İlk dönem değeri");
    await waitFor(() => expect((bodies.pivot[bodies.pivot.length - 1].values as { fn: string }[])[0].fn).toBe("first"));

    expect(within(panel).getByRole("group", { name: "Hazır değerler" })).toBeInTheDocument();
    const ready = within(panel).getByRole("button", { name: "Hazır değer ekle: Kullanılabilirlik" });
    await user.click(ready);
    await waitFor(() => expect((bodies.pivot[bodies.pivot.length - 1].values as object[])).toHaveLength(5));
    const values = bodies.pivot[bodies.pivot.length - 1].values as Record<string, unknown>[];
    expect(values[3]).toEqual({ id: "d4", fn: "sum", field: "AvailableCapacity" });                      // eksik işlenen eklendi
    expect(values[4]).toEqual({ id: "d5", kind: "calc", a: "d4", op: "div", b: "d2", percent: true });     // var olan işlenen (Toplam kapasite · Toplam) kullanıldı
    expect(await within(panel).findByRole("button", { name: "Kullanılabilirlik · Toplamlardan" })).toBeInTheDocument();
    expect(ready).toBeDisabled();
  });

  it("tablo görünümünde de istekler senaryoyu taşır; gruplamada İlk · Son dönem değeri ara toplam olarak istenmez", async () => {
    const { user, bodies } = await open();
    await user.click(screen.getByRole("button", { name: /^Tablo ayarları/ }));
    await user.click(within(screen.getByRole("menu")).getByText("Pivot görünümü"));
    await screen.findByText("KG-1");
    await waitFor(() => expect(bodies.query.length).toBeGreaterThan(0));
    expect(bodies.query[bodies.query.length - 1]).toMatchObject({ scenario_id: 7 });
    // Grupla: Ay (7.8 demo bulgusu): varsayılan ara toplamlar ağırlık alanıyla gider; Son dönem değeri gönderilmez
    await user.click(screen.getByRole("button", { name: /^Grupla/ }));
    await user.selectOptions(await screen.findByRole("combobox", { name: "Gruplanacak alan" }), "Ay");
    await waitFor(() => expect(bodies.groups.length).toBeGreaterThan(0));
    const sent = bodies.groups[bodies.groups.length - 1];
    expect(sent).toMatchObject({ scenario_id: 7, group_by: ["Month"] });
    expect(sent.aggregates).toEqual({ TotalCapacity: { fn: "sum" }, AvailableCapacity: { fn: "sum" }, Efficiency: { fn: "wavg", weight: "TotalCapacity" } });
  });

  it("sunucu liste isteğini reddederse nedeni ekranda yazar", async () => {
    const user = userEvent.setup();
    backend();
    mockApi({
      "/api/scenarios/current": { body: { id: 7, name: "Kısıtsız kapasite", is_base: false, is_active: true } },
      [`${LIST}/columns`]: { body: { chunk_size: 100, columns: COLUMNS, relations: [], period_table: true,
                                     export: { title: "x", file_slug: "x", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
      [`${LIST}/views`]: { body: { views: [], default_view_id: null } },
      [`${LIST}/query`]: { body: { rows: [{ Id: 7001, ResourceGroupCode: "KG-1", Period: "H47 2026" }], filtered: 1, total: 1 } },
      [`${LIST}/groups`]: { status: 422, body: { error: { code: "validation", message: "Girilen bilgiler geçersiz.", trace_id: "t",
                                                          details: [{ field: "aggregates.Efficiency.weight", problem: "Ağırlıklı ortalama için başka bir sayı alanı seçilmeli" }] } } },
    });
    renderApp(PATH, meAs("Key user"));
    await screen.findByText("KG-1", {}, { timeout: 5000 });
    await user.click(screen.getByRole("button", { name: /^Grupla/ }));
    await user.selectOptions(await screen.findByRole("combobox", { name: "Gruplanacak alan" }), "Ay");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Liste okunamadı");
    expect(alert).toHaveTextContent("Ağırlıklı ortalama için başka bir sayı alanı seçilmeli");
  });
});

describe("ekran 30 · yetki (K-185)", () => {
  it("End user ekranı görür: özet salt okunur, kayıt ekleme ya da düzenleme denetimi yok", async () => {
    backend();
    renderApp(PATH, meAs("End user"));
    const table = await screen.findByRole("table", { name: "Pivot" }, { timeout: 5000 });
    await within(table).findByText("KG-1");
    expect(screen.getByRole("heading", { level: 1, name: "Kapasite yönetimi" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Kapasite yönetimi" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Parametreler" })).toBeNull();          // Parametreler End user'da yok; Kapasite yönetimi istisna
    expect(screen.queryByRole("button", { name: /Yeni kayıt|Kaydet|Düzenle/ })).toBeNull();
  });
});

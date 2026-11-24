// Öncelik yönetimi (ekran 32, fonksiyon 25; K-195; docs/12 "Öncelik yönetimi"): üç sekme; değer hücrede listeden seçilir (1–5 ve boş); Kaydet hepsini tek
// istekte gönderir; reddedilen hücre kırmızı; ERP önceliği ve hesaplanan alanlar düzenlenmez; senaryo farkı işareti ve "Senaryo farkını kaldır"; kartlar
// (müşterinin siparişleri ve tahminleri, siparişin müşterisi ve projesi, Geçmiş); End user.
import { createEvent, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { meAs, mockApi, renderApp, type Reply } from "../test/helpers";
import { col, useTableTestSetup } from "../table/testBackend";
import { cellOf, listOptions, openEditor, setCell } from "../table/testEditing";

useTableTestSetup();

const paste = (target: HTMLElement, text: string) => {
  const event = createEvent.paste(target, { clipboardData: { getData: () => text } });
  fireEvent(target, event);
};

const PATH = "/parametre/oncelik-yonetimi";
const EXPORT = { title: "x", file_slug: "x", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const OWNER_COLUMNS = (first: string) => [col("Code", first, "text", "list"), col("Name", "Ad", "text", "text"), col("Priority", "ERP önceliği", "integer", "number"),
                                         col("PriorityGroup", "Öncelik grubu", "integer", "list"), col("Origin", "Kaynağı", "text", "list")];
const ORDER_COLUMNS = [col("LocationCode", "Lokasyon", "text", "list"), col("OrderNo", "Sipariş", "text", "text"), col("LineNo", "Satır", "integer", "number"),
                       col("CustomerCode", "Müşteri", "text", "list"), col("ProjectCode", "Proje", "text", "list"), col("Priority", "ERP önceliği", "integer", "number"),
                       col("PriorityGroup", "Öncelik grubu", "integer", "list"), col("EffectivePriorityGroup", "Geçerli öncelik grubu", "integer", "list"),
                       col("PrioritySource", "Öncelik kaynağı", "text", "list"), col("Origin", "Kaynağı", "text", "list")];
const FORECAST_COLUMNS = [col("MaterialCode", "Malzeme", "text", "list"), col("CustomerCode", "Müşteri", "text", "list"),
                          col("EffectivePriorityGroup", "Geçerli öncelik grubu", "integer", "list"), col("PrioritySource", "Öncelik kaynağı", "text", "list")];
const owner = (id: number, code: string, name: string, erp: number | null, group: number | null, extra: object = {}) => ({
  Id: id, Code: code, Name: name, Priority: erp, PriorityGroup: group, Origin: group === null ? null : "Baz", StoredId: group === null ? null : id + 100, OverriddenFields: null,
  BaseValues: null, CanRestore: false, ...extra });
const CUSTOMERS = [owner(1, "MUS-A", "Akdeniz Pompa", 1, 1), owner(2, "MUS-B", "Kuzey Enerji", 2, null), owner(3, "MUS-C", "Orta Anadolu", 3, 4)];
const FOLLOWER_CUSTOMERS = [CUSTOMERS[0], CUSTOMERS[1],
  owner(3, "MUS-C", "Orta Anadolu", 3, 2, { Origin: "Senaryo farkı", StoredId: 31, OverriddenFields: ",PriorityGroup,", BaseValues: JSON.stringify({ PriorityGroup: 4 }), CanRestore: true })];
const PROJECTS = [owner(1, "PRJ-01", "Santral A", 9, null), owner(2, "PRJ-02", "Arıtma tesisi", 2, 3)];
const order = (id: number, no: string, customer: [number, string], project: [number, string] | null, group: number | null, effective: number, source: string) => ({
  Id: id, LocationCode: "ORM-01", OrderNo: no, LineNo: 1, CustomerCode: customer[1], CustomerId: customer[0], ProjectCode: project?.[1] ?? null, ProjectId: project?.[0] ?? null,
  Priority: null, PriorityGroup: group, EffectivePriorityGroup: effective, PrioritySource: source, Origin: group === null ? null : "Baz", StoredId: group === null ? null : id + 100,
  OverriddenFields: null, BaseValues: null, CanRestore: false });
const ORDERS = [order(11, "SO-1001", [1, "MUS-A"], null, null, 1, "Müşteri"), order(13, "SO-1003", [1, "MUS-A"], null, 5, 5, "Sipariş"),
                order(30, "SO-1030", [2, "MUS-B"], [2, "PRJ-02"], null, 3, "Proje")];
const FORECASTS = [{ Id: 1, MaterialCode: "MAM-001", CustomerCode: "MUS-A", EffectivePriorityGroup: 1, PrioritySource: "Müşteri" }];

type Call = { method: string; url: string; body: Record<string, unknown> };

function backend(options: { scenario?: { id: number; name: string; is_base: boolean }; customers?: object[]; reply?: (call: Call) => Reply | undefined } = {}) {
  const scenario = options.scenario ?? { id: 1, name: "Baz", is_base: true };
  const calls: Call[] = [];
  const queries: Record<string, Record<string, unknown>[]> = {};
  const list = (name: string, columns: unknown[], found: object[]) => ({
    [`/api/${name}/columns`]: { body: { chunk_size: 100, columns, relations: [], scenario_list: true, export: EXPORT } },
    [`/api/${name}/views`]: { body: { views: [], default_view_id: null } },
    [`/api/${name}/query`]: (_url: string, init?: RequestInit) => {
      (queries[name] ??= []).push(JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>);
      return { body: { rows: found, filtered: found.length, total: found.length } };
    },
  });
  mockApi({
    "/api/scenarios/current": { body: { ...scenario, is_active: true } },
    "/api/scenarios/options": { body: { scenarios: [{ id: 1, name: "Baz", is_base: true }, ...(scenario.is_base ? [] : [scenario])] } },
    ...list("priority-customers", OWNER_COLUMNS("Müşteri"), options.customers ?? CUSTOMERS),
    ...list("priority-projects", OWNER_COLUMNS("Proje"), PROJECTS),
    ...list("priority-orders", ORDER_COLUMNS, ORDERS),
    ...list("priority-forecasts", FORECAST_COLUMNS, FORECASTS),
    ...list("record-history", [col("At", "Tarih", "datetime", "date"), col("FieldLabel", "Alan", "text", "list")], []),
    "/api/priorities/": (url: string, init?: RequestInit) => {
      const call = { method: init?.method ?? "GET", url, body: init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : {} };
      calls.push(call);
      return options.reply?.(call) ?? { body: { saved: 1, restored: true } };
    },
  });
  return { calls, queries };
}

const rowsOf = () => screen.getAllByRole("row").filter((r) => r.classList.contains("sc-table-row"));
async function open(role = "Key user", options: Parameters<typeof backend>[0] = {}, path = PATH) {
  const user = userEvent.setup();
  const server = backend(options);
  renderApp(path, meAs(role));
  await waitFor(() => expect(rowsOf().length).toBeGreaterThan(0), { timeout: 5000 });
  return { user, ...server };
}
/** Listeye bu süzmeyle sorgu gitti mi (tablo ardışık sorgular gönderir; sonuncusu olması gerekmez). */
const asked = (queries: Record<string, Record<string, unknown>[]>, list: string, filters: unknown) =>
  (queries[list] ?? []).some((q) => JSON.stringify(q.filters) === JSON.stringify(filters));
/** Kartın sekmesi (kart yeniden çizildiği için her tıklamada yeniden bulunur). */
const cardTab = (name: string) => within(screen.getByRole("radiogroup", { name: "Kayıt bölümleri" })).getByRole("radio", { name });
const heads = () => screen.getAllByRole("columnheader").map((h) => h.querySelector(".sc-table-label")?.textContent).filter(Boolean);
const editable = () => screen.getAllByRole("columnheader").filter((h) => h.querySelector(".sc-table-edit-mark")).map((h) => h.querySelector(".sc-table-label")?.textContent);

describe("ekran 32 · Öncelik yönetimi (K-195, 7.14a)", () => {
  it("üç sekme; Müşteri'de ERP önceliği ve Öncelik grubu ayrı kolonlar; yalnız Öncelik grubu düzenlenir; istek seçili senaryoyu taşır", async () => {
    const { queries } = await open();
    const tabs = within(screen.getByRole("radiogroup", { name: "Öncelik yönetimi bölümleri" })).getAllByRole("radio");
    expect(tabs.map((t) => [t.textContent, t.getAttribute("aria-checked")])).toEqual([["Müşteri", "true"], ["Proje", "false"], ["Sipariş", "false"]]);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Öncelik yönetimi");
    expect(screen.queryByRole("button", { name: "Yeni kayıt" })).toBeNull();                              // pencere yok: değer hücreye yazılır
    expect(queries["priority-customers"][0]).toMatchObject({ scenario_id: 1 });
    expect(heads()).toEqual(["Müşteri", "Ad", "ERP önceliği", "Öncelik grubu", "Kaynağı"]);
    expect(editable()).toEqual(["Öncelik grubu"]);
    expect([cellOf("MUS-A", "ERP önceliği").textContent, cellOf("MUS-A", "Öncelik grubu").textContent]).toEqual(["1", "1"]);
    expect([cellOf("MUS-B", "ERP önceliği").textContent, cellOf("MUS-B", "Öncelik grubu").textContent]).toEqual(["2", ""]);   // girilmemiş: ERP önceliği geçerli
    expect(cellOf("MUS-B", "Öncelik grubu")).toHaveClass("is-editable");
    expect(cellOf("MUS-B", "ERP önceliği")).not.toHaveClass("is-editable");
  });

  it("hücrede liste boş ve 1–5; değer seçilir ve boşaltılır; Kaydet hepsini tek istekte gönderir; reddedilen hücre kırmızı ve taslak durur", async () => {
    let reject = true;
    const { user, calls, queries } = await open("Key user", { reply: (call) => (call.method === "PUT" && reject
      ? { status: 422, body: { error: { code: "validation", message: "Kaydedilmedi.", trace_id: "t", details: [{ id: 2, field: "PriorityGroup", record: "Müşteri MUS-B", problem: "1 ile 5 arasında tam sayı olmalı." }] } } }
      : undefined) });
    const cell = cellOf("MUS-B", "Öncelik grubu");
    await openEditor(user, cell);
    expect(listOptions(cell).map((o) => o.textContent)).toEqual(["—", "1", "2", "3", "4", "5"]);       // boş seçenek soluk "—" (docs/12)
    expect(listOptions(cell)[0]).toHaveAccessibleName("Boş");
    await user.keyboard("{Escape}");
    await setCell(user, "MUS-B", "Öncelik grubu", "3");
    await setCell(user, "MUS-C", "Öncelik grubu", "");                                                    // boş: değer kalkar
    expect(cellOf("MUS-B", "Öncelik grubu")).toHaveTextContent("3");
    expect(cellOf("MUS-B", "Öncelik grubu")).toHaveClass("is-draft");
    expect(cellOf("MUS-C", "Öncelik grubu")).toHaveTextContent("");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT")).toHaveLength(1));
    expect(calls[0].url).toContain("/api/priorities/customers?scenario_id=1");
    expect(calls[0].body.changes).toEqual(expect.arrayContaining([{ id: 2, field: "PriorityGroup", value: 3 }, { id: 3, field: "PriorityGroup", value: null }]));
    await waitFor(() => expect(cellOf("MUS-B", "Öncelik grubu")).toHaveClass("is-invalid"));
    expect(cellOf("MUS-B", "Öncelik grubu")).toHaveTextContent("3");                                      // taslak durur
    reject = false;
    const before = queries["priority-customers"].length;
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(queries["priority-customers"].length).toBeGreaterThan(before));            // kaydedince tablo yenilenir
    await waitFor(() => expect(screen.queryByRole("button", { name: "Kaydet" })).toBeNull());
  });

  it("liste açıkken yapıştırma: liste kapanır, değerler o hücreden aşağı taslağa girer; 1–5 dışı değer alınmaz ve özetlenir", async () => {
    const { user, calls } = await open();
    const cell = cellOf("MUS-A", "Öncelik grubu");
    await openEditor(user, cell);
    expect(listOptions(cell)).toHaveLength(6);
    paste(within(cell).getByRole("listbox"), "4\n9\n2\n");
    await waitFor(() => expect(within(cellOf("MUS-A", "Öncelik grubu")).queryByRole("listbox")).toBeNull());
    expect(cellOf("MUS-A", "Öncelik grubu")).toHaveTextContent("4");
    expect(cellOf("MUS-A", "Öncelik grubu")).toHaveClass("is-draft");
    expect(cellOf("MUS-B", "Öncelik grubu")).toHaveTextContent("");                                       // 9: alınmaz
    expect(cellOf("MUS-B", "Öncelik grubu")).not.toHaveClass("is-draft");
    expect(cellOf("MUS-C", "Öncelik grubu")).toHaveTextContent("2");
    const report = screen.getByText("2 hücre taslağa alındı, 1 hücre alınmadı.").closest(".sc-alert")!;

    expect(report).toHaveTextContent("1–5 dışında değer: 1 hücre.");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT")).toHaveLength(1));
    expect((calls[0].body.changes as { id: number }[]).map((c) => c.id).sort()).toEqual([1, 3]);
  });

  it("yapıştırma: Öncelik grubu dışındaki alana düşen hücre alınmaz; boş değer hücreyi boşaltır", async () => {
    const { user } = await open();
    await user.click(cellOf("MUS-A", "ERP önceliği"));
    paste(cellOf("MUS-A", "ERP önceliği"), "3\t\n");
    expect(screen.getByText("1 hücre taslağa alındı, 1 hücre alınmadı.").closest(".sc-alert")!).toHaveTextContent("Düzenlenmeyen alanlar: ERP önceliği (1 hücre).");
    expect(cellOf("MUS-A", "ERP önceliği")).toHaveTextContent("1");
    expect(cellOf("MUS-A", "Öncelik grubu")).toHaveTextContent("");                                       // boş yapıştırıldı: değer kalkar
    expect(cellOf("MUS-A", "Öncelik grubu")).toHaveClass("is-draft");
  });

  it("Sipariş sekmesi: girilen ve hesaplanan ayrı kolonlar; Geçerli öncelik grubu ve Öncelik kaynağı düzenlenmez", async () => {
    const { user, calls } = await open("Key user", {}, `${PATH}?sekme=siparis`);
    expect(heads()).toEqual(["Lokasyon", "Sipariş", "Satır", "Müşteri", "Proje", "ERP önceliği", "Öncelik grubu", "Geçerli öncelik grubu", "Öncelik kaynağı", "Kaynağı"]);
    expect(editable()).toEqual(["Öncelik grubu"]);
    expect(["Öncelik grubu", "Geçerli öncelik grubu", "Öncelik kaynağı"].map((h) => cellOf("SO-1003", h).textContent)).toEqual(["5", "5", "Sipariş"]);
    expect(["Öncelik grubu", "Geçerli öncelik grubu", "Öncelik kaynağı"].map((h) => cellOf("SO-1030", h).textContent)).toEqual(["", "3", "Proje"]);
    expect(cellOf("SO-1030", "Geçerli öncelik grubu")).not.toHaveClass("is-editable");
    await setCell(user, "SO-1030", "Öncelik grubu", "2");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls[0]).toMatchObject({ method: "PUT", url: "/api/priorities/orders?scenario_id=1", body: { changes: [{ id: 30, field: "PriorityGroup", value: 2 }] } }));
  });

  it("Sipariş kartı: siparişin müşterisi ve projesi; Geçmiş kaydın düzeyli anahtarıyla", async () => {
    const { user, queries } = await open("Key user", {}, `${PATH}?sekme=siparis`);
    await user.click(screen.getByRole("button", { name: "SO-1030 / 1 işlemleri" }));
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Detay" }));
    const cards = await screen.findByRole("radiogroup", { name: "Kayıt bölümleri" });
    expect(within(cards).getAllByRole("radio").map((t) => t.textContent)).toEqual(["Müşteri", "Proje", "Geçmiş"]);
    await waitFor(() => expect(asked(queries, "priority-customers", [{ field: "Id", op: "in", values: ["2"] }])).toBe(true), { timeout: 4000 });   // siparişin müşterisi
    await user.click(cardTab("Proje"));
    await waitFor(() => expect(asked(queries, "priority-projects", [{ field: "Id", op: "in", values: ["2"] }])).toBe(true), { timeout: 4000 });
    await user.click(cardTab("Geçmiş"));
    // Geçmiş: kaydın anahtarı "<düzey>:<kimlik>" ve izleyen senaryodaki değişikliklerin senaryolu anahtarı
    await waitFor(() => expect((queries["record-history"] ?? []).some((q) => JSON.stringify(q).includes('"DemandPriority"')
      && JSON.stringify(q).includes('["orders:30","orders:30@1"]'))).toBe(true), { timeout: 4000 });
  }, 20000);

  it("Müşteri kartı: Siparişler ve Tahminler müşterinin koduyla süzülür; Geçmiş", async () => {
    const { user, queries } = await open();
    await user.click(screen.getByRole("button", { name: "MUS-A işlemleri" }));
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Detay" }));
    const cards = await screen.findByRole("radiogroup", { name: "Kayıt bölümleri" });
    expect(within(cards).getAllByRole("radio").map((t) => t.textContent)).toEqual(["Siparişler", "Tahminler", "Geçmiş"]);
    await waitFor(() => expect(asked(queries, "priority-orders", [{ field: "CustomerCode", op: "in", values: ["MUS-A"] }])).toBe(true), { timeout: 4000 });
    await user.click(cardTab("Tahminler"));
    await waitFor(() => expect(asked(queries, "priority-forecasts", [{ field: "CustomerCode", op: "in", values: ["MUS-A"] }])).toBe(true), { timeout: 4000 });
  });

  it("Proje sekmesi: kartta siparişler proje koduyla süzülür", async () => {
    const { user, queries } = await open("Key user", {}, `${PATH}?sekme=proje`);
    expect(heads()).toEqual(["Proje", "Ad", "ERP önceliği", "Öncelik grubu", "Kaynağı"]);
    expect([cellOf("PRJ-01", "ERP önceliği").textContent, cellOf("PRJ-01", "Öncelik grubu").textContent]).toEqual(["9", ""]);
    await user.click(screen.getByRole("button", { name: "PRJ-02 işlemleri" }));
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Detay" }));
    await waitFor(() => expect(asked(queries, "priority-orders", [{ field: "ProjectCode", op: "in", values: ["PRJ-02"] }])).toBe(true), { timeout: 4000 });
  });

  it("izleyen senaryo: fark işareti ve ipucunda Baz'daki değer; değeri senaryodan gelen satırda Senaryo farkını kaldır", async () => {
    const { user, calls } = await open("Key user", { scenario: { id: 2, name: "Kısıtsız kapasite", is_base: false }, customers: FOLLOWER_CUSTOMERS });
    const changed = cellOf("MUS-C", "Öncelik grubu");
    expect(changed).toHaveClass("sc-cell-diff");
    expect(cellOf("MUS-A", "Öncelik grubu")).not.toHaveClass("sc-cell-diff");
    await user.hover(within(changed).getByText("2"));
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Baz: 4");
    await user.click(screen.getByRole("button", { name: "MUS-A işlemleri" }));
    expect(within(await screen.findByRole("menu")).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Detay"]);
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "MUS-C işlemleri" }));
    const items = within(await screen.findByRole("menu")).getAllByRole("menuitem");
    expect(items.map((m) => m.textContent)).toEqual(["Detay", "Senaryo farkını kaldır"]);
    await user.click(items[1]);
    await waitFor(() => expect(calls.map((c) => [c.method, c.url])).toEqual([["POST", "/api/priorities/customers/3/restore?scenario_id=2"]]));
  });

  it("End user görür: düzenleme ve Kaydet yok; menüde yalnız Detay", async () => {
    const { user } = await open("End user", { scenario: { id: 2, name: "Kısıtsız kapasite", is_base: false }, customers: FOLLOWER_CUSTOMERS });
    expect(document.querySelector(".sc-table-edit-mark")).toBeNull();
    expect(cellOf("MUS-B", "Öncelik grubu")).not.toHaveClass("is-editable");
    await user.click(screen.getByRole("button", { name: "MUS-C işlemleri" }));
    expect(within(await screen.findByRole("menu")).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Detay"]);
  });
});

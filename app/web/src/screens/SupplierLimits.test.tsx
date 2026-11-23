// Model kısıtları › Tedarikçi limiti (ekran 31 ikinci sekme, fonksiyon 103; K-191; docs/12 "Model kısıtları"): ikinci sekme; Kayıtlar tablosu (iki tür
// aynı listede, türe uymayan hücre düzenlenmez); "Yeni kayıt" penceresi (tür seçimi, tedarikçiye göre malzeme listesi, zorunlu alan boşken Kaydet
// pasif; kapanışta çoklu malzeme ve "Tümü"); satır menüsü ve senaryo farkı; Geçerlilik zaman çubuğu (satır = tedarikçi + malzeme, "600 / ay", üst
// limit nane, kapanış amber ve üstte); End user.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { meAs, mockApi, renderApp, type Reply } from "../test/helpers";
import { col, useTableTestSetup } from "../table/testBackend";
import { cellOf } from "../table/testEditing";
import { forgetLocations } from "./locationField";

useTableTestSetup();

const PATH = "/parametre/model-kisitlari?sekme=tedarikci-limiti";
const LIST = "supplier-limits", VALIDITY = "supplier-limits-validity";
const EXPORT = { title: "x", file_slug: "x", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const COLUMNS = [
  col("LimitType", "Tür", "text", "list"), col("LocationCode", "Lokasyon", "text", "list"), col("SupplierCode", "Tedarikçi", "text", "list"),
  col("MaterialCode", "Malzeme", "text", "list"), col("ValidFrom", "Başlangıç", "date", "date"), col("ValidTo", "Bitiş", "date", "date"),
  col("UpperLimit", "Limit", "number", "number", { decimals: 2 }), col("LimitPeriod", "Limitin dönemi", "text", "list"), col("Uom", "Birim", "text", "list"),
  col("Reason", "Sebep", "text", "text"), col("Origin", "Kaynağı", "text", "list"), col("IsValid", "Geçerli", "bool", "list"),
];
const VALIDITY_COLUMNS = [
  col("LocationCode", "Lokasyon", "text", "list"), col("SupplierCode", "Tedarikçi", "text", "list"), col("MaterialCode", "Malzeme", "text", "list"),
  col("Status", "Durum", "text", "list"), col("ValidFrom", "Başlangıç", "date", "date"), col("ValidTo", "Bitiş", "date", "date"),
  col("UpperLimit", "Limit", "number", "number", { decimals: 2 }), col("LimitPeriod", "Limitin dönemi", "text", "list"),
  col("DailyAverage", "Günlük ortalama", "number", "number", { decimals: 2 }), col("Uom", "Birim", "text", "list"),
];
const entry = (id: number, type: string, supplier: [number, string], material: [number | null, string], extra: object = {}) => ({
  Id: id, StoredId: id, Origin: "Baz", IsValid: true, OverriddenFields: null, BaseValues: null, LimitType: type, LocationCode: "ORM-01", LocationId: 1,
  SupplierId: supplier[0], SupplierCode: supplier[1], MaterialId: material[0], MaterialCode: material[1], ValidFrom: "2026-10-26", ValidTo: null, UpperLimit: null,
  LimitPeriod: null, Uom: material[0] ? "KG" : null, Reason: null, ...extra });
const ROWS = [
  entry(11, "Üst limit", [1, "TED-01"], [121, "HAM-001"], { UpperLimit: 600, LimitPeriod: "Ay" }),
  entry(12, "Kapanış", [1, "TED-01"], [122, "HAM-002"], { ValidFrom: "2026-12-21", ValidTo: "2026-12-27", Reason: "Hat bakımı" }),
  entry(13, "Kapanış", [3, "TED-03"], [null, "Tümü"], { ValidFrom: "2026-12-28", ValidTo: "2027-01-03", Reason: "Yıl sonu tatili" }),
];
const FOLLOWER_ROWS = [
  entry(11, "Üst limit", [1, "TED-01"], [121, "HAM-001"], { UpperLimit: 900, LimitPeriod: "Ay", Origin: "Senaryo farkı", StoredId: 31, OverriddenFields: ",UpperLimit,",
                                                           BaseValues: JSON.stringify({ UpperLimit: 600, LimitPeriod: "Ay" }) }),
  ROWS[1],
];
const span = (id: number, supplier: [number, string], material: [number | null, string], status: string, from: string, to: string | null, extra: object = {}) => ({
  Id: id, LocationCode: "ORM-01", LocationId: 1, SupplierId: supplier[0], SupplierCode: supplier[1], MaterialId: material[0], MaterialCode: material[1], Status: status,
  ValidFrom: from, ValidTo: to, UpperLimit: null, LimitPeriod: null, DailyAverage: null, Uom: "KG", Reason: null, SourceRowId: id + 10, SourceOrigin: "Baz", ...extra });
const VALIDITY_ROWS = [
  span(1, [1, "TED-01"], [121, "HAM-001"], "Üst limit", "2026-10-26", "2027-01-10", { UpperLimit: 600, LimitPeriod: "Ay", DailyAverage: 19.35 }),
  span(2, [1, "TED-01"], [121, "HAM-001"], "Üst limit", "2027-01-11", null, { UpperLimit: 800, LimitPeriod: "Ay", DailyAverage: 25.81 }),
  span(3, [1, "TED-01"], [121, "HAM-001"], "Kapalı", "2026-12-21", "2026-12-27", { Reason: "Hat bakımı" }),
  span(4, [2, "TED-02"], [122, "HAM-002"], "Üst limit", "2026-10-26", null, { UpperLimit: 150, LimitPeriod: "Hafta", DailyAverage: 21.43 }),
  span(5, [3, "TED-03"], [null, "Tümü"], "Kapalı", "2026-12-28", "2027-01-03", { Reason: "Yıl sonu tatili", Uom: null }),
];
const OPTIONS = { suppliers: [
  { location_id: 1, location: "ORM-01", supplier_id: 1, code: "TED-01", name: "Anadolu Çubuk", materials: [{ id: 121, code: "HAM-001", name: "Çubuk 20", unit: "KG" },
                                                                                                       { id: 122, code: "HAM-002", name: "Çubuk 30", unit: "KG" }] },
  { location_id: 1, location: "ORM-01", supplier_id: 2, code: "TED-02", name: "Marmara Levha", materials: [{ id: 122, code: "HAM-002", name: "Çubuk 30", unit: "KG" }] },
] };

type Call = { method: string; url: string; body: Record<string, unknown> };

function backend(options: { scenario?: { id: number; name: string; is_base: boolean }; rows?: object[]; reply?: (call: Call) => Reply | undefined;
                            suppliers?: object[]; locations?: object[] } = {}) {
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
    "/api/capacity/horizon": { body: { start: "2026-11-16", end: "2027-02-14" } },
    ...list(LIST, COLUMNS, options.rows ?? ROWS),
    ...list(VALIDITY, VALIDITY_COLUMNS, VALIDITY_ROWS),
    ...list("model-constraints-resource-groups", [col("Code", "Kaynak grubu", "text", "text")], []),
    ...list("record-history", [col("At", "Tarih", "datetime", "date"), col("FieldLabel", "Alan", "text", "list")], []),
    "/api/model-constraints/supplier-limits/options": { body: options.suppliers ? { suppliers: options.suppliers } : OPTIONS },
    "/api/capacity/locations": { body: { locations: options.locations ?? [{ id: 1, code: "ORM-01", name: "Merkez fabrika" }] } },
    "/api/model-constraints/supplier-limits": (url: string, init?: RequestInit) => {
      const call = { method: init?.method ?? "GET", url, body: init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : {} };
      calls.push(call);
      return options.reply?.(call) ?? { status: call.method === "POST" && !url.includes("/restore") ? 201 : 200, body: { ids: [99], saved: 1, warnings: [] } };
    },
  });
  return { calls, queries };
}

const rowsOf = () => screen.getAllByRole("row").filter((r) => r.classList.contains("sc-table-row"));
async function open(role = "Key user", options: Parameters<typeof backend>[0] = {}) {
  const user = userEvent.setup();
  const server = backend(options);
  renderApp(PATH, meAs(role));
  await waitFor(() => expect(rowsOf().length).toBeGreaterThan(0), { timeout: 5000 });
  return { user, ...server };
}
const pick = async (user: ReturnType<typeof userEvent.setup>, dialog: HTMLElement, label: string, option: string) => {
  await user.click(within(dialog).getByRole("combobox", { name: label }));
  await user.click(await within(screen.getByRole("listbox", { name: label })).findByRole("option", { name: new RegExp(`^${option}`) }));
};
const typeDate = async (user: ReturnType<typeof userEvent.setup>, dialog: HTMLElement, label: string, text: string) => {
  const input = within(dialog).getByRole("textbox", { name: label });
  await user.clear(input);
  await user.type(input, text);
  await user.tab();
};

beforeEach(forgetLocations);

describe("ekran 31 · Model kısıtları › Tedarikçi limiti (K-191, 7.12)", () => {
  it("Lokasyon ilk alan (K-194): sıra Lokasyon · Tür · Tedarikçi · Malzeme; iki lokasyonda boş, tedarikçi listesi pasif; seçilince o lokasyonun tedarikçileri ('kod · ad')", async () => {
    const two = [...OPTIONS.suppliers, { location_id: 2, location: "ORM-02", supplier_id: 1, code: "TED-01", name: "Anadolu Çubuk",
                                         materials: [{ id: 221, code: "HAM-001", name: "Çubuk 20", unit: "KG" }] }];
    const { user, calls } = await open("Key user", { suppliers: two, locations: [{ id: 1, code: "ORM-01", name: "Merkez" }, { id: 2, code: "ORM-02", name: "İkinci" }] });
    await user.click(screen.getByRole("button", { name: "Yeni kayıt" }));
    const dialog = await screen.findByRole("dialog", { name: "Tedarikçi limiti · Yeni kayıt" });
    expect([...dialog.querySelectorAll(".sc-field-label")].map((l) => l.textContent).slice(0, 4)).toEqual(["Lokasyon", "Tür", "Tedarikçi", "Malzeme"]);
    const location = within(dialog).getByRole("combobox", { name: "Lokasyon" });
    const supplier = within(dialog).getByRole("combobox", { name: "Tedarikçi" });
    await waitFor(() => expect(supplier).toBeDisabled());
    expect(location).toHaveValue("");
    await user.click(location);
    await user.click(await screen.findByRole("option", { name: /^ORM-02/ }));
    await user.click(supplier);
    expect(within(await screen.findByRole("listbox", { name: "Tedarikçi" })).getAllByRole("option").map((o) => o.textContent)).toEqual(["TED-01Anadolu Çubuk"]);
    await user.click(screen.getByRole("option", { name: /TED-01/ }));
    await pick(user, dialog, "Malzeme", "HAM-001");
    await user.click(location);                                                                            // lokasyon değişir: tedarikçi ve malzeme temizlenir
    await user.click(await screen.findByRole("option", { name: /^ORM-01/ }));
    expect(supplier).toHaveValue("");
    expect(within(dialog).getByRole("combobox", { name: "Malzeme" })).toBeDisabled();
    await user.click(supplier);
    expect(within(await screen.findByRole("listbox", { name: "Tedarikçi" })).getAllByRole("option").map((o) => o.textContent)).toEqual(["TED-01Anadolu Çubuk", "TED-02Marmara Levha"]);
    await user.click(screen.getByRole("option", { name: /TED-02/ }));
    await pick(user, dialog, "Malzeme", "HAM-002");
    await typeDate(user, dialog, "Başlangıç", "01.02.2027");
    await user.type(within(dialog).getByRole("textbox", { name: /^Limit/ }), "10");
    await user.click(within(within(dialog).getByRole("radiogroup", { name: "Limitin dönemi" })).getByRole("radio", { name: "Ay" }));
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST")?.body.values).toMatchObject({ LocationId: 1, SupplierId: 2, MaterialId: 122 }));
  });

  it("veride tek lokasyon varsa Lokasyon dolu gelir (K-194)", async () => {
    const { user } = await open();
    await user.click(screen.getByRole("button", { name: "Yeni kayıt" }));
    const dialog = await screen.findByRole("dialog", { name: "Tedarikçi limiti · Yeni kayıt" });
    await waitFor(() => expect(within(dialog).getByRole("combobox", { name: "Lokasyon" })).toHaveValue("ORM-01 · Merkez fabrika"));
  });

  it("iki lokasyon: tedarikçisi olmayan lokasyon da listelenir, seçilince tedarikçi listesi boş ve 'Bu lokasyonda kayıt yok.'; Düzenle'de dört alan kilitli; kart başlığı lokasyonla (K-194)", async () => {
    const { user } = await open("Key user", { locations: [{ id: 1, code: "ORM-01", name: "Merkez" }, { id: 2, code: "ORM-02", name: "İkinci" }] });
    await user.click(screen.getByRole("button", { name: "Yeni kayıt" }));
    let dialog = await screen.findByRole("dialog", { name: "Tedarikçi limiti · Yeni kayıt" });
    const location = within(dialog).getByRole("combobox", { name: "Lokasyon" });
    await waitFor(() => expect(within(dialog).getByRole("combobox", { name: "Tedarikçi" })).toBeDisabled());
    expect(location).toHaveValue("");                                                                      // veride iki lokasyon: dolu gelmez (tedarikçiler tek lokasyonda olsa da)
    await user.click(location);
    await user.click(await screen.findByRole("option", { name: /^ORM-02/ }));
    await user.click(within(dialog).getByRole("combobox", { name: "Tedarikçi" }));
    const empty = await screen.findByRole("listbox", { name: "Tedarikçi" });
    expect(within(empty).queryAllByRole("option")).toHaveLength(0);
    expect(empty).toHaveTextContent("Bu lokasyonda kayıt yok.");
    expect(within(dialog).getByRole("button", { name: "Kaydet" })).toBeDisabled();
    await user.keyboard("{Escape}");
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: /^TED-01 · HAM-001 .* işlemleri$/ }));
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Düzenle" }));
    dialog = await screen.findByRole("dialog", { name: "Tedarikçi limiti · Düzenle" });
    expect(["Lokasyon", "Tür", "Tedarikçi", "Malzeme"].map((n) => [(within(dialog).getByRole("textbox", { name: n }) as HTMLInputElement).value,
                                                                     (within(dialog).getByRole("textbox", { name: n }) as HTMLInputElement).disabled])).toEqual([
      ["ORM-01", true], ["Üst limit", true], ["TED-01", true], ["HAM-001", true]]);
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: /^TED-01 · HAM-001 .* işlemleri$/ }));
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Detay" }));
    expect(await screen.findByText("ORM-01 · TED-01 · HAM-001")).toBeInTheDocument();                       // veride iki lokasyon: kart başlığı lokasyonla
  });

  it("ikinci sekme; Kayıtlar'da iki tür aynı listede; Lokasyon kodun solunda; türe uymayan hücre düzenlenmez; istek seçili senaryoyu taşır", async () => {
    const { queries } = await open();
    const tabs = within(screen.getByRole("radiogroup", { name: "Model kısıtları bölümleri" })).getAllByRole("radio");
    expect(tabs.map((t) => [t.textContent, t.getAttribute("aria-checked")])).toEqual([["Kaynak grubu", "false"], ["Tedarikçi limiti", "true"], ["Malzeme blokajı", "false"]]);
    expect(screen.getByRole("combobox", { name: "Tablo" })).toHaveValue("kayitlar");                                       // tablo seçimi Kayıtlar · Geçerlilik
    expect(screen.getByRole("button", { name: "Yeni kayıt" })).toBeInTheDocument();
    expect(queries[LIST][0]).toMatchObject({ scenario_id: 1 });
    const heads = screen.getAllByRole("columnheader").map((h) => h.querySelector(".sc-table-label")?.textContent).filter(Boolean);
    expect(heads.slice(0, 4)).toEqual(["Tür", "Lokasyon", "Tedarikçi", "Malzeme"]);
    const editable = screen.getAllByRole("columnheader").filter((h) => h.querySelector(".sc-table-edit-mark")).map((h) => h.querySelector(".sc-table-label")?.textContent);
    expect(editable).toEqual(["Başlangıç", "Bitiş", "Limit", "Limitin dönemi", "Sebep"]);
    expect(rowsOf()).toHaveLength(3);
    const [upper, closure, general] = rowsOf();
    const at = (row: HTMLElement, head: string) => row.querySelectorAll("td")[heads.indexOf(head)] as HTMLElement;
    expect([at(upper, "Tür").textContent, at(upper, "Limit").textContent, at(upper, "Limitin dönemi").textContent]).toEqual(["Üst limit", "600,00", "Ay"]);
    expect([at(general, "Tür").textContent, at(general, "Malzeme").textContent, at(general, "Limit").textContent, at(general, "Sebep").textContent]).toEqual([
      "Kapanış", "Tümü", "", "Yıl sonu tatili"]);
    // kapanışta Limit ve Limitin dönemi düzenlenmez; tarihler ve Sebep iki türde de düzenlenir
    expect(at(upper, "Limit")).toHaveClass("is-editable");
    expect(at(upper, "Sebep")).toHaveClass("is-editable");
    expect(at(closure, "Sebep")).toHaveClass("is-editable");
    expect(at(closure, "Limit")).not.toHaveClass("is-editable");
    expect(at(closure, "Limitin dönemi")).not.toHaveClass("is-editable");
    expect(at(closure, "Bitiş")).toHaveClass("is-editable");
    expect(at(upper, "Tür")).not.toHaveClass("is-editable");
    expect(cellOf("TED-03", "Malzeme")).toHaveTextContent("Tümü");
  });

  it("Yeni kayıt: 'Üst limit' seçili açılır; Sebep iki türde; malzeme listesi yalnız seçili tedarikçinin; zorunlu alan boşken Kaydet pasif; değerler tipli gider", async () => {
    const { user, calls } = await open();
    await user.click(screen.getByRole("button", { name: "Yeni kayıt" }));
    const dialog = await screen.findByRole("dialog", { name: "Tedarikçi limiti · Yeni kayıt" });
    const save = within(dialog).getByRole("button", { name: "Kaydet" });
    expect(save).toBeDisabled();
    const types = within(within(dialog).getByRole("radiogroup", { name: "Tür" })).getAllByRole("radio");
    expect(types.map((t) => [t.textContent, t.getAttribute("aria-checked")])).toEqual([["Üst limit", "true"], ["Tedarikçi kapanışı", "false"]]);    // "Üst limit" seçili açılır
    expect(within(within(dialog).getByRole("radiogroup", { name: "Limitin dönemi" })).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Gün", "Hafta", "Ay", "Çeyrek", "Yıl"]);
    expect(within(within(dialog).getByRole("radiogroup", { name: "Limitin dönemi" })).getAllByRole("radio").every((r) => r.getAttribute("aria-checked") === "false")).toBe(true);
    expect(within(dialog).getByRole("textbox", { name: "Sebep" })).toHaveValue("");                                          // Sebep üst limitte de var (isteğe bağlı)
    expect(within(dialog).getByRole("combobox", { name: "Malzeme" })).toBeDisabled();                                       // önce tedarikçi
    await pick(user, dialog, "Tedarikçi", "TED-02");
    await user.click(within(dialog).getByRole("combobox", { name: "Malzeme" }));
    expect(within(screen.getByRole("listbox", { name: "Malzeme" })).getAllByRole("option").map((o) => o.textContent)).toEqual(["HAM-002Çubuk 30"]);   // yalnız TED-02'nin malzemesi
    await user.keyboard("{Escape}");
    await pick(user, dialog, "Tedarikçi", "TED-01");
    await user.click(within(dialog).getByRole("combobox", { name: "Malzeme" }));
    expect(within(screen.getByRole("listbox", { name: "Malzeme" })).getAllByRole("option").map((o) => o.textContent)).toEqual(["HAM-001Çubuk 20", "HAM-002Çubuk 30"]);
    await user.click(within(screen.getByRole("listbox", { name: "Malzeme" })).getByRole("option", { name: /^HAM-001/ }));
    await typeDate(user, dialog, "Başlangıç", "01.02.2027");
    expect(save).toBeDisabled();                                                                                           // limit ve dönem boş
    await user.type(within(dialog).getByRole("textbox", { name: /^Limit/ }), "750,5");
    await user.click(within(within(dialog).getByRole("radiogroup", { name: "Limitin dönemi" })).getByRole("radio", { name: "Hafta" }));
    expect(save).toBeEnabled();                                                                                            // Sebep boşken de kaydedilir
    await user.type(within(dialog).getByRole("textbox", { name: "Sebep" }), "Sözleşme");
    await user.click(save);
    await waitFor(() => expect(calls.filter((c) => c.method === "POST")).toHaveLength(1));
    expect(calls[0].url).toContain("/api/model-constraints/supplier-limits?scenario_id=1");
    expect(calls[0].body.values).toEqual({ LimitType: "Üst limit", LocationId: 1, SupplierId: 1, MaterialId: 121, ValidFrom: "2027-02-01", ValidTo: null, UpperLimit: 750.5,
                                           LimitPeriod: "Hafta", Reason: "Sözleşme" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("Yeni kayıt · Tedarikçi kapanışı: birden çok malzeme seçilir (her biri ayrı kayıt), seçilmezse 'Tümü'; bitiş zorunlu; reddedilen alanın altında neden", async () => {
    let reject = true;
    const { user, calls } = await open("Key user", { reply: (call) => (call.method === "POST" && reject
      ? { status: 422, body: { error: { code: "validation", message: "Girilen bilgiler geçersiz.", trace_id: "t", details: [{ field: "ValidTo", problem: "Bitiş başlangıçtan önce olamaz." }] } } }
      : undefined) });
    await user.click(screen.getByRole("button", { name: "Yeni kayıt" }));
    const dialog = await screen.findByRole("dialog", { name: "Tedarikçi limiti · Yeni kayıt" });
    await user.click(within(dialog).getByRole("radio", { name: "Tedarikçi kapanışı" }));
    expect(within(dialog).queryByRole("textbox", { name: /^Limit/ })).toBeNull();
    expect(within(dialog).getByRole("textbox", { name: "Sebep" })).toBeInTheDocument();
    await pick(user, dialog, "Tedarikçi", "TED-01");
    const picked = () => within(within(dialog).getByRole("list", { name: "Seçilen malzemeler" })).getAllByRole("listitem").map((li) => li.textContent?.replace("×", ""));
    expect(picked()).toEqual(["Tümü"]);                                                                                    // malzeme seçilmezse bütün malzemeler
    await pick(user, dialog, "Malzeme", "HAM-001");
    await pick(user, dialog, "Malzeme", "HAM-002");
    expect(picked()).toEqual(["HAM-001", "HAM-002"]);
    await user.click(within(dialog).getByRole("button", { name: "HAM-001 seçimini kaldır" }));
    expect(picked()).toEqual(["HAM-002"]);
    await pick(user, dialog, "Malzeme", "HAM-001");
    await typeDate(user, dialog, "Başlangıç", "10.02.2027");
    const save = within(dialog).getByRole("button", { name: "Kaydet" });
    expect(save).toBeDisabled();                                                                                           // kapanışta bitiş zorunlu
    await typeDate(user, dialog, "Bitiş", "05.02.2027");
    await user.type(within(dialog).getByRole("textbox", { name: "Sebep" }), "Sayım");
    await user.click(save);
    expect(await within(dialog).findByText("Bitiş başlangıçtan önce olamaz.")).toBeInTheDocument();
    reject = false;
    await typeDate(user, dialog, "Bitiş", "12.02.2027");
    await user.click(save);
    await waitFor(() => expect(calls.filter((c) => c.method === "POST")).toHaveLength(2));
    expect(calls[1].body.values).toEqual({ LimitType: "Kapanış", LocationId: 1, SupplierId: 1, MaterialIds: [122, 121], ValidFrom: "2027-02-10", ValidTo: "2027-02-12",
                                           Reason: "Sayım" });
  });

  it("izleyen senaryo: fark işareti ve ipucu; farkta Senaryo farkını kaldır; Düzenle'de tür, tedarikçi ve malzeme kilitli", async () => {
    const { user, calls } = await open("Key user", { scenario: { id: 2, name: "Kısıtsız kapasite", is_base: false }, rows: FOLLOWER_ROWS });
    const changed = cellOf("HAM-001", "Limit");
    expect(changed).toHaveClass("sc-cell-diff");
    await user.hover(within(changed).getByText("900,00"));
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Baz: 600,00");
    await user.click(screen.getByRole("button", { name: /^TED-01 · HAM-001 .* işlemleri$/ }));
    const items = within(await screen.findByRole("menu")).getAllByRole("menuitem");
    expect(items.map((m) => m.textContent)).toEqual(["Detay", "Düzenle", "Yeni kayıt", "Geçersiz yap", "Senaryo farkını kaldır"]);
    await user.click(items[4]);
    await waitFor(() => expect(calls.map((c) => [c.method, c.url])).toEqual([["POST", "/api/model-constraints/supplier-limits/11/restore?scenario_id=2"]]));
    await user.click(screen.getByRole("button", { name: /^TED-01 · HAM-002 .* işlemleri$/ }));
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Tedarikçi limiti · Düzenle" });
    expect(["Tür", "Tedarikçi", "Malzeme"].map((n) => [(within(dialog).getByRole("textbox", { name: n }) as HTMLInputElement).value,
                                                         (within(dialog).getByRole("textbox", { name: n }) as HTMLInputElement).disabled])).toEqual([
      ["Tedarikçi kapanışı", true], ["TED-01", true], ["HAM-002", true]]);
    expect(within(dialog).getByRole("textbox", { name: "Sebep" })).toHaveValue("Hat bakımı");
  });

  it("Geçerlilik: zaman çubuğunda her satır bir tedarikçi ve malzeme; üst limit nane ve '600 / ay', kapanış amber ve üstte; genel kapanış 'Tümü' satırında", async () => {
    const { user, queries } = await open();
    await user.selectOptions(screen.getByRole("combobox", { name: "Tablo" }), "gecerlilik");
    await waitFor(() => expect(queries[VALIDITY]?.length ?? 0).toBeGreaterThan(0));
    const box = await screen.findByRole("group", { name: "Geçerlilik zaman çubuğu" });
    expect(box.querySelector(".sc-validity-corner")).toHaveTextContent("Tedarikçi · Malzeme");
    expect([...box.querySelectorAll(".sc-validity-label")].map((l) => l.textContent)).toEqual(["TED-01 · HAM-001", "TED-02 · HAM-002", "TED-03 · Tümü"]);
    const bars = [...box.querySelectorAll(".sc-validity-bar")];
    const spans = (i: number) => [...bars[i].querySelectorAll<HTMLElement>(".sc-validity-span")].map((s) => [s.textContent, s.classList.contains("is-own") ? "amber" : "nane"]);
    expect(spans(0)).toEqual([["600 / ay", "nane"], ["800 / ay", "nane"], ["Kapalı", "amber"]]);                            // kapanış sonda: üstte çizilir
    expect(spans(1)).toEqual([["150 / hafta", "nane"]]);
    expect(spans(2)).toEqual([["Kapalı", "amber"]]);
    expect(bars[0].querySelector<HTMLElement>(".sc-validity-span")!.title.split("\n")).toEqual([
      "TED-01 · HAM-001", "Limit: 600 KG / ay", "26.10.2026 – 10.01.2027", "Günlük ortalama: 19,35 KG"]);
    expect(bars[2].querySelector<HTMLElement>(".sc-validity-span")!.title.split("\n")).toEqual(["TED-03 · Tümü", "Kapalı", "28.12.2026 – 03.01.2027", "Yıl sonu tatili"]);
    expect(document.querySelector(".sc-table-edit-mark")).toBeNull();                                                      // Geçerlilik'te hücre düzenleme yok
  });

  it("End user görür: Yeni kayıt, düzenleme ve satır işlemleri yok (yalnız Detay)", async () => {
    const { user } = await open("End user");
    expect(screen.queryByRole("button", { name: "Yeni kayıt" })).toBeNull();
    expect(document.querySelector(".sc-table-edit-mark")).toBeNull();
    await user.click(screen.getByRole("button", { name: /^TED-01 · HAM-001 .* işlemleri$/ }));
    expect(within(await screen.findByRole("menu")).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Detay"]);
  });
});

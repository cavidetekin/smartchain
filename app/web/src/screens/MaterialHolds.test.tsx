// Model kısıtları › Malzeme blokajı (ekran 31 üçüncü sekme, fonksiyon 99; K-193; docs/12 "Model kısıtları"): üçüncü sekme; Kayıtlar tablosu (tür,
// tarihler, oran ve sebep düzenlenir); "Yeni kayıt" penceresi (tür ve oran boş açılır, malzemenin tedarik biçimine uymayan tür pasif, zorunlu alan
// boşken Kaydet pasif); satır menüsü ve senaryo farkı; Geçerlilik zaman çubuğu (satır = malzeme, dilim = plan dönemi; Üretim amber, Satın alma nane,
// ikisi mercan, açık kalan dönem çerçeveli; "%67"); End user.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { meAs, mockApi, renderApp, type Reply } from "../test/helpers";
import { col, useTableTestSetup } from "../table/testBackend";
import { cellOf } from "../table/testEditing";
import { forgetLocations } from "./locationField";
import { describePeriod, mergePeriods, typeFits } from "./MaterialHolds";

useTableTestSetup();

const PATH = "/parametre/model-kisitlari?sekme=malzeme-blokaji";
const LIST = "material-holds", VALIDITY = "material-holds-validity";
const EXPORT = { title: "x", file_slug: "x", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const COLUMNS = [
  col("LocationCode", "Lokasyon", "text", "list"), col("MaterialCode", "Malzeme", "text", "list"), col("HoldType", "Tür", "text", "list"),
  col("StartDate", "Başlangıç", "date", "date"), col("EndDate", "Bitiş", "date", "date"), col("ClosePct", "Dönemi kapatma oranı (%)", "number", "number", { decimals: 2 }),
  col("Reason", "Sebep", "text", "text"), col("Origin", "Kaynağı", "text", "list"), col("IsValid", "Geçerli", "bool", "list"),
];
const VALIDITY_COLUMNS = [
  col("LocationCode", "Lokasyon", "text", "list"), col("MaterialCode", "Malzeme", "text", "list"), col("Supply", "Tedarik", "text", "list"), col("Period", "Dönem", "text", "list"),
  col("PeriodStart", "Dönem başı", "date", "date"), col("PeriodEnd", "Dönem sonu", "date", "date"), col("BlockedDays", "Blokajlı gün", "integer", "number"),
  col("Ratio", "Oran (%)", "number", "number", { decimals: 1 }), col("Threshold", "Eşik (%)", "number", "number", { decimals: 2 }), col("Status", "Durum", "text", "list"),
];
const entry = (id: number, material: [number, string], type: string, from: string, to: string | null, extra: object = {}) => ({
  Id: id, StoredId: id, Origin: "Baz", IsValid: true, OverriddenFields: null, BaseValues: null, LocationCode: "ORM-01", LocationId: 1, MaterialId: material[0],
  MaterialCode: material[1], HoldType: type, StartDate: from, EndDate: to, ClosePct: 50, Reason: null, ...extra });
const ROWS = [
  entry(11, [81, "ALT-020"], "Üretim", "2027-02-01", "2027-02-10", { Reason: "Hat bakımı" }),
  entry(12, [81, "ALT-020"], "Üretim ve satın alma", "2027-03-01", "2027-03-20", { Reason: "Tasarım değişikliği" }),
  entry(13, [190, "SAT-030"], "Satın alma", "2027-04-01", null, { Reason: "Tedarikçi geçişi" }),
];
const FOLLOWER_ROWS = [
  ROWS[0],
  entry(12, [81, "ALT-020"], "Üretim ve satın alma", "2027-03-01", "2027-03-25", { Origin: "Senaryo farkı", StoredId: 31, OverriddenFields: ",EndDate,",
                                                                                  BaseValues: JSON.stringify({ EndDate: "2027-03-20" }) }),
];
const period = (id: number, material: [number, string], supply: string, label: string, from: string, to: string, days: number, blocked: number, status: string, source: number) => ({
  Id: id, LocationCode: "ORM-01", LocationId: 1, MaterialId: material[0], MaterialCode: material[1], Supply: supply, Period: label, PeriodStart: from, PeriodEnd: to,
  PeriodDays: days, BlockedDays: blocked, Ratio: Math.round(blocked * 1000 / days) / 10, Threshold: 50, Status: status, SourceRowId: source });
const VALIDITY_ROWS = [
  period(1, [81, "ALT-020"], "Üretim", "Şub 2027", "2027-02-01", "2027-02-28", 28, 10, "Açık", 11),
  period(2, [81, "ALT-020"], "Üretim", "Mar 2027", "2027-03-01", "2027-03-31", 31, 20, "Kapalı", 12),
  period(3, [81, "ALT-020"], "Satın alma", "Mar 2027", "2027-03-01", "2027-03-31", 31, 20, "Kapalı", 12),
  period(4, [190, "SAT-030"], "Satın alma", "Nis 2027", "2027-04-01", "2027-04-30", 30, 30, "Kapalı", 13),
  period(5, [82, "ALT-021"], "Üretim", "Nis 2027", "2027-04-01", "2027-04-30", 30, 20, "Kapalı", 14),
  period(6, [82, "ALT-021"], "Satın alma", "Nis 2027", "2027-04-01", "2027-04-30", 30, 5, "Açık", 15),
];
const OPTIONS = { types: ["Üretim", "Satın alma", "Üretim ve satın alma"], materials: [
  { location_id: 1, location: "ORM-01", material_id: 81, code: "ALT-020", name: "Mil grubu", producible: true, purchasable: null },
  { location_id: 1, location: "ORM-01", material_id: 82, code: "ALT-021", name: "Kapak montajı", producible: true, purchasable: false },
  { location_id: 1, location: "ORM-01", material_id: 190, code: "SAT-030", name: "Kama 8×7×40", producible: false, purchasable: true },
] };

type Call = { method: string; url: string; body: Record<string, unknown> };

function backend(options: { scenario?: { id: number; name: string; is_base: boolean }; rows?: object[]; reply?: (call: Call) => Reply | undefined;
                            materials?: object[]; validity?: object[] } = {}) {
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
    "/api/capacity/horizon": { body: { start: "2026-11-23", end: "2027-07-31" } },
    ...list(LIST, COLUMNS, options.rows ?? ROWS),
    ...list(VALIDITY, VALIDITY_COLUMNS, options.validity ?? VALIDITY_ROWS),
    ...list("model-constraints-resource-groups", [col("Code", "Kaynak grubu", "text", "text")], []),
    ...list("record-history", [col("At", "Tarih", "datetime", "date"), col("FieldLabel", "Alan", "text", "list")], []),
    "/api/model-constraints/material-holds/options": { body: options.materials ? { ...OPTIONS, materials: options.materials } : OPTIONS },
    "/api/capacity/locations": { body: { locations: options.materials ? [{ id: 1, code: "ORM-01", name: "Merkez" }, { id: 2, code: "ORM-02", name: "İkinci" },
                                                                        { id: 3, code: "V-LOC-1", name: "Boş lokasyon" }] : [{ id: 1, code: "ORM-01", name: "Merkez" }] } },
    "/api/model-constraints/material-holds": (url: string, init?: RequestInit) => {
      const call = { method: init?.method ?? "GET", url, body: init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : {} };
      calls.push(call);
      return options.reply?.(call) ?? { status: call.method === "POST" && !url.includes("/restore") ? 201 : 200, body: { id: 99, saved: 1, warnings: [] } };
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
const types = (dialog: HTMLElement) => within(within(dialog).getByRole("radiogroup", { name: "Tür" })).getAllByRole("radio");

beforeEach(forgetLocations);

describe("ekran 31 · Model kısıtları › Malzeme blokajı (K-193, 7.13)", () => {
  it("Lokasyon ilk alan (K-194): sıra Lokasyon · Malzeme · Tür; tek lokasyonda dolu; iki lokasyonda boş, malzeme listesi pasif ve seçilen lokasyona süzülür; Düzenle'de kilitli", async () => {
    const two = [...OPTIONS.materials, { location_id: 2, location: "ORM-02", material_id: 281, code: "ALT-020", name: "Mil grubu (2)", producible: true, purchasable: true }];
    const { user, calls } = await open("Key user", { materials: two });
    await user.click(screen.getByRole("button", { name: "Yeni kayıt" }));
    let dialog = await screen.findByRole("dialog", { name: "Malzeme blokajı · Yeni kayıt" });
    expect([...dialog.querySelectorAll(".sc-field-label")].map((l) => l.textContent).slice(0, 3)).toEqual(["Lokasyon", "Malzeme", "Tür"]);
    const location = within(dialog).getByRole("combobox", { name: "Lokasyon" });
    const material = within(dialog).getByRole("combobox", { name: "Malzeme" });
    await waitFor(() => expect(material).toBeDisabled());
    expect(location).toHaveValue("");
    await user.click(location);
    await user.click(await screen.findByRole("option", { name: /^V-LOC-1/ }));                             // malzemesi olmayan lokasyon da listelenir (demo bulgusu)
    await user.click(material);
    const empty = await screen.findByRole("listbox", { name: "Malzeme" });
    expect(within(empty).queryAllByRole("option")).toHaveLength(0);
    expect(empty).toHaveTextContent("Bu lokasyonda kayıt yok.");
    await user.click(location);
    await user.click(await screen.findByRole("option", { name: /^ORM-02/ }));
    await user.click(material);
    expect(within(await screen.findByRole("listbox", { name: "Malzeme" })).getAllByRole("option").map((o) => o.textContent)).toEqual(["ALT-020Mil grubu (2)"]);   // aynı kod, öteki lokasyon
    await user.click(screen.getByRole("option", { name: /ALT-020/ }));
    await user.click(types(dialog)[0]);
    await typeDate(user, dialog, "Başlangıç", "01.05.2027");
    await user.type(within(dialog).getByRole("textbox", { name: "Dönemi kapatma oranı (%)" }), "50");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls.find((c) => c.method === "POST")?.body.values).toMatchObject({ LocationId: 2, MaterialId: 281 }));
    await user.click(screen.getByRole("button", { name: /^SAT-030 · .* işlemleri$/ }));
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Düzenle" }));
    dialog = await screen.findByRole("dialog", { name: "Malzeme blokajı · Düzenle" });
    const locked = within(dialog).getByRole("textbox", { name: "Lokasyon" }) as HTMLInputElement;
    expect([locked.value, locked.disabled]).toEqual(["ORM-01", true]);
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: /^SAT-030 · .* işlemleri$/ }));                     // satırdan Yeni kayıt: lokasyon ve malzeme dolu
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Yeni kayıt" }));
    dialog = await screen.findByRole("dialog", { name: "Malzeme blokajı · Yeni kayıt" });
    await waitFor(() => expect(within(dialog).getByRole("combobox", { name: "Malzeme" })).toHaveValue("SAT-030 · Kama 8×7×40"));
    expect(within(dialog).getByRole("combobox", { name: "Lokasyon" })).toHaveValue("ORM-01 · Merkez");
  });

  it("Geçerlilik zaman çubuğu: veride birden çok lokasyon varsa sol kolonda kod lokasyonla (K-194)", async () => {
    const { user, queries } = await open("Key user", { validity: [VALIDITY_ROWS[0], { ...VALIDITY_ROWS[3], LocationCode: "ORM-02", LocationId: 2 }] });
    await user.selectOptions(screen.getByRole("combobox", { name: "Tablo" }), "gecerlilik");
    await waitFor(() => expect(queries[VALIDITY]?.length ?? 0).toBeGreaterThan(0));
    const box = await screen.findByRole("group", { name: "Geçerlilik zaman çubuğu" });
    expect([...box.querySelectorAll(".sc-validity-label")].map((l) => l.textContent)).toEqual(["ORM-01 · ALT-020", "ORM-02 · SAT-030"]);
  });

  it("üçüncü sekme; Kayıtlar'da Lokasyon kodun solunda; tür, tarihler, oran ve sebep düzenlenir; istek seçili senaryoyu taşır", async () => {
    const { queries } = await open();
    const tabs = within(screen.getByRole("radiogroup", { name: "Model kısıtları bölümleri" })).getAllByRole("radio");
    expect(tabs.map((t) => [t.textContent, t.getAttribute("aria-checked")])).toEqual([["Kaynak grubu", "false"], ["Tedarikçi limiti", "false"], ["Malzeme blokajı", "true"]]);
    expect(screen.getByRole("combobox", { name: "Tablo" })).toHaveValue("kayitlar");
    expect(screen.getByRole("button", { name: "Yeni kayıt" })).toBeInTheDocument();
    expect(queries[LIST][0]).toMatchObject({ scenario_id: 1 });
    const heads = screen.getAllByRole("columnheader").map((h) => h.querySelector(".sc-table-label")?.textContent).filter(Boolean);
    expect(heads.slice(0, 3)).toEqual(["Lokasyon", "Malzeme", "Tür"]);
    const editable = screen.getAllByRole("columnheader").filter((h) => h.querySelector(".sc-table-edit-mark")).map((h) => h.querySelector(".sc-table-label")?.textContent);
    expect(editable).toEqual(["Tür", "Başlangıç", "Bitiş", "Dönemi kapatma oranı (%)", "Sebep"]);
    expect(rowsOf()).toHaveLength(3);
    expect(cellOf("SAT-030", "Tür")).toHaveTextContent("Satın alma");
    expect(cellOf("SAT-030", "Bitiş")).toHaveTextContent("");                                                              // süresiz
    expect(cellOf("SAT-030", "Dönemi kapatma oranı (%)")).toHaveTextContent("50,00");
    expect(cellOf("SAT-030", "Malzeme")).not.toHaveClass("is-editable");
    expect(cellOf("SAT-030", "Tür")).toHaveClass("is-editable");
  });

  it("Yeni kayıt: tür ve oran boş açılır; malzemenin tedarik biçimine uymayan tür pasif (boş alan izin verir); zorunlu alan boşken Kaydet pasif; değerler tipli gider", async () => {
    const { user, calls } = await open();
    await user.click(screen.getByRole("button", { name: "Yeni kayıt" }));
    const dialog = await screen.findByRole("dialog", { name: "Malzeme blokajı · Yeni kayıt" });
    const save = within(dialog).getByRole("button", { name: "Kaydet" });
    expect(types(dialog).map((t) => [t.textContent, t.getAttribute("aria-checked")])).toEqual([["Üretim", "false"], ["Satın alma", "false"], ["Üretim ve satın alma", "false"]]);
    expect(within(dialog).getByRole("textbox", { name: "Dönemi kapatma oranı (%)" })).toHaveValue("");                       // tür ve oran boş (K-138)
    expect(save).toBeDisabled();
    await pick(user, dialog, "Malzeme", "SAT-030");                                                                          // yalnız satın alınan
    await waitFor(() => expect(types(dialog).map((t) => (t as HTMLInputElement | HTMLButtonElement).disabled)).toEqual([true, false, true]));
    await pick(user, dialog, "Malzeme", "ALT-021");                                                                          // yalnız üretilen
    await waitFor(() => expect(types(dialog).map((t) => (t as HTMLInputElement | HTMLButtonElement).disabled)).toEqual([false, true, true]));
    await user.click(types(dialog)[0]);
    await pick(user, dialog, "Malzeme", "SAT-030");                                                                          // seçili tür yeni malzemeye uymuyor: boşalır
    await waitFor(() => expect(types(dialog).every((t) => t.getAttribute("aria-checked") === "false")).toBe(true));
    await pick(user, dialog, "Malzeme", "ALT-020");                                                                          // satın alınabilirliği boş: üç tür de açık
    await waitFor(() => expect(types(dialog).map((t) => (t as HTMLInputElement | HTMLButtonElement).disabled)).toEqual([false, false, false]));
    await user.click(types(dialog)[2]);
    await typeDate(user, dialog, "Başlangıç", "01.05.2027");
    expect(save).toBeDisabled();                                                                                             // oran boş
    await user.type(within(dialog).getByRole("textbox", { name: "Dönemi kapatma oranı (%)" }), "62,5");
    await waitFor(() => expect(save).toBeEnabled());                                                                         // bitiş ve sebep boşken de kaydedilir
    await user.type(within(dialog).getByRole("textbox", { name: "Sebep" }), "Kalıp değişimi");
    await user.click(save);
    await waitFor(() => expect(calls.filter((c) => c.method === "POST")).toHaveLength(1));
    expect(calls[0].url).toContain("/api/model-constraints/material-holds?scenario_id=1");
    expect(calls[0].body.values).toEqual({ LocationId: 1, MaterialId: 81, HoldType: "Üretim ve satın alma", StartDate: "2027-05-01", EndDate: null, ClosePct: 62.5,
                                           Reason: "Kalıp değişimi" });
  });

  it("reddedilen alanın altında neden; pencere kapanmaz", async () => {
    const { user } = await open("Key user", { reply: (call) => (call.method === "POST" ? { status: 422, body: { error: { code: "validation", message: "Girilen bilgiler geçersiz.",
      details: [{ field: "HoldType", problem: "Bu malzeme satın alınmıyor." }, { field: "ClosePct", problem: "0'dan büyük, en çok 100 olmalı." }] } } } : undefined) });
    await user.click(screen.getByRole("button", { name: "Yeni kayıt" }));
    const dialog = await screen.findByRole("dialog", { name: "Malzeme blokajı · Yeni kayıt" });
    await pick(user, dialog, "Malzeme", "ALT-020");
    await user.click(types(dialog)[1]);
    await typeDate(user, dialog, "Başlangıç", "01.05.2027");
    await user.type(within(dialog).getByRole("textbox", { name: "Dönemi kapatma oranı (%)" }), "50");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    expect(await within(dialog).findByText("Bu malzeme satın alınmıyor.")).toBeInTheDocument();
    expect(within(dialog).getByText("0'dan büyük, en çok 100 olmalı.")).toBeInTheDocument();
  });

  it("izleyen senaryo: fark işareti ve ipucu; farkta Senaryo farkını kaldır; Düzenle'de malzeme kilitli, tür değişir", async () => {
    const { user, calls } = await open("Key user", { scenario: { id: 2, name: "Kısıtsız kapasite", is_base: false }, rows: FOLLOWER_ROWS });
    const [first, changedRow] = rowsOf();
    const heads = screen.getAllByRole("columnheader").map((h) => h.querySelector(".sc-table-label")?.textContent).filter(Boolean);
    const changed = changedRow.querySelectorAll("td")[heads.indexOf("Bitiş")] as HTMLElement;
    expect(changed).toHaveClass("sc-cell-diff");
    await user.hover(within(changed).getByText("25.03.2027"));
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Baz: 20.03.2027");
    await user.click(within(changedRow).getByRole("button", { name: /^ALT-020 · 01\.03\.2027 işlemleri$/ }));
    const items = within(await screen.findByRole("menu")).getAllByRole("menuitem");
    expect(items.map((m) => m.textContent)).toEqual(["Detay", "Düzenle", "Yeni kayıt", "Geçersiz yap", "Senaryo farkını kaldır"]);
    await user.click(items[4]);
    await waitFor(() => expect(calls.map((c) => [c.method, c.url])).toEqual([["POST", "/api/model-constraints/material-holds/12/restore?scenario_id=2"]]));
    await user.click(within(first).getByRole("button", { name: /^ALT-020 · 01\.02\.2027 işlemleri$/ }));
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Malzeme blokajı · Düzenle" });
    const material = within(dialog).getByRole("textbox", { name: "Malzeme" }) as HTMLInputElement;
    expect([material.value, material.disabled]).toEqual(["ALT-020", true]);
    expect(types(dialog).map((t) => t.getAttribute("aria-checked"))).toEqual(["true", "false", "false"]);
    expect(within(dialog).getByRole("textbox", { name: "Dönemi kapatma oranı (%)" })).toHaveValue("50,00");
    await user.click(types(dialog)[2]);
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls.at(-1)).toMatchObject({ method: "PUT", body: { changes: [{ id: 11, field: "HoldType", value: "Üretim ve satın alma" }] } }));
  });

  it("Geçerlilik: her satır bir malzeme, her dilim bir plan dönemi; Üretim amber, Satın alma nane, ikisi mercan; açık kalan dönem çerçeveli; dilimde oran", async () => {
    const { user, queries } = await open();
    await user.selectOptions(screen.getByRole("combobox", { name: "Tablo" }), "gecerlilik");
    await waitFor(() => expect(queries[VALIDITY]?.length ?? 0).toBeGreaterThan(0));
    const box = await screen.findByRole("group", { name: "Geçerlilik zaman çubuğu" });
    expect(box.querySelector(".sc-validity-corner")).toHaveTextContent("Malzeme");
    expect([...box.querySelectorAll(".sc-validity-label")].map((l) => l.textContent)).toEqual(["ALT-020", "SAT-030", "ALT-021"]);
    const bars = [...box.querySelectorAll(".sc-validity-bar")];
    const tone = (s: HTMLElement) => `${s.classList.contains("is-both") ? "mercan" : s.classList.contains("is-own") ? "amber" : "nane"}${s.classList.contains("is-outline") ? " çerçeveli" : ""}`;
    const spans = (i: number) => [...bars[i].querySelectorAll<HTMLElement>(".sc-validity-span")].map((s) => [s.textContent, tone(s)]);
    expect(spans(0)).toEqual([["%35,7", "amber çerçeveli"], ["%64,5", "mercan"]]);                                          // Şubat açık (10 / 28); Mart iki tedarik biçiminde kapalı
    expect(spans(1)).toEqual([["%100", "nane"]]);
    expect(spans(2)).toEqual([["%66,7", "amber"]]);                                                                         // yalnız Üretim kapalı; Satın alma blokajlı ama açık
    expect(bars[0].querySelectorAll<HTMLElement>(".sc-validity-span")[1].title.split("\n")).toEqual([
      "ALT-020", "Mar 2027 (01.03.2027 – 31.03.2027)", "Üretim: 20 / 31 gün · %64,5 · eşik %50 · Kapalı", "Satın alma: 20 / 31 gün · %64,5 · eşik %50 · Kapalı"]);
    expect(bars[2].querySelector<HTMLElement>(".sc-validity-span")!.title.split("\n").slice(2)).toEqual([
      "Üretim: 20 / 30 gün · %66,7 · eşik %50 · Kapalı", "Satın alma: 5 / 30 gün · %16,7 · eşik %50 · Açık"]);
    expect(rowsOf()).toHaveLength(6);                                                                                        // tabloda tedarik biçimleri ayrı satır
    expect(document.querySelector(".sc-table-edit-mark")).toBeNull();                                                        // Geçerlilik'te hücre düzenleme yok
  });

  it("dönem birleştirme ve tür uygunluğu (birim)", () => {
    const merged = mergePeriods(VALIDITY_ROWS);
    expect(merged.map((r) => [r.MaterialCode, r.ValidFrom, r.ValidTo, (r._parts as unknown[]).length])).toEqual([
      ["ALT-020", "2027-02-01", "2027-02-28", 1], ["ALT-020", "2027-03-01", "2027-03-31", 2], ["SAT-030", "2027-04-01", "2027-04-30", 1], ["ALT-021", "2027-04-01", "2027-04-30", 2]]);
    expect(merged.map((r) => { const s = describePeriod(r); return [s.tone, Boolean(s.outline)]; })).toEqual([["own", true], ["both", false], ["group", false], ["own", false]]);
    const open = describePeriod({ ...VALIDITY_ROWS[5], _parts: [{ ...VALIDITY_ROWS[5] }, { ...VALIDITY_ROWS[0], Status: "Açık" }] });
    expect([open.tone, open.outline]).toEqual(["both", true]);                                                              // ikisi de blokajlı ama açık: mercan çerçeve
    const only = { producible: true, purchasable: false }, unknown = { producible: true, purchasable: null };
    expect(["Üretim", "Satın alma", "Üretim ve satın alma"].map((t) => [typeFits(t, only), typeFits(t, unknown), typeFits(t, undefined)])).toEqual([
      [true, true, true], [false, true, true], [false, true, true]]);
  });

  it("End user görür: Yeni kayıt, düzenleme ve satır işlemleri yok (yalnız Detay)", async () => {
    const { user } = await open("End user");
    expect(screen.queryByRole("button", { name: "Yeni kayıt" })).toBeNull();
    expect(document.querySelector(".sc-table-edit-mark")).toBeNull();
    await user.click(screen.getByRole("button", { name: /^SAT-030 · .* işlemleri$/ }));
    expect(within(await screen.findByRole("menu")).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Detay"]);
  });
});

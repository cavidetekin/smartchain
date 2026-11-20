// Kapasite yönetimi · giriş sekmeleri ve kartlar (ekran 30, K-185, 7.9b; docs/12 "Kapasite yönetimi"): sekmeler, "Yeni kayıt" penceresi,
// tablo içi düzenleme, satır menüsü (Baz'da ve izleyen senaryoda), senaryo farkı işareti, geçersiz satır, kartlar ve süzmeleri, End user.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { meAs, mockApi, renderApp, type Reply } from "../test/helpers";
import { col, useTableTestSetup } from "../table/testBackend";
import { cellOf, setCell } from "../table/testEditing";

useTableTestSetup();

const PATH = "/parametre/kapasite-yonetimi";
const EXPORT = { title: "x", file_slug: "x", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const DAYS = ["DayMon", "DayTue", "DayWed", "DayThu", "DayFri", "DaySat", "DaySun"];
const DAY_LABELS = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"];
const WP_COLUMNS = [
  col("Level", "Seviye", "text", "list"), col("Code", "Kod", "text", "list"), col("ValidFrom", "Başlangıç", "date", "date"), col("ValidTo", "Bitiş", "date", "date"),
  col("DailyCapacity", "Günlük kapasite", "number", "number", { decimals: 2 }), col("CapacityUnit", "Birim", "text", "list"),
  ...DAYS.map((d, i) => col(d, DAY_LABELS[i], "text", "list")), col("Origin", "Kaynağı", "text", "list"), col("IsValid", "Geçerli", "bool", "list"),
];
const OT_COLUMNS = [
  col("Level", "Seviye", "text", "list"), col("Code", "Kod", "text", "list"), col("ValidFrom", "Başlangıç", "date", "date"), col("ValidTo", "Bitiş", "date", "date"),
  col("DailyLimit", "Günlük limit", "number", "number", { decimals: 2 }), col("CapacityUnit", "Birim", "text", "list"), col("Origin", "Kaynağı", "text", "list"),
  col("IsValid", "Geçerli", "bool", "list"),
];
const DT_COLUMNS = [
  col("Level", "Seviye", "text", "list"), col("Code", "Kod", "text", "list"), col("DowntimeType", "Tip", "text", "list"), col("Reason", "Sebep", "text", "text"),
  col("StartDate", "Başlangıç", "date", "date"), col("EndDate", "Bitiş", "date", "date"), col("Origin", "Kaynağı", "text", "list"), col("IsValid", "Geçerli", "bool", "list"),
];
// Geçerlilik (7.9c, K-188): kaynak grubu × kaynak × aralık; ufuk 16.11.2026 – 31.01.2027 (77 gün)
const VALIDITY_COLUMNS = [
  col("GroupCode", "Kaynak grubu", "text", "list"), col("Code", "Kaynak", "text", "list"), col("ValidFrom", "Başlangıç", "date", "date"), col("ValidTo", "Bitiş", "date", "date"),
  col("DailyCapacity", "Günlük kapasite", "number", "number", { decimals: 2 }), col("CapacityUnit", "Birim", "text", "list"), col("SourceRecord", "Geçerli kayıt", "text", "list"),
];
const span = (id: number, code: string, resource: number, from: string, to: string | null, capacity: number, source: number, record: string, text: string) => ({
  Id: id, ResourceGroupId: 12, ResourceId: resource, GroupCode: "ISL3", Code: code, ValidFrom: from, ValidTo: to, DailyCapacity: capacity, CapacityUnit: "SAAT",
  SourceRecord: record, SourceRowId: source, SourceSpan: text, SourceLevel: record.startsWith("Kaynak") ? "Kaynak" : "Grup", SourceOrigin: "Baz" });
const GROUP_RECORD = ["Grup ISL3 · 26.10.2026", "Grup ISL3 · 26.10.2026'dan itibaren"] as const;
const OWN_RECORD = ["Kaynak M3-01 · 23.11.2026", "Kaynak M3-01 · 23.11.2026 – 06.12.2026"] as const;
const VALIDITY_ROWS = [
  span(1, "M3-01", 5, "2026-10-26", "2026-11-22", 15, 101, ...GROUP_RECORD), span(2, "M3-01", 5, "2026-11-23", "2026-12-06", 20, 102, ...OWN_RECORD),
  span(3, "M3-01", 5, "2026-12-07", null, 15, 101, ...GROUP_RECORD), span(4, "M3-02", 6, "2026-10-26", null, 15, 101, ...GROUP_RECORD),
];
const HORIZON = { start: "2026-11-16", end: "2027-01-31" };
const GROUP_COLUMNS = [col("Code", "Kaynak grubu", "text", "text"), col("Name", "Ad", "text", "text"), col("ResourceCount", "Kaynak sayısı", "integer", "number")];
const HISTORY_COLUMNS = [col("At", "Tarih", "datetime", "date"), col("FieldLabel", "Alan", "text", "list"), col("OldValue", "Eski değer", "text", "text"),
                         col("NewValue", "Yeni değer", "text", "text"), col("ChangedBy", "Değiştiren", "text", "list"), col("SourceText", "Kaynak", "text", "list")];
const week = { DayMon: "Tam", DayTue: "Tam", DayWed: "Tam", DayThu: "Tam", DayFri: "Tam", DaySat: "—", DaySun: "—" };
const pattern = (id: number, level: string, code: string, extra: object = {}) => ({
  Id: id, StoredId: id, Origin: "Baz", IsValid: true, OverriddenFields: null, BaseValues: null, Level: level, Code: code,
  ResourceGroupId: level === "Grup" ? 12 : null, ResourceId: level === "Kaynak" ? 5 : null, ValidFrom: "2026-10-26", ValidTo: null, DailyCapacity: 15, CapacityUnit: "SAAT", ...week, ...extra });
const limit = (id: number, code: string, origin: string, extra: object = {}) => ({
  Id: id, StoredId: id, Origin: origin, IsValid: true, OverriddenFields: null, BaseValues: null, Level: "Grup", Code: code, ResourceGroupId: 7, ResourceId: null,
  ValidFrom: "2026-10-26", ValidTo: null, DailyLimit: 2, CapacityUnit: "SAAT", ...extra });

type Call = { method: string; url: string; body: Record<string, unknown> };

const STRICT_FIELDS = new Set(["capacity-work-patterns", "capacity-efficiency", "capacity-overtime-limits"]);   // sunucu olmayan alanı reddeder (docs/08)

function backend(options: { scenario?: { id: number; name: string; is_base: boolean }; reply?: (call: Call) => Reply | undefined; validity?: object[];
                            patterns?: object[] } = {}) {
  const scenario = options.scenario ?? { id: 1, name: "Baz", is_base: true };
  const calls: Call[] = [];
  const queries: Record<string, Record<string, unknown>[]> = {};
  const list = (name: string, columns: unknown[], rows: object[]) => ({
    [`/api/${name}/columns`]: { body: { chunk_size: 100, columns, relations: [], scenario_list: true, export: EXPORT } },
    [`/api/${name}/views`]: { body: { views: [], default_view_id: null } },
    [`/api/${name}/query`]: (_url: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body ?? "{}")) as { fields?: string[]; offset?: number; limit?: number };
      (queries[name] ??= []).push(body as Record<string, unknown>);
      const unknown = STRICT_FIELDS.has(name) && rows.length ? (body.fields ?? []).filter((f) => !(f in rows[0])) : [];
      if (unknown.length) {
        return { status: 422, body: { error: { code: "validation", message: "Girilen bilgiler geçersiz.", trace_id: "t",
                                               details: unknown.map((f) => ({ field: "fields", problem: `Bilinmeyen alan: ${f}` })) } } };
      }
      const offset = body.offset ?? 0;
      return { body: { rows: rows.slice(offset, offset + (body.limit ?? 100)), offset, filtered: rows.length, total: rows.length } };
    },
  });
  mockApi({
    "/api/scenarios/current": { body: { ...scenario, is_active: true } },
    "/api/scenarios/options": { body: { scenarios: [{ id: 1, name: "Baz", is_base: true }, ...(scenario.is_base ? [] : [scenario])] } },
    ...list("capacity-work-patterns", WP_COLUMNS, options.patterns ?? [pattern(101, "Grup", "ISL3"), pattern(102, "Kaynak", "M3-01", { ValidFrom: "2026-11-23", DailyCapacity: 20, DaySat: "Yarım" })]),
    ...list("capacity-overtime-limits-validity", [col("GroupCode", "Kaynak grubu", "text", "list"), col("Code", "Kaynak", "text", "list"), col("ValidFrom", "Başlangıç", "date", "date"),
                                                  col("ValidTo", "Bitiş", "date", "date"), col("DailyLimit", "Günlük limit", "number", "number", { decimals: 2 })],
            [{ ...span(1, "W-001", 30, "2026-10-26", "2026-12-31", 0, 201, "Grup CG-CNC · 26.10.2026", "Grup CG-CNC · 26.10.2026'dan itibaren"), DailyLimit: 2, GroupCode: "CG-CNC", ResourceGroupId: 7 },
             { ...span(2, "W-001", 30, "2027-01-01", null, 0, 203, "Kaynak W-001 · 01.01.2027", "Kaynak W-001 · 01.01.2027'dan itibaren"), DailyLimit: 3, GroupCode: "CG-CNC", ResourceGroupId: 7 }]),
    ...list("capacity-work-patterns-validity", VALIDITY_COLUMNS, options.validity ?? VALIDITY_ROWS),
    ...list("capacity-efficiency", [col("Level", "Seviye", "text", "list"), col("Code", "Kod", "text", "list"), col("ValidFrom", "Başlangıç", "date", "date"),
                                    col("EfficiencyPct", "Verimlilik (%)", "number", "number", { decimals: 2 })],
            [{ Id: 401, StoredId: 401, Origin: "Baz", IsValid: true, Level: "Grup", Code: "ISL3", ResourceGroupId: 12, ResourceId: null, ValidFrom: "2026-10-26", ValidTo: null, EfficiencyPct: 85 },
             { Id: 402, StoredId: 402, Origin: "Baz", IsValid: true, Level: "Kaynak", Code: "M3-01", ResourceGroupId: null, ResourceId: 5, ValidFrom: "2027-01-01", ValidTo: null, EfficiencyPct: 110 }]),
    ...list("capacity-efficiency-validity", [col("GroupCode", "Kaynak grubu", "text", "list"), col("Code", "Kaynak", "text", "list"), col("ValidFrom", "Başlangıç", "date", "date"),
                                             col("ValidTo", "Bitiş", "date", "date"), col("EfficiencyPct", "Verimlilik (%)", "number", "number", { decimals: 2 })],
            [{ ...span(1, "M3-01", 5, "2026-10-26", "2026-12-31", 0, 401, ...GROUP_RECORD), EfficiencyPct: 85, CapacityUnit: "SAAT" },
             { ...span(2, "M3-01", 5, "2027-01-01", null, 0, 402, ...OWN_RECORD), EfficiencyPct: 110 },
             { ...span(3, "M3-02", 6, "2026-10-26", null, 0, 401, ...GROUP_RECORD), EfficiencyPct: 87.5 }]),
    ...list("capacity-overtime-limits", OT_COLUMNS, [
      limit(201, "CG-CNC", "Baz"),
      limit(202, "CG-MON", "Senaryo farkı", { StoredId: 902, DailyLimit: 4, OverriddenFields: ",DailyLimit,", BaseValues: JSON.stringify({ IsValid: true, DailyLimit: 2 }) }),
      limit(203, "MONTAJ", "Senaryo", { DailyLimit: 3 }),
      limit(204, "CG-KAL", "Senaryo farkı", { StoredId: 904, IsValid: false, OverriddenFields: ",IsValid,", BaseValues: JSON.stringify({ IsValid: true, DailyLimit: 2 }) }),
    ]),
    ...list("capacity-downtime", DT_COLUMNS, [
      { Id: 301, StoredId: 301, Origin: "Baz", IsValid: true, Level: "Kaynak", Code: "M3-02", ResourceId: 6, ResourceGroupId: null, DowntimeType: "Arıza", Reason: "Mil arızası",
        StartDate: "2026-12-01", EndDate: "2026-12-02" },
      { Id: -2, StoredId: null, Origin: "ERP", IsValid: true, Level: "Kaynak", Code: "W-015", ResourceId: 30, ResourceGroupId: null, DowntimeType: "Çalışan izni", Reason: "Rapor",
        StartDate: "2026-11-17", EndDate: "2026-11-18" },
    ]),
    ...list("capacity-resource-groups", GROUP_COLUMNS, [{ Id: 12, Code: "ISL3", Name: "3 eksen işleme", ResourceCount: 3 }, { Id: 7, Code: "CG-CNC", Name: "CNC operatörü", ResourceCount: 10 }]),
    ...list("capacity-resources", [col("Code", "Kaynak", "text", "text"), col("Name", "Ad", "text", "text")], [{ Id: 5, Code: "M3-01", Name: "Tezgâh 1", CapacityUnit: "SAAT" }, { Id: 6, Code: "M3-02", Name: "Tezgâh 2", CapacityUnit: "SAAT" }]),
    ...list("record-history", HISTORY_COLUMNS, [{ Id: 1, At: "2026-11-19T10:42:00", FieldLabel: "Günlük kapasite", OldValue: "20", NewValue: "22,5", ChangedBy: "planlama", SourceText: "Kapasite yönetimi · planlama" }]),
    "/api/capacity/": (url: string, init?: RequestInit) => {
      const call = { method: init?.method ?? "GET", url, body: init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : {} };
      if (url.includes("/capacity/horizon")) return { body: HORIZON };
      calls.push(call);
      return options.reply?.(call) ?? { status: call.method === "POST" && !/\/\d+\//.test(url) ? 201 : 200, body: { id: 500, saved: 1, warnings: [] } };
    },
  });
  return { calls, queries };
}

const rowsOf = () => screen.getAllByRole("row").filter((r) => r.classList.contains("sc-table-row"));
async function open(tab: string, role = "Key user", options: Parameters<typeof backend>[0] = {}) {
  const user = userEvent.setup();
  const server = backend(options);
  renderApp(`${PATH}?sekme=${tab}`, meAs(role));
  await waitFor(() => expect(rowsOf().length).toBeGreaterThan(0), { timeout: 5000 });
  return { user, ...server };
}
const menuOf = async (user: ReturnType<typeof userEvent.setup>, name: string) => {
  await user.click(screen.getByRole("button", { name }));
  return within(await screen.findByRole("menu")).getAllByRole("menuitem").map((m) => m.textContent);
};

describe("ekran 30 · Kapasite yönetimi · giriş sekmeleri (K-185, 7.9b)", () => {
  it("sekiz sekme; giriş sekmesinde Yeni kayıt ve düzenlenebilir kolonlar; istekler seçili senaryoyu taşır", async () => {
    const { queries } = await open("calisma-duzeni");
    const tabs = within(screen.getByRole("radiogroup", { name: "Kapasite yönetimi bölümleri" })).getAllByRole("radio");
    expect(tabs.map((t) => t.textContent)).toEqual(["Kapasite özeti", "Kaynak grubu", "Kaynak", "Çalışma düzeni", "Bakım ve duruşlar", "Verimlilik", "Fabrika takvimi", "Ek mesai limitleri"]);
    expect(tabs[3]).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("button", { name: "Yeni kayıt" })).toBeInTheDocument();
    expect(queries["capacity-work-patterns"][0]).toMatchObject({ scenario_id: 1 });
    expect(cellOf("ISL3", "Başlangıç")).toHaveTextContent("26.10.2026");
    expect(cellOf("M3-01", "Günlük kapasite")).toHaveTextContent("20,00");
  });

  it("Yeni kayıt: aramalı seçim, gün kutuları; zorunlu alan boşken Kaydet pasif; değerler tipli gider; reddedilen alanın altında neden", async () => {
    let reject = true;
    const { user, calls } = await open("calisma-duzeni", "Key user", { reply: (call) => (call.method === "POST" && reject
      ? { status: 422, body: { error: { code: "validation", message: "Girilen bilgiler geçersiz.", trace_id: "t", details: [{ field: "DailyCapacity", problem: "Sıfırdan büyük olmalı." }] } } } : undefined) });
    await user.click(screen.getByRole("button", { name: "Yeni kayıt" }));
    expect(screen.getByRole("button", { name: "Yeni kayıt" }).querySelector("svg")).toBeNull();          // düğmede "+" yok (K-187)
    const dialog = await screen.findByRole("dialog", { name: "Çalışma düzeni · Yeni kayıt" });
    expect(dialog.textContent).not.toMatch(/zorunlu/);                                                   // alan adında "(zorunlu)" yok
    expect(dialog.querySelectorAll("[required]")).toHaveLength(0);                                       // tarayıcının kendi uyarısı çıkmaz
    const save = within(dialog).getByRole("button", { name: "Kaydet" });
    expect(save).toBeDisabled();                                                                         // zorunlu alanlar boş
    // gün kutuları: Pzt–Cum Tam, Cmt–Paz Çalışılmıyor; yazı tam; tıklayınca Tam → Yarım → Çalışılmıyor döner
    const days = within(within(dialog).getByRole("group", { name: "Günler" })).getAllByRole("button");
    expect(days.map((d) => d.getAttribute("aria-label"))).toEqual(["Pzt: Tam", "Sal: Tam", "Çar: Tam", "Per: Tam", "Cum: Tam", "Cmt: Çalışılmıyor", "Paz: Çalışılmıyor"]);
    expect(days[5]).toHaveTextContent("Çalışılmıyor");
    await user.click(days[5]);
    expect(days[5]).toHaveAccessibleName("Cmt: Tam");
    await user.click(days[5]);
    expect(days[5]).toHaveAccessibleName("Cmt: Yarım");
    // aramalı seçim: koda ya da ada göre süzülür; ok ve Enter seçer (Enter pencereyi kaydetmez)
    await user.click(within(dialog).getByRole("radio", { name: "Kaynak" }));
    const owner = within(dialog).getByRole("combobox", { name: "Kaynak" });
    await user.click(owner);
    const found = () => within(screen.getByRole("listbox", { name: "Kaynak" })).getAllByRole("option");
    await waitFor(() => expect(found().map((o) => o.textContent)).toEqual(["M3-01Tezgâh 1", "M3-02Tezgâh 2"]));
    await user.type(owner, "gâh 2");
    expect(found().map((o) => o.textContent)).toEqual(["M3-02Tezgâh 2"]);                                // ada göre
    await user.clear(owner);
    await user.type(owner, "m3-01");
    expect(found()).toHaveLength(1);
    expect(found()[0].querySelector("mark")).toHaveTextContent("M3-01");                                 // eşleşen kısım vurgulu
    await user.keyboard("{Enter}");
    expect(owner).toHaveValue("M3-01 · Tezgâh 1");
    expect(calls).toHaveLength(0);
    expect(save).toBeDisabled();                                                                         // başlangıç ve kapasite hâlâ boş
    await user.type(within(dialog).getByRole("textbox", { name: "Başlangıç" }), "23.11.2026");
    const capacity = within(dialog).getByRole("textbox", { name: "Günlük kapasite" });
    await user.type(capacity, "0");
    expect(capacity.parentElement).toHaveTextContent("SAAT");                                            // birim kutunun içinde
    expect(save).toBeEnabled();                                                                          // yazarken açılır (odak çıkması gerekmez)
    await user.click(save);
    expect(await within(dialog).findByText("Sıfırdan büyük olmalı.")).toBeInTheDocument();
    expect(calls[0]).toMatchObject({ method: "POST", url: "/api/capacity/work-patterns?scenario_id=1" });
    expect(calls[0].body.values).toMatchObject({ ResourceId: 5, ValidFrom: "2026-11-23", ValidTo: null, DailyCapacity: 0, DayMon: "Tam", DaySat: "Yarım", DaySun: "Çalışılmıyor" });
    expect(calls[0].body.values).not.toHaveProperty("ResourceGroupId");
    reject = false;
    await user.clear(capacity);
    await user.type(capacity, "20{Enter}");                                                              // Enter kaydeder
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect((calls[1].body.values as { DailyCapacity: number }).DailyCapacity).toBe(20);
  });

  it("pencere dolu alanla açılmaz: Tip ve Çalışma düğmedir, boş gelir; alan sırası tarihler sonra değerler; Esc pencereyi kapatır", async () => {
    const { user, calls } = await open("duruslar");
    await user.click(screen.getByRole("button", { name: "Yeni kayıt" }));
    let dialog = await screen.findByRole("dialog", { name: "Bakım ve duruşlar · Yeni kayıt" });
    const type = within(dialog).getByRole("radiogroup", { name: "Tip" });
    expect(within(type).getAllByRole("radio").map((r) => [r.textContent, r.getAttribute("aria-checked")])).toEqual([["Planlı bakım", "false"], ["Arıza", "false"], ["Diğer", "false"]]);
    const labels = [...dialog.querySelectorAll(".sc-field-label")].map((l) => l.textContent);
    expect(labels).toEqual(["Seviye", "Kaynak grubu", "Başlangıç", "Bitiş", "Tip", "Sebep"]);           // seviye ve kod, tarihler, değerler
    const owner = within(dialog).getByRole("combobox", { name: "Kaynak grubu" });
    await user.click(owner);
    await user.click(await screen.findByRole("option", { name: /ISL3/ }));
    await user.type(within(dialog).getByRole("textbox", { name: "Başlangıç" }), "01.12.2026");
    await user.type(within(dialog).getByRole("textbox", { name: "Bitiş" }), "02.12.2026");
    expect(within(dialog).getByRole("button", { name: "Kaydet" })).toBeDisabled();                       // Tip seçilmedi
    await user.click(within(type).getByRole("radio", { name: "Arıza" }));
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls[0]?.body.values).toEqual({ ResourceGroupId: 12, StartDate: "2026-12-01", EndDate: "2026-12-02", DowntimeType: "Arıza", Reason: null }));
    // Esc: aramalı liste açıkken önce liste kapanır, sonra pencere; odak pencerenin dışındayken de kapanır
    await user.click(screen.getByRole("button", { name: "Yeni kayıt" }));
    dialog = await screen.findByRole("dialog", { name: "Bakım ve duruşlar · Yeni kayıt" });
    await user.click(within(dialog).getByRole("combobox", { name: "Kaynak grubu" }));
    expect(await screen.findByRole("listbox")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    (document.activeElement as HTMLElement).blur();                                                      // boş alana tıklanmış gibi: odak pencerede değil
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("tablo içi düzenleme: değişen hücre işaretli; Kaydet hepsini birlikte gönderir; reddedilen hücre kırmızı ve taslak durur", async () => {
    let reject = true;
    const { user, calls } = await open("calisma-duzeni", "Key user", { reply: (call) => (call.method === "PUT" && reject
      ? { status: 422, body: { error: { code: "validation", message: "Kaydedilmedi.", trace_id: "t",
                                        details: [{ id: 102, field: "ValidTo", record: "Kaynak M3-01 · 23.11.2026", problem: "Bitiş başlangıçtan önce olamaz." }] } } } : undefined) });
    expect(screen.queryByRole("button", { name: "Kaydet" })).toBeNull();
    await setCell(user, "M3-01", "Günlük kapasite", "22,5");
    await setCell(user, "M3-01", "Bitiş", "01.11.2026");
    await setCell(user, "M3-01", "Pzt", "Yarım");
    expect(cellOf("M3-01", "Günlük kapasite")).toHaveClass("is-draft");
    expect(cellOf("M3-01", "Günlük kapasite")).toHaveTextContent("22,5");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(cellOf("M3-01", "Bitiş")).toHaveClass("is-invalid"));
    expect(calls[0]).toMatchObject({ method: "PUT", url: "/api/capacity/work-patterns?scenario_id=1" });
    expect(calls[0].body.changes).toEqual(expect.arrayContaining([{ id: 102, field: "DailyCapacity", value: "22,5" }, { id: 102, field: "ValidTo", value: "01.11.2026" },
                                                                 { id: 102, field: "DayMon", value: "Yarım" }]));
    expect(cellOf("M3-01", "Pzt")).toHaveClass("is-draft");                                             // hiçbiri kaydedilmedi: taslak durur
    expect(await screen.findByText(/Kaydedilmedi: Kaynak M3-01 · 23\.11\.2026 · Bitiş: bitiş başlangıçtan önce olamaz\./)).toBeInTheDocument();
    reject = false;
    await setCell(user, "M3-01", "Bitiş", "");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Kaydet" })).toBeNull());
    expect((calls[1].body.changes as { field: string }[]).map((c) => c.field).sort()).toEqual(["DailyCapacity", "DayMon"]);   // geri alınan hücre gönderilmez
  });

  it("satır menüsü Baz'da: Detay · Düzenle · Yeni kayıt · Sil; Sil onay ister; Düzenle'de seviye ve kod kilitli; Detay kartta Geçmiş'i açar", async () => {
    const { user, calls, queries } = await open("calisma-duzeni");
    expect(await menuOf(user, "Grup ISL3 · 26.10.2026 işlemleri")).toEqual(["Detay", "Düzenle", "Yeni kayıt", "Sil"]);
    await user.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Sil" }));
    const confirm = await screen.findByRole("dialog", { name: "Kayıt silinsin mi?" });
    expect(calls).toHaveLength(0);
    await user.click(within(confirm).getByRole("button", { name: "Sil" }));
    await waitFor(() => expect(calls[0]).toMatchObject({ method: "DELETE", url: "/api/capacity/work-patterns/101?scenario_id=1" }));
    await menuOf(user, "Kaynak M3-01 · 23.11.2026 işlemleri");
    await user.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Çalışma düzeni · Düzenle" });
    expect(within(dialog).getByRole("textbox", { name: "Kod" })).toBeDisabled();
    expect(within(dialog).getByRole("textbox", { name: "Kod" })).toHaveValue("M3-01");
    expect(within(dialog).getByRole("textbox", { name: /^Başlangıç/ })).toHaveValue("23.11.2026");
    const sunday = within(dialog).getByRole("button", { name: "Paz: Çalışılmıyor" });
    await user.click(sunday);                                                                            // Çalışılmıyor → Tam
    await user.click(sunday);                                                                            // Tam → Yarım
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls[1]).toMatchObject({ method: "PUT", body: { changes: [{ id: 102, field: "DaySun", value: "Yarım" }] } }));   // yalnız değişen alan
    await menuOf(user, "Kaynak M3-01 · 23.11.2026 işlemleri");
    await user.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Detay" }));
    expect(await screen.findByText("planlama")).toBeInTheDocument();                                    // Geçmiş: Değiştiren
    const filters = queries["record-history"][0].filters as { field: string; values: string[] }[];
    expect(filters).toEqual([{ field: "TableName", op: "in", values: ["WorkPattern"] }, { field: "RecordKey", op: "in", values: ["102", "102@1"] }]);
  });

  it("izleyen senaryo: fark işareti ve ipucu, geçersiz satır; Baz satırında Geçersiz yap, farkta Senaryo farkını kaldır, kendi satırında Sil", async () => {
    const { user, calls } = await open("ek-mesai", "Key user", { scenario: { id: 7, name: "Fazla mesaili", is_base: false } });
    expect(cellOf("CG-MON", "Günlük limit")).toHaveClass("sc-cell-diff");
    expect(cellOf("CG-MON", "Başlangıç")).not.toHaveClass("sc-cell-diff");
    await user.hover(cellOf("CG-MON", "Günlük limit").querySelector(".sc-cell-source")!);
    expect(await screen.findByText("Baz: 2,00")).toBeInTheDocument();
    expect(cellOf("CG-KAL", "Kod").closest("tr")).toHaveClass("sc-row-invalid");
    expect(cellOf("CG-CNC", "Kod").closest("tr")).not.toHaveClass("sc-row-invalid");
    expect(await menuOf(user, "Grup CG-CNC · 26.10.2026 işlemleri")).toEqual(["Detay", "Düzenle", "Yeni kayıt", "Geçersiz yap"]);
    await user.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Geçersiz yap" }));
    await waitFor(() => expect(calls[0]).toMatchObject({ method: "POST", url: "/api/capacity/overtime-limits/201/invalidate?scenario_id=7" }));
    expect(await menuOf(user, "Grup CG-MON · 26.10.2026 işlemleri")).toEqual(["Detay", "Düzenle", "Yeni kayıt", "Geçersiz yap", "Senaryo farkını kaldır"]);
    await user.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Senaryo farkını kaldır" }));
    await waitFor(() => expect(calls[1]).toMatchObject({ method: "POST", url: "/api/capacity/overtime-limits/202/restore?scenario_id=7" }));
    expect(await menuOf(user, "Grup CG-KAL · 26.10.2026 işlemleri")).toEqual(["Detay", "Düzenle", "Yeni kayıt", "Geçerli yap", "Senaryo farkını kaldır"]);
    await user.keyboard("{Escape}");
    expect(await menuOf(user, "Grup MONTAJ · 26.10.2026 işlemleri")).toEqual(["Detay", "Düzenle", "Yeni kayıt", "Sil"]);
  });

  it("ERP satırı (çalışan izni) salt okunur: düzenlenmez, menüde yalnız Detay", async () => {
    const { user } = await open("duruslar");
    expect(await menuOf(user, "Kaynak W-015 · 17.11.2026 işlemleri")).toEqual(["Detay"]);
    await user.keyboard("{Escape}");
    await user.dblClick(cellOf("W-015", "Sebep"));
    expect(cellOf("W-015", "Sebep").querySelector(".sc-cell-editor")).toBeNull();
    await user.dblClick(cellOf("M3-02", "Sebep"));
    expect(cellOf("M3-02", "Sebep").querySelector(".sc-cell-editor")).not.toBeNull();
  });

  it("Kaynak grubu kartı: sekmeler; giriş sekmesi grubun kendisini ve kaynaklarını süzer; Yeni kayıt seviyeyi ve grubu dolu getirir", async () => {
    const { user, queries, calls } = await open("grup");
    await menuOf(user, "ISL3 işlemleri");
    await user.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Detay" }));
    const tabs = await screen.findByRole("radiogroup", { name: "Kayıt bölümleri" });
    expect(within(tabs).getAllByRole("radio").map((t) => t.textContent)).toEqual(["Dönem özeti", "Kaynaklar", "Çalışma düzeni", "Bakım ve duruşlar", "Verimlilik", "Ek mesai limitleri"]);
    await user.click(within(tabs).getByRole("radio", { name: "Çalışma düzeni" }));
    await waitFor(() => expect(queries["capacity-work-patterns"]?.length).toBeGreaterThan(0));
    expect(queries["capacity-work-patterns"][0].filters).toEqual([{ field: "OwnerKeys", op: "contains", values: [",g12,"] }]);
    await user.click(await screen.findByRole("button", { name: "Yeni kayıt" }));
    const dialog = await screen.findByRole("dialog", { name: "Çalışma düzeni · Yeni kayıt" });
    expect(within(dialog).getByRole("radio", { name: "Grup" })).toHaveAttribute("aria-checked", "true");
    await waitFor(() => expect(within(dialog).getByRole("combobox", { name: "Kaynak grubu" })).toHaveValue("ISL3 · 3 eksen işleme"));
    await user.type(within(dialog).getByRole("textbox", { name: "Başlangıç" }), "01.02.2027");
    await user.type(within(dialog).getByRole("textbox", { name: "Günlük kapasite" }), "16");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls[0]?.body.values).toMatchObject({ ResourceGroupId: 12, ValidFrom: "2027-02-01", DailyCapacity: 16 }));
  });

  it("Kaynak kartında Geçmiş sekmesi yok; çoklu seçimde kart seçili kayıtların hepsini gösterir (K-171, K-187)", async () => {
    const { user, queries } = await open("kaynak");
    await menuOf(user, "M3-01 işlemleri");
    await user.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Detay" }));
    const tabs = await screen.findByRole("radiogroup", { name: "Kayıt bölümleri" });
    expect(within(tabs).getAllByRole("radio").map((t) => t.textContent)).toEqual(["Çalışma düzeni", "Bakım ve duruşlar", "Verimlilik", "Ek mesai limitleri"]);
    await waitFor(() => expect(queries["capacity-work-patterns"]?.[0].filters).toEqual([{ field: "OwnerKeys", op: "contains", values: [",r5,"] }]));
    // satıra tıklanır, ikinci satır Ctrl ile eklenir: kart iki kaynağın kayıtlarını birlikte süzer
    await user.click(cellOf("M3-01", "Kaynak"));
    await user.keyboard("{Control>}");
    await user.click(cellOf("M3-02", "Kaynak"));
    await user.keyboard("{/Control}");
    await waitFor(() => expect(queries["capacity-work-patterns"].some((q) => JSON.stringify(q.filters) === JSON.stringify([{ field: "OwnerKeys", op: "contains", values: [",r5,", ",r6,"] }])
      || JSON.stringify(q.filters) === JSON.stringify([{ field: "OwnerKeys", op: "contains", values: [",r6,", ",r5,"] }]))).toBe(true));
  });

  it("listeli hücre tek tıkla açık liste; baş harfle seçim ve Enter; sayı hücresi çift tıkta değer seçili (K-187)", async () => {
    const { user } = await open("calisma-duzeni");
    await user.click(cellOf("M3-01", "Cmt"));                                                           // tek tık: liste açık
    const list = within(cellOf("M3-01", "Cmt")).getByRole("listbox");
    expect(within(list).getAllByRole("option").map((o) => o.textContent)).toEqual(["Tam", "Yarım", "Çalışılmıyor"]);
    expect(list).toHaveFocus();
    await user.keyboard("ç{Enter}");                                                                     // baş harf işaretler, Enter taslağa alır
    expect(cellOf("M3-01", "Cmt")).toHaveClass("is-draft");
    expect(cellOf("M3-01", "Cmt")).toHaveTextContent("—");                                               // tabloda çalışılmayan gün "—"
    await user.dblClick(cellOf("M3-01", "Günlük kapasite"));
    const editor = cellOf("M3-01", "Günlük kapasite").querySelector("input") as HTMLInputElement;
    expect(editor).toHaveFocus();
    expect([editor.selectionStart, editor.selectionEnd]).toEqual([0, editor.value.length]);              // değer seçili: yazınca üzerine yazar
    await user.keyboard("25{Enter}");
    expect(cellOf("M3-01", "Günlük kapasite")).toHaveTextContent("25");
    await user.click(cellOf("ISL3", "Günlük kapasite"));                                                 // tek tık seçer; yazmaya başlamak üzerine yazar
    await user.keyboard("12{Enter}");
    expect(cellOf("ISL3", "Günlük kapasite")).toHaveTextContent("12");
  });

  it("çoklu satırda aynı değer: seçili satırlardan birine girilen değer hepsine; Ctrl+D en üstteki seçili satırın değerini kopyalar (K-187)", async () => {
    const { user } = await open("calisma-duzeni");
    await user.click(cellOf("ISL3", "Kod"));                                                             // satıra tıklanır
    await user.keyboard("{Control>}");
    await user.click(cellOf("M3-01", "Kod"));                                                            // ikinci satır Ctrl ile eklenir
    await user.keyboard("{/Control}");
    expect(cellOf("ISL3", "Kod").closest("tr")).toHaveAttribute("class", expect.stringContaining("is-picked"));
    await user.click(cellOf("M3-01", "Paz"));                                                            // seçili satırın listeli hücresi: seçim bozulmaz, liste açılır
    expect(cellOf("ISL3", "Kod").closest("tr")).toHaveAttribute("class", expect.stringContaining("is-picked"));
    await user.click(within(cellOf("M3-01", "Paz")).getByRole("option", { name: "Yarım" }));
    await waitFor(() => expect(cellOf("ISL3", "Paz")).toHaveTextContent("Yarım"));                       // öteki seçili satıra da yazıldı
    expect(cellOf("M3-01", "Paz")).toHaveTextContent("Yarım");
    expect(cellOf("ISL3", "Paz")).toHaveClass("is-draft");
    // Ctrl+D: imlecin kolonunda en üstteki seçili satırın (ISL3: 15,00) değeri ötekine (M3-01: 20,00)
    await user.click(cellOf("M3-01", "Günlük kapasite"));
    await user.keyboard("{Control>}d{/Control}");
    await waitFor(() => expect(cellOf("M3-01", "Günlük kapasite")).toHaveTextContent("15,00"));
    expect(cellOf("M3-01", "Günlük kapasite")).toHaveClass("is-draft");
    expect(cellOf("ISL3", "Günlük kapasite")).not.toHaveClass("is-draft");
  });

  it("End user görür: Yeni kayıt, düzenleme ve satır işlemleri yok (yalnız Detay)", async () => {
    const { user } = await open("calisma-duzeni", "End user");
    expect(screen.queryByRole("button", { name: "Yeni kayıt" })).toBeNull();
    expect(await menuOf(user, "Grup ISL3 · 26.10.2026 işlemleri")).toEqual(["Detay"]);
    await user.keyboard("{Escape}");
    await user.dblClick(cellOf("ISL3", "Günlük kapasite"));
    expect(cellOf("ISL3", "Günlük kapasite").querySelector(".sc-cell-editor")).toBeNull();
  });
});

describe("ekran 30 · Kapasite yönetimi · Geçerlilik (K-188, 7.9c)", () => {
  const choice = () => screen.getByRole("combobox", { name: "Tablo" });
  const timeline = () => screen.findByRole("group", { name: "Geçerlilik zaman çubuğu" });
  const spansOf = (box: HTMLElement, code: string) => {
    const labels = [...box.querySelectorAll(".sc-validity-label")];
    return [...box.querySelectorAll(".sc-validity-bar")][labels.findIndex((l) => l.textContent === code)].querySelectorAll<HTMLElement>(".sc-validity-span");
  };
  const toValidity = async (tab = "calisma-duzeni", role = "Key user", options: Parameters<typeof backend>[0] = {}) => {
    const server = await open(tab, role, options);
    await server.user.selectOptions(choice(), "gecerlilik");
    await waitFor(() => expect(server.queries["capacity-work-patterns-validity"]?.length).toBeGreaterThan(0));
    return { ...server, box: await timeline() };
  };

  it("tablo seçimi Kayıtlar · Geçerlilik; zaman çubuğu: yalnız kaynak kodu, iki renk (grup · kaynak), satır satır ipucu, açıklama listesi yok", async () => {
    const { user, queries } = await open("calisma-duzeni");
    expect(within(choice()).getAllByRole("option").map((o) => o.textContent)).toEqual(["Kayıtlar", "Geçerlilik"]);
    await user.selectOptions(choice(), "gecerlilik");
    await waitFor(() => expect(rowsOf()).toHaveLength(4));
    expect(queries["capacity-work-patterns-validity"][0]).toMatchObject({ scenario_id: 1 });
    expect(choice()).toHaveValue("gecerlilik");
    expect(screen.queryByRole("button", { name: "Yeni kayıt" })).toBeNull();                              // giriş yok
    expect(screen.queryAllByRole("button", { name: /^(M3-0\d|ISL3).* işlemleri$/ })).toHaveLength(0);     // satır menüsü düğmesi yok
    expect(document.querySelector(".is-editable")).toBeNull();                                            // hücre düzenleme yok
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Kaynak grubu", "Kaynak", "Başlangıç", "Bitiş", "Günlük kapasite", "Birim", "Geçerli kayıt"]);

    const box = await timeline();
    const labels = [...box.querySelectorAll<HTMLElement>(".sc-validity-label")];
    expect(labels.map((l) => [l.textContent, l.title])).toEqual([["M3-01", "M3-01 · ISL3"], ["M3-02", "M3-02 · ISL3"]]);   // yalnız kod; grup ipucunda
    const m1 = [...spansOf(box, "M3-01")];
    expect(m1.map((x) => x.textContent)).toEqual(["15,00", "20,00", "15,00"]);
    // ufuktan önce başlayan aralık ufkun başından çizilir: 16.11–22.11 yedi gün (77 günde); sonu açık aralık ufkun sonuna kadar
    expect(m1.map((x) => [x.style.left, x.style.width])).toEqual([["0%", "9.091%"], ["9.091%", "18.182%"], ["27.273%", "72.727%"]]);
    // iki renk, bir anlam: grubun kaydı nötr, kaynağın kendi kaydı petrol
    expect(m1.map((x) => (x.classList.contains("is-own") ? "kaynak" : x.classList.contains("is-group") ? "grup" : "?"))).toEqual(["grup", "kaynak", "grup"]);
    expect([...spansOf(box, "M3-02")].map((x) => x.className)).toEqual(["sc-validity-span is-group"]);
    expect(m1.every((x) => x.querySelector(".sc-validity-chip > b")?.textContent === x.textContent)).toBe(true);   // görünen şekil içteki çip (boşluk ve yuvarlak köşe)
    expect(box.querySelector(".sc-validity-corner")).toHaveTextContent(/^Kaynak$/);                        // sol başlık (düğmeler başlık satırının sağ ucunda)
    expect(box.querySelector(".sc-validity-axis .sc-validity-zooms")!.querySelectorAll("button")).toHaveLength(2);
    expect(spansOf(box, "M3-01")[0].parentElement!.querySelectorAll(".sc-validity-tick")).toHaveLength(2);  // ay sınırlarında dikey çizgi (üç ay)
    expect(m1[1].title.split("\n")).toEqual(["M3-01 · ISL3", "Günlük kapasite: 20,00 SAAT", "23.11.2026 – 06.12.2026", "Kaynağın kendi kaydı"]);
    expect(m1[2].title.split("\n")).toEqual(["M3-01 · ISL3", "Günlük kapasite: 15,00 SAAT", "07.12.2026'dan itibaren", "Grup kaydı"]);
    expect(within(box).queryAllByRole("listitem")).toHaveLength(0);                                       // kayıt açıklamaları (renk listesi) yok
    expect([...box.querySelectorAll(".sc-validity-month")].map((m) => m.textContent)).toEqual(["Kas 2026", "Ara 2026", "Oca 2027"]);

    await user.selectOptions(choice(), "kayitlar");
    expect(await screen.findByRole("button", { name: "Yeni kayıt" })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: "Geçerlilik zaman çubuğu" })).toBeNull();
  });

  it("yakınlaştırma (− +) ve tutamaç: çubuk yatayda genişler; yükseklik ve yakınlaştırma görünümün parçası (Standart * olur)", async () => {
    const { user, box } = await toValidity();
    const grid = box.querySelector<HTMLElement>(".sc-validity-grid")!;
    const out = within(box).getByRole("button", { name: "Uzaklaştır" }), zoomIn = within(box).getByRole("button", { name: "Yakınlaştır" });
    expect([grid.dataset.zoom, grid.style.width]).toEqual(["1", "calc(9rem + 1 * (100% - 9rem))"]);
    expect(out).toBeDisabled();
    await user.click(zoomIn);
    await user.click(within(await timeline()).getByRole("button", { name: "Yakınlaştır" }));
    const zoomed = (await timeline()).querySelector<HTMLElement>(".sc-validity-grid")!;
    expect([zoomed.dataset.zoom, zoomed.style.width]).toEqual(["2", "calc(9rem + 2 * (100% - 9rem))"]);
    expect(within(await timeline()).getByRole("button", { name: "Uzaklaştır" })).toBeEnabled();
    // tutamaç: klavyeyle de taşınır; çift tık varsayılana döner
    const handle = screen.getByRole("separator", { name: "Üst bölme ve tablo arasındaki ayraç" });
    expect(handle).toHaveAttribute("aria-valuenow", "40");
    handle.focus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByRole("separator", { name: "Üst bölme ve tablo arasındaki ayraç" })).toHaveAttribute("aria-valuenow", "45");
    expect(document.querySelector<HTMLElement>(".sc-above-pane")!.style.flex).toBe("0.45 1 0px");
    // Ctrl + fare tekerleği yakınlaştırır (ileri: büyür, geri: küçülür); düz tekerlek yakınlaştırmaz
    const zoomOf = async () => (await timeline()).querySelector<HTMLElement>(".sc-validity-grid")!.dataset.zoom;
    fireEvent.wheel(await timeline(), { deltaY: -100 });
    expect(await zoomOf()).toBe("2");
    fireEvent.wheel(await timeline(), { deltaY: -100, ctrlKey: true });
    await waitFor(async () => expect(await zoomOf()).toBe("2.4"));
    fireEvent.wheel(await timeline(), { deltaY: 100, ctrlKey: true });
    await waitFor(async () => expect(await zoomOf()).toBe("2"));
    expect(screen.getByRole("combobox", { name: "Görünüm" })).toHaveTextContent("Standart *");            // görünümle saklanacak değişiklik
  });

  it("dilime tıklamak tabloda o aralığın satırını seçer; sağ tık: Düzenle kaydın penceresini açar ve kaydedince yenilenir; Kayda git Kayıtlar'da kaydı seçer", async () => {
    const { user, box, queries, calls } = await toValidity();
    await waitFor(() => expect(rowsOf()).toHaveLength(4));
    await user.click(spansOf(box, "M3-01")[1]);
    await waitFor(() => expect(rowsOf().filter((r) => r.classList.contains("is-selected"))).toHaveLength(1));
    expect(rowsOf().findIndex((r) => r.classList.contains("is-selected"))).toBe(1);                       // 23.11.2026 – 06.12.2026 satırı
    expect(spansOf(await timeline(), "M3-01")[1]).toHaveAttribute("aria-pressed", "true");

    fireEvent.contextMenu(spansOf(await timeline(), "M3-01")[1]);
    expect(within(await screen.findByRole("menu")).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Düzenle", "Yeni kayıt", "Kayda git"]);
    // Yeni kayıt: pencere o kaynak seçili açılır; seviye ve kod değiştirilebilir
    await user.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Yeni kayıt" }));
    const fresh = await screen.findByRole("dialog", { name: "Çalışma düzeni · Yeni kayıt" });
    expect(within(fresh).getByRole("radio", { name: "Kaynak" })).toHaveAttribute("aria-checked", "true");
    expect(within(fresh).getByRole("radio", { name: "Grup" })).toBeEnabled();
    await waitFor(() => expect(within(fresh).getByRole("combobox", { name: "Kaynak" })).toHaveValue("M3-01 · Tezgâh 1"));
    expect(within(fresh).getByRole("combobox", { name: "Kaynak" })).toBeEnabled();
    await user.click(within(fresh).getByRole("button", { name: "Vazgeç" }));
    fireEvent.contextMenu(spansOf(await timeline(), "M3-01")[1]);
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Çalışma düzeni · Düzenle" });               // aralığın geldiği kayıt: Kaynak M3-01 · 23.11.2026
    await waitFor(() => expect(within(dialog).getByRole("textbox", { name: "Günlük kapasite" })).toHaveValue("20,00"));
    const before = queries["capacity-work-patterns-validity"].length;
    await user.clear(within(dialog).getByRole("textbox", { name: "Günlük kapasite" }));
    await user.type(within(dialog).getByRole("textbox", { name: "Günlük kapasite" }), "22");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls.find((c) => c.method === "PUT")?.body.changes).toEqual([{ id: 102, field: "DailyCapacity", value: 22 }]));
    await waitFor(() => expect(queries["capacity-work-patterns-validity"].length).toBeGreaterThan(before));   // çubuk ve tablo yenilenir

    // tablodaki satırda sağ tık: aynı seçenekler (Kopyala'nın ardında)
    fireEvent.contextMenu(within(rowsOf()[0]).getByText("Grup ISL3 · 26.10.2026"));
    expect(within(await screen.findByRole("menu")).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Kopyala", "Düzenle", "Yeni kayıt", "Kayda git"]);
    await user.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Kayda git" }));
    await waitFor(() => expect(choice()).toHaveValue("kayitlar"));
    await waitFor(() => expect(rowsOf().filter((r) => r.classList.contains("is-selected")).map((r) => within(r).getAllByRole("cell")[1].textContent)).toEqual(["ISL3"]));
  });

  it("verimlilik '%110' biçiminde yazılır (zaman çubuğunda ve ipucunda)", async () => {
    const { user, queries } = await open("verimlilik");
    await user.selectOptions(choice(), "gecerlilik");
    await waitFor(() => expect(queries["capacity-efficiency-validity"]?.length ?? 0).toBeGreaterThan(0));
    const box = await timeline();
    expect([...spansOf(box, "M3-01")].map((x) => x.textContent)).toEqual(["%85", "%110"]);
    expect(spansOf(box, "M3-02")[0]).toHaveTextContent("%87,5");
    expect(spansOf(box, "M3-01")[1].title.split("\n")[1]).toBe("Verimlilik: %110");
  });

  it.each([
    ["calisma-duzeni", "capacity-work-patterns-validity", "Çalışma düzeni", "M3-01", "Günlük kapasite", ["15,00", "20,00"]],
    ["verimlilik", "capacity-efficiency-validity", "Verimlilik", "M3-01", "Verimlilik (%)", ["85,00", "110,00"]],
    ["ek-mesai", "capacity-overtime-limits-validity", "Ek mesai limitleri", "W-001", "Günlük limit", ["2,00", "3,00"]],
  ] as const)("üç girişte sağ tık menüsü tam ve Düzenle kaydın penceresini açar: %s (dilimde ve tabloda, grup ve kaynak kaydında)", async (tab, list, title, code, field, values) => {
    const { user, queries } = await open(tab);
    await user.selectOptions(choice(), "gecerlilik");
    await waitFor(() => expect(queries[list]?.length ?? 0).toBeGreaterThan(0));
    await waitFor(() => expect(rowsOf().length).toBeGreaterThan(1));
    const menuItems = async () => within(await screen.findByRole("menu")).getAllByRole("menuitem").map((m) => m.textContent);
    // ilk dilim grubun kaydı, ikincisi kaynağın kendi kaydı: ikisinde de dilimde ve tablodaki satırda aynı menü; Düzenle o kaydı açar
    for (const at of [0, 1]) {
      const editFrom = async (opener: () => Promise<void> | void, expected: string[]) => {
        await opener();
        expect(await menuItems()).toEqual(expected);
        await user.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Düzenle" }));
        const dialog = await screen.findByRole("dialog", { name: `${title} · Düzenle` });
        await waitFor(() => expect(within(dialog).getByRole("textbox", { name: field })).toHaveValue(values[at]));
        await user.click(within(dialog).getByRole("button", { name: "Vazgeç" }));
        await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
      };
      await editFrom(async () => { fireEvent.contextMenu(spansOf(await timeline(), code)[at]); }, ["Düzenle", "Yeni kayıt", "Kayda git"]);
      await editFrom(() => { fireEvent.contextMenu(within(rowsOf()[at]).getAllByRole("cell")[1]); }, ["Kopyala", "Düzenle", "Yeni kayıt", "Kayda git"]);
    }
  }, 30_000);

  it("Kayda git: kayıt henüz yüklenmemiş satırdaysa parçalar sırayla yüklenir (ilk 100 satırın dışındaki kayıt)", async () => {
    // 250 kayıt; aralığın geldiği kayıt (102) 231. sırada: ilk parçada yok
    const many = Array.from({ length: 250 }, (_, i) => (i === 230 ? pattern(102, "Kaynak", "M3-01", { ValidFrom: "2026-11-23", DailyCapacity: 20 })
      : pattern(1000 + i, "Grup", `G-${String(i).padStart(3, "0")}`)));
    const { user, box, queries } = await toValidity("calisma-duzeni", "Key user", { patterns: many });
    await waitFor(() => expect(rowsOf()).toHaveLength(4));
    const before = queries["capacity-work-patterns"].length;
    fireEvent.contextMenu(spansOf(box, "M3-01")[1]);
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Kayda git" }));
    await waitFor(() => expect(choice()).toHaveValue("kayitlar"));
    // satır bulunana kadar parçalar istenir: 0, 100, 200 (kayıt üçüncü parçada); bulununca durur
    await waitFor(() => expect([...new Set(queries["capacity-work-patterns"].slice(before).map((q) => q.offset as number))].sort((a, b) => a - b)).toEqual([0, 100, 200]));
  }, 20_000);

  it("End user: Geçerlilik'i görür; sağ tıkta Düzenle ve Yeni kayıt yok. Senaryo farkından gelen dilimde işaret yok, ipucunda yazar", async () => {
    const diff = [{ ...VALIDITY_ROWS[1], SourceOrigin: "Senaryo farkı" }, VALIDITY_ROWS[3]];
    const { box } = await toValidity("calisma-duzeni", "End user", { scenario: { id: 2, name: "Fazla mesaili", is_base: false }, validity: diff });
    const marked = spansOf(box, "M3-01")[0];
    expect(marked.className).toBe("sc-validity-span is-own");                                             // işaret yok: fark tabloda belirtilir
    expect(marked.title.split("\n").at(-1)).toBe("Senaryo farkı");
    expect(spansOf(box, "M3-02")[0].className).toBe("sc-validity-span is-group");
    fireEvent.contextMenu(marked);
    expect(within(await screen.findByRole("menu")).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Kayda git"]);
  });

  it("geçerliliği olmayan girişte tablo seçimi yok; kartta her girişin seçimi ayrı ve kartın süzmesi geçerlilikte de geçerli", async () => {
    const { user, queries } = await open("duruslar");
    expect(screen.queryByRole("combobox", { name: "Tablo" })).toBeNull();
    await user.click(within(screen.getByRole("radiogroup", { name: "Kapasite yönetimi bölümleri" })).getByRole("radio", { name: "Kaynak grubu" }));
    await screen.findByRole("button", { name: "ISL3 işlemleri" });
    await menuOf(user, "ISL3 işlemleri");
    await user.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Detay" }));
    // şerit tabloyla birlikte yeniden çizilir: sekmeler her seferinde yeniden bulunur
    const cardTab = async (name: string) => within(await screen.findByRole("radiogroup", { name: "Kayıt bölümleri" })).getByRole("radio", { name });
    await user.click(await cardTab("Çalışma düzeni"));
    await screen.findByRole("button", { name: "Yeni kayıt" });                                            // kartın tablosu hazır
    await user.selectOptions(choice(), "gecerlilik");
    await waitFor(() => expect(queries["capacity-work-patterns-validity"]?.length ?? 0).toBeGreaterThan(0));
    expect(queries["capacity-work-patterns-validity"][0].filters).toEqual([{ field: "OwnerKeys", op: "contains", values: [",g12,"] }]);
    expect(await timeline()).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Yeni kayıt" })).toBeNull();
    await user.click(await cardTab("Ek mesai limitleri"));                                                // öteki girişin seçimi ayrı: Kayıtlar
    await waitFor(() => expect(choice()).toHaveValue("kayitlar"));
    expect(await screen.findByRole("button", { name: "Yeni kayıt" })).toBeInTheDocument();
    await user.click(await cardTab("Çalışma düzeni"));                                                    // geri dönünce seçim duruyor
    await waitFor(() => expect(choice()).toHaveValue("gecerlilik"));
  }, 20_000);   // uzun akış (iki ekran, kart, üç tablo): bütün testler birlikte koşarken varsayılan süre yetmeyebilir

  it("sekme durumu korunur: açık kart, kartın sekmesi ve tablo seçimi başka sekmeye gidip dönünce durur; tablolar yeniden yüklenmez", async () => {
    const { user, queries } = await open("grup");
    const top = (name: string) => within(screen.getByRole("radiogroup", { name: "Kapasite yönetimi bölümleri" })).getByRole("radio", { name });
    await menuOf(user, "ISL3 işlemleri");
    await user.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Detay" }));
    await user.click(within(await screen.findByRole("radiogroup", { name: "Kayıt bölümleri" })).getByRole("radio", { name: "Çalışma düzeni" }));
    await screen.findByRole("button", { name: "Yeni kayıt" });
    await user.selectOptions(choice(), "gecerlilik");
    await timeline();
    const groupQueries = queries["capacity-resource-groups"].length;

    await user.click(top("Bakım ve duruşlar"));
    await waitFor(() => expect(cellOf("M3-02", "Sebep")).toHaveTextContent("Mil arızası"));
    expect(screen.queryByRole("radiogroup", { name: "Kayıt bölümleri" })).toBeNull();                      // öteki sekme gizli
    expect(screen.queryByRole("group", { name: "Geçerlilik zaman çubuğu" })).toBeNull();

    await user.click(top("Kaynak grubu"));
    const tabs = await screen.findByRole("radiogroup", { name: "Kayıt bölümleri" });                      // kart açık, sekmesi yerinde
    expect(within(tabs).getByRole("radio", { name: "Çalışma düzeni" })).toHaveAttribute("aria-checked", "true");
    expect(choice()).toHaveValue("gecerlilik");
    expect(await timeline()).toBeInTheDocument();
    expect(queries["capacity-resource-groups"]).toHaveLength(groupQueries);                               // sekme yeniden kurulmadı
    await user.click(top("Bakım ve duruşlar"));                                                           // öteki sekmenin durumu da duruyor
    expect(cellOf("M3-02", "Sebep")).toHaveTextContent("Mil arızası");
  }, 20_000);
});

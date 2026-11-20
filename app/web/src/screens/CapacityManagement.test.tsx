// Kapasite yönetimi · giriş sekmeleri ve kartlar (ekran 30, K-185, 7.9b; docs/12 "Kapasite yönetimi"): sekmeler, "Yeni kayıt" penceresi,
// tablo içi düzenleme, satır menüsü (Baz'da ve izleyen senaryoda), senaryo farkı işareti, geçersiz satır, kartlar ve süzmeleri, End user.
import { screen, waitFor, within } from "@testing-library/react";
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

function backend(options: { scenario?: { id: number; name: string; is_base: boolean }; reply?: (call: Call) => Reply | undefined } = {}) {
  const scenario = options.scenario ?? { id: 1, name: "Baz", is_base: true };
  const calls: Call[] = [];
  const queries: Record<string, Record<string, unknown>[]> = {};
  const list = (name: string, columns: unknown[], rows: object[]) => ({
    [`/api/${name}/columns`]: { body: { chunk_size: 100, columns, relations: [], scenario_list: true, export: EXPORT } },
    [`/api/${name}/views`]: { body: { views: [], default_view_id: null } },
    [`/api/${name}/query`]: (_url: string, init?: RequestInit) => {
      (queries[name] ??= []).push(JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>);
      return { body: { rows, filtered: rows.length, total: rows.length } };
    },
  });
  mockApi({
    "/api/scenarios/current": { body: { ...scenario, is_active: true } },
    "/api/scenarios/options": { body: { scenarios: [{ id: 1, name: "Baz", is_base: true }, ...(scenario.is_base ? [] : [scenario])] } },
    ...list("capacity-work-patterns", WP_COLUMNS, [pattern(101, "Grup", "ISL3"), pattern(102, "Kaynak", "M3-01", { ValidFrom: "2026-11-23", DailyCapacity: 20, DaySat: "Yarım" })]),
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

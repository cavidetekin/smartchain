// Veri kuralları (ekran 04, fonksiyon 16, 18, 19; K-140…K-145): yetki, sıra (yalnız sürükle-bırak), toplu kayıt, yeniden uygulama
// sorusu, kural penceresi (Sonuç ve Seçenek), Çalışmadı çipi, hücre izi, menü sırası.
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, FakeWebSocket, meAs, mockApi, renderApp, type Reply, type Routes } from "../test/helpers";
import { SCREENS } from "./catalog";
import { dropId } from "./DataRules";
import { parseEffects, resultComplete } from "./dataRulesApi";
import { RULE_TRACE, RULE_TRACE_CELL } from "./ValidationDrawer";

useTableTestSetup();

const EXPORT = { title: "x", file_slug: "x", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const COLUMNS = [
  col("Seq", "Sıra", "number", "number"), col("RuleName", "Kural", "text", "text"), col("ConditionText", "Koşul", "text", "text"),
  col("ResultText", "Sonuç", "text", "text"), col("ApplyMode", "Seçenek", "text", "list"), col("IsActive", "Aktif", "bool", "list"),
  col("RunState", "Durum", "text", "list"),
];
const RULES = [
  { Id: 7, EntityName: "Location", Seq: 1, RuleName: "Tesis bayrağı", ConditionText: "Tip = Tesis", ResultText: "Tesis = Evet", ApplyMode: "Yalnız boşsa",
    IsActive: true, RunState: "Çalıştı", LastRunAt: "2026-11-09T08:30:00", LastRunMessage: null },
  { Id: 8, EntityName: "Location", Seq: 2, RuleName: "Depo bayrağı", ConditionText: "Tip = Depo", ResultText: "Depo = Evet", ApplyMode: "Yalnız boşsa",
    IsActive: true, RunState: "Çalışmadı", LastRunMessage: "Alan yok: EskiAlan" },
];
const FIELDS = [
  { name: "Code", label: "Lokasyon kodu", kind: "text", values: [], target: false, reason: "Anahtar alan hedef olamaz." },
  { name: "Type", label: "Tip", kind: "text", values: ["Tesis", "Depo", "Fason deposu"], target: true, reason: null },
  { name: "IsFactory", label: "Tesis", kind: "bool", values: [], target: true, reason: null },
  { name: "AdditionalNumber1", label: "Ek sayı 1", kind: "number", values: [], target: true, reason: null },
  { name: "AdditionalNumber2", label: "Ek sayı 2", kind: "number", values: [], target: true, reason: null },
];

const saved = (changed: string[] = []) => (_url: string, init?: RequestInit) => (init?.method === "PUT" ? { body: { saved: 1, changed_entities: changed } } : { body: {} });

function backend(routes: Routes = {}) {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/data-rules/columns": { body: { chunk_size: 100, columns: COLUMNS, export: EXPORT } },
    "/api/data-rules/query": { body: { rows: RULES, filtered: 2, total: 2 } },
    "/api/data-rules/views": { body: { views: [], default_view_id: null } },
    "/api/data-rules/fields/Location": { body: FIELDS as unknown as Reply["body"] },
    "/api/data-entities/query": { body: { rows: [{ Id: 1, Entity: "Location", Name: "Lokasyon" }], filtered: 1, total: 1 } },
    ...routes,
  });
}

const calls = () => vi.mocked(fetch).mock.calls.map(([url, init]) => ({ url: String(url), method: (init as RequestInit | undefined)?.method ?? "GET",
                                                                       body: (init as RequestInit | undefined)?.body ? JSON.parse(String((init as RequestInit).body)) : null }));
const PATH = "/veri/veri-kurallari";

describe("ekran 04 · Veri kuralları", () => {
  it("End user açamaz", async () => {
    backend();
    renderApp(PATH, meAs("End user"));
    expect(await screen.findByText(/Bu ekranı açma yetkiniz yok/)).toBeInTheDocument();
  });

  it("Key user salt okunur: Yeni kural ve yeniden uygula pasif, aktiflik değişmez", async () => {
    backend();
    renderApp(PATH, meAs("Key user"));
    expect(await screen.findByText("Tesis bayrağı", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Yeni kural/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Kuralları yeniden uygula/ })).toBeDisabled();
    expect(screen.getByRole("switch", { name: "Tesis bayrağı aktif" })).toBeDisabled();
  });

  it("şerit: Tablo, Yeni kural, Kuralları yeniden uygula aynı üst şeritte; Çalışmadı çipi", async () => {
    backend();
    renderApp(PATH, meAs("Admin"));
    await screen.findByText("Tesis bayrağı", {}, { timeout: 5000 });
    const strip = screen.getByRole("group", { name: "Tablo seçimi" });
    expect(within(strip).getByRole("combobox", { name: "Tablo" })).toBeInTheDocument();
    expect(within(strip).getByRole("button", { name: "Kuralları yeniden uygula" }).className).toContain("sc-btn--secondary");
    expect(screen.getAllByText("Çalışmadı").find((el) => el.classList.contains("sc-tag"))!.className).toContain("sc-tag--critical");
  });

  it("Durum her zaman dolu: Çalıştı soluk yeşil ve ipucunda zaman, Pasif ve Uygulanmadı gri; Sıra sola hizalı (K-145)", async () => {
    const user = userEvent.setup();
    backend({ "/api/data-rules/query": { body: { rows: [
      { ...RULES[0], RunState: "Çalıştı", LastRunAt: "2026-11-09T08:30:00" }, { ...RULES[1], RunState: "Pasif", IsActive: false },
      { ...RULES[0], Id: 9, Seq: 3, RuleName: "Yeni", RunState: "Uygulanmadı" },
    ], filtered: 3, total: 3 } } });
    renderApp(PATH, meAs("Admin"));
    await screen.findByText("Yeni", {}, { timeout: 5000 });
    const chip = (text: string) => screen.getAllByText(text).find((el) => el.classList.contains("sc-tag"))!;
    const ran = chip("Çalıştı");
    expect(ran.className).toContain("sc-tag--ok");
    expect(ran.className).toContain("sc-tag--soft");
    expect(chip("Pasif").className).toContain("sc-tag--neutral");
    expect(chip("Uygulanmadı").className).toContain("sc-tag--neutral");
    await user.hover(ran);
    expect(await screen.findByText(/^Son çalışma: 09\.11\.2026/)).toBeInTheDocument();
    const seqHeader = screen.getByRole("columnheader", { name: /Sıra/ });
    expect(seqHeader.className).not.toContain("is-num");
  });

  it("Tümü seçiliyken satır sürüklenmez; tablo seçilince sürüklenir, Kaydet sırayı gönderir, yeniden uygulama sorulur; Alt + ok yok (K-145)", async () => {
    const user = userEvent.setup();
    backend({ "/api/data-rules": saved(["Location"]), "/api/data-rules/apply": { status: 202, body: { job_ids: [3] } } });
    renderApp(PATH, meAs("Admin"));
    await screen.findByText("Tesis bayrağı", {}, { timeout: 5000 });
    const rowOf = (name: string) => screen.getByText(name).closest("tr")!;
    expect(rowOf("Tesis bayrağı")).not.toHaveAttribute("draggable");
    expect(screen.queryByRole("button", { name: /sırayı değiştir/ })).not.toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Tablo" }), "Location");
    await waitFor(() => expect(rowOf("Tesis bayrağı")).toHaveAttribute("draggable", "true"));
    rowOf("Tesis bayrağı").focus();
    await user.keyboard("{Alt>}{ArrowDown}{/Alt}");
    expect(screen.queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument();  // klavyeyle taşıma yok
    fireEvent.dragStart(rowOf("Tesis bayrağı"));
    fireEvent.dragOver(rowOf("Depo bayrağı"), { clientY: 10 });
    fireEvent.drop(rowOf("Depo bayrağı"));
    await user.click(await screen.findByRole("button", { name: "Kaydet" }));
    const confirm = await screen.findByRole("dialog", { name: "Kurallar yeniden uygulansın mı?" });
    const put = calls().find((c) => c.method === "PUT" && c.url === "/api/data-rules")!;
    expect(put.body).toEqual({ changes: [], orders: [{ entity: "Location", ids: [8, 7] }] });
    await user.click(within(confirm).getByRole("button", { name: "Uygula" }));
    await waitFor(() => expect(calls().find((c) => c.method === "POST" && c.url === "/api/data-rules/apply")?.body).toEqual({ entity: "Location" }));
  });

  it("yeni kural: hedef listesinde anahtar alan yok, Formül sayı alanında operatör ister, Boşalt'ta seçenek Her zaman", async () => {
    const user = userEvent.setup();
    backend({ "/api/data-rules": saved(["Location"]) });
    renderApp(PATH, meAs("Admin"));
    await screen.findByText("Tesis bayrağı", {}, { timeout: 5000 });
    await user.selectOptions(screen.getByRole("combobox", { name: "Tablo" }), "Location");
    await user.click(screen.getByRole("button", { name: "Yeni kural" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni veri kuralı" });
    const target = await within(dialog).findByRole("combobox", { name: /Hedef alan/ });
    expect(within(target).queryByRole("option", { name: "Lokasyon kodu" })).not.toBeInTheDocument();
    expect(within(dialog).getByText(/Koşulsuz kural tablonun bütün satırlarına uygulanır/)).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText(/^Kural adı/), "Ek sayı hesabı");
    await user.selectOptions(target, "AdditionalNumber1");
    await user.click(within(dialog).getByRole("radio", { name: "Formül" }));
    const op = within(dialog).getByRole("combobox", { name: "Operatör" });
    expect(within(op).getAllByRole("option").map((o) => o.textContent)).toEqual(["—", "+", "−", "×", "÷"]);
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Alan" }), "AdditionalNumber2");
    await user.selectOptions(op, "×");
    await user.type(within(dialog).getByRole("textbox", { name: "Değer" }), "2");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls().some((c) => c.method === "PUT")).toBe(true));
    const put = calls().find((c) => c.method === "PUT")!;
    expect(put.body.changes[0]).toEqual({ entity: "Location", name: "Ek sayı hesabı", target: "AdditionalNumber1", mode: "Yalnız boşsa", active: true, groups: [],
                                          result: { kind: "Formül", value: null, source_field: "AdditionalNumber2", operator: "×", operand_value: "2", operand_field: null } });
    expect(await screen.findByRole("dialog", { name: "Kurallar yeniden uygulansın mı?" })).toBeInTheDocument();
  });

  it("satırdan sürükle-bırak sırayı değiştirir; satırın tamamı bırakma yeri (K-143)", async () => {
    const user = userEvent.setup();
    backend({ "/api/data-rules": saved(["Location"]) });
    renderApp(PATH, meAs("Admin"));
    await screen.findByText("Tesis bayrağı", {}, { timeout: 5000 });
    await user.selectOptions(screen.getByRole("combobox", { name: "Tablo" }), "Location");
    const rowOf = (name: string) => screen.getByText(name).closest("tr")!;
    await waitFor(() => expect(rowOf("Tesis bayrağı")).toHaveAttribute("draggable", "true"));
    fireEvent.dragStart(rowOf("Tesis bayrağı"));
    fireEvent.dragOver(rowOf("Depo bayrağı"), { clientY: 10 });  // alt yarı: arkasına
    fireEvent.drop(screen.getByText("Depo = Evet"));  // satırın herhangi bir hücresine
    await user.click(await screen.findByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls().find((c) => c.method === "PUT")?.body).toEqual({ changes: [], orders: [{ entity: "Location", ids: [8, 7] }] }));
  });

  it("Sonuç'ta değer listeli alanda seçim kutusu kalır (Smartchain değeri)", async () => {
    const user = userEvent.setup();
    backend();
    renderApp(PATH, meAs("Admin"));
    await screen.findByText("Tesis bayrağı", {}, { timeout: 5000 });
    await user.selectOptions(screen.getByRole("combobox", { name: "Tablo" }), "Location");
    await user.click(screen.getByRole("button", { name: "Yeni kural" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni veri kuralı" });
    await user.selectOptions(await within(dialog).findByRole("combobox", { name: /Hedef alan/ }), "Type");
    expect(within(dialog).getByRole("combobox", { name: "Değer" }).tagName).toBe("SELECT");
  });

  it("Boşalt seçilince seçenek Her zaman olur ve değişmez", async () => {
    const user = userEvent.setup();
    backend();
    renderApp(PATH, meAs("Admin"));
    await screen.findByText("Tesis bayrağı", {}, { timeout: 5000 });
    await user.selectOptions(screen.getByRole("combobox", { name: "Tablo" }), "Location");
    await user.click(screen.getByRole("button", { name: "Yeni kural" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni veri kuralı" });
    await within(dialog).findByRole("combobox", { name: /Hedef alan/ });
    await user.click(within(dialog).getByRole("radio", { name: "Boşalt" }));
    expect(within(dialog).getByRole("radio", { name: "Her zaman" })).toHaveAttribute("aria-checked", "true");
    await user.click(within(dialog).getByRole("radio", { name: "Yalnız boşsa" }));
    expect(within(dialog).getByRole("radio", { name: "Her zaman" })).toHaveAttribute("aria-checked", "true");
  });

  it("menü sırası: Veri yükleme, Dünden bugüne, Veri kuralları, Validasyon kuralları, Ana veri, Veri kalitesi", () => {
    expect(SCREENS.filter((s) => s.group === "veri").map((s) => s.name)).toEqual(["Veri yükleme", "Dünden bugüne", "Veri kuralları", "Validasyon kuralları", "Ana veri", "Veri kalitesi"]);
  });
});

describe("sıra ve kural izi yardımcıları", () => {
  it("taşıma ve bırakma", () => {
    expect(dropId(["a", "b", "c"], "c", "a", "before")).toEqual(["c", "a", "b"]);
    expect(dropId(["a", "b", "c"], "a", "c", "after")).toEqual(["b", "c", "a"]);
  });

  it("sonuç tamam mı", () => {
    expect(resultComplete({ kind: "Boşalt", value: null, source_field: null, operator: null, operand_value: null, operand_field: null })).toBe(true);
    expect(resultComplete({ kind: "Formül", value: null, source_field: "A", operator: "+", operand_value: null, operand_field: null })).toBe(false);
  });

  it("hücre izi: kuralla değişen hücrenin zemini lila (sınıf), ipucunda kural adı ve ham değer, numara yok (K-143)", async () => {
    const user = userEvent.setup();
    const row = { Id: 1, RuleEffects: "IsFactory\u001f3\u001fTesis bayrağı\u001f\u001eIsDepot\u001f4\u001fDepo bayrağı\u001f0" };
    expect(parseEffects(row.RuleEffects).get("IsDepot")).toEqual({ seq: "4", rule: "Depo bayrağı", raw: "0" });
    expect(RULE_TRACE_CELL("IsFactory", row)).toBe("is-rule-changed");
    expect(RULE_TRACE_CELL("Code", row)).toBeUndefined();
    render(<>{RULE_TRACE("IsFactory", row, "Evet")}{RULE_TRACE("Code", row, "ORM-01")}</>);
    await user.hover(screen.getByText("Evet"));
    expect(await screen.findByText("Tesis bayrağı · Ham değer: boş")).toBeInTheDocument();
  });

  it("kural listesi 100 satırdan fazla istemez; sıra sayfa sayfa okunur", async () => {
    const limits: number[] = [];
    backend({ "/api/data-rules/query": (_url: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body ?? "{}"));
      limits.push(body.limit);
      return body.limit > 100 ? { status: 422, body: { error: { code: "validation", message: "x", details: [] } } } : { body: { rows: RULES, filtered: 2, total: 2 } };
    } });
    renderApp(PATH, meAs("Admin"));
    await screen.findByText("Tesis bayrağı", {}, { timeout: 5000 });
    expect(Math.max(...limits)).toBeLessThanOrEqual(100);
  });

  it("Kuralları yeniden uygula işi bitince liste kendiliğinden yenilenir (K-143)", async () => {
    backend({ "/api/jobs": { body: { jobs: [], counters: {} } as unknown as Reply["body"] } });
    renderApp(PATH, { ...meAs("Admin"), id: 1 });
    await screen.findByText("Tesis bayrağı", {}, { timeout: 5000 });
    await waitFor(() => expect(FakeWebSocket.instances.some((s) => s.url.includes("/api/ws"))).toBe(true));
    const before = calls().filter((c) => c.url === "/api/data-rules/query").length;
    act(() => FakeWebSocket.instances.find((s) => s.url.includes("/api/ws"))!.send({ type: "job", job: {
      id: 9, job_type: "Validasyon", status: "Bitti", summary: "Validasyon · Lokasyon", requested_by: 1, created_at: "2026-11-09T08:00:00", result: null, validation: null,
    } }));
    await waitFor(() => expect(calls().filter((c) => c.url === "/api/data-rules/query").length).toBeGreaterThan(before), { timeout: 3000 });
  });
});

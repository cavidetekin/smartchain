// Model kısıtları (ekran 31, fonksiyon 103; K-189; docs/12 "Model kısıtları"): tek sekme, her kaynak grubu bir satır; değer hücreye yazılır, "%85"
// yazımı, boşaltma, Kaydet'te tek istek, reddedilen hücre; kritik olmayan grupta da giriş; Lokasyon alanı; senaryo farkı işareti ve "Senaryo farkını kaldır"; Detay kartı; End user.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { meAs, mockApi, renderApp, type Reply } from "../test/helpers";
import { col, useTableTestSetup } from "../table/testBackend";
import { cellOf, setCell } from "../table/testEditing";
import { constraintText, FACTOR, TARGET } from "./ModelConstraints";

useTableTestSetup();

const PATH = "/parametre/model-kisitlari";
const LIST = "model-constraints-resource-groups";
const EXPORT = { title: "x", file_slug: "x", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const COLUMNS = [
  col("LocationCode", "Lokasyon", "text", "list"), col("Code", "Kaynak grubu", "text", "text"), col("Name", "Ad", "text", "text"), col("IsCritical", "Kritik", "bool", "list"), col("CapacityUnit", "Kapasite birimi", "text", "list"),
  col(FACTOR, "Kısıtsız kapasite çarpanı", "number", "number", { decimals: 2 }), col(TARGET, "Hedef doluluk (%)", "number", "number", { decimals: 2 }),
  col("Origin", "Kaynağı", "text", "list"),
];
const group = (id: number, code: string, critical: boolean, extra: object = {}) => ({
  Id: id, LocationCode: "ORM-01", Code: code, Name: `${code} adı`, IsCritical: critical, CapacityUnit: "SAAT", [FACTOR]: null, [TARGET]: null, Origin: null, StoredId: null, OverriddenFields: null,
  BaseValues: null, CanRestore: false, ...extra });
const BASE_ROWS = [
  group(1, "TORNA", true, { [TARGET]: 85, Origin: "Baz", StoredId: 11 }),
  group(2, "MONTAJ", true, { [FACTOR]: 1.5, Origin: "Baz", StoredId: 12 }),
  group(3, "KALITE", true),
  group(4, "F-KAPLA", false),
  group(5, "ESKI", false, { [FACTOR]: 1.25, Origin: "Baz", StoredId: 15 }),          // kritik olmayan grupta da değer durur
];
const FOLLOWER_ROWS = [
  group(1, "TORNA", true, { [TARGET]: 85, Origin: "Baz" }),
  group(2, "MONTAJ", true, { [FACTOR]: 2, Origin: "Senaryo farkı", StoredId: 22, OverriddenFields: `,${FACTOR},`, BaseValues: JSON.stringify({ [FACTOR]: 1.5, [TARGET]: null }),
                             CanRestore: true }),
  group(3, "KALITE", true, { [FACTOR]: 1.25, Origin: "Senaryo", StoredId: 23, CanRestore: true }),   // Baz'da değeri yok: kaldırınca boşalır
  // önce senaryoda, sonra Baz'da girilmiş: tek satır, senaryonun değeri, Senaryo farkı (iki alan da senaryodan)
  group(4, "ISL5", true, { [FACTOR]: 1.25, Origin: "Senaryo farkı", StoredId: 24, OverriddenFields: `,${FACTOR},${TARGET},`, BaseValues: JSON.stringify({ [FACTOR]: 1.5, [TARGET]: 80 }),
                           CanRestore: true }),
];

type Call = { method: string; url: string; body: Record<string, unknown> };

function backend(options: { scenario?: { id: number; name: string; is_base: boolean }; rows?: object[]; reply?: (call: Call) => Reply | undefined } = {}) {
  const scenario = options.scenario ?? { id: 1, name: "Baz", is_base: true };
  const rows = options.rows ?? BASE_ROWS;
  const calls: Call[] = [];
  const queries: Record<string, Record<string, unknown>[]> = {};
  const list = (name: string, columns: unknown[], found: object[]) => ({
    [`/api/${name}/columns`]: { body: { chunk_size: 100, columns, relations: [{ path: "LocationId", label: "Lokasyon" }], scenario_list: true, export: EXPORT } },
    [`/api/${name}/views`]: { body: { views: [], default_view_id: null } },
    [`/api/${name}/query`]: (_url: string, init?: RequestInit) => {
      (queries[name] ??= []).push(JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>);
      return { body: { rows: found, filtered: found.length, total: found.length } };
    },
  });
  mockApi({
    "/api/scenarios/current": { body: { ...scenario, is_active: true } },
    "/api/scenarios/options": { body: { scenarios: [{ id: 1, name: "Baz", is_base: true }, ...(scenario.is_base ? [] : [scenario])] } },
    ...list(LIST, COLUMNS, rows),
    ...list("record-history", [col("At", "Tarih", "datetime", "date"), col("FieldLabel", "Alan", "text", "list"), col("OldValue", "Eski değer", "text", "text"),
                               col("NewValue", "Yeni değer", "text", "text"), col("ChangedBy", "Değiştiren", "text", "list")],
            [{ Id: 1, At: "2026-11-20T10:42:00", FieldLabel: "Hedef doluluk (%)", OldValue: null, NewValue: "%85", ChangedBy: "planlama" }]),
    "/api/model-constraints/": (url: string, init?: RequestInit) => {
      const call = { method: init?.method ?? "GET", url, body: init?.body ? JSON.parse(String(init.body)) as Record<string, unknown> : {} };
      calls.push(call);
      return options.reply?.(call) ?? { body: { saved: 1, restored: true } };
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
const menuOf = async (user: ReturnType<typeof userEvent.setup>, name: string) => {
  await user.click(screen.getByRole("button", { name }));
  return within(await screen.findByRole("menu")).getAllByRole("menuitem").map((m) => m.textContent);
};

describe("ekran 31 · Model kısıtları (K-189, 7.10)", () => {
  it("yazım: çarpan iki ondalık, hedef doluluk '%85'; düzenleyicide sayı", () => {
    expect([constraintText(FACTOR, 1.5), constraintText(TARGET, 85), constraintText(TARGET, 87.5), constraintText(TARGET, 85, true), constraintText(FACTOR, null)])
      .toEqual(["1,50", "%85", "%87,5", "85", ""]);
  });

  it("tek sekme; her kaynak grubu bir satır; Yeni kayıt yok; istek seçili senaryoyu taşır; değerler yazımıyla", async () => {
    const { queries } = await open();
    const tabs = within(screen.getByRole("radiogroup", { name: "Model kısıtları bölümleri" })).getAllByRole("radio");
    expect(tabs.map((t) => [t.textContent, t.getAttribute("aria-checked")])).toEqual([["Kaynak grubu", "true"], ["Tedarikçi limiti", "false"], ["Malzeme blokajı", "false"]]);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Model kısıtları");
    expect(screen.queryByRole("button", { name: "Yeni kayıt" })).toBeNull();
    expect(queries[LIST][0]).toMatchObject({ scenario_id: 1 });
    expect(rowsOf()).toHaveLength(5);
    expect(cellOf("TORNA", "Hedef doluluk (%)")).toHaveTextContent("%85");
    expect(cellOf("MONTAJ", "Kısıtsız kapasite çarpanı")).toHaveTextContent("1,50");
    expect(cellOf("KALITE", "Kısıtsız kapasite çarpanı")).toHaveTextContent("");
    expect(cellOf("KALITE", "Kaynağı")).toHaveTextContent("");
    // düzenlenebilir kolonlar yalnız iki değer
    const editable = screen.getAllByRole("columnheader").filter((h) => h.querySelector(".sc-table-edit-mark")).map((h) => h.querySelector(".sc-table-label")?.textContent);
    expect(editable).toEqual(["Kısıtsız kapasite çarpanı", "Hedef doluluk (%)"]);
    expect(cellOf("KALITE", "Hedef doluluk (%)")).toHaveClass("is-editable");                            // kritik grup: boş hücreye de yazılır
    expect(cellOf("KALITE", "Ad")).not.toHaveClass("is-editable");
  });

  it("değer hücreye yazılır ve boşaltılır; Kaydet hepsini tek istekte gönderir; reddedilen hücre kırmızı ve taslak durur", async () => {
    let reject = true;
    const { user, calls, queries } = await open("Key user", { reply: (call) => (call.method === "PUT" && reject
      ? { status: 422, body: { error: { code: "validation", message: "Kaydedilmedi.", trace_id: "t", details: [{ id: 3, field: FACTOR, record: "Kaynak grubu KALITE", problem: "En az 1 olmalı." }] } } }
      : undefined) });
    await setCell(user, "KALITE", "Kısıtsız kapasite çarpanı", "0,8");
    await setCell(user, "KALITE", "Hedef doluluk (%)", "90");
    await setCell(user, "TORNA", "Hedef doluluk (%)", "");                                              // boşaltmak değeri kaldırır
    expect(cellOf("KALITE", "Hedef doluluk (%)")).toHaveTextContent("%90");                             // taslak da "%" ile görünür
    expect(cellOf("KALITE", "Hedef doluluk (%)")).toHaveClass("is-draft");
    expect(cellOf("TORNA", "Hedef doluluk (%)")).toHaveTextContent("");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT")).toHaveLength(1));
    expect(calls[0].url).toContain("/api/model-constraints/resource-groups?scenario_id=1");
    expect(calls[0].body.changes).toEqual(expect.arrayContaining([{ id: 3, field: FACTOR, value: "0,8" }, { id: 3, field: TARGET, value: "90" }, { id: 1, field: TARGET, value: null }]));
    await waitFor(() => expect(cellOf("KALITE", "Kısıtsız kapasite çarpanı")).toHaveClass("is-invalid"));
    expect(cellOf("KALITE", "Kısıtsız kapasite çarpanı")).toHaveTextContent("0,8");                     // taslak durur
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeEnabled();
    reject = false;
    const before = queries[LIST].length;
    await setCell(user, "KALITE", "Kısıtsız kapasite çarpanı", "1,2");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(queries[LIST].length).toBeGreaterThan(before));                           // kaydedince tablo yenilenir
    await waitFor(() => expect(screen.queryByRole("button", { name: "Kaydet" })).toBeNull());
  });

  it("giriş kısıtlanmaz: kritik olmayan grupta da değer hücreleri düzenlenir ve gönderilir; soluk yazım yok; Lokasyon kodun solunda", async () => {
    const { user, calls } = await open();
    const heads = screen.getAllByRole("columnheader").map((h) => h.querySelector(".sc-table-label")?.textContent).filter(Boolean);
    expect(heads.slice(0, 2)).toEqual(["Lokasyon", "Kaynak grubu"]);
    expect(cellOf("TORNA", "Lokasyon")).toHaveTextContent("ORM-01");
    for (const code of ["F-KAPLA", "ESKI", "KALITE"]) {
      expect(cellOf(code, "Kısıtsız kapasite çarpanı")).toHaveClass("is-editable");
      expect(cellOf(code, "Hedef doluluk (%)")).toHaveClass("is-editable");
    }
    expect(document.querySelector(".sc-cell-unapplied")).toBeNull();
    expect(cellOf("ESKI", "Kısıtsız kapasite çarpanı")).toHaveTextContent("1,25");
    await setCell(user, "F-KAPLA", "Kısıtsız kapasite çarpanı", "2");                                   // kritik olmayan, boş hücre: yazılır
    await setCell(user, "ESKI", "Hedef doluluk (%)", "70");
    expect(cellOf("F-KAPLA", "Kısıtsız kapasite çarpanı")).toHaveClass("is-draft");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT")).toHaveLength(1));
    expect(calls[0].body.changes).toEqual(expect.arrayContaining([{ id: 4, field: FACTOR, value: "2" }, { id: 5, field: TARGET, value: "70" }]));
  });

  it("izleyen senaryo: değişen hücre işaretli, ipucunda Baz değeri; değeri senaryodan gelen her satırda Senaryo farkını kaldır", async () => {
    const { user, calls, queries } = await open("Key user", { scenario: { id: 2, name: "Kısıtsız kapasite", is_base: false }, rows: FOLLOWER_ROWS });
    expect(queries[LIST][0]).toMatchObject({ scenario_id: 2 });
    const changed = cellOf("MONTAJ", "Kısıtsız kapasite çarpanı");
    expect(changed).toHaveClass("sc-cell-diff");
    expect(changed).toHaveTextContent("2,00");
    expect(cellOf("MONTAJ", "Hedef doluluk (%)")).not.toHaveClass("sc-cell-diff");
    await user.hover(within(changed).getByText("2,00"));
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Baz: 1,50");
    expect(cellOf("MONTAJ", "Kaynağı")).toHaveTextContent("Senaryo farkı");
    expect(rowsOf()).toHaveLength(4);                                                                    // her grup tek satır
    // önce senaryoda sonra Baz'da girilen grup: iki hücre de işaretli, ipucunda Baz değeri, Kaynağı Senaryo farkı
    expect(cellOf("ISL5", "Kısıtsız kapasite çarpanı")).toHaveClass("sc-cell-diff");
    expect(cellOf("ISL5", "Hedef doluluk (%)")).toHaveClass("sc-cell-diff");
    expect(cellOf("ISL5", "Kaynağı")).toHaveTextContent("Senaryo farkı");
    await user.unhover(within(changed).getByText("2,00"));
    await user.hover(within(cellOf("ISL5", "Kısıtsız kapasite çarpanı")).getByText("1,25"));
    await waitFor(() => expect(screen.getByRole("tooltip")).toHaveTextContent("Baz: 1,50"));
    expect(await menuOf(user, "ISL5 işlemleri")).toEqual(["Detay", "Senaryo farkını kaldır"]);
    await user.keyboard("{Escape}");
    expect(await menuOf(user, "KALITE işlemleri")).toEqual(["Detay", "Senaryo farkını kaldır"]);         // yalnız senaryoda olan değer: kaldırınca boşalır
    await user.keyboard("{Escape}");
    expect(await menuOf(user, "TORNA işlemleri")).toEqual(["Detay"]);                                    // Baz'dan okunan, değişmemiş
    await user.keyboard("{Escape}");
    expect(await menuOf(user, "MONTAJ işlemleri")).toEqual(["Detay", "Senaryo farkını kaldır"]);
    const before = queries[LIST].length;
    await user.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Senaryo farkını kaldır" }));
    await waitFor(() => expect(calls.map((c) => [c.method, c.url])).toEqual([["POST", "/api/model-constraints/resource-groups/2/restore?scenario_id=2"]]));
    await waitFor(() => expect(queries[LIST].length).toBeGreaterThan(before));
  });

  it("Detay kartında yalnız Geçmiş: kaynak grubu kimliğiyle ve senaryolu anahtarla süzülür", async () => {
    const { user, queries } = await open();
    await menuOf(user, "TORNA işlemleri");
    await user.click(within(screen.getByRole("menu")).getByRole("menuitem", { name: "Detay" }));
    const tabs = await screen.findByRole("radiogroup", { name: "Kayıt bölümleri" });
    expect(within(tabs).getAllByRole("radio").map((t) => t.textContent)).toEqual(["Geçmiş"]);
    await waitFor(() => expect(queries["record-history"]?.length ?? 0).toBeGreaterThan(0));
    expect(queries["record-history"][0].filters).toEqual([{ field: "TableName", op: "in", values: ["ResourceGroupConstraint"] },
                                                         { field: "RecordKey", op: "in", values: ["1", "1@1"] }]);
    await waitFor(() => expect(rowsOf().some((r) => r.textContent?.includes("planlama") && r.textContent.includes("%85"))).toBe(true));   // Geçmiş satırı
  });

  it("End user görür: düzenleme, Kaydet ve Senaryo farkını kaldır yok", async () => {
    const { user } = await open("End user", { scenario: { id: 2, name: "Kısıtsız kapasite", is_base: false }, rows: FOLLOWER_ROWS });
    expect(document.querySelector(".sc-table-edit-mark")).toBeNull();
    expect(document.querySelector("td.is-editable")).toBeNull();
    await user.dblClick(cellOf("TORNA", "Hedef doluluk (%)"));
    expect(cellOf("TORNA", "Hedef doluluk (%)").querySelector(".sc-cell-editor")).toBeNull();
    expect(await menuOf(user, "MONTAJ işlemleri")).toEqual(["Detay"]);
    expect(cellOf("MONTAJ", "Kısıtsız kapasite çarpanı")).toHaveClass("sc-cell-diff");                  // işaret görünür
  });
});

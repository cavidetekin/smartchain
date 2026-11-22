// Parametreler › Uyarı eşikleri (fonksiyon 26; K-190; docs/12 "Parametreler"): sekizinci başlık; öteki başlıklardaki düzen (solda alt başlıklar Talep ·
// Malzeme · Kapasite · Plan kalitesi, sağda seçili kategorinin kartı); kolonlar Uyarı · Birim · Yön · Düşük · Orta · Yüksek · Kritik · Aktif; yüzde "%95"
// yazımı; hücre düzenleme ve boşaltma; yöne göre kademe sırası (bozuksa hücre kırmızı, Kaydet pasif); eşiksiz uyarıda dört önem kolonunun yerinde tek
// seçim düğmesi; kapatılan uyarının satırı belirgin soluk ve değerleri durur; kaydetme kategori başına (istek tablonun tamamını taşır); sunucunun
// reddettiği hücre; kaydedilmemiş değişiklikle kategori değişirken uyarı.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { meAs, mockApi, renderApp, type Reply } from "../test/helpers";

const PATH = "/parametre/parametreler?sekme=uyari-esikleri";
const CATEGORIES = ["Talep", "Malzeme", "Kapasite", "Plan kalitesi"];
const SLUG: Record<string, string> = { Talep: "talep", Malzeme: "malzeme", Kapasite: "kapasite", "Plan kalitesi": "plan-kalitesi" };
const SECTIONS = [
  { key: "model", title: "Model", table: null, subs: [{ key: "model-tipi", title: "Model tipi", table: null, params: [{ key: "ModelType", label: "Model tipi", kind: "choice", options: ["LP", "MILP"] }] }] },
  { key: "hedefler", title: "Hedefler", table: "objectives", subs: [] },
  { key: "uyari-esikleri", title: "Uyarı eşikleri", table: null, subs: CATEGORIES.map((c) => ({ key: SLUG[c], title: c, table: "warnings", params: [] })) },
];
const SEVERITIES = ["Düşük", "Orta", "Yüksek", "Kritik"];
type Tiers = [number | null, number | null, number | null, number | null];
const tiered = (code: string, label: string, category: string, unit: string, direction: string, [low, medium, high, critical]: Tiers, active = true) =>
  ({ code, label, category, unit, direction, low, medium, high, critical, severity: null, active });
const plain = (code: string, label: string, category: string, severity: string) =>
  ({ code, label, category, unit: null, direction: null, low: null, medium: null, high: null, critical: null, severity, active: true });
const ROWS = [
  tiered("ORDER_LATE", "Gecikme", "Talep", "gün", "above", [5, 10, 15, 20]),
  tiered("OTIF_RATE", "OTIF oranı", "Talep", "%", "below", [95, 90, 85, 80]),
  plain("FORECAST_UNMET", "Karşılanmayan tahmin", "Talep", "Orta"),
  tiered("MAT_EXCESS", "Fazla stok", "Malzeme", "%", "above", [100, 125, 150, null]),
  tiered("CAP_OVERLOAD", "Aşırı yük", "Kapasite", "%", "above", [null, 100, 110, 125]),
  tiered("CAP_LOW_LOAD", "Düşük doluluk", "Kapasite", "%", "below", [40, 20, null, null], false),
  plain("PLAN_RELAXED", "Kısıt gevşetildi", "Plan kalitesi", "Yüksek"),
];
type Sent = { code: string; active: boolean; severity: string | null; low: number | null; medium: number | null; high: number | null; critical: number | null };

function backend(reply?: (rows: Sent[]) => Reply | undefined) {
  const sent: Sent[][] = [];
  let current = ROWS;
  mockApi({
    "/api/parameters/warning-thresholds": (_url: string, init?: RequestInit) => {
      if (init?.method !== "PUT") return { body: { rows: current, categories: CATEGORIES, severities: SEVERITIES } };
      const rows = (JSON.parse(String(init.body)) as { rows: Sent[] }).rows;
      sent.push(rows);
      const answer = reply?.(rows);
      if (answer) return answer;
      current = current.map((r) => ({ ...r, ...rows.find((x) => x.code === r.code)! })) as typeof ROWS;
      return { body: { rows: current, categories: CATEGORIES, severities: SEVERITIES, saved: 1 } };
    },
    "/api/parameters/objectives": { body: { rows: [], total_seconds: 0 } },
    "/api/parameters": { body: { scenario: { id: 1, name: "Baz" }, sections: SECTIONS, values: { ModelType: "LP" }, computed: { fix_period_end: null } } },
  });
  return sent;
}

const tableOf = (category: string) => screen.findByRole("table", { name: `Uyarı eşikleri · ${category}` }, { timeout: 5000 });
async function open(category = "Talep", role = "Key user", reply?: Parameters<typeof backend>[0]) {
  const user = userEvent.setup();
  const sent = backend(reply);
  renderApp(category === "Talep" ? PATH : `${PATH}&bolum=${SLUG[category]}`, meAs(role));
  return { user, sent, table: await tableOf(category) };
}
const save = () => screen.getByRole("button", { name: "Kaydet" });
const menu = () => screen.getByRole("navigation", { name: "Uyarı eşikleri bölümleri" });
const rowOf = (table: HTMLElement, label: string) => within(table).getAllByRole("row").find((r) => r.querySelector("td")?.textContent === label)!;
const HEADS = ["Uyarı", "Birim", "Yön", "Düşük", "Orta", "Yüksek", "Kritik", "Aktif"];
const cell = (table: HTMLElement, label: string, head: string) => rowOf(table, label).querySelectorAll("td")[HEADS.indexOf(head)] as HTMLElement;
const labels = (table: HTMLElement) => within(table).getAllByRole("row").slice(1).map((r) => r.querySelector("td")?.textContent);
const choice = (table: HTMLElement, label: string) => within(rowOf(table, label)).getByRole("radiogroup", { name: `${label} önemi` });
async function write(user: ReturnType<typeof userEvent.setup>, table: HTMLElement, label: string, head: string, text: string) {
  await user.dblClick(cell(table, label, head));
  const editor = within(table).getByRole("textbox");
  await user.clear(editor);
  await user.type(editor, text ? `${text}{Enter}` : "{Enter}");
}

describe("ekran 06 · Parametreler › Uyarı eşikleri (K-190)", () => {
  it("öteki başlıklardaki düzen: solda dört alt başlık, sağda seçili kategorinin kartı; kolonlar ve Yön; yüzde '%95'; düğmeler kartın altında", async () => {
    const { user, table } = await open();
    const tabs = within(screen.getByRole("radiogroup", { name: "Parametre başlıkları" })).getAllByRole("radio");
    expect(tabs.map((t) => [t.textContent, t.getAttribute("aria-checked")])).toEqual([["Model", "false"], ["Hedefler", "false"], ["Uyarı eşikleri", "true"]]);
    expect(within(menu()).getAllByRole("button").map((b) => [b.textContent, b.getAttribute("aria-current")])).toEqual([
      ["Talep", "true"], ["Malzeme", null], ["Kapasite", null], ["Plan kalitesi", null]]);
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent?.replace("✎", ""))).toEqual(HEADS);
    // düzenlenen kolonların hepsinde işaret: dört önem ve Aktif
    expect(within(table).getAllByRole("columnheader").filter((h) => h.textContent?.includes("✎")).map((h) => h.textContent?.replace("✎", ""))).toEqual([...SEVERITIES, "Aktif"]);
    expect(labels(table)).toEqual(["Gecikme", "OTIF oranı", "Karşılanmayan tahmin"]);                                       // yalnız seçili kategori; grup satırı yok
    expect(table.querySelector(".sc-edit-grid-group")).toBeNull();
    expect(SEVERITIES.map((s) => cell(table, "Gecikme", s).textContent)).toEqual(["5", "10", "15", "20"]);
    expect(SEVERITIES.map((s) => cell(table, "OTIF oranı", s).textContent)).toEqual(["%95", "%90", "%85", "%80"]);
    expect(["Gecikme", "OTIF oranı", "Karşılanmayan tahmin"].map((l) => [cell(table, l, "Birim").textContent, cell(table, l, "Yön").textContent])).toEqual([
      ["gün", "Aşınca"], ["%", "Altına düşünce"], ["", ""]]);
    expect(cell(table, "Gecikme", "Yön")).not.toHaveClass("is-editable");                                                  // salt okunur
    expect(save()).toBeDisabled();
    expect(table.closest(".sc-settings-card")?.querySelector(".sc-settings-foot")).not.toBeNull();                            // Vazgeç ve Kaydet kartın altında
    expect(table.closest(".sc-settings-body")?.querySelector(".sc-settings-nav")).not.toBeNull();                             // alt başlık menüsüyle aynı gövdede
    // öteki kategoriler: alt başlıktan geçilir
    await user.click(within(menu()).getByRole("button", { name: "Kapasite" }));
    const capacity = await tableOf("Kapasite");
    expect(labels(capacity)).toEqual(["Aşırı yük", "Düşük doluluk"]);
    expect(SEVERITIES.map((s) => cell(capacity, "Aşırı yük", s).textContent)).toEqual(["", "%100", "%110", "%125"]);        // boş kademe kullanılmıyor
    expect(rowOf(capacity, "Düşük doluluk")).toHaveClass("is-off", "is-dim");                                               // kapalı uyarı belirgin soluk, değerleri durur
    expect(cell(capacity, "Düşük doluluk", "Düşük")).toHaveTextContent("%40");
    expect(within(capacity).getByRole("switch", { name: "Düşük doluluk aktif" })).not.toBeChecked();
    await user.click(within(menu()).getByRole("button", { name: "Malzeme" }));
    expect(labels(await tableOf("Malzeme"))).toEqual(["Fazla stok"]);
    await user.click(within(menu()).getByRole("button", { name: "Plan kalitesi" }));
    expect(labels(await tableOf("Plan kalitesi"))).toEqual(["Kısıt gevşetildi"]);
  });

  it("eşiksiz uyarıda dört önem kolonunun yerinde tek seçim düğmesi; tik yok; seçim değişince hücre lila", async () => {
    const { user, sent, table } = await open();
    const cells = rowOf(table, "Karşılanmayan tahmin").querySelectorAll("td");
    expect(cells).toHaveLength(5);                                                                                         // Uyarı · Birim · Yön · (dört önem tek hücre) · Aktif
    expect(cells[3]).toHaveAttribute("colspan", "4");
    const options = within(choice(table, "Karşılanmayan tahmin")).getAllByRole("radio");
    expect(options.map((o) => [o.textContent, o.getAttribute("aria-checked")])).toEqual([["Düşük", "false"], ["Orta", "true"], ["Yüksek", "false"], ["Kritik", "false"]]);
    expect(choice(table, "Karşılanmayan tahmin")).toHaveClass("sc-segment");                                                // Parametreler'deki seçim düğmesi
    expect(table.querySelector(".sc-severity-pick")).toBeNull();
    expect(rowOf(table, "Karşılanmayan tahmin").querySelector("svg")).toBeNull();                                           // tik işareti yok
    await user.click(within(choice(table, "Karşılanmayan tahmin")).getByRole("radio", { name: "Yüksek" }));
    expect(within(choice(table, "Karşılanmayan tahmin")).getAllByRole("radio").map((o) => o.getAttribute("aria-checked"))).toEqual(["false", "false", "true", "false"]);
    expect(cells[3]).toHaveClass("is-draft");
    await user.click(save());
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0].find((r) => r.code === "FORECAST_UNMET")).toEqual({ code: "FORECAST_UNMET", active: true, severity: "Yüksek", low: null, medium: null, high: null, critical: null });
    await waitFor(() => expect(save()).toBeDisabled());
  });

  it("hücre düzenlenir ve boşaltılır; uyarı kapatılır; Kaydet kategori başına çalışır ve tablonun tamamını tek istekte gönderir", async () => {
    const { user, sent, table } = await open();
    await write(user, table, "Gecikme", "Orta", "12");
    await write(user, table, "OTIF oranı", "Düşük", "%97,5");                                                               // "%" ile yazılsa da sayı alınır
    await write(user, table, "Gecikme", "Kritik", "");                                                                      // kademe boşaltılır
    expect(cell(table, "Gecikme", "Orta")).toHaveClass("is-draft");
    expect(cell(table, "OTIF oranı", "Düşük")).toHaveTextContent("%97,5");
    expect(cell(table, "Gecikme", "Kritik")).toHaveTextContent("");
    await user.click(within(table).getByRole("switch", { name: "OTIF oranı aktif" }));                                       // kapatılan uyarının değerleri durur
    expect(rowOf(table, "OTIF oranı")).toHaveClass("is-dim");
    expect(cell(table, "OTIF oranı", "Düşük")).toHaveTextContent("%97,5");
    expect(save()).toBeEnabled();
    await user.click(save());
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0]).toEqual([
      { code: "ORDER_LATE", active: true, severity: null, low: 5, medium: 12, high: 15, critical: null },
      { code: "OTIF_RATE", active: false, severity: null, low: 97.5, medium: 90, high: 85, critical: 80 },
      { code: "FORECAST_UNMET", active: true, severity: "Orta", low: null, medium: null, high: null, critical: null },
      { code: "MAT_EXCESS", active: true, severity: null, low: 100, medium: 125, high: 150, critical: null },               // öteki kategoriler kayıtlı hâliyle
      { code: "CAP_OVERLOAD", active: true, severity: null, low: null, medium: 100, high: 110, critical: 125 },
      { code: "CAP_LOW_LOAD", active: false, severity: null, low: 40, medium: 20, high: null, critical: null },
      { code: "PLAN_RELAXED", active: true, severity: "Yüksek", low: null, medium: null, high: null, critical: null }]);
    await waitFor(() => expect(save()).toBeDisabled());                                                                     // kaydedildi: taslak kalmadı
    expect(cell(table, "Gecikme", "Orta")).not.toHaveClass("is-draft");
    await user.click(within(menu()).getByRole("button", { name: "Kapasite" }));                                             // kayıt sonrası geçişte uyarı yok
    expect(await tableOf("Kapasite")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("kademe sırası yöne göre: bozuksa hücre kırmızı, nedeni ipucunda, Kaydet pasif; Vazgeç geri alır", async () => {
    const { user, table } = await open();
    await write(user, table, "Gecikme", "Yüksek", "8");                                                                      // aşınca: Yüksek, Orta'dan (10) büyük olmalı
    expect(cell(table, "Gecikme", "Yüksek")).toHaveClass("is-invalid");
    expect(cell(table, "Gecikme", "Yüksek")).toHaveAttribute("title", "Yüksek eşiği Orta eşiğinden büyük olmalı.");
    expect(save()).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Vazgeç" }));
    expect(cell(table, "Gecikme", "Yüksek")).toHaveTextContent("15");
    await write(user, table, "OTIF oranı", "Orta", "96");                                                                    // altında: Orta, Düşük'ten (95) küçük olmalı
    expect(cell(table, "OTIF oranı", "Orta")).toHaveAttribute("title", "Orta eşiği Düşük eşiğinden küçük olmalı.");
    await write(user, table, "OTIF oranı", "Orta", "95");                                                                    // eşit de olmaz
    expect(cell(table, "OTIF oranı", "Orta")).toHaveClass("is-invalid");
    await write(user, table, "OTIF oranı", "Orta", "");                                                                      // boş kademe atlanır: Yüksek (85) < Düşük (95)
    expect(table.querySelector("td.is-invalid")).toBeNull();
    await write(user, table, "Gecikme", "Düşük", "2,5");                                                                     // gün tam sayı
    expect(cell(table, "Gecikme", "Düşük")).toHaveAttribute("title", "Tam sayı girilmeli.");
    await write(user, table, "Gecikme", "Düşük", "5");
    await write(user, table, "OTIF oranı", "Kritik", "79,125");                                                              // yüzde en çok iki ondalık
    expect(cell(table, "OTIF oranı", "Kritik")).toHaveAttribute("title", "En çok 2 ondalıklı sayı girilmeli.");
    await write(user, table, "OTIF oranı", "Kritik", "abc");
    expect(cell(table, "OTIF oranı", "Kritik")).toHaveAttribute("title", "Sayı girilmeli.");
    await user.click(screen.getByRole("button", { name: "Vazgeç" }));
    for (const s of SEVERITIES) await write(user, table, "Gecikme", s, "");                                                  // aktif uyarıda hiç kademe kalmadı
    expect(cell(table, "Gecikme", "Aktif")).toHaveAttribute("title", "Aktif uyarıda en az bir kademe dolu olmalı.");
    expect(save()).toBeDisabled();
    await user.click(within(table).getByRole("switch", { name: "Gecikme aktif" }));                                           // kapalı uyarıda kademeler boş olabilir
    expect(save()).toBeEnabled();
  });

  it("sunucunun reddettiği hücre kırmızı ve taslak durur; kaydedilmemiş değişiklikle kategori değişirken uyarı, vazgeçince taslak atılır", async () => {
    const { user, sent, table } = await open("Talep", "Key user", () => ({ status: 422, body: { error: { code: "validation", message: "Girilen bilgiler geçersiz.", trace_id: "t",
      details: [{ field: "rows.1.medium", problem: "Orta eşiği Düşük eşiğinden büyük olmalı.", record: "Gecikme" }] } } }));
    await write(user, table, "Gecikme", "Orta", "12");
    await user.click(save());
    await waitFor(() => expect(sent).toHaveLength(1));
    await waitFor(() => expect(cell(table, "Gecikme", "Orta")).toHaveClass("is-invalid"));
    expect(cell(table, "Gecikme", "Orta")).toHaveAttribute("title", "Orta eşiği Düşük eşiğinden büyük olmalı.");
    expect(cell(table, "Gecikme", "Orta")).toHaveTextContent("12");                                                          // taslak durur
    expect(await screen.findByText(/Kaydedilmedi\. Gecikme: Orta eşiği/)).toBeInTheDocument();
    await user.click(within(menu()).getByRole("button", { name: "Kapasite" }));                                              // kaydedilmemiş değişiklikle kategori değişimi
    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveTextContent("Kaydedilmemiş");
    expect(screen.queryByRole("table", { name: "Uyarı eşikleri · Kapasite" })).toBeNull();                                   // onaylanmadan geçilmez: değişiklik kaybolmaz
    await user.click(within(dialog).getAllByRole("button").at(-1)!);
    expect(await tableOf("Kapasite")).toBeInTheDocument();
    await user.click(within(menu()).getByRole("button", { name: "Talep" }));
    expect(cell(await tableOf("Talep"), "Gecikme", "Orta")).toHaveTextContent("10");                                         // ayrılınca taslak atıldı
  });

  it("yazma yetkisi yoksa (fonksiyon 26 okuma) düzenleme işareti yok, seçim düğmesi ve anahtar pasif", async () => {
    const user = userEvent.setup();
    backend();
    const me = meAs("Key user");
    renderApp(PATH, { ...me, permissions: { ...me.permissions, "26": "read" } });
    const table = await tableOf("Talep");
    expect(table.querySelector(".sc-table-edit-mark")).toBeNull();
    await user.dblClick(cell(table, "Gecikme", "Orta"));
    expect(within(table).queryByRole("textbox")).toBeNull();
    expect(within(choice(table, "Karşılanmayan tahmin")).getAllByRole("radio").every((o) => (o as HTMLButtonElement).disabled)).toBe(true);
    expect(within(table).getByRole("switch", { name: "Gecikme aktif" })).toBeDisabled();
  });
});

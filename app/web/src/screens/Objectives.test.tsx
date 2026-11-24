// Parametreler › Hedefler (K-196; 7.14b): hedef listesi kullanıcının. Kolonlar (Grup, Hedef, Kapsam, Açıklama), kapsamda kalın kategori adı, grup
// rengi ve tablonun altında renk açıklaması; soluk yalnız kapalı satır; şeritte işlemler sekmelerin yanında, Vazgeç ve Kaydet yalnız değişiklik
// olunca; pencere (Grup ve Hedef aramalı seçim, boş seçenek yok; kapsam aramalı çoklu seçim, hepsi = tümü; kapsam almayan hedefte kapsam satırı yok;
// zorunlu alan eksikken pasif), Düzenle (satırın seçimleriyle), Hedefi sil (her satırda), Başlangıç düzenine getir; kaydedilmemiş değişiklik
// varken dördü pasif; kolon genişliği (Alanlar yok); boş liste.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { meAs, mockApi, renderApp } from "../test/helpers";

const PATH = "/parametre/parametreler?sekme=hedefler";
const SECTIONS = [{ key: "hedefler", title: "Hedefler", table: "objectives", subs: [] }];
const GROUPS: Record<string, string> = { talep: "Talep", malzeme: "Malzeme", kaynak: "Kaynak", diger: "Diğer" };
const LABELS: Record<string, string> = { DemandType: "Talep türü", PriorityGroup: "Öncelik grubu", MaterialLevel: "Malzeme seviyesi", MaterialGroup: "Malzeme grubu",
                                         ResourceType: "Kaynak grubu tipi" };
type Scope = Record<string, (string | number)[]>;
const R = (id: number, code: string, label: string, family: string, scope: Scope, seq: number | null, seconds: number | null, extra: object = {}) => {
  const parts = Object.entries(scope).map(([k, values]) => ({ label: LABELS[k], values }));
  return { id, code, label, family, group: GROUPS[family], scope, scope_parts: parts,
           scope_text: parts.length ? parts.map((p) => `${p.label}: ${p.values.join(", ")}`).join(" · ") : (family === "diger" ? "" : "Tümü"),
           description: null as string | null, seq, seconds, tolerance: seq === null ? null : 0, active: seq !== null, ...extra };
};
const ROWS = [
  R(1, "UNMET_DEMAND", "Karşılanmayan talep", "talep", { DemandType: ["Kesin sipariş", "Teklif"], PriorityGroup: [1, 2, 3] }, 1, 210, { description: "Öncelikliler önce" }),
  R(2, "UNMET_DEMAND", "Karşılanmayan talep", "talep", { DemandType: ["Kesin sipariş"] }, 2, 100),                    // 1. satırla örtüşür
  R(3, "SAFETY_STOCK", "Güvenlik stoğunun altı", "malzeme", {}, 3, 20),
  R(4, "OVERTIME", "Ek mesai", "kaynak", { ResourceType: ["İşçi"] }, 4, 20),
  R(5, "SUBCONTRACT", "Fason", "diger", {}, 5, 60),
  R(6, "UNMET_DEMAND", "Karşılanmayan talep", "talep", { DemandType: ["Teklif"] }, null, null),
];
const MANY = Array.from({ length: 40 }, (_, i) => `Grup ${String(i + 1).padStart(2, "0")}`);
const CATALOG = [
  { code: "UNMET_DEMAND", label: "Karşılanmayan talep", family: "talep", group: "Talep", axes: [
    { key: "DemandType", label: "Talep türü", values: ["Kesin sipariş", "Teklif", "Beklemedeki sipariş", "Tahmin"], open: false },
    { key: "PriorityGroup", label: "Öncelik grubu", values: [1, 2, 3, 4, 5], open: false }] },
  { code: "LATENESS", label: "Gecikme", family: "talep", group: "Talep", axes: [
    { key: "DemandType", label: "Talep türü", values: ["Kesin sipariş", "Teklif", "Beklemedeki sipariş", "Tahmin"], open: false },
    { key: "PriorityGroup", label: "Öncelik grubu", values: [1, 2, 3, 4, 5], open: false }] },
  { code: "SAFETY_STOCK", label: "Güvenlik stoğunun altı", family: "malzeme", group: "Malzeme", axes: [
    { key: "MaterialLevel", label: "Malzeme seviyesi", values: ["Hammadde", "Yarı mamul", "Nihai ürün"], open: false },
    { key: "MaterialGroup", label: "Malzeme grubu", values: MANY, open: true }] },
  { code: "OVERTIME", label: "Ek mesai", family: "kaynak", group: "Kaynak", axes: [{ key: "ResourceType", label: "Kaynak grubu tipi", values: ["İşçi", "Makine", "Diğer"], open: false }] },
  { code: "SUBCONTRACT", label: "Fason", family: "diger", group: "Diğer", axes: [] },
];
type Call = { method: string; url: string; body: Record<string, unknown> };

function backend(rows = ROWS) {
  const calls: Call[] = [];
  const data = (list = rows) => ({ body: { rows: list, total_seconds: list.reduce((n, r) => n + (r.seconds ?? 0), 0), catalog: CATALOG } });
  const record = (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    calls.push({ method: init?.method ?? "GET", url, body });
    return body as Record<string, unknown>;
  };
  mockApi({
    "/api/scenarios/current": { body: { id: 1, name: "Baz", is_base: true, is_active: true } },
    "/api/parameters/objectives/reset": (url: string, init?: RequestInit) => { record(url, init); return data(rows.slice(0, 3)); },
    "/api/parameters/objectives/": (url: string, init?: RequestInit) => {
      const body = record(url, init);
      const id = Number(/objectives\/(\d+)/.exec(url)?.[1]);
      if (init?.method === "DELETE") return data(rows.filter((r) => r.id !== id));
      return data(rows.map((r) => (r.id === id ? { ...r, description: body.description as string | null } : r)));
    },
    "/api/parameters/objectives": (url: string, init?: RequestInit) => {
      if (!init?.method || init.method === "GET") return data();
      const body = record(url, init);
      if (init.method === "PUT") return data();
      return data([...rows.slice(0, 5), R(9, String(body.code), "Güvenlik stoğunun altı", "malzeme", body.scope as Scope, 6, Number(body.seconds)), ...rows.slice(5)]);
    },
    "/api/parameters": { body: { scenario: { id: 1, name: "Baz" }, sections: SECTIONS, values: {}, computed: { fix_period_end: null } } },
  });
  return calls;
}

async function open(rows = ROWS) {
  const user = userEvent.setup();
  const calls = backend(rows);
  renderApp(PATH, meAs("Key user"));
  const table = await screen.findByRole("table", { name: "Hedefler" }, { timeout: 5000 });
  return { user, calls, table };
}
const bodyRows = (table: HTMLElement) => within(table).getAllByRole("row").slice(1, -1);
const texts = (table: HTMLElement, col: number) => bodyRows(table).map((r) => r.querySelectorAll("td")[col].textContent);
const heads = (table: HTMLElement) => within(table).getAllByRole("columnheader").map((h) => h.textContent?.replace("✎", ""));
const strip = () => document.querySelector(".sc-section-actions") as HTMLElement;
const button = (name: string) => screen.getByRole("button", { name });
const box = (dialog: HTMLElement, name: string) => within(dialog).getByRole("combobox", { name });
/** Aramalı seçimde (Grup, Hedef) seçeneği seçer; listenin seçeneklerini döner. */
async function choose(user: ReturnType<typeof userEvent.setup>, dialog: HTMLElement, name: string, option: string) {
  await user.click(box(dialog, name));
  const list = await screen.findByRole("listbox", { name });
  const options = within(list).getAllByRole("option").map((o) => o.textContent);
  await user.click(within(list).getByRole("option", { name: option }));
  return options;
}

beforeEach(() => localStorage.clear());

describe("Parametreler › Hedefler · hedef listesi kullanıcının (K-196, 7.14b)", () => {
  it("kolonlar Grup, Hedef, Kapsam, Açıklama; kapsamda kategori adı kalın; örtüşen satırlar olduğu gibi; grup rengi ve altta renk açıklaması; soluk yalnız kapalı satır", async () => {
    const { table } = await open();
    expect(heads(table)).toEqual(["Sıra", "Grup", "Hedef", "Kapsam", "Açıklama", "Süre bütçesi (sn)", "Ödün payı (%)", "Aktif", ""]);
    expect(texts(table, 1)).toEqual(["Talep", "Talep", "Malzeme", "Kaynak", "Diğer", "Talep"]);
    expect(texts(table, 3)).toEqual(["Talep türü: Kesin sipariş, Teklif · Öncelik grubu: 1, 2, 3", "Talep türü: Kesin sipariş", "Tümü", "Kaynak grubu tipi: İşçi", "", "Talep türü: Teklif"]);
    expect([...bodyRows(table)[0].querySelectorAll("td")[3].querySelectorAll("b")].map((b) => b.textContent)).toEqual(["Talep türü:", "Öncelik grubu:"]);
    expect(texts(table, 4)[0]).toBe("Öncelikliler önce");
    expect(bodyRows(table).map((r) => r.className.match(/sc-objective--(\w+)/)?.[1])).toEqual(["talep", "talep", "malzeme", "kaynak", "diger", "talep"]);
    expect(bodyRows(table).map((r) => r.classList.contains("is-off"))).toEqual([false, false, false, false, false, true]);   // soluk: yalnız kapalı satır
    expect(table.querySelector(".is-dimmed")).toBeNull();
    const legend = screen.getByRole("list", { name: "Grup renkleri" });
    expect(within(legend).getAllByRole("listitem").map((l) => l.textContent)).toEqual(["Talep", "Malzeme", "Kaynak", "Diğer"]);
    expect(table.compareDocumentPosition(legend) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();       // renk açıklaması tablonun altında
    expect(within(table).getAllByRole("row").at(-1)).toHaveTextContent("Toplam6 hedef410");
    expect(within(table).queryByRole("button", { name: /sırala/i })).toBeNull();                         // kolon başlığından sıralama yok
    expect(screen.queryByRole("button", { name: /Alanlar/ })).toBeNull();                                // Alanlar düğmesi yok
  });

  it("şeritte işlemler sekmelerin hemen yanında; Vazgeç ve Kaydet yalnız değişiklik olunca, sağda", async () => {
    const { user, table } = await open();
    expect(within(strip()).getAllByRole("button").map((b) => b.textContent)).toEqual(["Başlangıç düzenine getir", "Yeni hedef tanımla"]);
    expect(strip().previousElementSibling?.querySelector("[role='radiogroup']") ?? strip().previousElementSibling).not.toBeNull();   // sekmelerin yanında
    expect(strip().closest(".sc-section-switch")).not.toBeNull();
    expect(screen.queryByRole("button", { name: "Vazgeç" })).toBeNull();                                 // değişiklik yokken görünmez (K-132)
    expect(screen.queryByRole("button", { name: "Kaydet" })).toBeNull();
    await user.click(within(table).getByRole("switch", { name: "Ek mesai · Kaynak grubu tipi: İşçi aktif" }));
    expect(button("Vazgeç").closest(".sc-section-actions-end")).not.toBeNull();
    expect(button("Kaydet")).toBeEnabled();
    expect(button("Yeni hedef tanımla")).toBeDisabled();                                                 // kaydedilmemiş değişiklik varken işlemler pasif
    expect(button("Başlangıç düzenine getir")).toBeDisabled();
    await user.click(within(bodyRows(table)[0]).getByRole("button", { name: /işlemleri$/ }));
    expect(await screen.findByRole("menuitem", { name: "Düzenle" })).toBeDisabled();
    expect(screen.getByRole("menuitem", { name: "Hedefi sil" })).toBeDisabled();
    await user.keyboard("{Escape}");
    await user.click(button("Vazgeç"));
    expect(screen.queryByRole("button", { name: "Kaydet" })).toBeNull();
    expect(button("Yeni hedef tanımla")).toBeEnabled();
  });

  it("Yeni hedef tanımla: Grup ve Hedef aramalı seçim (boş seçenek yok); kapsam aramalı çoklu seçim; kapsamsız hedefte kapsam satırı yok; zorunlu alan eksikken pasif", async () => {
    const { user, calls, table } = await open();
    await user.click(button("Yeni hedef tanımla"));
    const dialog = await screen.findByRole("dialog", { name: "Yeni hedef tanımla" });
    const labels = () => [...dialog.querySelectorAll("label.sc-field-label")].map((l) => l.textContent);
    expect(labels()).toEqual(["Grup", "Hedef", "Açıklama", "Süre bütçesi", "Ödün payı"]);              // kapsam hedefe göre
    expect(dialog.querySelector("select")).toBeNull();                                                   // tarayıcının açılır kutusu yok
    expect(box(dialog, "Grup")).toHaveValue("");                                                         // seçilmeden önce boş
    expect(box(dialog, "Hedef")).toBeDisabled();                                                         // önce grup
    expect(within(dialog).queryByText("Bugünkü satır")).toBeNull();
    expect(await choose(user, dialog, "Grup", "Diğer")).toEqual(["Talep", "Malzeme", "Kaynak", "Diğer"]);   // boş seçenek yok
    expect(await choose(user, dialog, "Hedef", "Fason")).toEqual(["Fason"]);                             // gruba göre süzülür
    expect(labels()).toEqual(["Grup", "Hedef", "Açıklama", "Süre bütçesi", "Ödün payı"]);              // kapsam almayan hedefte kapsam satırı yok
    await choose(user, dialog, "Grup", "Malzeme");
    expect(box(dialog, "Hedef")).toHaveValue("");                                                        // grup değişince hedef temizlenir
    await choose(user, dialog, "Hedef", "Güvenlik stoğunun altı");
    expect(labels()).toEqual(["Grup", "Hedef", "Malzeme seviyesi", "Malzeme grubu", "Açıklama", "Süre bütçesi", "Ödün payı"]);
    // hepsini seçmek ile hiç seçmemek aynı: kutuda "Tümü", kapsama yazılmaz
    const levels = box(dialog, "Malzeme seviyesi");
    await user.click(levels);
    const levelList = await screen.findByRole("listbox", { name: "Malzeme seviyesi" });
    for (const name of ["Hammadde", "Yarı mamul", "Nihai ürün"]) await user.click(within(levelList).getByRole("option", { name }));
    await user.keyboard("{Escape}");
    expect(levels).toHaveAttribute("placeholder", "Tümü");
    const groups = box(dialog, "Malzeme grubu");
    expect(groups).toHaveAttribute("placeholder", "Tümü");                                               // seçim yok: tümü
    await user.click(groups);
    const list = await screen.findByRole("listbox", { name: "Malzeme grubu" });
    expect(within(list).getAllByRole("option")).toHaveLength(40);                                        // çok sayıda grup: kaydırılan liste
    await user.type(groups, "grup 3");
    expect(within(list).getAllByRole("option").map((o) => o.textContent)).toEqual(["Grup 30", "Grup 31", "Grup 32", "Grup 33", "Grup 34", "Grup 35", "Grup 36", "Grup 37",
                                                                                 "Grup 38", "Grup 39"]);                 // yazdıkça süzülür
    await user.click(within(list).getByRole("option", { name: "Grup 31" }));
    await user.clear(groups);
    await user.type(groups, "03");
    await user.click(within(list).getByRole("option", { name: "Grup 03" }));
    await user.clear(groups);
    expect(within(list).getByRole("option", { name: "Grup 31" })).toHaveAttribute("aria-selected", "true");   // liste açık kalır
    await user.keyboard("{Escape}");                                                                     // Esc önce listeyi kapatır, pencereyi değil
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(screen.getByRole("dialog", { name: "Yeni hedef tanımla" })).toBeInTheDocument();
    await user.tab();
    expect(groups).toHaveValue("Grup 03, Grup 31");                                                      // eksenin sırasıyla
    const submit = within(dialog).getByRole("button", { name: "Tanımla" });
    expect(submit).toBeDisabled();                                                                       // süre ve ödün payı zorunlu, varsayılan yok
    await user.type(within(dialog).getByRole("textbox", { name: "Açıklama" }), "Kritik gruplar");
    await user.type(within(dialog).getByRole("textbox", { name: "Süre bütçesi" }), "45");
    expect(submit).toBeDisabled();
    expect(dialog.querySelector(".sc-field-error")).toBeNull();                                          // mesaj gösterilmez
    await user.type(within(dialog).getByRole("textbox", { name: "Ödün payı" }), "2,5");
    expect(submit).toBeEnabled();
    await user.click(submit);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const sent = calls.filter((c) => c.method === "POST");
    expect(sent).toHaveLength(1);
    expect(sent[0].url).toContain("/api/parameters/objectives?scenario_id=1");
    expect(sent[0].body).toEqual({ code: "SAFETY_STOCK", scope: { MaterialGroup: ["Grup 03", "Grup 31"] }, description: "Kritik gruplar", seconds: 45, tolerance: 2.5 });
    expect(texts(table, 3)[5]).toBe("Malzeme grubu: Grup 03, Grup 31");                                  // yalnız seçilen kategori yazar
  });

  it("Düzenle satırın seçimleriyle açılır; Kaydet gönderir. Kapalı satırda süre ve ödün payı pasif", async () => {
    const { user, calls, table } = await open();
    await user.click(within(bodyRows(table)[0]).getByRole("button", { name: /işlemleri$/ }));
    await user.click(await screen.findByRole("menuitem", { name: "Düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Düzenle" });
    expect(box(dialog, "Grup")).toHaveValue("Talep");
    expect(box(dialog, "Hedef")).toHaveValue("Karşılanmayan talep");
    expect(box(dialog, "Talep türü")).toHaveValue("Kesin sipariş, Teklif");
    expect(box(dialog, "Öncelik grubu")).toHaveValue("1, 2, 3");
    expect(within(dialog).getByRole("textbox", { name: "Açıklama" })).toHaveValue("Öncelikliler önce");
    expect(within(dialog).getByRole("textbox", { name: "Süre bütçesi" })).toHaveValue("210");
    await user.click(box(dialog, "Öncelik grubu"));
    await user.click(within(await screen.findByRole("listbox", { name: "Öncelik grubu" })).getByRole("option", { name: "3" }));   // seçili: kaldırılır
    await user.keyboard("{Escape}");
    await user.clear(within(dialog).getByRole("textbox", { name: "Açıklama" }));
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    const sent = calls.filter((c) => c.method === "PUT" && c.url.includes("/objectives/1?"));
    expect(sent).toHaveLength(1);
    expect(sent[0].body).toEqual({ code: "UNMET_DEMAND", scope: { DemandType: ["Kesin sipariş", "Teklif"], PriorityGroup: [1, 2] }, description: null, seconds: 210, tolerance: 0 });
    await user.click(within(bodyRows(table)[5]).getByRole("button", { name: /işlemleri$/ }));            // kapalı satır
    await user.click(await screen.findByRole("menuitem", { name: "Düzenle" }));
    const closed = await screen.findByRole("dialog", { name: "Düzenle" });
    expect(within(closed).getByRole("textbox", { name: "Süre bütçesi" })).toBeDisabled();
    expect(within(closed).getByRole("button", { name: "Kaydet" })).toBeEnabled();
  });

  it("Hedefi sil her satırda (kapsamsız satırda da); Başlangıç düzenine getir onaylı", async () => {
    const { user, calls, table } = await open();
    expect(bodyRows(table).every((r) => within(r).queryByRole("button", { name: /işlemleri$/ }) !== null)).toBe(true);   // silinemeyen satır yok
    await user.click(within(bodyRows(table)[4]).getByRole("button", { name: "Fason işlemleri" }));
    await user.click(await screen.findByRole("menuitem", { name: "Hedefi sil" }));
    const confirm = await screen.findByRole("dialog", { name: "Hedefi sil" });
    expect(confirm).toHaveTextContent("Fason silinir.");
    await user.click(within(confirm).getByRole("button", { name: "Hedefi sil" }));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE" && c.url.includes("/api/parameters/objectives/5?scenario_id=1"))).toBe(true));
    await waitFor(() => expect(bodyRows(table)).toHaveLength(5));
    await user.click(button("Başlangıç düzenine getir"));
    const reset = await screen.findByRole("dialog", { name: "Başlangıç düzenine getir" });
    await user.click(within(reset).getByRole("button", { name: "Başlangıç düzenine getir" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.url.includes("/objectives/reset"))).toBe(true));
    await waitFor(() => expect(bodyRows(table)).toHaveLength(3));
  });

  it("kolon genişliği ayarlanır ve saklanır", async () => {
    const { table } = await open();
    const handle = within(table).getByRole("separator", { name: "Hedef genişliği" });
    handle.focus();
    fireEvent.keyDown(handle, { key: "ArrowRight" });
    const saved = JSON.parse(localStorage.getItem("sc.objectives.columns")!) as { widths: Record<string, number> };
    expect(Object.keys(saved.widths)).toEqual(["label"]);
    expect(within(table).queryByRole("separator", { name: " genişliği" })).toBeNull();
  });

  it("boş liste: tablo başlığı ve toplam; işlemler çalışır", async () => {
    const { table } = await open([]);
    expect(bodyRows(table)).toHaveLength(0);
    expect(within(table).getAllByRole("row").at(-1)).toHaveTextContent("Toplam0 hedef0");
    expect(button("Yeni hedef tanımla")).toBeEnabled();
    expect(screen.queryByText("En az bir hedef aktif olmalı.")).toBeNull();
  });
});

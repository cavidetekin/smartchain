// Üretim akışı (K-200): satır menüsünden açılır (Malzeme ve Alokasyon kuralı; başka tabloda yok), kapalı açılır, + aç ve kapat, yaprakta + yok,
// alternatif kutuları, okta miktar, seviyeye göre renk (hayalet gri), "veya G1" etiketi, benzetilen notu başlığın altında, "Tümünü kapat",
// çift tıklama, "+N malzeme" (20 ve 200'er), hata ve yeniden deneme, yakınlaştırma, PNG indirme (izi yazılır), renk açıklaması, Esc, End user.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

// Görsel tarayıcıda tuvalde çizilir (jsdom'da tuval yok): çizim yerine çağrı kaydedilir
const images: { nodes: string[]; options: { title: string; note?: string; legend: { label: string; tone: string }[] } }[] = [];
vi.mock("../ui/flow/flowImage", () => ({
  flowPng: vi.fn(async (layout: { nodes: { node: { title: string } }[] }, options: { title: string; note?: string; legend: { label: string; tone: string }[] }) => {
    images.push({ nodes: layout.nodes.map((n) => n.node.title), options });
    return new Blob(["png"], { type: "image/png" });
  }),
}));

import { genitive } from "../i18n/tr";
import { col, useTableTestSetup } from "../table/testBackend";
import { meAs, mockApi, renderApp, type Reply, type Routes } from "../test/helpers";
import { parentEdge, quantityText, toneOf } from "./ProductionFlow";
import type { FlowMaterial, FlowParent } from "./productionFlowApi";

useTableTestSetup();

const EXPORT = { title: "x", file_slug: "x", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const mat = (id: number, code: string, level: string, up: boolean, down: boolean, extra: Partial<FlowMaterial> = {}): FlowMaterial =>
  ({ id, code, name: `${code} adı`, level, phantom: false, has_parents: up, has_components: down, ...extra });
const M = {
  top: mat(1, "MAM-006", "Nihai ürün", false, true), alt: mat(2, "ALT-017", "Yarı mamul", true, true), raw: mat(3, "HAM-008", "Hammadde", true, false),
  sat: mat(4, "SAT-001", "Hammadde", true, false), ghost: mat(5, "HYL-001", "Yarı mamul", true, false, { phantom: true }), ref: mat(6, "MAM-011", "Nihai ürün", false, true),
  wide: mat(7, "GEN-001", "Nihai ürün", false, true), bolt: mat(8, "CIV-008", "Hammadde", true, false),
};
const item = (m: FlowMaterial, quantity: number, uom = "ADET", group: string | null = null) => ({ material: m, quantity, uom, group, group_priority: group ? 1 : null });
const COMPONENTS: Record<number, unknown> = {
  1: { reference: null, alternatives: [{ no: 1, versions: ["V1"], bom_code: "B-MAM-006", items: [item(M.alt, 1), item(M.raw, 0.4, "KG"), item(M.ghost, 2, "ADET", "G1")] }] },
  2: { reference: null, alternatives: [{ no: 1, versions: ["V1", "V3"], bom_code: "B1", items: [item(M.raw, 2)] }, { no: 2, versions: ["V2"], bom_code: "B2", items: [item(M.raw, 2), item(M.sat, 1)] }] },
  6: { reference: { code: "MAM-001" }, alternatives: [{ no: 1, versions: ["V1"], bom_code: "B-MAM-001", items: [item(M.raw, 3)] }] },
  7: { reference: null, alternatives: [{ no: 1, versions: ["V1"], bom_code: "BW", items: Array.from({ length: 25 }, (_, i) => item(mat(100 + i, `BLS-${String(i + 1).padStart(3, "0")}`, "Hammadde", true, false), i + 1)) }] },
};
const users = (n: number): FlowParent[] => Array.from({ length: n }, (_, i) => ({ material: mat(1000 + i, `KUL-${String(i + 1).padStart(4, "0")}`, "Yarı mamul", false, true), alternatives: 1,
                                                                                 uses: [{ alternative: 1, quantity: 4, uom: "ADET", group: null }] }));
const PARENTS: Record<number, FlowParent[]> = {
  3: [{ material: M.alt, alternatives: 2, uses: [{ alternative: 1, quantity: 2, uom: "ADET", group: null }, { alternative: 2, quantity: 2, uom: "ADET", group: null }] },
      { material: M.top, alternatives: 1, uses: [{ alternative: 1, quantity: 0.4, uom: "KG", group: null }] }],
  8: users(245),
};
const ROWS: Record<string, object[]> = {
  materials: [{ Id: 1, Code: "MAM-006", Name: "Pompa" }, { Id: 3, Code: "HAM-008", Name: "Sac" }, { Id: 6, Code: "MAM-011", Name: "Benzetilen" },
              { Id: 7, Code: "GEN-001", Name: "Geniş" }, { Id: 8, Code: "CIV-008", Name: "Cıvata" }],
  "master-allocation-rule": [{ Id: 90, MaterialId: 2, MaterialCode: "ALT-017", AllocationKey: "PRJ-01" }],
  "master-material-reference": [{ Id: 70, MaterialCode: "MAM-011" }],
};
const COLUMNS: Record<string, unknown[]> = {
  materials: [col("Code", "Malzeme kodu", "text", "text"), col("Name", "Malzeme adı", "text", "text")],
  "master-allocation-rule": [col("MaterialCode", "Malzeme", "text", "text"), col("AllocationKey", "Alokasyon anahtarı", "text", "text")],
  "master-material-reference": [col("MaterialCode", "Malzeme kodu", "text", "text")],
};

const calls: string[] = [];
let failOnce = false;
let logFails = false;
const saved: string[] = [];

function backend() {
  calls.length = 0;
  images.length = 0;
  saved.length = 0;
  failOnce = false;
  logFails = false;
  // indirme: saveBlob geçici bir bağlantıya tıklar; dosya adı oradan okunur
  Object.assign(URL, { createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function click(this: HTMLAnchorElement) { if (this.download) saved.push(this.download); });
  const routes: Routes = {
    "/api/master-data/counts": { body: { data_version: 35, tabs: [{ key: "malzeme", tables: Object.keys(ROWS).map((list) => ({ list, label: list, count: ROWS[list].length })) }] } },
    "/api/production-flow/": (url): Reply => {
      calls.push(url.replace("/api/production-flow/", ""));
      const [, id, rest] = url.match(/production-flow\/(\d+)(.*)$/)!;
      const all = Object.values(M).find((m) => m.id === Number(id));
      if (rest.startsWith("/export-log")) return logFails ? { status: 503, body: { error: { code: "audit_failed", message: "İşlem yapılamadı: denetim kaydı yazılamadı.", trace_id: "t", details: [] } } }
                                                          : { body: { file_name: `uretim-akisi-${all?.code}.png` } };
      if (rest.startsWith("/components")) {
        if (failOnce) { failOnce = false; return { status: 500, body: { error: { code: "internal", message: "Sunucu hatası.", trace_id: "t", details: [] } } }; }
        return { body: COMPONENTS[Number(id)] };
      }
      if (rest.startsWith("/parents")) {
        const q = new URLSearchParams(rest.split("?")[1]);
        const list = PARENTS[Number(id)] ?? [];
        return { body: { total: list.length, items: list.slice(Number(q.get("offset")), Number(q.get("offset")) + Number(q.get("limit"))) } };
      }
      return all ? { body: { material: all, location: "IST01", reference: Number(id) === 6 ? { code: "MAM-001" } : null } } : { status: 404, body: { error: { code: "not_found", message: "yok", trace_id: "t", details: [] } } };
    },
  };
  for (const list of Object.keys(ROWS)) {
    routes[`/api/${list}/columns`] = { body: { chunk_size: 100, columns: COLUMNS[list], export: EXPORT } };
    routes[`/api/${list}/views`] = { body: { views: [], default_view_id: null } };
    routes[`/api/${list}/query`] = { body: { rows: ROWS[list], filtered: ROWS[list].length, total: ROWS[list].length } };
  }
  return mockApi(routes);
}

async function openFlow(code: string, table = "malzeme", role = "Key user") {
  const user = userEvent.setup();
  backend();
  renderApp(`/veri/ana-veri?sekme=malzeme&tablo=${table}`, meAs(role));
  await screen.findByRole("heading", { level: 1, name: "Ana veri" }, { timeout: 5000 });
  await user.click(await screen.findByRole("button", { name: `${code} işlemleri` }));
  await user.click(await screen.findByRole("menuitem", { name: "Üretim akışı" }));
  const dialog = await screen.findByRole("dialog", { name: "Üretim akışı" });
  await within(dialog).findByRole("group", { name: "Üretim akışı" });
  return { user, dialog };
}

const boxes = (dialog: HTMLElement) => [...dialog.querySelectorAll<SVGGElement>("g.sc-flow-node")];
const codes = (dialog: HTMLElement) => boxes(dialog).map((g) => g.querySelector("text")!.textContent);
const node = (dialog: HTMLElement, text: string) => boxes(dialog).find((g) => g.querySelector("text")!.textContent === text)!;
const toggle = (dialog: HTMLElement, name: string) => within(dialog).getByRole("button", { name });
/** Okun yazısı: üst satır (miktar) ve varsa alt satır (alternatif, grup). */
const labels = (dialog: HTMLElement) => [...dialog.querySelectorAll("g[data-edge-label]")].map((g) => [...g.querySelectorAll("text")].map((t) => t.textContent).join(" · "));

describe("Üretim akışı", () => {
  it("satır menüsünde Detay'dan sonra; pencere kapalı açılır: yalnız seçili malzeme, alt başlıkta kod, ad ve lokasyon", async () => {
    const user = userEvent.setup();
    backend();
    renderApp("/veri/ana-veri?sekme=malzeme&tablo=malzeme", meAs("Key user"));
    await user.click(await screen.findByRole("button", { name: "MAM-006 işlemleri" }, { timeout: 5000 }));
    expect(within(screen.getByRole("menu")).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Detay", "Üretim akışı"]);
    await user.click(screen.getByRole("menuitem", { name: "Üretim akışı" }));
    const dialog = await screen.findByRole("dialog", { name: "Üretim akışı" });
    await within(dialog).findByRole("group", { name: "Üretim akışı" });
    expect(within(dialog).getByText("MAM-006 · MAM-006 adı · Lokasyon IST01")).toBeInTheDocument();
    expect(codes(dialog)).toEqual(["MAM-006"]);
    expect(node(dialog, "MAM-006")).toHaveClass("is-current");
    expect(node(dialog, "MAM-006").textContent).toContain("Nihai ürün");
    // kullananı yok: sol + yok; alt malzemesi var: sağ + var
    expect(within(dialog).queryByRole("button", { name: "MAM-006 kullananlarını aç" })).toBeNull();
    expect(toggle(dialog, "MAM-006 kullandıklarını aç")).toHaveAttribute("aria-expanded", "false");
    expect(within(dialog).getByRole("button", { name: "Tümünü kapat" })).toBeDisabled();
    expect(calls).toEqual(["1"]);                          // ağaç baştan yüklenmez
    expect(window.location.search).not.toContain("akis");
    expect(within(dialog).queryByRole("button", { name: "Vazgeç" })).toBeNull();   // salt okunur: yalnız Kapat
    // alt satır: renk açıklaması (yalnız renkler, bu sırayla) ve Kapat aynı satırda
    const key = within(dialog).getByRole("list", { name: "Renkler" });
    expect(within(key).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["Seçili malzeme", "Nihai ürün", "Yarı mamul", "Hammadde", "Hayalet", "Alternatif"]);
    expect(key.parentElement).toBe(within(dialog).getByRole("button", { name: "Kapat" }).parentElement);
    expect(dialog.textContent).not.toMatch(/Sol \+|Sağ \+|Okun üstü|Çift tıklama/);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("sağ + bir seviye açar: tek alternatifte malzemeler doğrudan; okta miktar ve birim, alternatif grubu, hayalet; yaprakta + yok; açık olana basınca kapanır", async () => {
    const { user, dialog } = await openFlow("MAM-006");
    await user.click(toggle(dialog, "MAM-006 kullandıklarını aç"));
    await waitFor(() => expect(codes(dialog)).toEqual(["MAM-006", "ALT-017", "HAM-008", "HYL-001"]));
    expect(labels(dialog)).toEqual(["×1 ADET", "×0,4 KG", "×2 ADET"]);                 // okta yalnız miktar
    expect(node(dialog, "HYL-001").textContent).toContain("Yarı mamul · Hayalet");
    // alternatif grubu üyesi: kutunun köşesinde nötr etiket; hayalet gri, ötekiler seviyesinin renginde, seçili nane
    expect(node(dialog, "HYL-001").querySelector(".sc-flow-badge text")).toHaveTextContent("veya G1");
    expect(node(dialog, "ALT-017").querySelector(".sc-flow-badge")).toBeNull();
    expect(["MAM-006", "ALT-017", "HAM-008", "HYL-001"].map((c) => node(dialog, c).dataset.tone)).toEqual(["current", "semi", "raw", "phantom"]);
    expect(within(dialog).queryByRole("button", { name: "HAM-008 kullandıklarını aç" })).toBeNull();
    expect(toggle(dialog, "ALT-017 kullandıklarını aç")).toBeInTheDocument();
    // üç bileşenin çizgisi ortak gövdede birleşir: kutunun önünde tek ok ucu
    expect(dialog.querySelectorAll("path.sc-flow-edge")).toHaveLength(4);
    expect([...dialog.querySelectorAll("path.sc-flow-edge[marker-end]")].map((p) => p.getAttribute("data-edge"))).toEqual(["d:stem:right"]);
    await user.click(toggle(dialog, "MAM-006 kullandıklarını kapat"));
    expect(codes(dialog)).toEqual(["MAM-006"]);
    await user.click(toggle(dialog, "MAM-006 kullandıklarını aç"));
    expect(codes(dialog)).toHaveLength(4);
    expect(calls.filter((c) => c === "1/components")).toHaveLength(1);       // kapatılıp açılan dal yeniden istenmez
  });

  it("birden çok ürün ağacı: önce Alternatif kutuları (kapalı, versiyon kodlarıyla); basılanın malzemeleri açılır; aynı malzeme iki yolda iki kutu", async () => {
    const { user, dialog } = await openFlow("ALT-017", "alokasyon-kurali");   // Alokasyon kuralı satırından, satırın malzemesiyle
    expect(calls).toEqual(["2"]);
    await user.click(toggle(dialog, "ALT-017 kullandıklarını aç"));
    await waitFor(() => expect(codes(dialog)).toEqual(["ALT-017", "Alternatif 1", "Alternatif 2"]));
    expect(node(dialog, "Alternatif 1").textContent).toContain("V1, V3");
    await user.click(node(dialog, "Alternatif 2"));                           // kutuya basmak da açar
    expect(codes(dialog)).toEqual(["ALT-017", "Alternatif 1", "Alternatif 2", "HAM-008", "SAT-001"]);
    await user.click(toggle(dialog, "Alternatif 1 malzemelerini aç"));
    expect(codes(dialog).filter((c) => c === "HAM-008")).toHaveLength(2);
    await user.click(within(dialog).getByRole("button", { name: "Tümünü kapat" }));
    expect(codes(dialog)).toEqual(["ALT-017"]);
  });

  it("sol + kullananları açar; üst malzemenin birden çok alternatifi varsa okta yazar; çift tıklama seçili malzemeyi değiştirir", async () => {
    const { user, dialog } = await openFlow("HAM-008");
    expect(within(dialog).queryByRole("button", { name: "HAM-008 kullandıklarını aç" })).toBeNull();
    await user.click(toggle(dialog, "HAM-008 kullananlarını aç"));
    await waitFor(() => expect(codes(dialog)).toEqual(["HAM-008", "ALT-017", "MAM-006"]));
    expect(labels(dialog)).toEqual(["×2 ADET · Alternatif 1, 2", "×0,4 KG"]);
    expect(dialog.querySelectorAll("path.sc-flow-edge[marker-end]")).toHaveLength(2);       // her kullanana kendi ok ucu
    expect(node(dialog, "MAM-006").dataset.tone).toBe("final");
    expect(calls).toContain("3/parents?offset=0&limit=20");
    await user.dblClick(node(dialog, "ALT-017"));
    await waitFor(() => expect(within(dialog).getByText("ALT-017 · ALT-017 adı · Lokasyon IST01")).toBeInTheDocument());
    expect(codes(dialog)).toEqual(["ALT-017"]);
    expect(node(dialog, "ALT-017")).toHaveClass("is-current");
  });

  it("benzetilen ürün: not yalnız seçili malzemede, başlığın altında kalın; çizimin içinde yazı yok", async () => {
    const { user, dialog } = await openFlow("MAM-011");
    const note = within(dialog).getByText("MAM-001'in ağacı (benzetilen)");
    expect(note.tagName).toBe("STRONG");
    expect(note.closest(".sc-dialog-subtitle")).not.toBeNull();
    await user.click(toggle(dialog, "MAM-011 kullandıklarını aç"));
    await waitFor(() => expect(codes(dialog)).toEqual(["MAM-011", "HAM-008"]));
    expect(dialog.querySelector("svg[aria-label='Üretim akışı']")!.textContent).not.toContain("benzetilen");
    await user.dblClick(node(dialog, "HAM-008"));                              // seçili malzeme benzetilen değil: not kalkar
    await waitFor(() => expect(node(dialog, "HAM-008")).toHaveClass("is-current"));
    expect(within(dialog).queryByText(/benzetilen/)).toBeNull();
  });

  it("yakınlaştırma: − · + · Sığdır · %100 (simge düğmeler, adlarıyla); adımlar ve sınırlar", async () => {
    const { user, dialog } = await openFlow("MAM-006");
    const zoom = () => within(dialog).getByTestId("flow-scroll").dataset.zoom;
    const btn = (name: string) => within(dialog).getByRole("button", { name });
    expect(zoom()).toBe("100");
    expect(btn("Normal boy (%100)")).toBeDisabled();
    await user.click(btn("Yakınlaştır"));
    expect(zoom()).toBe("125");
    expect(within(dialog).getByText("%125")).toBeInTheDocument();
    await user.click(btn("Normal boy (%100)"));
    expect(zoom()).toBe("100");
    for (let i = 0; i < 8; i += 1) await user.click(btn("Uzaklaştır"));
    expect(zoom()).toBe("25");
    expect(btn("Uzaklaştır")).toBeDisabled();
    await user.click(btn("Sığdır"));                                            // küçük çizim: en çok %100
    expect(zoom()).toBe("100");
    for (let i = 0; i < 8; i += 1) await user.click(btn("Yakınlaştır"));
    expect(zoom()).toBe("200");
    expect(btn("Yakınlaştır")).toBeDisabled();
    // Ctrl + tekerlek yakınlaştırır; Ctrl'siz tekerlek kaydırmadır
    fireEvent.wheel(within(dialog).getByTestId("flow-scroll"), { deltaY: 300, ctrlKey: true });
    await waitFor(() => expect(Number(zoom())).toBeLessThan(200));
    const after = zoom();
    fireEvent.wheel(within(dialog).getByTestId("flow-scroll"), { deltaY: 300 });
    expect(zoom()).toBe(after);
  });

  it("PNG indirme: açık çizimin tamamı, başlık satırı ve renk açıklamasıyla; izi yazılır, dosya adı malzeme koduyla", async () => {
    const { user, dialog } = await openFlow("MAM-011");
    await user.click(toggle(dialog, "MAM-011 kullandıklarını aç"));
    await waitFor(() => expect(codes(dialog)).toHaveLength(2));
    await user.click(within(dialog).getByRole("button", { name: "PNG olarak indir" }));
    await waitFor(() => expect(saved).toEqual(["uretim-akisi-MAM-011.png"]));
    expect(images).toHaveLength(1);
    expect(images[0].nodes).toEqual(["MAM-011", "HAM-008"]);
    expect(images[0].options.title).toBe("MAM-011 · MAM-011 adı · Lokasyon IST01");
    expect(images[0].options.note).toBe("MAM-001'in ağacı (benzetilen)");
    expect(images[0].options.legend.map((l) => l.label)).toEqual(["Seçili malzeme", "Nihai ürün", "Yarı mamul", "Hammadde", "Hayalet", "Alternatif"]);
    expect(calls.filter((c) => c.endsWith("/export-log"))).toEqual(["6/export-log"]);
  });

  it("PNG indirme: iz yazılamazsa dosya inmez", async () => {
    const { user, dialog } = await openFlow("MAM-006");
    logFails = true;
    await user.click(within(dialog).getByRole("button", { name: "PNG olarak indir" }));
    await waitFor(() => expect(calls).toContain("1/export-log"));
    await waitFor(() => expect(within(dialog).getByRole("button", { name: "PNG olarak indir" })).toBeEnabled());
    expect(saved).toEqual([]);
  });

  it("20'den çok kutu: ilk 20 ve \"+N malzeme\"; basınca kalanı açılır", async () => {
    const { user, dialog } = await openFlow("GEN-001");
    await user.click(toggle(dialog, "GEN-001 kullandıklarını aç"));
    await waitFor(() => expect(codes(dialog)).toHaveLength(22));
    expect(codes(dialog).at(-1)).toBe("+5 malzeme");
    expect(node(dialog, "+5 malzeme")).toHaveClass("sc-flow-node--more");
    await user.click(node(dialog, "+5 malzeme"));
    expect(codes(dialog)).toHaveLength(26);
    expect(codes(dialog).some((c) => c?.startsWith("+"))).toBe(false);
  });

  it("çok kullanılan malzeme: kalan 200'den çoksa 200'er açılır, sayfa sunucudan istenir", async () => {
    const { user, dialog } = await openFlow("CIV-008");
    await user.click(toggle(dialog, "CIV-008 kullananlarını aç"));
    await waitFor(() => expect(codes(dialog)).toHaveLength(22));
    expect(codes(dialog).at(-1)).toBe("+225 malzeme");
    await user.click(node(dialog, "+225 malzeme"));
    await waitFor(() => expect(codes(dialog).at(-1)).toBe("+25 malzeme"));
    expect(codes(dialog)).toHaveLength(222);
    expect(calls).toContain("8/parents?offset=20&limit=200");
    await user.click(node(dialog, "+25 malzeme"));
    await waitFor(() => expect(codes(dialog)).toHaveLength(246));
    expect(calls).toContain("8/parents?offset=220&limit=25");
  });

  it("dal yüklenemezse kısa hata; + yeniden basılınca yüklenir", async () => {
    const { user, dialog } = await openFlow("MAM-006");
    failOnce = true;
    await user.click(toggle(dialog, "MAM-006 kullandıklarını aç"));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Sunucu hatası.");
    expect(codes(dialog)).toEqual(["MAM-006"]);
    await user.click(toggle(dialog, "MAM-006 kullandıklarını aç"));
    await waitFor(() => expect(codes(dialog)).toHaveLength(4));
    expect(within(dialog).queryByRole("alert")).toBeNull();
  });

  it("klavye: işarette Enter açar, kutuda Enter seçili yapar", async () => {
    const { user, dialog } = await openFlow("MAM-006");
    toggle(dialog, "MAM-006 kullandıklarını aç").focus();
    await user.keyboard("{Enter}");
    await waitFor(() => expect(codes(dialog)).toHaveLength(4));
    expect(screen.getByRole("dialog", { name: "Üretim akışı" })).toBeInTheDocument();   // Enter pencereyi kapatmaz
    node(dialog, "ALT-017").focus();
    fireEvent.keyDown(node(dialog, "ALT-017"), { key: "Enter" });
    await waitFor(() => expect(node(dialog, "ALT-017")).toHaveClass("is-current"));
    expect(node(dialog, "ALT-017")).toHaveFocus();          // odak kaybolmaz: yeni seçili kutuda
  });

  it("yalnız Malzeme ve Alokasyon kuralı tablolarında: başka tabloda seçenek yok", async () => {
    const user = userEvent.setup();
    backend();
    renderApp("/veri/ana-veri?sekme=malzeme&tablo=benzetilen-urun", meAs("End user"));
    await user.click(await screen.findByRole("button", { name: "MAM-011 işlemleri" }, { timeout: 5000 }));
    expect(within(screen.getByRole("menu")).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Detay"]);
  });

  it("End user açar (görüntüleme)", async () => {
    const { dialog } = await openFlow("MAM-006", "malzeme", "End user");
    expect(codes(dialog)).toEqual(["MAM-006"]);
  });

  it("metinler: miktar Türkçe biçimde, alternatife göre değişen miktar ayrı ayrı, kodun tamlayan eki", () => {
    expect([quantityText(8, "AD"), quantityText(0.4, "KG"), quantityText(1234.5, null), quantityText(0.333333, "M")]).toEqual(["×8 AD", "×0,4 KG", "×1.234,5", "×0,333333 M"]);
    const p = (uses: [number, number][], alternatives: number): FlowParent => ({ material: M.alt, alternatives, uses: uses.map(([alternative, quantity]) => ({ alternative, quantity, uom: "AD", group: null })) });
    expect(parentEdge(p([[1, 2]], 1))).toEqual({ edge: "×2 AD" });
    expect([toneOf(M.top), toneOf(M.alt), toneOf(M.raw), toneOf(M.ghost), toneOf({ ...M.raw, level: null })]).toEqual(["final", "semi", "raw", "phantom", undefined]);
    expect(parentEdge(p([[2, 2]], 2))).toEqual({ edge: "×2 AD", edgeNote: "Alternatif 2" });
    expect(parentEdge(p([[1, 2], [2, 3]], 2))).toEqual({ edge: "×2 AD Alt. 1", edgeNote: "×3 AD Alt. 2" });
    expect(["MAM-001", "ALT-016", "ALT-017", "SAT-003", "PRC-040", "HAM-100", "ABC"].map(genitive)).toEqual(["in", "nın", "nin", "ün", "ın", "ün", ""]);
  });
});

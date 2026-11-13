// Detay kartı (K-171, K-173): "Detay ›" rozeti, satıra tıklamak yalnız seçer, kart açıkken kayıt değiştirme, ✕ / Esc, adres ve tercihte
// hatırlama, Geçmiş (kaynak ve biçim sunucudan), İlişkili kayıtlar (sayılar, boş ilişki pasif, ilişkili satırın rozeti o kaydın kartını açar),
// güncel veride olmayan kayıt, İşlem verisi'nde yalnız Geçmiş, End user; denetim izinde "Kayda git".
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { locative } from "../i18n/tr";
import { col, useTableTestSetup } from "../table/testBackend";
import { meAs, mockApi, renderApp, type Reply } from "../test/helpers";
import type { AuditDetail } from "./auditLogApi";
import { recordUrl } from "./dataScreenTabs";

useTableTestSetup();

const EXPORT = { title: "x", file_slug: "x", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const list = (columns: unknown[], rows: object[], sent?: { url: string; body: unknown }[]) => ({
  [`columns`]: { body: { chunk_size: 100, columns, export: EXPORT } },
  views: { body: { views: [], default_view_id: null } },
  query: (url: string, init?: RequestInit) => {
    sent?.push({ url, body: JSON.parse(String(init?.body)) });
    return { body: { rows, filtered: rows.length, total: rows.length } };
  },
});
function routesOf(name: string, l: ReturnType<typeof list>): Record<string, Reply | ((url: string, init?: RequestInit) => Reply)> {
  return { [`/api/${name}/columns`]: l.columns, [`/api/${name}/views`]: l.views, [`/api/${name}/query`]: l.query };
}

const CUSTOMER_COLS = [col("Code", "Müşteri kodu", "text", "text"), col("Name", "Müşteri adı", "text", "text")];
const CUSTOMERS = [{ Id: 1, Code: "MUS-A", Name: "Akdeniz", _sources: {} }, { Id: 2, Code: "MUS-B", Name: "Batı", _sources: {} }];
const HISTORY_COLS = [col("At", "Tarih", "datetime", "date"), col("DataVersion", "Veri", "text", "text"), col("FieldLabel", "Alan", "text", "list"),
                      col("OldValue", "Eski değer", "text", "text"), col("NewValue", "Yeni değer", "text", "text"), col("SourceText", "Kaynak", "text", "list")];
const HISTORY = [
  { Id: 9, At: "2026-11-12T07:14:00+00:00", DataVersion: "v64", FieldLabel: "Müşteri adı", OldValue: "Akdeniz Pompa", NewValue: "Akdeniz", SourceText: "Manuel değer · Ayşe Planlama" },
  { Id: 8, At: "2026-10-26T08:40:00+00:00", DataVersion: "v1", FieldLabel: "—", OldValue: null, NewValue: "Kayıt oluştu", SourceText: "Aktarım · Tam" },
];
const ORDER_COLS = [col("OrderNo", "Sipariş no", "text", "text"), col("LineNo", "Satır no", "integer", "number")];
const ORDERS = [{ Id: 11, OrderNo: "SO-1", LineNo: 1, _sources: {} }, { Id: 12, OrderNo: "SO-2", LineNo: 1, _sources: {} }];

const card = (id: number, extra: object = {}) => ({
  list: "master-customer", table: "Customer", id: String(id), code: id === 1 ? "MUS-A" : "MUS-B", name: id === 1 ? "Akdeniz" : "Batı",
  label: id === 1 ? "MUS-A · Akdeniz" : "MUS-B · Batı", current: true, closed_version: null,
  relations: [{ key: "sales-order", label: "Satış siparişi", list: "transaction-sales-order", count: 2, filters: [{ field: "Id", op: "in", values: ["11", "12"] }] },
              { key: "project", label: "Proje", list: "transaction-project", count: 0, filters: [{ field: "Id", op: "in", values: [] }] }],
  ...extra,
});

function backend(extra: Record<string, unknown> = {}) {
  const history: { url: string; body: unknown }[] = [];
  const orders: { url: string; body: unknown }[] = [];
  const cards: string[] = [];
  mockApi({
    "/api/master-data/counts": { body: { data_version: 64, tabs: [] } },
    "/api/transaction-data/counts": { body: { data_version: 64, tabs: [] } },
    ...routesOf("master-customer", list(CUSTOMER_COLS, CUSTOMERS)),
    ...routesOf("record-history", list(HISTORY_COLS, HISTORY, history)),
    ...routesOf("record-history-many", list([col("RecordLabel", "Kayıt", "text", "list"), ...HISTORY_COLS], HISTORY.map((h) => ({ ...h, RecordLabel: "MUS-A" })), history)),
    "/api/records/master-customer/many": (url: string, init?: RequestInit) => {
      cards.push(`${url} ${String(init?.body)}`);
      return { body: { list: "master-customer", table: "Customer", ids: ["1", "2"], relations: card(1).relations } };
    },
    ...routesOf("transaction-sales-order", list(ORDER_COLS, ORDERS, orders)),
    "/api/records/": (url: string) => {
      cards.push(url);
      const id = Number(url.split("/").pop());
      if (url.includes("transaction-sales-order")) return { body: { ...card(id), list: "transaction-sales-order", table: "SalesOrderLine", code: `SO-${id - 10} / 1`, name: null, label: `SO-${id - 10} / 1`, relations: [] } };
      return { body: card(id) };
    },
    ...extra,
  } as Parameters<typeof mockApi>[0]);
  return { history, orders, cards };
}

const CUSTOMER_URL = "/veri/ana-veri?sekme=tedarikci-ve-musteri&tablo=musteri";

async function open(path = CUSTOMER_URL, role = "Key user", extra: Record<string, unknown> = {}) {
  const user = userEvent.setup();
  const calls = backend(extra);
  const { router } = renderApp(path, meAs(role));
  await screen.findByText("MUS-B", {}, { timeout: 5000 });
  return { user, router, ...calls };
}

const rowOf = (code: string) => screen.getByText(code, { selector: "td, td *" }).closest("tr")!;
/** Satırın ⋯ menüsünden Detay (K-171). */
async function openDetail(user: ReturnType<typeof userEvent.setup>, code: string, scope: HTMLElement = document.body) {
  await user.click(within(scope).getByRole("button", { name: `${code} işlemleri` }));
  await user.click(await screen.findByRole("menuitem", { name: "Detay" }));
}
const cardPane = () => document.querySelector<HTMLElement>(".sc-md-detail");

describe("detay kartı", () => {
  it("satıra tıklamak yalnız seçer; ⋯ menüsünde ilk seçenek Detay, kartı Geçmiş'te açar; başlık yok", async () => {
    const { user, history, router } = await open();
    await user.click(rowOf("MUS-A"));
    expect(cardPane()).toBeNull();
    expect(document.querySelector(".sc-table-detail")).toBeNull();   // detay simgesi ve kolonu yok
    await user.click(within(rowOf("MUS-A")).getByRole("button", { name: "MUS-A işlemleri" }));
    expect(within(screen.getByRole("menu")).getAllByRole("menuitem")[0]).toHaveTextContent("Detay");
    await user.click(screen.getByRole("menuitem", { name: "Detay" }));
    await waitFor(() => expect(cardPane()).not.toBeNull());
    const pane = cardPane()!;
    expect(within(pane).getByRole("radio", { name: "Geçmiş" })).toHaveAttribute("aria-checked", "true");
    expect(await within(pane).findByRole("heading", { name: "MUS-A · Akdeniz" })).toHaveClass("sc-visually-hidden");
    expect(pane.querySelector(".sc-card-record")).toBeNull();   // kartta kod ve ad gösterilmez (K-173)
    const strip = pane.querySelector(".sc-table-toolbar--compact")!;   // tek şerit: solda sekmeler, sağda tablo düğmeleri, Büyüt ve ✕
    expect(within(strip.querySelector(".sc-table-toolbar-main") as HTMLElement).getByRole("radiogroup", { name: "Kart bölümleri" })).toBeInTheDocument();
    const tools = strip.querySelector(".sc-table-tools") as HTMLElement;
    expect(within(tools).getAllByRole("button").map((b) => b.getAttribute("aria-label")).slice(-2)).toEqual(["Büyüt", "Kapat"]);
        expect(await within(pane).findByText("Manuel değer · Ayşe Planlama")).toBeInTheDocument();
    expect(within(pane).getByText("Kayıt oluştu")).toBeInTheDocument();
    await waitFor(() => expect(history.at(-1)?.body).toMatchObject({ filters: [{ field: "TableName", values: ["Customer"] }, { field: "RecordKey", values: ["1"] }] }));
    expect(rowOf("MUS-A")).toHaveClass("is-selected");
    expect(router.state.location.search).toContain("kayit=1");
    expect(router.state.location.search).toContain("kart=gecmis");
  });

  it("sağ tık aynı menüyü açar: hücre seçenekleri başta (Kopyala), ardından Detay", async () => {
    const { user } = await open();
    fireEvent.contextMenu(screen.getByText("Batı").closest("td")!);
    const menu = screen.getByRole("menu", { name: "MUS-B işlemleri" });
    expect(within(menu).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Kopyala", "Detay"]);
    expect(menu.querySelector("[role=separator]")).not.toBeNull();
    await user.click(within(menu).getByRole("menuitem", { name: "Detay" }));
    expect(await screen.findByRole("heading", { name: "MUS-B · Batı" }, { timeout: 5000 })).toBeInTheDocument();
  });

  it("kart açıkken başka satıra tıklamak kartı o kayda geçirir; seçili satıra yeniden tıklamak kapatmaz; Esc kapatır", async () => {
    const { user, cards, router } = await open();
    await openDetail(user, "MUS-A");
    await screen.findByRole("heading", { name: "MUS-A · Akdeniz" }, { timeout: 5000 });
    await user.click(rowOf("MUS-B"));
    expect(await screen.findByRole("heading", { name: "MUS-B · Batı" }, { timeout: 5000 })).toBeInTheDocument();
    expect(cards.at(-1)).toContain("/api/records/master-customer/2");
    await user.click(rowOf("MUS-B"));
    expect(cardPane()).not.toBeNull();
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(cardPane()).toBeNull());
    expect(router.state.location.search).not.toContain("kayit=");
  });

  it("✕ kapatır; açık kart tablo başına hatırlanır", async () => {
    const { user } = await open();
    await openDetail(user, "MUS-B");
    await screen.findByRole("heading", { name: "MUS-B · Batı" }, { timeout: 5000 });
    await within(cardPane()!).findByText("Manuel değer · Ayşe Planlama");   // kart tablosu yüklendi
    const saved = JSON.parse(window.localStorage.getItem("smartchain.u3.masterData") ?? "{}") as { cards: Record<string, unknown> };
    expect(saved.cards["master-customer"]).toEqual({ id: "2", tab: "history" });
    await user.click(within(cardPane()!).getByRole("button", { name: "Kapat" }));
    await waitFor(() => expect(cardPane()).toBeNull());
  });

  it("sekmeler tek sıra (Geçmiş ve ilişkiler, sayısız, boş ilişki de seçilir); süzülmüş tablo; ilişkili satırın Detay'ı o kaydın kartını açar (ekran değişir)", async () => {
    const { user, orders, router } = await open(`${CUSTOMER_URL}&kayit=1&kart=satis-siparisi`);
    const pane = await waitFor(() => { const p = cardPane(); expect(p).not.toBeNull(); return p!; });
    expect(await within(pane).findByRole("radio", { name: "Satış siparişi" })).toHaveAttribute("aria-checked", "true");
    expect(within(pane).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Geçmiş", "Satış siparişi", "Proje"]);
    expect(within(pane).getByRole("radio", { name: "Proje" })).toBeEnabled();   // boş ilişki öteki sekmelerle aynı; tıklanınca boş tablo (K-171)
    expect(within(pane).queryByRole("radio", { name: "İlişkili kayıtlar" })).toBeNull();
    expect(await within(pane).findByText("SO-2")).toBeInTheDocument();
    expect(orders.at(-1)?.body).toMatchObject({ filters: [{ field: "Id", op: "in", values: ["11", "12"] }] });
    await openDetail(user, "SO-2 / 1", pane);
    await waitFor(() => expect(router.state.location.pathname).toBe("/veri/islem-verisi"));
    expect(router.state.location.search).toContain("kayit=12");
    expect(await screen.findByRole("heading", { name: "SO-2 / 1" }, { timeout: 5000 })).toBeInTheDocument();
    expect(within(cardPane()!).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Geçmiş"]);   // tek sekme olsa da sekme görünür (K-171)
  });

  it("çoklu seçimde kart seçili kayıtların hepsini gösterir; Geçmiş'te başta Kayıt kolonu; Esc önce seçimi, sonra kartı kapatır (K-171)", async () => {
    const { user, history, cards } = await open(`${CUSTOMER_URL}&kayit=1&kart=gecmis`);
    await screen.findByRole("heading", { name: "MUS-A · Akdeniz" }, { timeout: 5000 });
    await user.keyboard("{Control>}");
    await user.click(rowOf("MUS-A"));
    await user.click(rowOf("MUS-B"));
    await user.keyboard("{/Control}");
    expect(await screen.findByRole("heading", { name: "Seçili 2 kayıt" }, { timeout: 5000 })).toBeInTheDocument();
    expect(cards.at(-1)).toBe('/api/records/master-customer/many {"ids":["1","2"]}');
    await waitFor(() => expect(history.at(-1)?.url).toContain("/api/record-history-many/query"));
    expect(history.at(-1)?.body).toMatchObject({ filters: [{ field: "TableName", values: ["Customer"] }, { field: "RecordKey", values: ["1", "2"] }] });
    expect(await within(cardPane()!).findByRole("columnheader", { name: /Kayıt/ })).toBeInTheDocument();
    expect(within(cardPane()!).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Geçmiş", "Satış siparişi", "Proje"]);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(await screen.findByRole("heading", { name: "MUS-A · Akdeniz" }, { timeout: 5000 })).toBeInTheDocument();   // seçim temizlendi, kart kaldı
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(cardPane()).toBeNull());
  });

  it("güncel veride olmayan kayıt: kart açılır, uyarı, Geçmiş okunur", async () => {
    await open(`${CUSTOMER_URL}&kayit=1&kart=gecmis`, "Key user", {
      "/api/records/": { body: card(1, { current: false, closed_version: 64, relations: [] }) },
    });
    expect(await screen.findByText("Kayıt güncel veride yok (v64'te kapandı).")).toBeInTheDocument();
    expect(await screen.findByText("Manuel değer · Ayşe Planlama")).toBeInTheDocument();
  });

  it("End user Geçmiş'i görür", async () => {
    const { user } = await open(CUSTOMER_URL, "End user");
    await openDetail(user, "MUS-A");
    expect(await screen.findByText("Manuel değer · Ayşe Planlama")).toBeInTheDocument();
  });
});

describe("denetim izinde Kayda git", () => {
  const COLUMNS = [col("At", "Zaman", "datetime", "date"), col("ActorName", "Kullanıcı", "text", "list", { values_from_server: true }), col("Action", "İşlem", "text", "list")];
  const ROWS = [{ Id: 6, At: "2026-11-12T07:14:00+00:00", ActorName: "Ayşe", Action: "Manuel değer girildi" }];
  const detail = (extra: Partial<AuditDetail>): AuditDetail => ({
    id: 6, at: "2026-11-12T07:14:00+00:00", actor: "Ayşe", action: "Manuel değer girildi", object_type: "Manuel değer", object: "Müşteri · MUS-A",
    has_object: true, changes: [], ...extra,
  });

  async function openAudit(d: AuditDetail) {
    const user = userEvent.setup();
    backend({ ...routesOf("audit-log", list(COLUMNS, ROWS)), "/api/audit-log/6": { body: d } });
    const { router } = renderApp("/yonetim/denetim-izi", meAs("Admin"));
    await screen.findByText("Ayşe", {}, { timeout: 5000 });
    await user.click(screen.getByRole("button", { name: "Kayıt detayı" }));
    await user.click(await screen.findByRole("menuitem", { name: "Detay" }));
    return { user, router, dialog: await screen.findByRole("dialog", { name: "Kayıt detayı" }) };
  }

  it("hedefe gider: ekran, kayıt seçili, kart Geçmiş'te", async () => {
    const { user, dialog, router } = await openAudit(detail({ target: { list: "master-customer", id: "1" } }));
    await user.click(within(dialog).getByRole("button", { name: "Kayda git" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/veri/ana-veri"));
    expect(router.state.location.search).toBe(`?${recordUrl("master-customer", 1)!.split("?")[1]}`);
    expect(await screen.findByRole("heading", { name: "MUS-A · Akdeniz" }, { timeout: 5000 })).toBeInTheDocument();
  });

  it("bulunamazsa pasif, nedeni ipucunda; veri kaydı olmayan satırda düğme yok", async () => {
    const { dialog } = await openAudit(detail({ target: null, target_reason: "Kayıt bulunamadı." }));
    const go = within(dialog).getByRole("button", { name: "Kayda git" });
    expect(go).toBeDisabled();
    expect(go).toHaveAttribute("title", "Kayıt bulunamadı.");
  });
});

describe("yardımcılar", () => {
  it.each([[63, "te"], [64, "te"], [60, "ta"], [61, "de"], [50, "de"], [40, "ta"], [100, "de"], [6, "da"], [9, "da"], [10, "da"]])("v%i'%s", (n, ek) => {
    expect(locative(n)).toBe(ek);
  });

  it("recordUrl: liste ekranı, sekmesi ve tablosu", () => {
    expect(recordUrl("master-customer", 1)).toBe("/veri/ana-veri?sekme=tedarikci-ve-musteri&tablo=musteri&kayit=1&kart=gecmis");
    expect(recordUrl("transaction-purchase-order", 5, "history")).toBe("/veri/islem-verisi?sekme=satin-alma&kayit=5&kart=gecmis");
    expect(recordUrl("nope", 1)).toBeNull();
  });
});

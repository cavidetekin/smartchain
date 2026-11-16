// Veri kalitesi (ekran 05; K-174): Yüksek · Normal · Yok sayılan sekmeleri (Yüksek varsayılan, süzgeçler), durum çipleri, satır menüsü (Detay ·
// Kayda git · Kural oluştur · Yok say), Kural oluştur'un pasifliği, çoklu seçimde toplu Yok say ve gerekçe zorunluluğu, Yok saymayı kaldır,
// detay kartı Kayıt · Talep zinciri (yalnız Yüksek), Kayda git'in kaydı süzülü açması, Yok sayılan sekmesinin kendi listesi (Gerekçe açık).
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { meAs, mockApi, renderApp } from "../test/helpers";
import { onlyRecordUrl } from "./dataScreenTabs";

useTableTestSetup();

const EXPORT = { title: "x", file_slug: "x", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const COLUMNS = [col("State", "Durum", "text", "list"), col("EntityLabel", "Tablo", "text", "list"), col("RecordLabel", "Kayıt", "text", "text"),
                 col("Message", "Mesaj", "text", "text"), col("FirstSeenAt", "Tespit tarihi", "datetime", "date"),
                 col("RuleName", "Kontrol", "text", "list", { default_visible: false })];
const IGNORED_COLUMNS = [...COLUMNS.slice(0, 4), col("IgnoreReason", "Gerekçe", "text", "text"), ...COLUMNS.slice(4)];
const W = (id: number, extra: object = {}) => ({
  Id: id, State: "Yeni", EntityName: "MaterialSupplier", EntityLabel: "Malzeme tedarikçisi", RecordKey: String(30 + id), RecordLabel: `Malzeme: HAM-0${id} · Tedarikçi: TED-02`,
  RuleName: "Tedarik süresi yok", Message: "Tedarik süresi yok.", FirstSeenAt: "2026-11-16T08:00:00+00:00", TargetList: "master-material-supplier",
  FixField: "FixedLeadTimeDays", Importance: "Yüksek", Source: "Kural", ...extra,
});
const ROWS = [W(1), W(2, { State: "Açık", RuleName: "Kota toplamı 1 değil", FixField: null }), W(3, { State: "Açık" })];

function backend(rows = ROWS) {
  const queries: { list: string; filters: { field: string; values?: string[] }[] }[] = [];
  const recordQueries: { filters: { field: string; values?: string[] }[] }[] = [];
  const posts: { url: string; body: unknown }[] = [];
  const warnings = (list: string, columns: object[]) => ({
    [`/api/${list}/columns`]: { body: { chunk_size: 100, columns, export: EXPORT } },
    [`/api/${list}/views`]: { body: { views: [], default_view_id: null } },
    [`/api/${list}/query`]: (_u: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body));
      queries.push({ list, ...body });
      const ids = body.filters.find((f: { field: string }) => f.field === "Id")?.values as string[] | undefined;
      const out = ids ? rows.filter((r) => ids.includes(String(r.Id))) : rows;
      return { body: { rows: out, filtered: out.length, total: out.length } };
    },
  });
  const fetchMock = mockApi({
    ...warnings("data-quality-warnings", COLUMNS),
    ...warnings("data-quality-ignored", IGNORED_COLUMNS),
    "/api/master-data/counts": { body: { data_version: 35, tabs: [] } },
    "/api/data-quality/": (url: string, init?: RequestInit) => {
      posts.push({ url, body: init?.body ? JSON.parse(String(init.body)) : null });
      return { body: url.includes("demand-chain") ? { count: 1, truncated: false } : { ignored: 2, unignored: 1 } };
    },
    "/api/data-quality-demand-chain/columns": { body: { chunk_size: 100, columns: [col("DemandLabel", "Talep", "text", "text"), col("MaterialPath", "Malzeme yolu", "text", "text")], export: EXPORT } },
    "/api/data-quality-demand-chain/views": { body: { views: [], default_view_id: null } },
    "/api/data-quality-demand-chain/query": { body: { rows: [{ Id: 1, DemandLabel: "SO-1182 / 1", MaterialPath: "MAM-002 → ALT-001 → HAM-012" }], filtered: 1, total: 1 } },
    "/api/master-material-supplier/columns": { body: { chunk_size: 100, columns: [col("MaterialCode", "Malzeme", "text", "text")], export: EXPORT } },
    "/api/master-material-supplier/views": { body: { views: [], default_view_id: null } },
    "/api/master-material-supplier/query": (_u: string, init?: RequestInit) => {
      recordQueries.push(JSON.parse(String(init?.body)));
      return { body: { rows: [{ Id: 31, MaterialCode: "HAM-01" }], filtered: 1, total: 1 } };
    },
  });
  return { queries, recordQueries, posts, fetchMock };
}

async function open(path = "/veri/veri-kalitesi", role = "Key user", rows = ROWS) {
  const user = userEvent.setup();
  const calls = backend(rows);
  const { router } = renderApp(path, meAs(role));
  await screen.findByText("Malzeme: HAM-01 · Tedarikçi: TED-02", {}, { timeout: 5000 });
  return { user, router, ...calls };
}
const rowOf = (label: string) => screen.getByText(label, { selector: "td, td *" }).closest("tr") as HTMLElement;

describe("ekran 05 · Veri kalitesi", () => {
  it("üç sekme şeridin solunda, Yüksek varsayılan; sekme süzgeci; durum çipleri; Önem kolonu yok", async () => {
    const { user, queries } = await open();
    const tabs = screen.getByRole("radiogroup", { name: "Önem" });
    expect(within(tabs).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Yüksek", "Normal", "Yok sayılan"]);
    expect(within(tabs).getByRole("radio", { name: "Yüksek" })).toHaveAttribute("aria-checked", "true");
    expect(tabs.closest(".sc-table-toolbar-main")).not.toBeNull();
    expect(queries.at(-1)?.filters).toEqual([{ field: "Importance", op: "in", values: ["Yüksek"] }, { field: "State", op: "in", values: ["Yeni", "Açık"] }]);
    expect(screen.queryByRole("columnheader", { name: /Önem/ })).toBeNull();
    expect(within(rowOf("Malzeme: HAM-01 · Tedarikçi: TED-02")).getByText("Yeni").className).toContain("sc-tag--info");
    for (const name of ["Durum", "Tablo", "Kayıt", "Mesaj", "Tespit tarihi"]) expect(screen.getByRole("columnheader", { name: new RegExp(name) })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: /Kontrol|Kural|Gerekçe/ })).toBeNull();
    await user.click(within(tabs).getByRole("radio", { name: "Yok sayılan" }));
    await waitFor(() => expect(queries.at(-1)).toMatchObject({ list: "data-quality-ignored", filters: [{ field: "State", op: "in", values: ["Yok sayıldı"] }] }));
    expect(await screen.findByRole("columnheader", { name: /Gerekçe/ })).toBeInTheDocument();
  });

  it("satır menüsü: Detay · Kayda git · Kural oluştur · Yok say; alanı olmayan sorunda Kural oluştur pasif; Kayda git yalnız o kaydı açar", async () => {
    const { user, router, recordQueries } = await open("/veri/veri-kalitesi", "System owner");
    await user.click(within(rowOf("Malzeme: HAM-02 · Tedarikçi: TED-02")).getByRole("button", { name: "Malzeme: HAM-02 · Tedarikçi: TED-02 işlemleri" }));
    const menu = screen.getByRole("menu");
    expect(within(menu).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Detay", "Kayda git", "Kural oluştur", "Yok say"]);
    expect(within(menu).getByRole("menuitem", { name: "Kural oluştur" })).toBeDisabled();
    await user.keyboard("{Escape}");
    await user.click(within(rowOf("Malzeme: HAM-01 · Tedarikçi: TED-02")).getByRole("button", { name: "Malzeme: HAM-01 · Tedarikçi: TED-02 işlemleri" }));
    await user.click(screen.getByRole("menuitem", { name: "Kayda git" }));
    await waitFor(() => expect(`${router.state.location.pathname}${router.state.location.search}`).toBe(onlyRecordUrl("master-material-supplier", "31")));
    expect(router.state.location.search).toContain("yalniz=31");
    // hedef tablo kaydın Id'siyle süzülü; bilgi satırından bütün kayıtlara dönülür
    await waitFor(() => expect(recordQueries.at(-1)?.filters).toEqual([{ field: "Id", op: "in", values: ["31"] }]));
    expect(screen.getByText("Yalnız Veri kalitesinden açılan kayıt gösteriliyor.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Bütün kayıtları göster" }));
    await waitFor(() => expect(recordQueries.at(-1)?.filters).toEqual([]));
    expect(router.state.location.search).not.toContain("yalniz");
    expect(screen.queryByText("Yalnız Veri kalitesinden açılan kayıt gösteriliyor.")).toBeNull();
  });

  it("Kural oluştur Veri kuralları'nı tablo ve alanla açar; Veri kurallarını düzenleyemeyen Key user'da pasif", async () => {
    const { user, router } = await open("/veri/veri-kalitesi", "System owner");
    await user.click(within(rowOf("Malzeme: HAM-01 · Tedarikçi: TED-02")).getByRole("button", { name: "Malzeme: HAM-01 · Tedarikçi: TED-02 işlemleri" }));
    await user.click(screen.getByRole("menuitem", { name: "Kural oluştur" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/veri/veri-kurallari"));
    const key = await open("/veri/veri-kalitesi", "Key user");
    await key.user.click(within(rowOf("Malzeme: HAM-01 · Tedarikçi: TED-02")).getByRole("button", { name: "Malzeme: HAM-01 · Tedarikçi: TED-02 işlemleri" }));
    expect(screen.getByRole("menuitem", { name: "Kural oluştur" })).toBeDisabled();                    // Key user: 16 okuma
  });

  it("çoklu seçimde toplu Yok say: gerekçe zorunlu, tek gerekçe seçilenlere gider; End user'da pasif", async () => {
    const { user, posts } = await open();
    await user.keyboard("{Control>}");
    await user.click(rowOf("Malzeme: HAM-01 · Tedarikçi: TED-02"));
    await user.click(rowOf("Malzeme: HAM-03 · Tedarikçi: TED-02"));
    await user.keyboard("{/Control}");
    fireEvent.contextMenu(within(rowOf("Malzeme: HAM-03 · Tedarikçi: TED-02")).getByText("Tedarik süresi yok."));
    const menu = screen.getByRole("menu");
    expect(within(menu).getByText("Seçili 2 satır")).toBeInTheDocument();
    await user.click(within(menu).getAllByRole("menuitem", { name: "Yok say" })[0]);
    const dialog = screen.getByRole("dialog", { name: "Yok say · 2 uyarı" });
    expect(within(dialog).getByRole("button", { name: "Kaydet" })).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/Gerekçe/), "Numune lotları");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(posts.find((p) => p.url.endsWith("/ignore"))?.body).toEqual({ ids: ["1", "3"], reason: "Numune lotları" }));
  });

  it("End user listeyi görür, Yok say pasif", async () => {
    const { user } = await open("/veri/veri-kalitesi", "End user");
    await user.click(within(rowOf("Malzeme: HAM-01 · Tedarikçi: TED-02")).getByRole("button", { name: "Malzeme: HAM-01 · Tedarikçi: TED-02 işlemleri" }));
    expect(screen.getByRole("menuitem", { name: "Yok say" })).toBeDisabled();
  });

  it("Yok sayılan sekmesinde Yok saymayı kaldır", async () => {
    const { user, posts } = await open("/veri/veri-kalitesi?sekme=yok-sayilan", "Key user", [W(4, { State: "Yok sayıldı", RecordLabel: "Malzeme: HAM-01 · Tedarikçi: TED-02" })]);
    expect(within(rowOf("Malzeme: HAM-01 · Tedarikçi: TED-02")).getByText("Yok sayıldı").className).toContain("sc-tag--muted");
    await user.click(within(rowOf("Malzeme: HAM-01 · Tedarikçi: TED-02")).getByRole("button", { name: "Malzeme: HAM-01 · Tedarikçi: TED-02 işlemleri" }));
    await user.click(screen.getByRole("menuitem", { name: "Yok saymayı kaldır" }));
    await waitFor(() => expect(posts.find((p) => p.url.endsWith("/unignore"))?.body).toEqual({ ids: ["4"] }));
  });

  it("detay kartı: Yüksek'te Kayıt · Talep zinciri; Talep zinciri hesaplanır ve gösterilir; Normal'de yalnız Kayıt", async () => {
    const { user, posts } = await open();
    await user.click(within(rowOf("Malzeme: HAM-01 · Tedarikçi: TED-02")).getByRole("button", { name: "Malzeme: HAM-01 · Tedarikçi: TED-02 işlemleri" }));
    await user.click(screen.getByRole("menuitem", { name: "Detay" }));
    const pane = await waitFor(() => { const p = document.querySelector<HTMLElement>(".sc-md-detail"); expect(p).not.toBeNull(); return p!; });
    expect(within(pane).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Kayıt", "Talep zinciri"]);
    expect(await within(pane).findByText("HAM-01")).toBeInTheDocument();                                 // kaydın kendi listesi
    await user.click(within(pane).getByRole("radio", { name: "Talep zinciri" }));
    expect(await within(pane).findByText("MAM-002 → ALT-001 → HAM-012")).toBeInTheDocument();
    expect(posts.some((p) => p.url.endsWith("/1/demand-chain"))).toBe(true);
    await user.click(screen.getByRole("radio", { name: "Normal" }));
    await screen.findByText("Malzeme: HAM-01 · Tedarikçi: TED-02", { selector: "td, td *" }, { timeout: 5000 });
    await user.click(within(rowOf("Malzeme: HAM-01 · Tedarikçi: TED-02")).getByRole("button", { name: "Malzeme: HAM-01 · Tedarikçi: TED-02 işlemleri" }));
    await user.click(screen.getByRole("menuitem", { name: "Detay" }));
    const pane2 = await waitFor(() => { const p = document.querySelector<HTMLElement>(".sc-md-detail"); expect(p).not.toBeNull(); return p!; });
    expect(within(pane2).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Kayıt"]);
  });
});

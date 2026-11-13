// Entegrasyon (ekran 23, fonksiyon 91; K-130, K-132): tek kart, alan uyumu, toplu kayıt, bağlantı testi, önizleme, view sürümleri, yetki.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { cellOf, openEditor, setCell } from "../table/testEditing";

import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, meAs, mockApi, renderApp, type Routes } from "../test/helpers";
import type { Connection, Preview, TestResult, ViewVersion } from "./integrationApi";

useTableTestSetup();

const CONNECTION: Connection = { database: "SmartchainIntegration", account: "SUNUCU\\smartchain", last_read: "2026-11-05T08:00:00", last_upload: null, sql_tables: 2, excel_tables: 23 };
const COLUMNS = [col("Name", "Tablo", "text", "text"), col("Method", "Yöntem", "text", "list"), col("ViewName", "Kaynak", "text", "text"), col("ColumnMatch", "Alan uyumu", "text", "text"), col("LastPullStatus", "Son durum", "text", "text")];
const ROWS = [
  { Id: 1, Entity: "Material", Name: "Malzeme", Method: "SQL", ViewName: "View_Material", ColumnMatch: "33 / 33", LastCheckStatus: "Uyumlu", LastCheckMessage: null, LastPullStatus: "Alındı", LastPullMessage: null },
  { Id: 2, Entity: "Stock", Name: "Stok", Method: "SQL", ViewName: "View_Stock", ColumnMatch: "12 / 13", LastCheckStatus: "Uyarılı", LastCheckMessage: "İsteğe bağlı kolon yok: Warehouse (Depo).", LastPullStatus: "Yeni veri yok", LastPullMessage: "Son çekimden beri değişiklik yok." },
  { Id: 3, Entity: "Resource", Name: "Kaynak", Method: "Excel", ViewName: null, ColumnMatch: null, LastCheckStatus: null, LastCheckMessage: null, LastPullStatus: null, LastPullMessage: null },
];
const TEST: TestResult = {
  database: "SmartchainIntegration", ok: false,
  steps: [
    { key: "access", label: "Sunucu erişimi", ok: true, detail: "SmartchainIntegration", ms: 0 },
    { key: "signal", label: "Bitti sinyali", ok: false, detail: "ERP_LoadLog tablosu bulunamadı.", ms: 2 },
  ],
  tables: [
    { entity: "Material", name: "Malzeme", view: "View_Material", status: "Uyumlu", matched: 33, expected: 33, errors: [], warnings: [], notes: ["Tekrar eden anahtar: 1 kayıt."] },
    { entity: "Stock", name: "Stok", view: "View_Stock", status: "Uyarılı", matched: 12, expected: 13, errors: [], warnings: ["İsteğe bağlı kolon yok: Warehouse (Depo)."], notes: [] },
  ],
};
const PREVIEW: Preview = {
  entity: "Material", name: "Malzeme", view: "View_Material", status: "Uyumlu", errors: [], warnings: [],
  columns: [{ field: "Code", label: "Kod" }],
  rows: [{ values: { Code: "HAM-001" }, findings: [] }, { values: { Code: "HAM-002" }, findings: [{ severity: "Hata", field: "Kod", message: "Zorunlu alan boş." }] }],
};
const VERSIONS: ViewVersion[] = [
  { version: 2, view: "View_Material", seen_at: "2026-11-05T08:00:00", app_version: "0.23.0", definition: "CREATE VIEW yeni" },
  { version: 1, view: "View_Material", seen_at: "2026-11-04T08:00:00", app_version: "0.23.0", definition: "CREATE VIEW eski" },
];

function backend(routes: Routes = {}) {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/integration-entities/columns": { body: { chunk_size: 100, columns: COLUMNS, export: { title: "Entegrasyon tabloları", file_slug: "entegrasyon-tablolari", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    "/api/integration-entities/query": { body: { rows: ROWS, filtered: 3, total: 3 } },
    "/api/integration-entities/views": { body: { views: [], default_view_id: null } },
    "/api/integration/connection": { body: CONNECTION },
    "/api/integration/test": { body: TEST },
    "/api/integration/entities/Material/preview": { body: PREVIEW },
    "/api/integration/entities/Material/view-versions": { body: VERSIONS },
    "/api/integration/entities": { body: { saved: 1 } },
    ...routes,
  });
}

async function open(role: string, routes: Routes = {}) {
  const fetchMock = backend(routes);
  renderApp("/yonetim/entegrasyon", meAs(role));
  await screen.findByText("Malzeme", {}, { timeout: 5000 });
  return { user: userEvent.setup(), fetchMock };
}

const calls = (fetchMock: ReturnType<typeof vi.fn>, method: string, url: string) =>
  fetchMock.mock.calls.filter(([u, init]) => String(u).startsWith(url) && (init as RequestInit | undefined)?.method === method);

describe("ekran 23", () => {
  it("tek satır şerit: kart başlığı, Excel ve API yok, anlatım satırları yok, hesap var", async () => {
    await open("Admin");
    expect(screen.queryByRole("heading", { name: "SQL view" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Excel şablonları" })).not.toBeInTheDocument();
    expect(screen.queryByText(/\bAPI\b/)).not.toBeInTheDocument();
    expect(await screen.findByText(/Hesap: SUNUCU\\smartchain/)).toBeInTheDocument();
    expect(screen.queryByText(/son okuma/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Ham tablo/)).not.toBeInTheDocument();
  });

  it("System owner: şeritte alan, Kaydet indigo, Bağlantıyı test et tonal mor, hesap", async () => {
    await open("System owner");
    const strip = (await screen.findByRole("textbox", { name: /SQL kaynağı/ })).closest(".sc-table-toolbar-main") as HTMLElement;  // tablonun şeridinde (K-171)
    expect(within(strip).getByRole("button", { name: "Kaydet" }).className).toContain("sc-btn--primary");
    expect(within(strip).getByRole("button", { name: "Bağlantıyı test et" }).className).toContain("sc-btn--secondary");
    expect(await within(strip).findByText(/Hesap: SUNUCU/)).toBeInTheDocument();
  });

  it("alan uyumu: zorunlu kolon eksikse kırmızı", async () => {
    await open("Admin", { "/api/integration-entities/query": { body: { rows: [{ ...ROWS[0], ColumnMatch: "32 / 33", LastCheckStatus: "Hatalı", LastCheckMessage: "Zorunlu kolon yok: Code (Kod)." }], filtered: 1, total: 1 } } });
    expect(screen.getByText("32 / 33").className).toContain("critical");
  });

  it("alan uyumu tek kolon: tam uyum yeşil, yalnız isteğe bağlı eksik sarı; notu ipucunda", async () => {
    const { user } = await open("Admin");
    expect(screen.queryByRole("columnheader", { name: /^Uyum$/ })).not.toBeInTheDocument();
    expect(screen.getByText("33 / 33").className).toContain("ok");
    const partial = screen.getByText("12 / 13");
    expect(partial.className).toContain("risk");
    await user.hover(partial);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Warehouse");
    expect(screen.getByText("Alındı").className).toContain("ok");
    expect(screen.getByText("Yeni veri yok").className).toContain("neutral");
  });

  it("System owner yöntem ve view'ı tabloda düzenler, Kaydet toplu yazar", async () => {
    const { user, fetchMock } = await open("System owner");
    const method = await openEditor(user, cellOf("Kaynak", "Yöntem"));
    expect(within(method).getAllByRole("option").map((o) => o.textContent)).toEqual(["Excel", "SQL"]);
    await user.selectOptions(method, "SQL");
    await user.keyboard("{Enter}");
    await setCell(user, "Kaynak", "Kaynak", "View_Resource");
    await setCell(user, "Malzeme", "Kaynak", "View_Yeni");
    expect(calls(fetchMock, "PUT", "/api/integration/entities")).toHaveLength(0);
    const table = screen.getByTestId("table-scroll").parentElement!;
    await user.click(within(table.querySelector(".sc-edit-bar") as HTMLElement).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls(fetchMock, "PUT", "/api/integration/entities")).toHaveLength(1));
    expect(JSON.parse(String((calls(fetchMock, "PUT", "/api/integration/entities")[0][1] as RequestInit).body)).changes).toEqual([
      { entity: "Resource", method: "SQL", view: "View_Resource" }, { entity: "Material", view: "View_Yeni" },
    ]);
  });

  it("System owner SQL kaynağını kaydeder", async () => {
    const { user, fetchMock } = await open("System owner", { "/api/integration/connection": (_url, init) => ({ body: init?.method === "PUT" ? { ...CONNECTION, database: "Yeni" } : CONNECTION }) });
    const field = await screen.findByRole("textbox", { name: /SQL kaynağı/ });
    await waitFor(() => expect(field).toHaveValue("SmartchainIntegration"));
    await user.clear(field);
    await user.type(field, "Yeni");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls(fetchMock, "PUT", "/api/integration/connection")).toHaveLength(1));
  });

  it("Admin SQL kaynağını, yöntemi ve view'ı değiştiremez", async () => {
    await open("Admin");
    expect(screen.queryByRole("textbox", { name: /SQL kaynağı/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Malzeme view adı" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Malzeme yöntemi" })).not.toBeInTheDocument();
    expect(screen.getByText("View_Material")).toBeInTheDocument();
  });

  it("bağlantı testi: adımlar, alan uyumu çipi, not; bant yok", async () => {
    const { user } = await open("Admin");
    const button = screen.getByRole("button", { name: "Bağlantıyı test et" });
    await waitFor(() => expect(button).toBeEnabled());
    await user.click(button);
    const dialog = await screen.findByRole("dialog", { name: "Bağlantı testi" });
    expect(dialog).toHaveTextContent("ERP_LoadLog tablosu bulunamadı.");
    expect(within(dialog).getByText("33 / 33").className).toContain("ok");
    expect(within(dialog).getByText("12 / 13").className).toContain("risk");
    expect(dialog).toHaveTextContent("Tekrar eden anahtar: 1 kayıt.");
    expect(dialog.querySelector(".sc-alert")).toBeNull();
    expect(dialog.querySelector(".sc-table-grid")).not.toBeNull();
    expect(within(dialog).getByText("Tekrar eden anahtar: 1 kayıt.").className).toContain("is-wrap");  // uzun metin alt satıra kayar
    const items = within(dialog).getAllByRole("listitem");
    expect(items[1].children).toHaveLength(3);  // çip, kontrol adı, ayrıntı
    expect(items[1].children[1]).toHaveTextContent("Bitti sinyali");
    expect(items[1].children[2]).toHaveTextContent("ERP_LoadLog tablosu bulunamadı.");
  });

  it("SQL kaynağı yoksa test pasif", async () => {
    await open("Admin", { "/api/integration/connection": { body: { ...CONNECTION, database: null } } });
    await waitFor(() => expect(screen.getByRole("button", { name: "Bağlantıyı test et" })).toBeDisabled());
    expect(screen.getByText("tanımlı değil")).toBeInTheDocument();
  });

  it("önizleme: ortak tablo görünümü, satırlar ve sorun; bant yok; view yoksa pasif", async () => {
    const { user } = await open("Admin");
    await user.click(screen.getByRole("button", { name: "Kaynak işlemleri" }));
    expect(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Önizleme" })).toBeDisabled();
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Malzeme işlemleri" }));
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Önizleme" }));
    const dialog = await screen.findByRole("dialog", { name: "Önizleme · Malzeme" });
    expect(await within(dialog).findByText("HAM-002")).toBeInTheDocument();
    expect(dialog).toHaveTextContent("Kod: Zorunlu alan boş.");
    expect(dialog.querySelector(".sc-alert")).toBeNull();
    expect(dialog.querySelector(".sc-table-grid")).not.toBeNull();
    await user.click(within(dialog).getByRole("button", { name: "Kod" }));
    await user.click(within(dialog).getByRole("button", { name: "Kod" }));
    expect(within(within(dialog).getAllByRole("row")[1]).getAllByRole("cell")[0]).toHaveTextContent("HAM-002");
  });

  it("view sürümleri: en yenisi önce, tanım okunur; bant yok", async () => {
    const { user } = await open("Admin");
    await user.click(screen.getByRole("button", { name: "Malzeme işlemleri" }));
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "View sürümleri" }));
    const dialog = await screen.findByRole("dialog", { name: "View sürümleri · Malzeme" });
    expect(await within(dialog).findByText("CREATE VIEW yeni")).toBeInTheDocument();
    expect(dialog).toHaveTextContent("v1 · View_Material");
    expect(dialog.querySelector(".sc-alert")).toBeNull();
  });

  it.each(["Key user", "End user"])("%s ekranı göremez", async (role) => {
    backend();
    renderApp("/yonetim/entegrasyon", meAs(role));
    expect(await screen.findByRole("heading", { level: 1 })).not.toHaveTextContent("SQL view");
    expect(screen.queryByRole("heading", { name: "SQL view" })).not.toBeInTheDocument();
  });
});

// Zamanlanmış işler (Sistem ayarları sekmesi, fonksiyon 92; K-163, K-164): bağlam çubuğundaki çip ve kapatma, zamanlanmış iş sürerken pasif
// düğmeler, sekme (bekleme süreleri, ana–detay geçmiş), pencere (adımlar, kümeler, Excel pasif, kısmide Veri çekimi varsayılanı),
// şimdi çalıştır onayı, Admin salt okunur.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, meAs, mockApi, renderApp, type Routes } from "../test/helpers";
import type { Flow, FlowsResponse, FlowStatus, FlowTable } from "./flowsApi";

useTableTestSetup();

const RUN = {
  id: 7, flow_id: 1, flow_name: "Hafta içi kısmi", trigger: "Zamanlanmış", state: "Durdu", step: "Veri çekme", reason: "Veri çekilemedi · Stok: SQL kaynağına ulaşılamadı.",
  scheduled_at: "2026-11-10T23:00:00+00:00", started_at: "2026-11-10T23:00:05+00:00", ended_at: "2026-11-10T23:14:00+00:00", data_version_id: null, transfer_job_id: null,
};
const STOPPED: FlowStatus = { running: null, alerts: [{ ...RUN, at: RUN.ended_at }], can_view_history: true };
const IDLE: FlowStatus = { running: null, alerts: [], can_view_history: true };
const RUNNING: FlowStatus = {
  running: { ...RUN, state: "Çalışıyor", reason: null, ended_at: null, message: "Zamanlanmış iş sürüyor: Hafta içi kısmi (başlama 02:00)" },
  alerts: [], can_view_history: true,
};
const FLOW: Flow = {
  id: 1, name: "Hafta içi kısmi", is_active: true, run_time: "02:00", days: [1, 2, 3, 4, 5], days_text: "Hafta içi", pull_scope: "Seçilen", pull_tables: ["Stock"],
  transfer_mode: "Kısmi", transfer_groups: ["Stok"], cleanup: false, updated_at: "2026-11-09T10:00:00+00:00", updated_by_name: "Mert Planlama",
  next_at: "2026-11-11T23:00:00+00:00", last: RUN,
};
const t = (entity: string, name: string, method = "SQL"): FlowTable => ({ entity, name, method });
const FLOWS: FlowsResponse = {
  flows: [FLOW],
  options: {
    tables: [t("Material", "Malzeme"), t("Stock", "Stok"), t("BorrowPayback", "Ödünç ve geri ödeme"), t("Forecast", "Tahmin", "Excel"), t("SalesOrderLine", "Satış siparişi")],
    sql_tables: ["Material", "Stock", "BorrowPayback", "SalesOrderLine"],
    groups: [{ name: "Talep", tables: [t("SalesOrderLine", "Satış siparişi"), t("Forecast", "Tahmin", "Excel")], sql_tables: ["SalesOrderLine"] },
             { name: "Stok", tables: [t("Stock", "Stok"), t("BorrowPayback", "Ödünç ve geri ödeme")], sql_tables: ["Stock", "BorrowPayback"] }],
    pull_sets: [{ name: "Ana veri", tables: [t("Material", "Malzeme")] },
                { name: "Talep", tables: [t("SalesOrderLine", "Satış siparişi"), t("Forecast", "Tahmin", "Excel")] },
                { name: "Stok", tables: [t("Stock", "Stok"), t("BorrowPayback", "Ödünç ve geri ödeme")] }],
  },
  running: null, can_edit: true, settings: { FlowWaitMinutes: 60, FlowRefreshWaitMinutes: 120 },
  limits: { FlowWaitMinutes: { min: 5, max: 720 }, FlowRefreshWaitMinutes: { min: 5, max: 720 } },
};
const ENTITY_COLUMNS = [col("Name", "Tablo", "text", "text"), col("Method", "Yöntem", "text", "list")];
const FLOW_COLUMNS = [col("Name", "Zamanlanmış iş", "text", "text"), col("Schedule", "Zaman", "text", "text"), col("LastState", "Son çalışma", "text", "list")];
const RUN_COLUMNS = [col("StartedAt", "Başlama", "datetime", "date"), col("TriggerText", "Tetik", "text", "text"), col("State", "Durum", "text", "list"), col("Reason", "Neden", "text", "text")];
const EXPORT = { title: "Tablolar", file_slug: "tablolar", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const FLOW_ROW = { Id: 1, Name: "Hafta içi kısmi", Schedule: "Hafta içi 02:00", LastState: "Durdu", LastAt: RUN.ended_at, LastReason: RUN.reason };

function backend(routes: Routes = {}) {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/health": { body: { status: "ok", app_version: "0.32.0" } },
    "/api/flows/status": { body: IDLE },
    "/api/flows": { body: FLOWS },
    "/api/flows/columns": { body: { chunk_size: 100, columns: FLOW_COLUMNS, export: EXPORT } },
    "/api/flows/query": { body: { rows: [FLOW_ROW], filtered: 1, total: 1 } },
    "/api/flows/views": { body: { views: [], default_view_id: null } },
    "/api/flow-runs/columns": { body: { chunk_size: 100, columns: RUN_COLUMNS, export: EXPORT } },
    "/api/flow-runs/query": { body: { rows: [{ Id: 7, StartedAt: RUN.started_at, TriggerText: "Elle · sahip", State: "Durdu", Reason: RUN.reason }], filtered: 1, total: 1 } },
    "/api/flow-runs/views": { body: { views: [], default_view_id: null } },
    "/api/data-entities/columns": { body: { chunk_size: 100, columns: ENTITY_COLUMNS, export: EXPORT } },
    "/api/data-entities/query": { body: { rows: [{ Id: 1, Entity: "Material", Name: "Malzeme", Method: "Excel", Version: 4 }], filtered: 1, total: 1 } },
    "/api/data-entities/views": { body: { views: [], default_view_id: null } },
    ...routes,
  });
}

const calls = (fetchMock: ReturnType<typeof vi.fn>, method: string, url: string) =>
  fetchMock.mock.calls.filter(([u, init]) => String(u) === url && ((init as RequestInit | undefined)?.method ?? "GET") === method);
const body = (fetchMock: ReturnType<typeof vi.fn>, method: string, url: string) => JSON.parse(String(calls(fetchMock, method, url)[0][1]?.body));

describe("bağlam çubuğundaki çip", () => {
  it("zamanlanmış iş durunca her ekranda görünür; açınca adım ve neden; Kapat o kullanıcı için kapatır", async () => {
    let status = STOPPED;
    const fetchMock = backend({ "/api/flows/status": () => ({ body: status }), "/api/flows/runs/7/dismiss": () => { status = IDLE; return { status: 204, body: null }; } });
    renderApp("/veri/veri-yukleme", meAs("Key user"));
    const chip = await screen.findByTestId("flow-alert");
    expect(chip).toHaveTextContent(/^Zamanlanmış iş durdu · Hafta içi kısmi$/);
    expect(chip).toHaveClass("sc-tag--critical");
    expect(chip.closest(".sc-context-right")).not.toBeNull();
    const user = userEvent.setup();
    await user.click(chip);
    const card = screen.getByRole("dialog", { name: "Zamanlanmış iş" });
    expect(within(card).getByText(RUN.reason)).toBeInTheDocument();
    expect(card).toHaveTextContent("Veri çekme");
    expect(within(card).getByRole("button", { name: "Geçmiş" })).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Kapat" }));
    await waitFor(() => expect(screen.queryByTestId("flow-alert")).not.toBeInTheDocument());
    expect(calls(fetchMock, "POST", "/api/flows/runs/7/dismiss")).toHaveLength(1);
  });

  it("başarılı zamanlanmış işte ve End user'da çip yok", async () => {
    const fetchMock = backend();
    renderApp("/veri/veri-yukleme", meAs("Key user"));
    await screen.findAllByText("Malzeme", {}, { timeout: 5000 });
    expect(screen.queryByTestId("flow-alert")).not.toBeInTheDocument();
    fetchMock.mockClear();
    renderApp("/ana-sayfa", meAs("End user"));
    await waitFor(() => expect(calls(fetchMock, "GET", "/api/flows/status")).toHaveLength(0));
  });

  it("başlamayan iş: \"Zamanlanmış iş başlamadı\"; Geçmiş Sistem ayarları'nın sekmesinde o işin geçmişini açar", async () => {
    backend({ "/api/flows/status": { body: { ...STOPPED, alerts: [{ ...RUN, state: "Başlamadı", step: "Başlangıç", reason: "Servis kapalıydı; zamanlanmış iş saatinde başlamadı.", at: RUN.scheduled_at }] } } });
    renderApp("/veri/veri-yukleme", meAs("Admin"));
    const chip = await screen.findByTestId("flow-alert");
    expect(chip).toHaveTextContent(/^Zamanlanmış iş başlamadı · Hafta içi kısmi$/);
    const user = userEvent.setup();
    await user.click(chip);
    await user.click(screen.getByRole("button", { name: "Geçmiş" }));
    expect(await screen.findByRole("heading", { name: "Hafta içi kısmi · Geçmiş" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Sistem ayarları");
    expect(await screen.findByText("Elle · sahip")).toBeInTheDocument();
  });
});

describe("zamanlanmış iş sürerken", () => {
  it("Veri yükleme düğmeleri pasif, ipucunda işin adı ve başlama saati", async () => {
    backend({ "/api/flows/status": { body: RUNNING } });
    renderApp("/veri/veri-yukleme", meAs("System owner"));
    await screen.findAllByText("Malzeme", {}, { timeout: 5000 });
    await waitFor(() => expect(screen.getByRole("button", { name: "Veri çek" })).toBeDisabled());
    expect(screen.getByRole("button", { name: "Veri çek" })).toHaveAttribute("title", "Zamanlanmış iş sürüyor: Hafta içi kısmi (başlama 02:00)");
    expect(screen.getByRole("button", { name: "Veri yükle" })).toBeDisabled();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Veri aktarma" }));
    expect(await screen.findByRole("menuitem", { name: "Tam veri aktarımı" })).toBeDisabled();
  });
});

describe("Sistem ayarları → Zamanlanmış işler", () => {
  async function openTab(role: string, routes: Routes = {}) {
    const fetchMock = backend(routes);
    renderApp("/yonetim/sistem-ayarlari?sekme=zamanlanmis-isler", meAs(role));
    await screen.findByText("Hafta içi kısmi", {}, { timeout: 5000 });
    return { user: userEvent.setup(), fetchMock };
  }

  it("tek şerit (K-171): solda sekmeler, Yeni zamanlanmış iş, Bekleme süreleri; bekleme süreleri küçük pencerede; satıra tıklayınca alt kartta geçmiş", async () => {
    const { user, fetchMock } = await openTab("System owner", { "/api/flows/settings": { body: { ...FLOWS, settings: { FlowWaitMinutes: 45, FlowRefreshWaitMinutes: 120 } } } });
    const strip = screen.getByRole("button", { name: "Yeni zamanlanmış iş" }).closest(".sc-table-toolbar-main") as HTMLElement;
    expect(within(strip).getByRole("radio", { name: "Zamanlanmış işler" })).toBeChecked();  // ekranın sekmeleri şeridin başında
    expect(within(strip).getAllByRole("button").map((b) => b.textContent)).toEqual(["Yeni zamanlanmış iş", "Bekleme süreleri"]);
    expect(within(strip).getByRole("button", { name: "Yeni zamanlanmış iş" }).className).toContain("sc-btn--primary");
    expect(screen.queryByLabelText("Başlangıç bekleme süresi (dk)")).toBeNull();  // bekleme süreleri şeridi yok
    await user.click(within(strip).getByRole("button", { name: "Bekleme süreleri" }));
    const dialog = screen.getByRole("dialog", { name: "Bekleme süreleri" });
    const wait = within(dialog).getByLabelText("Başlangıç bekleme süresi (dk)");
    expect(wait).toHaveValue("60");
    expect(wait).toHaveAccessibleDescription("Saatinde başlayamayan zamanlanmış iş en çok bu kadar bekler.");
    const erp = within(dialog).getByLabelText("ERP bekleme süresi (dk)");
    expect(erp).toHaveValue("120");
    expect(erp).toHaveAccessibleDescription("ERP verisi hazır değilse çekim en çok bu kadar bekler.");
    expect(within(dialog).getByRole("button", { name: "Vazgeç" })).toBeEnabled();
    expect(within(dialog).getByRole("button", { name: "Kaydet" })).toBeDisabled();
    fireEvent.change(wait, { target: { value: "4" } });
    expect(within(dialog).getByRole("button", { name: "Kaydet" })).toBeDisabled();
    expect(within(dialog).getByText("En az 5, en çok 720.")).toBeInTheDocument();
    fireEvent.change(wait, { target: { value: "45" } });
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls(fetchMock, "PUT", "/api/flows/settings")).toHaveLength(1));
    expect(body(fetchMock, "PUT", "/api/flows/settings")).toEqual({ FlowWaitMinutes: 45 });
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Bekleme süreleri" })).toBeNull());
    await user.click(screen.getByText("Hafta içi kısmi"));
    expect(await screen.findByRole("heading", { name: "Hafta içi kısmi · Geçmiş" })).toBeInTheDocument();
    expect(await screen.findByText("Elle · sahip")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Geçmiş" })).toBeInTheDocument();  // tek sekme olsa da sekme görünür (K-171)
  });

  it("pencere: adımlar sabit sırayla, Aktif başlıkta, kümeler ve Excel pasif; kısmide Veri çekimi seçilen grubun SQL tabloları", async () => {
    const { user, fetchMock } = await openTab("System owner", { "/api/flows": (_u, init) => ({ body: init?.method === "POST" ? { ...FLOWS, id: 2 } : FLOWS }) });
    await user.click(screen.getByRole("button", { name: "Yeni zamanlanmış iş" }));
    const dialog = screen.getByRole("dialog", { name: "Yeni zamanlanmış iş" });
    expect([...dialog.querySelectorAll(".sc-flow-step > h3")].map((h) => h.textContent))
      .toEqual(["1 · İş tanımı*", "2 · Zamanlama*", "3 · Veri çekimi", "4 · Veri aktarımı", "5 · Ham veri temizliği"]);
    expect(dialog.querySelectorAll("[placeholder]")).toHaveLength(0);  // yer tutucu yok (K-166)
    expect(dialog.querySelectorAll(".sc-segment-fill")).toHaveLength(2);
    expect(within(dialog).getByRole("switch", { name: "Aktif" })).toBeChecked();
    expect(dialog).not.toHaveTextContent("(zorunlu)");
    expect(dialog).not.toHaveTextContent("sunucunun yerel saati");
    await user.type(within(dialog).getByRole("textbox", { name: "Ad (zorunlu)" }), "Öğlen stok");
    const days = within(dialog).getByRole("group", { name: "Günler" });
    expect(within(days).getAllByRole("button").map((b) => b.getAttribute("aria-pressed"))).toEqual(["true", "true", "true", "true", "true", "false", "false"]);
    await user.click(within(days).getByRole("button", { name: "Cmt" }));
    await user.click(within(dialog).getByRole("radio", { name: "Kısmi veri aktarımı" }));
    expect(within(dialog).getByText("Satış siparişi · Tahmin")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("checkbox", { name: "Stok grubunu aktar" }));  // aktarım grubu kartı
    expect(within(dialog).getByRole("radio", { name: "Seçili tablolar" })).toHaveAttribute("aria-checked", "true");
    expect(within(dialog).getByRole("checkbox", { name: "Stok grubunu aktar" }).closest(".sc-group-row")).toHaveClass("is-on");
    const stok = within(dialog).getByRole("group", { name: "Stok" });
    expect(within(stok).getByText("2 / 2")).toBeInTheDocument();
    expect(within(stok).getByRole("button", { name: "Stok" })).toHaveAttribute("aria-pressed", "true");
    const talep = within(dialog).getByRole("group", { name: "Talep" });
    expect(within(talep).getByText("0 / 1")).toBeInTheDocument();
    const excel = within(talep).getByRole("button", { name: /Tahmin/ });
    expect(excel).toBeDisabled();
    expect(excel).toHaveClass("is-excel");
    expect(within(excel).getByText("Excel")).toBeInTheDocument();
    await user.click(within(talep).getByRole("checkbox", { name: "Talep grubunun tablolarının hepsi" }));
    expect(within(talep).getByText("1 / 1")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls(fetchMock, "POST", "/api/flows")).toHaveLength(1));
    expect(body(fetchMock, "POST", "/api/flows")).toEqual({
      name: "Öğlen stok", is_active: true, run_time: "02:00", days: [1, 2, 3, 4, 5, 6], pull_scope: "Seçilen", pull_tables: ["Stock", "BorrowPayback", "SalesOrderLine"],
      transfer_mode: "Kısmi", transfer_groups: ["Stok"], cleanup: false,
    });
  });

  it("Şimdi çalıştır onaylıdır", async () => {
    const { user, fetchMock } = await openTab("System owner", { "/api/flows/1/run": { body: { run_id: 9 } } });
    await user.click(screen.getByRole("button", { name: "Hafta içi kısmi için işlemler" }));
    await user.click(await screen.findByRole("menuitem", { name: "Şimdi çalıştır" }));
    const confirm = screen.getByRole("dialog", { name: "Zamanlanmış işi şimdi çalıştır" });
    expect(confirm).toHaveTextContent("Kısmi · Stok");
    await user.click(within(confirm).getByRole("button", { name: "Şimdi çalıştır" }));
    await waitFor(() => expect(calls(fetchMock, "POST", "/api/flows/1/run")).toHaveLength(1));
  });

  it("Admin: menüde Sistem ayarları, yalnız Zamanlanmış işler sekmesi, salt okunur", async () => {
    const { user } = await openTab("Admin", { "/api/flows": { body: { ...FLOWS, can_edit: false } } });
    expect(screen.queryByRole("radio", { name: "Veri sözlüğü" })).toBeNull();
    expect(screen.queryByRole("radio", { name: "Giriş ve oturum" })).toBeNull();
    expect(screen.queryByRole("radio", { name: "Zamanlanmış işler" })).toBeNull();  // tek sekme: ekran sekmesi yok
    expect(screen.getByRole("button", { name: "Yeni zamanlanmış iş" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Bekleme süreleri" }));
    const wait = screen.getByRole("dialog", { name: "Bekleme süreleri" });
    expect(within(wait).getByLabelText("Başlangıç bekleme süresi (dk)")).toBeDisabled();
    expect(within(wait).getByRole("button", { name: "Kaydet" })).toBeDisabled();
    await user.click(within(wait).getByRole("button", { name: "Vazgeç" }));
    await user.click(screen.getByRole("button", { name: "Hafta içi kısmi için işlemler" }));
    expect(await screen.findByRole("menuitem", { name: "Şimdi çalıştır" })).toBeDisabled();
    expect(screen.queryByRole("menuitem", { name: "Düzenle" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("menuitem", { name: "Görüntüle" }));
    expect(screen.getByRole("dialog", { name: "Zamanlanmış iş · Hafta içi kısmi" })).toHaveTextContent("Hafta içi 02:00");
  });

  it("Entegrasyon'da zamanlanmış iş düğmesi yok", async () => {
    backend({
      "/api/integration-entities/columns": { body: { chunk_size: 100, columns: ENTITY_COLUMNS, export: EXPORT } },
      "/api/integration-entities/query": { body: { rows: [{ Id: 1, Entity: "Material", Name: "Malzeme", Method: "SQL" }], filtered: 1, total: 1 } },
      "/api/integration-entities/views": { body: { views: [], default_view_id: null } },
      "/api/integration/connection": { body: { database: "Kaynak", account: "SUNUCU\\smartchain", last_read: null, last_upload: null, sql_tables: 2, excel_tables: 23 } },
    });
    renderApp("/yonetim/entegrasyon", meAs("System owner"));
    await screen.findByText("Malzeme", {}, { timeout: 5000 });
    expect(screen.queryByRole("button", { name: /Zamanlanmış/ })).toBeNull();
  });
});

// Zamanlanmış akışlar (ekran 23, fonksiyon 92; K-163): bağlam çubuğundaki çip ve kapatma, akış sürerken pasif düğmeler,
// akış penceresi (adımlar sabit sırayla, kısmide Veri çek varsayılanı), şimdi çalıştır onayı, Admin salt okunur, zamanlayıcı satırı.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, meAs, mockApi, renderApp, type Routes } from "../test/helpers";
import type { Flow, FlowsResponse, FlowStatus } from "./flowsApi";

useTableTestSetup();

const RUN = {
  id: 7, flow_id: 1, flow_name: "Hafta içi kısmi", trigger: "Zamanlanmış", state: "Durdu", step: "Veri çekme", reason: "Veri çekilemedi · Stok: SQL kaynağına ulaşılamadı.",
  scheduled_at: "2026-11-10T23:00:00+00:00", started_at: "2026-11-10T23:00:05+00:00", ended_at: "2026-11-10T23:14:00+00:00", data_version_id: null, transfer_job_id: null,
};
const STOPPED: FlowStatus = { running: null, alerts: [{ ...RUN, at: RUN.ended_at }], can_view_history: true };
const IDLE: FlowStatus = { running: null, alerts: [], can_view_history: true };
const RUNNING: FlowStatus = {
  running: { ...RUN, state: "Çalışıyor", reason: null, ended_at: null, message: "Zamanlanmış akış sürüyor: Hafta içi kısmi (başlama 02:00). Bitince yeniden deneyin." },
  alerts: [], can_view_history: true,
};
const FLOW: Flow = {
  id: 1, name: "Hafta içi kısmi", is_active: true, run_time: "02:00", days: [1, 2, 3, 4, 5], days_text: "Hafta içi", pull_scope: "Seçilen", pull_tables: ["Stock"],
  transfer_mode: "Kısmi", transfer_groups: ["Stok"], cleanup: false, updated_at: "2026-11-09T10:00:00+00:00", updated_by_name: "Mert Planlama",
  next_at: "2026-11-11T23:00:00+00:00", last: RUN,
};
const FLOWS: FlowsResponse = {
  flows: [FLOW],
  options: {
    tables: [{ entity: "Material", name: "Malzeme", method: "SQL" }, { entity: "Stock", name: "Stok", method: "SQL" }, { entity: "Customer", name: "Müşteri", method: "Excel" }],
    sql_tables: ["Material", "Stock"],
    groups: [{ name: "Talep", tables: [{ entity: "SalesOrderLine", name: "Satış siparişi" }], sql_tables: [] },
             { name: "Stok", tables: [{ entity: "Stock", name: "Stok" }, { entity: "BorrowPayback", name: "Ödünç ve geri ödeme" }], sql_tables: ["Stock"] }],
  },
  running: null, can_edit: true, settings: { FlowWaitMinutes: 60, FlowRefreshWaitMinutes: 120 },
};
const ENTITY_COLUMNS = [col("Name", "Tablo", "text", "text"), col("Method", "Yöntem", "text", "list")];
const EXPORT = { title: "Tablolar", file_slug: "tablolar", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };

function backend(routes: Routes = {}) {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/flows/status": { body: IDLE },
    "/api/flows": { body: FLOWS },
    "/api/integration-entities/columns": { body: { chunk_size: 100, columns: ENTITY_COLUMNS, export: EXPORT } },
    "/api/integration-entities/query": { body: { rows: [{ Id: 1, Entity: "Material", Name: "Malzeme", Method: "SQL" }], filtered: 1, total: 1 } },
    "/api/integration-entities/views": { body: { views: [], default_view_id: null } },
    "/api/integration/connection": { body: { database: "Kaynak", account: "SUNUCU\\smartchain", last_read: null, last_upload: null, sql_tables: 2, excel_tables: 23 } },
    "/api/data-entities/columns": { body: { chunk_size: 100, columns: ENTITY_COLUMNS, export: EXPORT } },
    "/api/data-entities/query": { body: { rows: [{ Id: 1, Entity: "Material", Name: "Malzeme", Method: "Excel", Version: 4 }], filtered: 1, total: 1 } },
    "/api/data-entities/views": { body: { views: [], default_view_id: null } },
    ...routes,
  });
}

const calls = (fetchMock: ReturnType<typeof vi.fn>, method: string, url: string) =>
  fetchMock.mock.calls.filter(([u, init]) => String(u) === url && ((init as RequestInit | undefined)?.method ?? "GET") === method);

describe("bağlam çubuğundaki akış çipi", () => {
  it("akış durunca her ekranda görünür; açınca neden; Kapat o kullanıcı için kapatır", async () => {
    let status = STOPPED;
    const fetchMock = backend({ "/api/flows/status": () => ({ body: status }), "/api/flows/runs/7/dismiss": () => { status = IDLE; return { status: 204, body: null }; } });
    renderApp("/veri/veri-yukleme", meAs("Key user"));
    const chip = await screen.findByTestId("flow-alert");
    expect(chip).toHaveTextContent(/^Gece akışı durdu · \d\d:\d\d · Veri çekme$/);
    expect(chip).toHaveClass("sc-tag--critical");
    expect(chip.closest(".sc-context-right")).not.toBeNull();
    const user = userEvent.setup();
    await user.click(chip);
    const card = screen.getByRole("dialog", { name: "Zamanlanmış akış" });
    expect(within(card).getByText(RUN.reason)).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Akış geçmişi" })).toBeInTheDocument();
    await user.click(within(card).getByRole("button", { name: "Kapat" }));
    await waitFor(() => expect(screen.queryByTestId("flow-alert")).not.toBeInTheDocument());
    expect(calls(fetchMock, "POST", "/api/flows/runs/7/dismiss")).toHaveLength(1);
  });

  it("başarılı akışta ve End user'da çip yok", async () => {
    const fetchMock = backend();
    renderApp("/veri/veri-yukleme", meAs("Key user"));
    await screen.findAllByText("Malzeme", {}, { timeout: 5000 });
    expect(screen.queryByTestId("flow-alert")).not.toBeInTheDocument();
    fetchMock.mockClear();
    renderApp("/ana-sayfa", meAs("End user"));
    await waitFor(() => expect(calls(fetchMock, "GET", "/api/flows/status")).toHaveLength(0));
  });

  it("başlamayan akış: \"Gece akışı başlamadı\"", async () => {
    backend({ "/api/flows/status": { body: { ...STOPPED, alerts: [{ ...RUN, state: "Başlamadı", step: "Başlangıç", reason: "Servis kapalıydı; akış saatinde başlamadı.", at: RUN.scheduled_at }] } } });
    renderApp("/veri/veri-yukleme", meAs("Admin"));
    expect(await screen.findByTestId("flow-alert")).toHaveTextContent(/^Gece akışı başlamadı · \d\d:\d\d$/);
  });
});

describe("akış sürerken", () => {
  it("Veri yükleme düğmeleri pasif, ipucunda akışın adı ve başlama saati", async () => {
    backend({ "/api/flows/status": { body: RUNNING } });
    renderApp("/veri/veri-yukleme", meAs("System owner"));
    await screen.findAllByText("Malzeme", {}, { timeout: 5000 });
    await waitFor(() => expect(screen.getByRole("button", { name: "Veri çek" })).toBeDisabled());
    expect(screen.getByRole("button", { name: "Veri çek" })).toHaveAttribute("title", RUNNING.running!.message);
    expect(screen.getByRole("button", { name: "Veri yükle" })).toBeDisabled();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Veri aktarma" }));
    expect(await screen.findByRole("menuitem", { name: "Tam veri aktarımı" })).toBeDisabled();
  });
});

describe("Zamanlanmış akışlar çekmecesi", () => {
  async function openDrawer(role: string, routes: Routes = {}) {
    const fetchMock = backend(routes);
    renderApp("/yonetim/entegrasyon", meAs(role));
    await screen.findByText("Malzeme", {}, { timeout: 5000 });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Zamanlanmış akışlar" }));
    await screen.findByText("Hafta içi kısmi");
    return { user, fetchMock };
  }

  it("System owner yeni akış tanımlar: adımlar sabit sırayla; kısmide Veri çek seçilen grupların SQL tabloları", async () => {
    const { user, fetchMock } = await openDrawer("System owner", { "/api/flows": (_u, init) => ({ body: init?.method === "POST" ? { ...FLOWS, id: 2 } : FLOWS }) });
    await user.click(screen.getByRole("button", { name: "Yeni akış" }));
    const dialog = screen.getByRole("dialog", { name: "Yeni akış" });
    expect([...dialog.querySelectorAll(".sc-flow-step > legend")].map((l) => l.textContent)).toEqual(["1 · Ad ve zaman", "2 · Veri çek", "3 · Aktarım", "4 · Ham veri temizliği"]);
    await user.type(within(dialog).getByRole("textbox", { name: /^Ad/ }), "Öğlen stok");
    await user.click(within(dialog).getByRole("radio", { name: "Kısmi aktarım" }));
    await user.click(within(dialog).getByRole("checkbox", { name: /^Stok \(/ }));
    expect(within(dialog).getByRole("radio", { name: "Seçilen tablolar" })).toBeChecked();
    expect(within(dialog).getByRole("checkbox", { name: "Stok" })).toBeChecked();
    expect(within(dialog).getByRole("checkbox", { name: "Malzeme" })).not.toBeChecked();
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls(fetchMock, "POST", "/api/flows")).toHaveLength(1));
    expect(JSON.parse(String(calls(fetchMock, "POST", "/api/flows")[0][1]?.body))).toEqual({
      name: "Öğlen stok", is_active: true, run_time: "02:00", days: [1, 2, 3, 4, 5], pull_scope: "Seçilen", pull_tables: ["Stock"],
      transfer_mode: "Kısmi", transfer_groups: ["Stok"], cleanup: false,
    });
  });

  it("Şimdi çalıştır onaylıdır", async () => {
    const { user, fetchMock } = await openDrawer("System owner", { "/api/flows/1/run": { body: { run_id: 9 } } });
    await user.click(screen.getByRole("button", { name: "Hafta içi kısmi için işlemler" }));
    await user.click(await screen.findByRole("menuitem", { name: "Şimdi çalıştır" }));
    const confirm = screen.getByRole("dialog", { name: "Akışı şimdi çalıştır" });
    expect(confirm).toHaveTextContent("Kısmi · Stok");
    await user.click(within(confirm).getByRole("button", { name: "Şimdi çalıştır" }));
    await waitFor(() => expect(calls(fetchMock, "POST", "/api/flows/1/run")).toHaveLength(1));
  });

  it("Admin salt okunur: Yeni akış ve Şimdi çalıştır pasif, Düzenle yerine Görüntüle", async () => {
    const { user } = await openDrawer("Admin", { "/api/flows": { body: { ...FLOWS, can_edit: false } } });
    expect(screen.getByRole("button", { name: "Yeni akış" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Hafta içi kısmi için işlemler" }));
    expect(await screen.findByRole("menuitem", { name: "Şimdi çalıştır" })).toBeDisabled();
    expect(screen.queryByRole("menuitem", { name: "Düzenle" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("menuitem", { name: "Görüntüle" }));
    expect(screen.getByRole("dialog", { name: "Hafta içi kısmi" })).toHaveTextContent("Hafta içi 02:00");
  });
});

// Veri aktarım geçmişi, Veri aktarım raporu ve ham veri temizliği (ekran 02, fonksiyon 08, 09; K-151, K-156).
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, meAs, mockApi, renderApp, type Routes } from "../test/helpers";

useTableTestSetup();

const EXPORT = { title: "Tablolar", file_slug: "tablolar", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const ENTITY_COLUMNS = [col("Name", "Tablo", "text", "text")];
const HISTORY_COLUMNS = [col("StartedAt", "Tarih", "datetime", "date"), col("TransferType", "Tür", "text", "list", { values: ["Tam", "Kısmi"] }),
                         col("Groups", "Gruplar", "text", "text"), col("DataVersionId", "Veri versiyonu", "integer", "number"),
                         col("Status", "Durum", "text", "list"), col("NewCount", "Yeni", "integer", "number")];
const HISTORY = [
  { Id: 742, StartedAt: "2026-11-10T12:04:31", TransferType: "Tam", Groups: null, DataVersionId: 60, Status: "Bitti", NewCount: 2 },
  { Id: 741, StartedAt: "2026-11-10T12:04:04", TransferType: "Kısmi", Groups: "Talep", DataVersionId: 59, Status: "Bitti", NewCount: 0 },
];
const REPORT = {
  job_id: 741, status: "Bitti", progress: "Kısmi aktarım bitti · v59", error: null, data_version: 59, transfer_type: "Kısmi", groups: ["Talep"],
  requested_by_name: "Ayşe Planlama", started_at: "2026-11-10T12:04:04", duration_seconds: 2,
  tables: [{ entity: "SalesOrderLine", name: "Satış siparişi", new: 0, changed: 1, closed: 0, not_transferred: 4,
             note: "1 satır, bağlı ana veri henüz aktarılmadığı için bekliyor (kısmi aktarım)." }],
};
const STATE = {
  retention_days: 7,
  last: { job_id: 900, status: "Bitti", requested_at: "2026-11-09T03:00:00", ended_at: "2026-11-09T03:01:00", error: null, requested_by_name: "Smartchain",
          result: { retention_days: 7, batches: 12, abandoned: 1, rows: 3400, files: 2, size: 1258291, tables: [] } },
};
const PLAN = { retention_days: 7, blocked: null,
               preview: { retention_days: 7, batches: 3, abandoned: 1, rows: 1500, files: 2, size: 2048, tables: [{ entity: "Customer", name: "Müşteri", rows: 1500 }] } };

function backend(routes: Routes = {}) {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/data-entities/columns": { body: { chunk_size: 100, columns: ENTITY_COLUMNS, export: EXPORT } },
    "/api/data-entities/query": { body: { rows: [{ Id: 1, Entity: "Material", Name: "Malzeme", Version: 4, Method: "Excel", IsPullEnabled: true }], filtered: 1, total: 1 } },
    "/api/data-entities/views": { body: { views: [], default_view_id: null } },
    "/api/transfer-history/columns": { body: { chunk_size: 100, columns: HISTORY_COLUMNS, export: { ...EXPORT, title: "Veri aktarım geçmişi" } } },
    "/api/transfer-history/query": { body: { rows: HISTORY, filtered: 2, total: 2 } },
    "/api/transfer-history/views": { body: { views: [], default_view_id: null } },
    "/api/transfers/741": { body: REPORT },
    "/api/transfers/741/excel": { body: {}, headers: { "Content-Disposition": "attachment; filename=rapor.xlsx" } },
    "/api/cleanup": { body: STATE },
    "/api/cleanup/plan": { body: PLAN },
    ...routes,
  });
}

async function open(role: string, routes: Routes = {}, path = "/veri/veri-yukleme") {
  const fetchMock = backend(routes);
  renderApp(path, meAs(role));
  await screen.findAllByText("Malzeme", {}, { timeout: 5000 });
  return { user: userEvent.setup(), fetchMock };
}

const calls = (m: ReturnType<typeof vi.fn>, url: string, method = "GET") =>
  m.mock.calls.filter(([u, init]) => String(u) === url && ((init as RequestInit | undefined)?.method ?? "GET") === method);

describe("Veri aktarım geçmişi", () => {
  it("düğmeden çekmece açılır: saklama süresi ve son temizlik, geçmiş tablosu; satıra tıklayınca rapor üst bilgisi ve Excel", async () => {
    const { user, fetchMock } = await open("Key user");
    await user.click(screen.getByRole("button", { name: "Veri aktarma" }));
    await user.click(await screen.findByRole("menuitem", { name: "Veri aktarım geçmişi" }));
    const drawer = await screen.findByRole("dialog", { name: "Veri aktarım geçmişi" });
    expect(await within(drawer).findByText(/Saklama süresi 7 gün · Son temizlik .*: 12 yükleme · 3\.400 eski satır · 2 dosya \(1,2 MB\)/)).toBeInTheDocument();
    expect(within(drawer).getByRole("button", { name: "Ham veri temizliği" })).toBeDisabled();  // yalnız System owner
    await user.click(await within(drawer).findByText("Talep"));
    const report = await screen.findByRole("dialog", { name: "Veri aktarım raporu" });
    expect(await within(report).findByText(/Kısmi · Talep · Ayşe Planlama · .* · 2 sn/)).toBeInTheDocument();
    expect(within(report).getByText("1 satır, bağlı ana veri henüz aktarılmadığı için bekliyor (kısmi aktarım).")).toBeInTheDocument();
    await user.click(within(report).getByRole("button", { name: "Excel'e aktar" }));
    await waitFor(() => expect(calls(fetchMock, "/api/transfers/741/excel")).toHaveLength(1));
  });

  it("saklama süresi yoksa çekmece söyler", async () => {
    const { user } = await open("Admin", { "/api/cleanup": { body: { retention_days: null, last: null } } });
    await user.click(screen.getByRole("button", { name: "Veri aktarma" }));
    await user.click(await screen.findByRole("menuitem", { name: "Veri aktarım geçmişi" }));
    const drawer = await screen.findByRole("dialog", { name: "Veri aktarım geçmişi" });
    expect(await within(drawer).findByText("Saklama süresi tanımlı değil; temizlik çalışmaz. · henüz temizlik yapılmadı")).toBeInTheDocument();
  });

  it("\"Sonucu aç\" adresi çekmeceyi açar", async () => {
    await open("Key user", {}, "/veri/veri-yukleme?gecmis=1");
    expect(await screen.findByRole("dialog", { name: "Veri aktarım geçmişi" })).toBeInTheDocument();
  });
});

describe("Ham veri temizliği", () => {
  it("System owner: onay penceresi silinecekleri gösterir, başlatınca iş kuyruğuna gider", async () => {
    const { user, fetchMock } = await open("System owner", { "/api/cleanup": (_u: string, init?: RequestInit) =>
      (init?.method === "POST" ? { status: 202, body: { job_id: 901 } } : { body: STATE }) });
    await user.click(screen.getByRole("button", { name: "Veri aktarma" }));
    await user.click(await screen.findByRole("menuitem", { name: "Veri aktarım geçmişi" }));
    const drawer = await screen.findByRole("dialog", { name: "Veri aktarım geçmişi" });
    await user.click(within(drawer).getByRole("button", { name: "Ham veri temizliği" }));
    const dialog = await screen.findByRole("dialog", { name: "Ham veri temizliği" });
    expect(await within(dialog).findByText("Silinecek: 3 yükleme · 1.500 eski satır · 2 dosya (2,0 KB)")).toBeInTheDocument();
    expect(within(dialog).getByText("7 günden eski yükleme kayıtları ve dosyaları silinir. Kullanılan veri ve aktarım geçmişi etkilenmez. Bu işlem geri alınamaz."))
      .toBeInTheDocument();
    expect(within(dialog).getByRole("columnheader", { name: /Silinecek eski satır/ })).toBeInTheDocument();
    expect(within(dialog).queryByText(/parti|güncel olmayan|ön kontrol|staging|işlenmiş veri|validasyon bulgu/i)).toBeNull();  // kullanıcı dili (K-157)
    await user.click(within(dialog).getByRole("button", { name: "Temizliği başlat" }));
    await waitFor(() => expect(calls(fetchMock, "/api/cleanup", "POST")).toHaveLength(1));
  });

  it("başlatılamıyorsa neden yazar, başlat pasif", async () => {
    const { user } = await open("System owner", { "/api/cleanup/plan": { body: { retention_days: null, preview: null,
      blocked: "Saklama süresi tanımlı değil; temizlik çalışmaz. Sistem ayarları'nda girin." } } });
    await user.click(screen.getByRole("button", { name: "Veri aktarma" }));
    await user.click(await screen.findByRole("menuitem", { name: "Veri aktarım geçmişi" }));
    await user.click(within(await screen.findByRole("dialog", { name: "Veri aktarım geçmişi" })).getByRole("button", { name: "Ham veri temizliği" }));
    const dialog = await screen.findByRole("dialog", { name: "Ham veri temizliği" });
    expect(await within(dialog).findByText(/Sistem ayarları'nda girin\./)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Temizliği başlat" })).toBeDisabled();
  });
});

// Tam ve kısmi aktarım (ekran 02, fonksiyon 05 ve 06; K-149…K-155): düğme ve yetki, onay penceresi, başlatma, sonuç ve "Sonucu aç".
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, meAs, mockApi, renderApp, type Routes } from "../test/helpers";

useTableTestSetup();

const COLUMNS = [col("Name", "Tablo", "text", "text"), col("Method", "Yöntem", "text", "list")];
const ROW = { Id: 1, Entity: "Material", Name: "Malzeme", Version: 4, Method: "Excel", IsPullEnabled: true, Warning: null, ViewName: null };
const PLAN = {
  blocked: null,
  tables: [
    { entity: "Material", name: "Malzeme", current_rows: 212, error_rows: 3, status: "Aktarılır", note: null },
    { entity: "Forecast", name: "Tahmin", current_rows: 0, error_rows: 0, status: "Veri gelmedi", note: "Veri gelmedi; mevcut veri korunur." },
    { entity: "Routing", name: "Rota", current_rows: 400, error_rows: 90, status: "Eşik aşıldı", note: "Hatalı satır oranı %22,5, eşik %5; tablo aktarılmadı, mevcut veri korunur." },
  ],
};
const RESULT = {
  job_id: 91, status: "Bitti", progress: "Tam aktarım bitti · v12", error: null, data_version: 12,
  tables: [
    { entity: "Material", name: "Malzeme", new: 10, changed: 2, closed: 1, not_transferred: 3, note: null },
    { entity: "Routing", name: "Rota", new: null, changed: null, closed: null, not_transferred: null, note: "Hatalı satır oranı %22,5, eşik %5; tablo aktarılmadı, mevcut veri korunur." },
  ],
};

function backend(routes: Routes = {}) {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/data-entities/columns": { body: { chunk_size: 100, columns: COLUMNS, export: { title: "Tablolar", file_slug: "tablolar", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    "/api/data-entities/query": { body: { rows: [ROW], filtered: 1, total: 1 } },
    "/api/data-entities/views": { body: { views: [], default_view_id: null } },
    "/api/transfers/plan": { body: PLAN },
    "/api/transfers/91": { body: RESULT },
    "/api/transfers": { status: 202, body: { job_id: 91 } },
    ...routes,
  });
}

async function open(role: string, routes: Routes = {}, path = "/veri/veri-yukleme") {
  const fetchMock = backend(routes);
  renderApp(path, meAs(role));
  await screen.findAllByText("Malzeme", {}, { timeout: 5000 });
  return { user: userEvent.setup(), fetchMock };
}

const posts = (fetchMock: ReturnType<typeof vi.fn>, url: string) =>
  fetchMock.mock.calls.filter(([u, init]) => String(u) === url && (init as RequestInit | undefined)?.method === "POST");

describe("Tam aktar", () => {
  it("Key user onaylar: tablolar, aktarılmayanlar ve not; başlatınca sonuç penceresi sayıları ve veri versiyonunu gösterir", async () => {
    const { user, fetchMock } = await open("Key user");
    await user.click(screen.getByRole("button", { name: "Tam aktar" }));
    const dialog = await screen.findByRole("dialog", { name: "Tam aktarım" });
    expect(await within(dialog).findByText("1 tablo aktarılacak")).toBeInTheDocument();
    expect(within(dialog).getAllByText("Aktarılmaz")).toHaveLength(2);
    expect(within(dialog).getByText("Hatalı satır oranı %22,5, eşik %5; tablo aktarılmadı, mevcut veri korunur.")).toBeInTheDocument();
    expect(within(dialog).queryByText(/Açık çalışmalar|core|staging/i)).not.toBeInTheDocument();  // açıklama bandı yok; iç terimler yok (K-154)
    await user.click(within(dialog).getByRole("button", { name: "Aktarımı başlat" }));
    await waitFor(() => expect(posts(fetchMock, "/api/transfers")).toHaveLength(1));
    const result = await screen.findByRole("dialog", { name: "Veri aktarım raporu" });
    expect(await within(result).findByText("Bitti · Veri v12")).toBeInTheDocument();
    const row = within(result).getByText("Malzeme").closest("tr")!;
    expect(within(row).getAllByRole("cell").map((c) => c.textContent)).toEqual(["Malzeme", "10", "2", "1", "3", ""]);
  });

  it("başlatılamıyorsa neden ve tablolar yazar, başlat pasif", async () => {
    const { user } = await open("Admin", { "/api/transfers/plan": { body: { ...PLAN, blocked: { reason: "Validasyonu bitmemiş tablo var; önce valide edin.", tables: ["Malzeme"] } } } });
    await user.click(screen.getByRole("button", { name: "Tam aktar" }));
    const dialog = await screen.findByRole("dialog", { name: "Tam aktarım" });
    expect(await within(dialog).findByText(/Validasyonu bitmemiş tablo var; önce valide edin\. Tablolar: Malzeme\./)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Aktarımı başlat" })).toBeDisabled();
  });

  it.each(["Key user", "Admin", "System owner"])("%s için düğme etkin, Veri çek'in yanında ikincil (End user ekranı açamaz)", async (role) => {
    await open(role);
    const button = screen.getByRole("button", { name: "Tam aktar" });
    expect(button).toBeEnabled();
    expect(button.className).toContain("sc-btn--secondary");
  });

  it("\"Sonucu aç\" adresi sonuç penceresini açar", async () => {
    await open("Key user", {}, "/veri/veri-yukleme?aktarim=91");
    const result = await screen.findByRole("dialog", { name: "Veri aktarım raporu" });
    expect(await within(result).findByText("Hatalı satır oranı %22,5, eşik %5; tablo aktarılmadı, mevcut veri korunur.")).toBeInTheDocument();
  });
});

// Kısmi aktarım (fonksiyon 06; K-150, K-155): ayrı düğme, grup seçimi (hiçbiri seçili açılır), engel seçime göre.
const row = (entity: string, name: string, status = "Aktarılır", current = 10) =>
  ({ entity, name, current_rows: current, error_rows: 0, status, note: status === "Aktarılır" ? null : "Veri gelmedi; mevcut veri korunur." });
const PARTIAL = {
  busy: null,
  pending: ["Stock"],
  groups: [
    { name: "Talep", tables: [row("SalesOrderLine", "Satış siparişi"), row("Forecast", "Tahmin", "Veri gelmedi", 0), row("ProjectGroup", "Proje grubu", "Veri gelmedi", 0), row("Project", "Proje", "Veri gelmedi", 0)] },
    { name: "Stok", tables: [row("Stock", "Stok"), row("BorrowPayback", "Ödünç ve geri ödeme", "Veri gelmedi", 0)] },
    { name: "Üretim", tables: [row("WorkOrder", "İş emri")] },
    { name: "Satın alma", tables: [row("PurchaseOrderLine", "Satın alma siparişi")] },
    { name: "İzin", tables: [row("EmployeeAbsence", "Çalışan izni")] },
  ],
};

describe("Kısmi aktar", () => {
  const partialRoutes = { "/api/transfers/partial/plan": { body: PARTIAL }, "/api/transfers/partial": { status: 202, body: { job_id: 91 } } };

  it("hiçbir grup seçili açılır; seçince tabloları gelir, başlatınca seçilen gruplar gider ve rapor açılır", async () => {
    const { user, fetchMock } = await open("Key user", partialRoutes);
    await user.click(screen.getByRole("button", { name: "Kısmi aktar" }));
    const dialog = await screen.findByRole("dialog", { name: "Kısmi aktarım" });
    expect(await within(dialog).findByText("En az bir grup seçin.")).toBeInTheDocument();
    expect(within(dialog).getAllByRole("checkbox").filter((c) => (c as HTMLInputElement).checked)).toHaveLength(0);
    expect(within(dialog).getByRole("button", { name: "Aktarımı başlat" })).toBeDisabled();
    await user.click(within(dialog).getByRole("checkbox", { name: /^Talep · Satış siparişi, Tahmin/ }));
    expect(await within(dialog).findByText("1 tablo aktarılacak; ana veri aktarılmaz")).toBeInTheDocument();
    expect(within(dialog).getAllByText("Aktarılmaz")).toHaveLength(3);
    await user.click(within(dialog).getByRole("checkbox", { name: /^İzin/ }));
    await user.click(within(dialog).getByRole("button", { name: "Aktarımı başlat" }));
    await waitFor(() => expect(posts(fetchMock, "/api/transfers/partial")).toHaveLength(1));
    expect(JSON.parse(String((posts(fetchMock, "/api/transfers/partial")[0][1] as RequestInit).body))).toEqual({ groups: ["Talep", "İzin"] });
    expect(await screen.findByRole("dialog", { name: "Veri aktarım raporu" })).toBeInTheDocument();
  });

  it("seçilen grupta validasyonu bitmemiş tablo varsa neden yazar, başlat pasif; süren iş her seçimde engeller", async () => {
    const { user } = await open("Admin", partialRoutes);
    await user.click(screen.getByRole("button", { name: "Kısmi aktar" }));
    const dialog = await screen.findByRole("dialog", { name: "Kısmi aktarım" });
    await user.click(await within(dialog).findByRole("checkbox", { name: /^Stok/ }));
    expect(within(dialog).getByText(/Seçilen gruplarda validasyonu bitmemiş tablo var; önce valide edin\. Tablolar: Stok\./)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Aktarımı başlat" })).toBeDisabled();
    await user.click(within(dialog).getByRole("checkbox", { name: /^Stok/ }));
    await user.click(within(dialog).getByRole("checkbox", { name: /^Üretim/ }));
    expect(within(dialog).queryByText(/validasyonu bitmemiş/)).not.toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Aktarımı başlat" })).toBeEnabled();
  });

  it("süren iş varsa neden yazar", async () => {
    const { user } = await open("Key user", { ...partialRoutes, "/api/transfers/partial/plan": { body: { ...PARTIAL, busy: "Validasyon sürüyor. Bitince aktarımı başlatabilirsiniz." } } });
    await user.click(screen.getByRole("button", { name: "Kısmi aktar" }));
    const dialog = await screen.findByRole("dialog", { name: "Kısmi aktarım" });
    expect(await within(dialog).findByText("Validasyon sürüyor. Bitince aktarımı başlatabilirsiniz.")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("checkbox", { name: /^Üretim/ }));
    expect(within(dialog).getByRole("button", { name: "Aktarımı başlat" })).toBeDisabled();
  });

  it.each(["Key user", "Admin", "System owner"])("%s için düğme etkin ve ikincil", async (role) => {
    await open(role, partialRoutes);
    const button = screen.getByRole("button", { name: "Kısmi aktar" });
    expect(button).toBeEnabled();
    expect(button.className).toContain("sc-btn--secondary");
  });
});

// Tam aktarım (ekran 02, fonksiyon 05; K-149…K-153): düğme ve yetki, onay penceresi, başlatma, sonuç ve "Sonucu aç".
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
    const result = await screen.findByRole("dialog", { name: "Aktarım sonucu" });
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
    const result = await screen.findByRole("dialog", { name: "Aktarım sonucu" });
    expect(await within(result).findByText("Hatalı satır oranı %22,5, eşik %5; tablo aktarılmadı, mevcut veri korunur.")).toBeInTheDocument();
  });
});

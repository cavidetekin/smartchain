// Veri yükleme iskeleti (ekran 02; K-110): ekran kapısı, satır menüsü, şablon indirme, Şablon bilgisi penceresi.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, meAs, mockApi, renderApp, type Reply } from "../test/helpers";
import type { TemplateInfo } from "./dataLoadApi";

useTableTestSetup();

const COLUMNS = [
  col("Name", "Tablo", "text", "text"), col("EntityClass", "Kategori", "text", "list"), col("Description", "Açıklama", "text", "text"),
];
const ROWS = [{ Id: 9, Entity: "Resource", Name: "Kaynak", EntityClass: "Ana veri", Description: "Makine, işçi ve fason kaynakları ve kapasiteleri", Version: 1 }];
const INFO: TemplateInfo = {
  entity: "Resource", name: "Kaynak", version: 1, file_name: "smartchain_kaynak_v1.xlsx", field_count: 15,
  required: ["Lokasyon kodu", "Kaynak kodu"],
};

function backend(routes: Record<string, Reply> = {}) {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/data-entities/columns": { body: { chunk_size: 100, columns: COLUMNS, export: { title: "Tablolar", file_slug: "tablolar", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    "/api/data-entities/query": { body: { rows: ROWS, filtered: 1, total: 1 } },
    "/api/data-entities/views": { body: { views: [], default_view_id: null } },
    "/api/templates/Resource/info": { body: INFO as unknown as Reply["body"] },
    ...routes,
  });
}

async function openMenu(role = "Key user", routes: Record<string, Reply> = {}) {
  const user = userEvent.setup();
  backend(routes);
  renderApp("/veri/veri-yukleme", meAs(role));
  await screen.findByText("Kaynak", {}, { timeout: 5000 });
  await user.click(screen.getByRole("button", { name: "Kaynak işlemleri" }));
  return { user, menu: await screen.findByRole("menu") };
}

function fetched(): string[] {
  return vi.mocked(fetch).mock.calls.map(([url]) => String(url));
}

describe("ekran 02", () => {
  it.each(["System owner", "Admin", "Key user"])("%s açar", async (role) => {
    backend();
    renderApp("/veri/veri-yukleme", meAs(role));
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Veri yükleme");
    expect(await screen.findByText("Kaynak", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByText("Makine, işçi ve fason kaynakları ve kapasiteleri")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/K-\d+/);
  });

  it("End user açamaz", async () => {
    backend();
    renderApp("/veri/veri-yukleme", meAs("End user"));
    expect(await screen.findByText(/Bu ekranı açma yetkiniz yok/)).toBeInTheDocument();
    expect(screen.queryByText("Kaynak")).not.toBeInTheDocument();
  });

  it("satır menüsü: şablon, bilgi ve tek dosyalık yükleme etkin; \"Son Excel yüklemesini gör\" yok (K-158)", async () => {
    const { menu } = await openMenu();
    const item = (name: string | RegExp) => within(menu).getByRole("menuitem", { name });
    expect(item("Şablonu indir (v1)")).toBeEnabled();
    expect(item("Şablon bilgisi")).toBeEnabled();
    expect(item("Excel'den yükle")).toBeEnabled();
    expect(item("Excel'den yükle")).not.toHaveAttribute("title");
    expect(within(menu).queryByRole("menuitem", { name: "Son Excel yüklemesini gör" })).toBeNull();
  });

  it("şablon tek tıkla iner", async () => {
    const { user, menu } = await openMenu("Key user", { "/api/templates/Resource": { body: {} } });
    await user.click(within(menu).getByRole("menuitem", { name: "Şablonu indir (v1)" }));
    await waitFor(() => expect(fetched()).toContain("/api/templates/Resource"));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("indirme hatası görünür", async () => {
    const { user, menu } = await openMenu("Key user", {
      "/api/templates/Resource": { status: 503, body: { error: { code: "audit_failed", message: "İşlem yapılamadı: denetim kaydı yazılamadı." } } },
    });
    await user.click(within(menu).getByRole("menuitem", { name: "Şablonu indir (v1)" }));
    expect(await screen.findByText("İşlem yapılamadı: denetim kaydı yazılamadı.")).toBeInTheDocument();
  });

  it("Şablon bilgisi penceresi", async () => {
    const { user, menu } = await openMenu("Key user", { "/api/templates/Resource": { body: {} } });
    await user.click(within(menu).getByRole("menuitem", { name: "Şablon bilgisi" }));
    const dialog = await screen.findByRole("dialog", { name: "Şablon bilgisi" });
    expect(await within(dialog).findByText("smartchain_kaynak_v1.xlsx")).toBeInTheDocument();
    expect(within(dialog).getByText("Lokasyon kodu, Kaynak kodu")).toBeInTheDocument();
    expect(within(dialog).getByText("Toplam alan")).toBeInTheDocument();
    expect(within(dialog).queryByText("Varsayımlar")).not.toBeInTheDocument();
    expect(within(dialog).queryByText("Kod listeleri")).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "İndir" }));
    await waitFor(() => expect(fetched()).toContain("/api/templates/Resource"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("değeri olmayan satır görünmez", async () => {
    const empty = { ...INFO, required: [] };
    const { user, menu } = await openMenu("Key user", { "/api/templates/Resource/info": { body: empty as unknown as Reply["body"] } });
    await user.click(within(menu).getByRole("menuitem", { name: "Şablon bilgisi" }));
    const dialog = await screen.findByRole("dialog", { name: "Şablon bilgisi" });
    await within(dialog).findByText("smartchain_kaynak_v1.xlsx");
    expect(within(dialog).queryByText("Zorunlu alan")).not.toBeInTheDocument();
    expect(within(dialog).queryByText("Yok")).not.toBeInTheDocument();
  });
});

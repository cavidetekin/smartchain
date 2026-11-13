// Denetim izi (ekran 26; K-108): ekran kapısı, rozet, detay, nesne geçmişi.
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, meAs, mockApi, renderApp, type Reply } from "../test/helpers";
import type { AuditDetail } from "./auditLogApi";

useTableTestSetup();

const COLUMNS = [
  col("At", "Zaman", "datetime", "date"), col("ActorName", "Kullanıcı", "text", "list", { values_from_server: true }),
  col("Action", "İşlem", "text", "list", { values_from_server: true }), col("ObjectShown", "Nesne", "text", "text"),
  col("OldText", "Eski değer", "text", "text"), col("NewText", "Yeni değer", "text", "text"),
];
const ROWS = [
  { Id: 7, At: "2026-11-03T15:47:03+00:00", ActorName: "Smartchain", Action: "Ayar değişikliği", ObjectShown: "Disk uyarı eşiği (%)", OldText: "Değer: 85", NewText: "Değer: 30" },
  { Id: 6, At: "2026-11-03T15:33:58+00:00", ActorName: "Ayşe", Action: "İş iptali", ObjectShown: "528", OldText: "Durum: Sırada", NewText: "Durum: İptal" },
];
const DETAIL: AuditDetail = {
  id: 6, at: "2026-11-03T15:33:58+00:00", actor: "Ayşe", action: "İş iptali", object_type: "İş", object: "528", has_object: true,
  changes: [{ field: "Durum", old: "Sırada", new: "İptal" }, { field: "Neden", old: "—", new: "Kuyruk boşalıyor" }],
};

function backend(routes: Record<string, Reply> = {}) {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/audit-log/columns": { body: { chunk_size: 100, columns: COLUMNS, export: { title: "Denetim izi", file_slug: "denetim-izi", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    "/api/audit-log/query": { body: { rows: ROWS, filtered: 2, total: 2 } },
    "/api/audit-log/views": { body: { views: [], default_view_id: null } },
    "/api/audit-log/6": { body: DETAIL as unknown as Reply["body"] },
    ...routes,
  });
}

async function openScreen(role = "Admin", routes: Record<string, Reply> = {}) {
  const user = userEvent.setup();
  backend(routes);
  renderApp("/yonetim/denetim-izi", meAs(role));
  await screen.findByText("Ayşe", {}, { timeout: 5000 });
  return user;
}

/** Ayşe'nin satırının (ikinci satır) detayı. */
async function openRow(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getAllByRole("button", { name: "Kayıt detayı" })[1]);  // ⋯ menüsü (K-171)
  await user.click(await screen.findByRole("menuitem", { name: "Detay" }));
  return screen.findByRole("dialog", { name: "Kayıt detayı" });
}

describe("ekran", () => {
  it("başlık, satırlar; silinemez etiketi yok", async () => {
    await openScreen();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Denetim izi");
    expect(screen.queryByText("Silinemez")).not.toBeInTheDocument();
    expect(screen.getByText("Durum: Sırada")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/K-\d+/);
  });

  it.each(["System owner", "Admin", "Key user"])("%s açar", async (role) => {
    await openScreen(role);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Denetim izi");
  });

  it("End user açamaz", () => {
    backend();
    renderApp("/yonetim/denetim-izi", meAs("End user"));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Bu ekranı açma yetkiniz yok");
  });
});

describe("detay", () => {
  it("alan, eski ve yeni yan yana", async () => {
    const dialog = await openRow(await openScreen());
    const table = await within(dialog).findByRole("table", { name: "Değişiklikler" });
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Alan", "Eski değer", "Yeni değer"]);
    const row = within(table).getByRole("row", { name: /^Neden/ });
    expect([...row.children].map((c) => c.textContent)).toEqual(["Neden", "—", "Kuyruk boşalıyor"]);
    expect(dialog).toHaveTextContent("Ayşe");
    expect(dialog).toHaveTextContent("03.11.2026");
    expect(within(dialog).queryByRole("button", { name: "Vazgeç" })).toBeNull();
  });

  it("nesne geçmişi: zaman sırası, kayda geçiş, geri", async () => {
    const user = await openScreen("Admin", {
      "/api/audit-log/6/history": { body: { truncated: false, rows: [
        { id: 5, at: "2026-11-03T15:30:00+00:00", actor: "Mert", action: "İş öne alma" },
        { id: 6, at: "2026-11-03T15:33:58+00:00", actor: "Ayşe", action: "İş iptali" },
      ] } },
      "/api/audit-log/5": { body: { ...DETAIL, id: 5, actor: "Mert", action: "İş öne alma", changes: [] } as unknown as Reply["body"] },
    });
    const dialog = await openRow(user);
    await user.click(await within(dialog).findByRole("button", { name: "Bu nesnenin tüm geçmişi" }));
    const table = await within(dialog).findByRole("table", { name: "Bu nesnenin tüm geçmişi" });
    expect(within(table).getAllByRole("row").slice(1).map((r) => r.children[2].textContent)).toEqual(["İş öne alma", "İş iptali"]);

    await user.click(within(dialog).getByRole("button", { name: "Geri" }));
    expect(await within(dialog).findByRole("table", { name: "Değişiklikler" })).toBeInTheDocument();

    await user.click(within(dialog).getByRole("button", { name: "Bu nesnenin tüm geçmişi" }));
    const again = await within(dialog).findByRole("table", { name: "Bu nesnenin tüm geçmişi" });
    await user.click(within(again).getAllByRole("button")[0]);
    await waitFor(() => expect(dialog).toHaveTextContent("Mert"));
  });

  it("nesnesi yoksa geçmiş pasif, nedeni ipucunda", async () => {
    const dialog = await openRow(await openScreen("Admin", { "/api/audit-log/6": { body: { ...DETAIL, has_object: false } as unknown as Reply["body"] } }));
    const button = await within(dialog).findByRole("button", { name: "Bu nesnenin tüm geçmişi" });
    expect(button).toHaveAttribute("title", "Bu kaydın nesnesi yok.");
  });

  it("kayıt bulunamazsa uyarı", async () => {
    const dialog = await openRow(await openScreen("Key user", { "/api/audit-log/6": { status: 404, body: { error: { code: "audit_not_found", message: "Kayıt bulunamadı.", trace_id: "t", details: [] } } } }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Kayıt bulunamadı.");
  });
});

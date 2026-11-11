// Dünden bugüne (ekran 28, fonksiyon 101; K-159, K-160, K-161): üst tablo, "—" ve "Önceki veri yok", ana–detay düzeni (üç sekme, ilk dolu sekme, kapatma, ayraç), End user görür.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, meAs, mockApi, renderApp, type Routes } from "../test/helpers";

useTableTestSetup();

const EXPORT = { title: "Dünden bugüne", file_slug: "dunden-bugune", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const list = (columns: unknown[], rows: unknown[]) => ({
  columns: { body: { chunk_size: 100, columns, export: EXPORT } },
  query: { body: { rows, filtered: rows.length, total: rows.length } },
  views: { body: { views: [], default_view_id: null } },
});
const routesOf = (name: string, l: ReturnType<typeof list>): Routes => ({
  [`/api/${name}/columns`]: l.columns, [`/api/${name}/query`]: l.query, [`/api/${name}/views`]: l.views,
});

const COLUMNS = [col("Name", "Tablo", "text", "text"), col("YesterdayAt", "Dünkü veri", "datetime", "date"), col("TodayLoad", "Bugünkü yükleme", "text", "list"),
                 col("YesterdayRows", "Dünkü satır", "integer", "number"), col("ChangePct", "Değişim %", "number", "number"), col("NewCount", "Yeni gelen", "integer", "number"),
                 col("State", "Durum", "text", "list")];
const ROWS = [
  { Id: 1, Entity: "Material", Name: "Malzeme", YesterdayAt: "2026-11-10T12:00:00", TodayLoad: "Karma", YesterdayRows: 200, ChangePct: 0.075, NewCount: 15, MissingCount: 0, ChangedCount: 3, State: "Hazır" },
  { Id: 3, Entity: "BOM", Name: "Ürün ağacı", YesterdayAt: "2026-11-10T12:00:00", TodayLoad: "Tam", YesterdayRows: 10, ChangePct: 0, NewCount: 0, MissingCount: 0, ChangedCount: 4, State: "Hazır" },
  { Id: 4, Entity: "Customer", Name: "Müşteri", YesterdayAt: "2026-11-10T12:00:00", TodayLoad: "Tam", YesterdayRows: 5, ChangePct: 0, NewCount: 0, MissingCount: 0, ChangedCount: 0, State: "Hazır" },
  { Id: 2, Entity: "Routing", Name: "Rota", YesterdayAt: null, TodayLoad: "Tam", YesterdayRows: null, ChangePct: null, NewCount: null, MissingCount: null, ChangedCount: null, State: "Önceki veri yok" },
];

function backend() {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    ...routesOf("raw-compare", list(COLUMNS, ROWS)),
    ...routesOf("raw-compare-new-Material", list([col("RowKey", "Kayıt", "text", "text", { default_visible: false }), col("Name", "Malzeme adı", "text", "text")], [{ Id: 11, RowKey: "ORM-01 · MAM-096", Name: "Yeni ürün" }])),
    ...routesOf("raw-compare-new-Customer", list([col("Name", "Müşteri adı", "text", "text")], [])),
    ...routesOf("raw-compare-missing-Material", list([col("RowKey", "Kayıt", "text", "text")], [{ Id: 12, RowKey: "ORM-01 · MAM-001" }])),
    ...routesOf("raw-compare-changes", list([col("RowKey", "Kayıt", "text", "text"), col("FieldLabel", "Alan", "text", "text"), col("OldValue", "Dünkü değer", "text", "text"), col("NewValue", "Bugünkü değer", "text", "text")],
                                            [{ Id: 13, RowKey: "ORM-01 · MAM-002", FieldLabel: "Ad", OldValue: "Eski ad", NewValue: "Yeni ad" }])),
  });
}

async function open(role: string) {
  const fetchMock = backend();
  renderApp("/veri/dunden-bugune", meAs(role));
  await screen.findByText("Malzeme", {}, { timeout: 5000 });
  return { user: userEvent.setup(), fetchMock };
}

describe("Dünden bugüne", () => {
  it.each(["End user", "Key user", "Admin", "System owner"])("%s görür", async (role) => {
    await open(role);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Dünden bugüne");
  });

  it("karşılaştırma alanları; önceki verisi olmayan tabloda — ve durum", async () => {
    await open("Key user");
    const material = screen.getByText("Malzeme").closest("tr")!;
    expect(within(material).getByText("Karma")).toBeInTheDocument();
    expect(within(material).getByText(/%7,5/)).toBeInTheDocument();
    const routing = screen.getByText("Rota").closest("tr")!;
    expect(within(routing).getByText("Önceki veri yok")).toBeInTheDocument();
    expect(within(routing).getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });

  it("satır seçilince üç sekme; Güncellenenler tabloyla süzülür", async () => {
    const { user, fetchMock } = await open("End user");
    expect(screen.queryByRole("radio", { name: /Yeni gelenler/ })).toBeNull();
    await user.click(screen.getByText("Malzeme"));
    expect(await screen.findByRole("heading", { level: 2, name: "Malzeme" })).toBeInTheDocument();
    expect(await screen.findByText("Yeni ürün")).toBeInTheDocument();
    expect(screen.queryByText("ORM-01 · MAM-096")).toBeNull();                               // Kayıt varsayılan gizli (K-161)
    await user.click(screen.getByRole("radio", { name: "Gelmeyenler · 0" }));
    expect(await screen.findByText("ORM-01 · MAM-001")).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Güncellenenler · 3" }));
    expect(await screen.findByText("Eski ad")).toBeInTheDocument();
    expect(screen.getByText("Yeni ad")).toBeInTheDocument();
    await waitFor(() => {
      const body = (vi.mocked(fetchMock).mock.calls.filter(([u]) => String(u).startsWith("/api/raw-compare-changes/query")).pop()?.[1] as RequestInit | undefined)?.body;
      expect(JSON.parse(String(body)).filters).toEqual(expect.arrayContaining([expect.objectContaining({ field: "EntityName", value: "Material" })]));
    });
  });

  it("önceki verisi olmayan satır seçilmez", async () => {
    const { user } = await open("Key user");
    await user.click(screen.getByText("Rota"));
    expect(screen.queryByRole("heading", { level: 2, name: "Rota" })).toBeNull();
  });
});

describe("ana–detay düzeni (K-161)", () => {
  const card = (name: string) => screen.findByRole("heading", { level: 2, name });
  const noCard = (name: string) => expect(screen.queryByRole("heading", { level: 2, name })).toBeNull();

  it("kart kayıt olan ilk sekmeyle açılır; hepsi 0 ise ilk sekme; başka satırda yeniden hesaplanır", async () => {
    const { user } = await open("Key user");
    await user.click(screen.getByText("Ürün ağacı"));
    await card("Ürün ağacı");
    expect(screen.getByRole("radio", { name: "Güncellenenler · 4" })).toBeChecked();
    await user.click(screen.getByText("Müşteri"));
    await card("Müşteri");
    expect(screen.getByRole("radio", { name: "Yeni gelenler · 0" })).toBeChecked();
  });

  it("× kapatır, üst tablo tüm yüksekliği alır, seçim işareti kalkar", async () => {
    const { user } = await open("Key user");
    await user.click(screen.getByText("Malzeme"));
    await card("Malzeme");
    const row = screen.getByText("Malzeme", { selector: "td *, td" }).closest("tr")!;
    expect(row).toHaveClass("is-selected");
    await user.click(screen.getByRole("button", { name: "Kapat" }));
    noCard("Malzeme");
    expect(screen.queryByRole("separator", { name: "Tablo yükseklikleri" })).toBeNull();
    expect(row).not.toHaveClass("is-selected");
    expect(document.querySelector<HTMLElement>(".sc-md-pane")!.style.flexGrow).toBe("1");
  });

  it("Esc ve seçili satıra yeniden tıklama kapatır", async () => {
    const { user } = await open("Key user");
    await user.click(screen.getByText("Malzeme"));
    await card("Malzeme");
    await user.keyboard("{Escape}");
    noCard("Malzeme");
    await user.click(screen.getByText("Malzeme"));
    await card("Malzeme");
    await user.click(screen.getByText("Malzeme", { selector: "td *, td" }));
    noCard("Malzeme");
  });

  it("açık pencere varken Esc kartı kapatmaz", async () => {
    const { user } = await open("Key user");
    await user.click(screen.getByText("Malzeme"));
    await card("Malzeme");
    const overlay = document.createElement("div");
    overlay.className = "sc-floating";
    document.body.appendChild(overlay);
    await user.keyboard("{Escape}");
    await card("Malzeme");
    overlay.remove();
    await user.keyboard("{Escape}");
    noCard("Malzeme");
  });

  it("ayraç klavyeyle ve sürükleyerek değişir, oran hatırlanır, sınırı aşmaz", async () => {
    const { user } = await open("Key user");
    await user.click(screen.getByText("Malzeme"));
    await card("Malzeme");
    const splitter = screen.getByRole("separator", { name: "Tablo yükseklikleri" });
    expect(splitter).toHaveAttribute("aria-valuenow", "50");
    splitter.focus();
    await user.keyboard("{ArrowDown}");
    expect(splitter).toHaveAttribute("aria-valuenow", "55");
    expect(localStorage.getItem("smartchain.pane.raw-compare")).toBe("0.55");
    const root = document.querySelector<HTMLElement>(".sc-md")!;
    vi.spyOn(root, "getBoundingClientRect").mockReturnValue({ top: 100, height: 400 } as DOMRect);
    fireEvent.mouseDown(splitter);
    fireEvent.mouseMove(document, { clientY: 200 });
    expect(splitter).toHaveAttribute("aria-valuenow", "25");
    fireEvent.mouseMove(document, { clientY: 110 });
    expect(splitter).toHaveAttribute("aria-valuenow", "15");
    fireEvent.mouseUp(document);
    expect(localStorage.getItem("smartchain.pane.raw-compare")).toBe("0.15");
    localStorage.removeItem("smartchain.pane.raw-compare");
  });
});

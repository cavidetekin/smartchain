// Veri yükle (birden çok Excel dosyası) ve tablodaki "Son aktarım" ile "Yeni veri" (ekran 02; K-158).
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, meAs, mockApi, renderApp, type Routes } from "../test/helpers";

useTableTestSetup();

const COLUMNS = [col("Name", "Tablo", "text", "text"), col("LastTransferAt", "Son aktarım", "datetime", "date"), col("HasNewData", "Yeni veri", "bool", "list")];
const ROWS = [
  { Id: 1, Entity: "Material", Name: "Malzeme", Version: 4, LastTransferAt: "2026-11-10T09:04:00", LastTransferType: "Kısmi", HasNewData: true },
  { Id: 2, Entity: "Routing", Name: "Rota", Version: 2, LastTransferAt: null, LastTransferType: null, HasNewData: false },
];
const summary = (batch: number, entity: string, name: string, read: number, errors: number) => ({
  batch_id: batch, entity, name, file_name: `${entity}.xlsx`, mode: "Değişen", status: "Ön kontrol", checked: true, template_version: 1, current_version: 1,
  read, valid: read - errors, errors, notes: 0, file_findings: [], job: null,
});

function backend(routes: Routes = {}) {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/data-entities/columns": { body: { chunk_size: 100, columns: COLUMNS, export: { title: "Tablolar", file_slug: "tablolar", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    "/api/data-entities/query": { body: { rows: ROWS, filtered: 2, total: 2 } },
    "/api/data-entities/views": { body: { views: [], default_view_id: null } },
    ...routes,
  });
}

const file = (name: string) => new File(["x"], name, { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
const posts = (m: ReturnType<typeof vi.fn>) =>
  m.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "POST").map(([u, init]) => ({ url: String(u), body: (init as RequestInit).body }));

async function open(routes: Routes = {}) {
  const fetchMock = backend(routes);
  renderApp("/veri/veri-yukleme", meAs("Key user"));
  await screen.findAllByText("Malzeme", {}, { timeout: 5000 });
  return { user: userEvent.setup(), fetchMock };
}

describe("Son aktarım ve Yeni veri", () => {
  it("son aktarım zamanı ve türü; hiç yazılmadıysa —; yeni veri çipi", async () => {
    await open();
    const material = screen.getAllByText("Malzeme")[0].closest("tr")!;
    expect(within(material).getByText(/10\.11\.2026 \d{2}:\d{2} · Kısmi/)).toBeInTheDocument();
    expect(within(material).getByText("Yeni veri")).toBeInTheDocument();
    const routing = screen.getByText("Rota").closest("tr")!;
    expect(within(routing).getByText("—")).toBeInTheDocument();
    expect(within(routing).queryByText("Yeni veri")).toBeNull();
  });
});

describe("Veri yükle", () => {
  it("birden çok dosya tek listede: tablo dosyadan, ret nedeni satırda, mod dosya başına; Devam geçenleri modlarıyla alır", async () => {
    let n = 0;
    const replies = [
      { status: 200, body: summary(41, "Material", "Malzeme", 10, 2) },
      { status: 409, body: { error: { code: "import_duplicate", message: "Aynı tabloya ikinci dosya (Malzeme); bir tabloya tek dosya yüklenir.", details: [{ entity: "Material", name: "Malzeme" }] } } },
      { status: 422, body: { error: { code: "import_unknown_template", message: "Dosyanın tablosu anlaşılamadı: şablon bilgisi yok. Şablonu indirip doldurun.", details: [] } } },
      { status: 200, body: summary(42, "Customer", "Müşteri", 5, 0) },
    ];
    const { user, fetchMock } = await open({
      "/api/imports?": () => replies[n++],
      "/api/imports/41/continue": { body: summary(41, "Material", "Malzeme", 10, 2) },
      "/api/imports/42/continue": { body: summary(42, "Customer", "Müşteri", 5, 0) },
    });
    expect(screen.getByRole("button", { name: "Veri yükle" }).className).toContain("sc-btn--primary");
    fireEvent.change(screen.getByTestId("veri-yukle-dosya"), { target: { files: [file("malzeme.xlsx"), file("malzeme2.xlsx"), file("eski.xlsx"), file("musteri.xlsx")] } });
    const dialog = await screen.findByRole("dialog", { name: "Veri yükle" });
    expect(await within(dialog).findByText("4 dosya · 2 dosya devam etmeye hazır")).toBeInTheDocument();
    const row = (name: string) => within(dialog).getByText(name).closest("tr")!;
    expect(within(row("malzeme.xlsx")).getByText("Hatalı satır var")).toBeInTheDocument();
    expect(within(row("malzeme2.xlsx")).getByText("Aynı tabloya ikinci dosya (Malzeme); bir tabloya tek dosya yüklenir.")).toBeInTheDocument();
    expect(within(row("eski.xlsx")).getByText("Reddedildi")).toBeInTheDocument();
    expect(within(row("musteri.xlsx")).getByText("Müşteri")).toBeInTheDocument();
    const skip = posts(fetchMock).filter((p) => p.url.startsWith("/api/imports?")).map((p) => new URLSearchParams(p.url.split("?")[1]).get("skip"));
    expect(skip).toEqual(["", "Material", "Material", "Material"]);                               // kabul edilen tablolar sunucuya söylenir
    await user.selectOptions(within(row("musteri.xlsx")).getByRole("combobox", { name: "musteri.xlsx yükleme modu" }), "Tam");
    await user.click(within(dialog).getByRole("button", { name: "2 dosyayla devam et" }));
    await waitFor(() => expect(posts(fetchMock).filter((p) => p.url.endsWith("/continue"))).toHaveLength(2));
    const bodies = posts(fetchMock).filter((p) => p.url.endsWith("/continue")).map((p) => [p.url, JSON.parse(String(p.body))]);
    expect(bodies).toEqual([["/api/imports/41/continue", { mode: "Değişen" }], ["/api/imports/42/continue", { mode: "Tam" }]]);
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Veri yükle" })).toBeNull());
  });

  it("Vazgeç kontrol edilen bütün dosyaları bırakır", async () => {
    let n = 0;
    const replies = [{ status: 200, body: summary(51, "Material", "Malzeme", 3, 0) }, { status: 200, body: summary(52, "Customer", "Müşteri", 3, 0) }];
    const { user, fetchMock } = await open({
      "/api/imports?": () => replies[n++],
      "/api/imports/51/cancel": { body: summary(51, "Material", "Malzeme", 3, 0) },
      "/api/imports/52/cancel": { body: summary(52, "Customer", "Müşteri", 3, 0) },
    });
    fireEvent.change(screen.getByTestId("veri-yukle-dosya"), { target: { files: [file("a.xlsx"), file("b.xlsx")] } });
    const dialog = await screen.findByRole("dialog", { name: "Veri yükle" });
    await within(dialog).findByText("2 dosya · 2 dosya devam etmeye hazır");
    await user.click(within(dialog).getByRole("button", { name: "Vazgeç" }));
    await waitFor(() => expect(posts(fetchMock).filter((p) => p.url.endsWith("/cancel")).map((p) => p.url)).toEqual(["/api/imports/51/cancel", "/api/imports/52/cancel"]));
  });

  it("büyük dosya arka planda kontrol edilir; bitene kadar Devam pasif", async () => {
    let polls = 0;
    const pending = { ...summary(61, "Material", "Malzeme", 0, 0), checked: false, read: null, valid: null, errors: null, job: { id: 9, status: "Çalışıyor", progress: "Satır 1000" } };
    const { fetchMock } = await open({
      "/api/imports?": { status: 202, body: { batch_id: 61, job_id: 9, entity: "Material", name: "Malzeme" } },
      "/api/imports/61": () => ({ body: polls++ < 1 ? pending : summary(61, "Material", "Malzeme", 1000, 0) }),
    });
    fireEvent.change(screen.getByTestId("veri-yukle-dosya"), { target: { files: [file("buyuk.xlsx")] } });
    const dialog = await screen.findByRole("dialog", { name: "Veri yükle" });
    expect(await within(dialog).findByText("Kontrol ediliyor")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "0 dosyayla devam et" })).toBeDisabled();
    expect(await within(dialog).findByText("Hazır", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "1 dosyayla devam et" })).toBeEnabled();
    expect(fetchMock).toHaveBeenCalled();
  });
});

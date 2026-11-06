// Yöntem, çekim anahtarı, tablo içi düzenleme ve Veri çek (ekran 02, fonksiyon 01 ve 91; K-130, K-132).
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, meAs, mockApi, renderApp, type Routes } from "../test/helpers";

useTableTestSetup();

const COLUMNS = [col("Name", "Tablo", "text", "text"), col("Method", "Yöntem", "text", "list"), col("IsPullEnabled", "Çekim", "bool", "list")];
const ROW = {
  Id: 1, Entity: "Material", Name: "Malzeme", Version: 4, Method: "SQL", IsPullEnabled: true, Warning: "View tanımlı değil", ViewName: null,
  DisabledReason: null, DisabledByName: null, DisabledAt: null,
};
const OFF_ROW = { ...ROW, Id: 2, Entity: "Stock", Name: "Stok", Method: "Excel", IsPullEnabled: false, Warning: null, DisabledReason: "Sayım", DisabledByName: "Ayşe Yönetici", DisabledAt: "2026-11-05T09:00:00+00:00" };
const PLAN = {
  database: "SmartchainIntegration",
  last: { at: "2026-11-05T08:00:00Z", by: "Mert Planlama" },
  tables: [
    { entity: "Material", name: "Malzeme", method: "SQL", source: "View_Material", state: "Okunacak", reason: null },
    { entity: "BOM", name: "Ürün ağacı", method: "SQL", source: "View_BOM", state: "Okunacak", reason: null },
    { entity: "Stock", name: "Stok", method: "SQL", source: "View_Stock", state: "Yeni veri yok", reason: "Son çekimden beri değişiklik yok." },
    { entity: "Routing", name: "Rota", method: "SQL", source: "View_Routing", state: "Veri güncellemesi devam ediyor", reason: "Veri güncellemesi devam ediyor." },
    { entity: "Resource", name: "Kaynak", method: "Excel", source: null, state: "Atlandı", reason: "Yöntemi Excel" },
  ],
};
const table = (entity: string, name: string, status: string, extra = {}) => ({ entity, name, method: "SQL", source: `View_${entity}`, status, reason: null, read: null, valid: null, errors: null, batch_id: null, attempts: [], ...extra });
const RESULT = {
  job_id: 81, status: "Bitti", progress: "1 tablo alındı", error: null, requested_at: "2026-11-05T08:00:00Z",
  tables: [
    table("Material", "Malzeme", "Alındı", { read: 201, valid: 199, errors: 2, batch_id: 7 }),
    table("Stock", "Stok", "Veri güncellemesi devam ediyor", { reason: "Veri güncellemesi devam ediyor." }),
    table("BOM", "Ürün ağacı", "Hata", { reason: "Zorunlu kolon yok: Code (Kod).", attempts: [{ attempt: 1, at: "2026-11-05T08:01:00", message: "SQL kaynağına ulaşılamadı." }] }),
    table("Routing", "Rota", "Atlandı", { reason: "Çekim kapalı" }),
  ],
};

function backend(routes: Routes = {}) {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/data-entities/columns": { body: { chunk_size: 100, columns: COLUMNS, export: { title: "Tablolar", file_slug: "tablolar", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    "/api/data-entities/query": { body: { rows: [ROW, OFF_ROW], filtered: 2, total: 2 } },
    "/api/data-entities/views": { body: { views: [], default_view_id: null } },
    "/api/integration/entities": { body: { saved: 1 } },
    "/api/pulls/plan": { body: PLAN },
    "/api/pulls/81": { body: RESULT },
    "/api/pulls": { status: 202, body: { job_id: 81 } },
    ...routes,
  });
}

async function open(role: string, routes: Routes = {}, path = "/veri/veri-yukleme") {
  const fetchMock = backend(routes);
  renderApp(path, meAs(role));
  await screen.findAllByText("Malzeme", {}, { timeout: 5000 });
  return { user: userEvent.setup(), fetchMock };
}

const calls = (fetchMock: ReturnType<typeof vi.fn>, method: string, url: string) =>
  fetchMock.mock.calls.filter(([u, init]) => String(u).startsWith(url) && (init as RequestInit | undefined)?.method === method);
const bodyOf = (call: unknown[]) => JSON.parse(String((call[1] as RequestInit).body));

describe("tablo içi düzenleme (K-132)", () => {
  it("anında kaydedilmez; Kaydet ve Vazgeç çıkar, Kaydet toplu yazar", async () => {
    const { user, fetchMock } = await open("System owner");
    expect(screen.queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument();
    const select = screen.getByRole("combobox", { name: "Malzeme yöntemi" });
    expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual(["Excel", "SQL"]);
    await user.selectOptions(select, "Excel");
    expect(calls(fetchMock, "PUT", "/api/integration/entities")).toHaveLength(0);
    await user.selectOptions(screen.getByRole("combobox", { name: "Stok yöntemi" }), "SQL");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls(fetchMock, "PUT", "/api/integration/entities")).toHaveLength(1));
    expect(bodyOf(calls(fetchMock, "PUT", "/api/integration/entities")[0])).toEqual({ changes: [{ entity: "Material", method: "Excel" }, { entity: "Stock", method: "SQL" }] });
    await waitFor(() => expect(screen.queryByRole("button", { name: "Vazgeç" })).not.toBeInTheDocument());
  });

  it("Vazgeç kaydedilmemişleri geri alır; değeri eskiye dönen hücre değişiklik sayılmaz", async () => {
    const { user, fetchMock } = await open("System owner");
    const select = screen.getByRole("combobox", { name: "Malzeme yöntemi" });
    await user.selectOptions(select, "Excel");
    expect(select.className).toContain("is-edited");
    await user.click(screen.getByRole("button", { name: "Vazgeç" }));
    expect(screen.getByRole("combobox", { name: "Malzeme yöntemi" })).toHaveValue("SQL");
    await user.selectOptions(screen.getByRole("combobox", { name: "Malzeme yöntemi" }), "Excel");
    await user.selectOptions(screen.getByRole("combobox", { name: "Malzeme yöntemi" }), "SQL");
    expect(screen.queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument();
    expect(calls(fetchMock, "PUT", "/api/integration/entities")).toHaveLength(0);
  });

  it("kayıt düşerse hata görünür, değişiklikler durur", async () => {
    const { user } = await open("System owner", { "/api/integration/entities": { status: 422, body: { error: { code: "integration_view_not_found", message: "View bulunamadı: X.", trace_id: "x", details: [] } } } });
    await user.selectOptions(screen.getByRole("combobox", { name: "Malzeme yöntemi" }), "Excel");
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("View bulunamadı: X.")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Malzeme yöntemi" })).toHaveValue("Excel");
    expect(screen.getByRole("button", { name: "Vazgeç" })).toBeInTheDocument();
  });

  it("kaydedilmemiş değişiklikle ekrandan çıkınca uyarı", async () => {
    const { user } = await open("System owner");
    await user.selectOptions(screen.getByRole("combobox", { name: "Malzeme yöntemi" }), "Excel");
    await user.click(screen.getByRole("link", { name: /Kullanıcılar/ }));
    const dialog = await screen.findByRole("dialog", { name: "Kaydedilmemiş değişiklikler var" });
    await user.click(within(dialog).getByRole("button", { name: "Vazgeç" }));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Veri yükleme");
    expect(screen.getByRole("combobox", { name: "Malzeme yöntemi" })).toHaveValue("Excel");
    await user.click(screen.getByRole("link", { name: /Kullanıcılar/ }));
    await user.click(within(await screen.findByRole("dialog", { name: "Kaydedilmemiş değişiklikler var" })).getByRole("button", { name: "Kaydetmeden çık" }));
    await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Kullanıcılar"));
  });

  it("değişiklik yokken çıkışta uyarı yok; varken sayfa kapatma tarayıcı uyarısı", async () => {
    const { user } = await open("System owner");
    const before = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(before);
    expect(before.defaultPrevented).toBe(false);
    await user.selectOptions(screen.getByRole("combobox", { name: "Malzeme yöntemi" }), "Excel");
    const after = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(after);
    expect(after.defaultPrevented).toBe(true);
  });
});

describe("yöntem ve çekim kolonları", () => {
  it("anahtarın görünen şeridine tıklamak da çalışır (2. demo: tıklama şeritte kalıyordu)", async () => {
    await open("Admin");
    const track = screen.getByRole("switch", { name: "Malzeme çekimi" }).parentElement!.querySelector(".sc-toggle-track")!;
    fireEvent.click(track);
    expect(await screen.findByRole("dialog", { name: "Malzeme çekimi kapatılsın mı?" })).toBeInTheDocument();
  });

  it("Admin yöntemi değiştiremez, çekim anahtarını değiştirir", async () => {
    await open("Admin");
    expect(screen.queryByRole("combobox", { name: "Malzeme yöntemi" })).not.toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Malzeme çekimi" })).toBeEnabled();
  });

  it("Key user ikisini yalnız görür; kaydet çıkmaz", async () => {
    await open("Key user");
    expect(screen.queryByRole("combobox", { name: "Malzeme yöntemi" })).not.toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Malzeme çekimi" })).toBeDisabled();
    expect(screen.getByText("SQL")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument();
  });

  it("uyarı kolon değil, tablo adının yanında üçgen; metni ipucunda", async () => {
    const { user } = await open("Key user");
    expect(screen.queryByRole("columnheader", { name: /Uyarı/ })).not.toBeInTheDocument();
    const icon = screen.getByLabelText("Malzeme: View tanımlı değil");
    await user.hover(icon);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("View tanımlı değil");
  });

  it("kapatırken sebep zorunlu, değişiklik Kaydet'le yazılır; kiremit düğme", async () => {
    const { user, fetchMock } = await open("Admin");
    await user.click(screen.getByRole("switch", { name: "Malzeme çekimi" }));
    const dialog = await screen.findByRole("dialog", { name: "Malzeme çekimi kapatılsın mı?" });
    const off = within(dialog).getByRole("button", { name: "Çekimi kapat" });
    expect(off).toBeDisabled();
    expect(off.className).toContain("sc-btn--danger");
    await user.type(within(dialog).getByRole("textbox"), "ERP bakımı");
    await user.click(off);
    expect(screen.getByRole("switch", { name: "Malzeme çekimi" })).not.toBeChecked();
    expect(calls(fetchMock, "PUT", "/api/integration/entities")).toHaveLength(0);
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls(fetchMock, "PUT", "/api/integration/entities")).toHaveLength(1));
    expect(bodyOf(calls(fetchMock, "PUT", "/api/integration/entities")[0])).toEqual({ changes: [{ entity: "Material", pull_enabled: false, reason: "ERP bakımı" }] });
  });

  it("taslağı geri çevirmek sebep sormaz", async () => {
    const { user } = await open("Admin");
    await user.click(screen.getByRole("switch", { name: "Malzeme çekimi" }));
    const dialog = await screen.findByRole("dialog", { name: "Malzeme çekimi kapatılsın mı?" });
    await user.type(within(dialog).getByRole("textbox"), "x");
    await user.click(within(dialog).getByRole("button", { name: "Çekimi kapat" }));
    await user.click(screen.getByRole("switch", { name: "Malzeme çekimi" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kaydet" })).not.toBeInTheDocument();
  });

  it("açarken uyarı; ipucu üç satır, tarih Türkçe", async () => {
    const { user, fetchMock } = await open("Admin");
    const box = screen.getByRole("switch", { name: "Stok çekimi" });
    await user.hover(box);
    const tip = await screen.findByRole("tooltip");
    expect(tip).toHaveTextContent("Çekim kapalı");
    expect(tip).toHaveTextContent("Sebep: Sayım");
    expect(tip).toHaveTextContent(/Ayşe Yönetici · 05\.11\.2026/);
    expect(tip.textContent).not.toContain("NaN");
    await user.click(box);
    const dialog = await screen.findByRole("dialog", { name: "Stok çekimi açılsın mı?" });
    await user.click(within(dialog).getByRole("button", { name: "Çekimi aç" }));
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calls(fetchMock, "PUT", "/api/integration/entities")).toHaveLength(1));
    expect(bodyOf(calls(fetchMock, "PUT", "/api/integration/entities")[0]).changes[0]).toMatchObject({ entity: "Stock", pull_enabled: true });
  });
});

describe("Excel yöntemden bağımsız", () => {
  it("yöntemi SQL olan tabloda Excel'den yükle açık, Veri çek var", async () => {
    const { user } = await open("Key user");
    await user.click(screen.getByRole("button", { name: "Malzeme işlemleri" }));
    const menu = await screen.findByRole("menu");
    expect(within(menu).getByRole("menuitem", { name: "Excel'den yükle" })).toBeEnabled();
    expect(within(menu).getByRole("menuitem", { name: "Veri çek" })).toBeEnabled();
  });

  it("çekimi kapalı Excel tablosunda da yükleme açık, Veri çek yok", async () => {
    const { user } = await open("Key user");
    await user.click(screen.getByRole("button", { name: "Stok işlemleri" }));
    const menu = await screen.findByRole("menu");
    expect(within(menu).getByRole("menuitem", { name: "Excel'den yükle" })).toBeEnabled();
    expect(within(menu).queryByRole("menuitem", { name: "Veri çek" })).not.toBeInTheDocument();
  });
});

describe("Veri çek", () => {
  it("yalnız SQL tabloları; bant ve Neden kolonu yok; okunacakta çip yok; düğmede sayı", async () => {
    const { user } = await open("Key user");
    await user.click(screen.getByRole("button", { name: "Veri çek" }));
    const dialog = await screen.findByRole("dialog", { name: "Veri çek" });
    expect(await within(dialog).findByText("View_Material")).toBeInTheDocument();
    expect(within(dialog).queryByText("Kaynak")?.tagName).not.toBe("TD");
    expect(dialog).not.toHaveTextContent("Yöntemi Excel");
    expect(within(dialog).queryByRole("columnheader", { name: "Neden" })).not.toBeInTheDocument();
    expect(within(dialog).queryByText("Okunacak")).not.toBeInTheDocument();
    expect(dialog.querySelector(".sc-alert")).toBeNull();
    expect(within(dialog).getByRole("button", { name: "2 tabloyu çek" })).toBeEnabled();
    expect(within(dialog).getByText("Yeni veri yok").className).toContain("neutral");
    await user.hover(within(dialog).getByText("Veri güncellemesi devam ediyor"));
    expect(await screen.findByRole("tooltip")).toHaveTextContent("Veri güncellemesi devam ediyor.");
    expect(dialog.textContent).not.toMatch(/müşteri/i);
  });

  it("Yine de oku yalnız Yeni veri yok satırında; sayıyı artırır, tabloya özel gider", async () => {
    const { user, fetchMock } = await open("Key user");
    await user.click(screen.getByRole("button", { name: "Veri çek" }));
    const dialog = await screen.findByRole("dialog", { name: "Veri çek" });
    await within(dialog).findByText("View_Material");
    const boxes = within(dialog).getAllByRole("checkbox", { name: "Yine de oku" });
    expect(boxes).toHaveLength(1);
    await user.click(boxes[0]);
    await user.click(within(dialog).getByRole("button", { name: "3 tabloyu çek" }));
    await waitFor(() => expect(calls(fetchMock, "POST", "/api/pulls")).toHaveLength(1));
    expect(bodyOf(calls(fetchMock, "POST", "/api/pulls")[0])).toEqual({ entities: ["Material", "BOM", "Stock"], read_anyway: ["Stock"] });
    expect(await screen.findByRole("dialog", { name: "Çekim sonucu" })).toBeInTheDocument();
  });

  it("okunacak tablo yoksa başlatılamaz", async () => {
    const { user } = await open("Key user", { "/api/pulls/plan": { body: { ...PLAN, tables: [PLAN.tables[3]] } } });
    await user.click(screen.getByRole("button", { name: "Veri çek" }));
    const dialog = await screen.findByRole("dialog", { name: "Veri çek" });
    await within(dialog).findByText("View_Routing");
    expect(within(dialog).getByRole("button", { name: "0 tabloyu çek" })).toBeDisabled();
  });

  it("satır menüsünden tek tablo", async () => {
    const { user, fetchMock } = await open("Key user");
    await user.click(screen.getByRole("button", { name: "Malzeme işlemleri" }));
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Veri çek" }));
    const dialog = await screen.findByRole("dialog", { name: "Veri çek" });
    await within(dialog).findByText("View_Material");
    expect(within(dialog).queryByText("View_Stock")).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "1 tabloyu çek" }));
    await waitFor(() => expect(calls(fetchMock, "POST", "/api/pulls")).toHaveLength(1));
    expect(bodyOf(calls(fetchMock, "POST", "/api/pulls")[0]).entities).toEqual(["Material"]);
  });

  it("pencere tablosu sıralanır", async () => {
    const { user } = await open("Key user");
    await user.click(screen.getByRole("button", { name: "Veri çek" }));
    const dialog = await screen.findByRole("dialog", { name: "Veri çek" });
    await within(dialog).findByText("View_Material");
    const first = () => within(within(dialog).getAllByRole("row")[1]).getAllByRole("cell")[0].textContent;
    expect(first()).toBe("Malzeme");
    await user.click(within(dialog).getByRole("button", { name: "Tablo" }));
    expect(first()).toBe("Malzeme");
    await user.click(within(dialog).getByRole("button", { name: "Tablo" }));
    expect(first()).toBe("Ürün ağacı");
    expect(within(dialog).getAllByRole("columnheader")[0]).toHaveAttribute("aria-sort", "descending");
  });
});

describe("Çekim sonucu", () => {
  const result = async (routes: Routes = {}) => {
    const out = await open("Key user", routes, "/veri/veri-yukleme?cekim=81");
    const dialog = await screen.findByRole("dialog", { name: "Çekim sonucu" });
    await within(dialog).findByText("Alındı");
    return { ...out, dialog };
  };
  const rowOf = (dialog: HTMLElement, name: string) => within(dialog).getAllByRole("row").find((r) => r.textContent?.includes(name))!;

  it("çip renkleri, okunmayan tabloda —, iş numarası yok", async () => {
    const { dialog } = await result();
    expect(within(dialog).getByText("Alındı").className).toContain("ok");
    expect(within(dialog).getByText("Hata").className).toContain("critical");
    expect(within(dialog).getByText("Atlandı").className).toContain("neutral");
    expect(within(rowOf(dialog, "Malzeme")).getByText("199")).toBeInTheDocument();
    expect(within(rowOf(dialog, "Ürün ağacı")).getAllByText("—")).toHaveLength(3);
    expect(dialog.textContent).not.toContain("#81");
    expect(dialog.textContent).not.toMatch(/müşteri/i);
  });

  it("Bulgular ve Yeniden dene küçük tonal düğme, yalnız gereken satırda; ⋯ menüsü yok", async () => {
    const { user, dialog, fetchMock } = await result();
    expect(within(dialog).queryByRole("button", { name: /işlemleri/ })).not.toBeInTheDocument();
    expect(within(rowOf(dialog, "Stok")).queryByRole("button")).not.toBeInTheDocument();
    const findings = within(rowOf(dialog, "Malzeme")).getByRole("button", { name: "Bulgular" });
    expect(findings.className).toContain("sc-btn--secondary");
    expect(findings.className).toContain("sc-btn--row");
    expect(within(rowOf(dialog, "Malzeme")).queryByRole("button", { name: "Yeniden dene" })).not.toBeInTheDocument();
    await user.click(within(rowOf(dialog, "Ürün ağacı")).getByRole("button", { name: "Yeniden dene" }));
    await waitFor(() => expect(calls(fetchMock, "POST", "/api/pulls")).toHaveLength(1));
    expect(bodyOf(calls(fetchMock, "POST", "/api/pulls")[0])).toEqual({ entities: ["BOM"], read_anyway: [] });
  });

  it("Bulgular listeyi Excel penceresiyle aynı filtreyle ister (eq, sayı)", async () => {
    const queries: unknown[] = [];
    const { user, dialog } = await result({
      "/api/import-findings/columns": { body: { chunk_size: 100, columns: [col("RowKey", "Kayıt", "text", "text"), col("Message", "Sorun", "text", "text")], export: { title: "Bulgular", file_slug: "bulgular", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
      "/api/import-findings/views": { body: { views: [], default_view_id: null } },
      "/api/import-findings/query": (_url, init) => {
        queries.push(JSON.parse(String(init?.body)));
        return { body: { rows: [{ Id: 1, RowKey: "ORM-01 · SAT-040", Message: "Aynı kayıt" }], filtered: 1, total: 1 } };
      },
    });
    await user.click(within(rowOf(dialog, "Malzeme")).getByRole("button", { name: "Bulgular" }));
    expect(await screen.findByText("ORM-01 · SAT-040")).toBeInTheDocument();
    expect((queries[0] as { filters: unknown[] }).filters).toContainEqual({ field: "ImportBatchId", op: "eq", value: 7 });
    // Pencere kipi (kontrol demosu): tablo pencereye sığar, genişlik içerikten, Sorun alt satıra kayar
    const grid = screen.getByText("ORM-01 · SAT-040").closest("table")!;
    expect(grid.className).toContain("sc-table-grid--fit");
    expect(grid.querySelector("colgroup")).toBeNull();
    expect(grid.getAttribute("style")).toBeNull();
    expect(screen.getByText("Aynı kayıt").closest("td")!.className).toContain("is-wrap");
    expect(screen.getByText("ORM-01 · SAT-040").closest("td")!.className).not.toContain("is-wrap");
  });

  it("Neden kolonu alt satıra kayabilir", async () => {
    const { dialog } = await result();
    expect(within(dialog).getByText("Zorunlu kolon yok: Code (Kod).").closest("td")!.className).toContain("is-wrap");
  });

  it("çekim sürerken durum yazar", async () => {
    await open("Key user", { "/api/pulls/81": { body: { ...RESULT, status: "Çalışıyor", tables: [] } } }, "/veri/veri-yukleme?cekim=81");
    const dialog = await screen.findByRole("dialog", { name: "Çekim sonucu" });
    expect(await within(dialog).findByRole("status")).toHaveTextContent("Çekim sürüyor");
  });
});

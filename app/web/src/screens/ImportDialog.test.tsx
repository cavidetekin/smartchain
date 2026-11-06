// Excel'den yükle penceresi (ekran 02, fonksiyon 03; K-129): dosya, mod, iki yol, ön kontrol, devam, vazgeç, hata raporu, geri dönüş.
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, FakeWebSocket, meAs, mockApi, renderApp, type Reply } from "../test/helpers";
import type { ImportSummary } from "./dataLoadApi";

useTableTestSetup();

const ENTITY_COLUMNS = [col("Name", "Tablo", "text", "text"), { ...col("LastLoadAt", "Son yükleme zamanı", "datetime", "date"), note: "Dosyanın ham veriye alındığı zaman." }];
const ENTITY_ROWS = [{ Id: 9, Entity: "Resource", Name: "Kaynak", Version: 3, LastLoadAt: null }];
const FINDING_COLUMNS = [col("RowNo", "Satır", "number", "number"), col("RowKey", "Kod", "text", "text"), col("Message", "Sorun", "text", "text"), col("Severity", "Önem", "text", "list")];

const SUMMARY: ImportSummary = {
  batch_id: 41, entity: "Resource", name: "Kaynak", file_name: "kaynak.xlsx", mode: "Değişen", status: "Ön kontrol", checked: true,
  template_version: 3, current_version: 3, read: 46, valid: 43, errors: 3, notes: 1, file_findings: [{ severity: "Bilgi", message: "Tanınmayan kolon yok sayıldı: Hata." }], job: null,
};
const RUNNING: ImportSummary = { ...SUMMARY, checked: false, read: null, valid: null, errors: null, notes: null, file_findings: [], job: { id: 7, status: "Çalışıyor", progress: "120.000 satır" } };

const reply = (body: unknown, status = 200): Reply => ({ status, body: body as Reply["body"] });

function backend(routes: Record<string, Reply | ((url: string, init?: RequestInit) => Reply)> = {}) {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/data-entities/columns": { body: { chunk_size: 100, columns: ENTITY_COLUMNS, export: { title: "Tablolar", file_slug: "tablolar", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    "/api/data-entities/query": { body: { rows: ENTITY_ROWS, filtered: 1, total: 1 } },
    "/api/data-entities/views": { body: { views: [], default_view_id: null } },
    "/api/import-findings/columns": { body: { chunk_size: 100, columns: FINDING_COLUMNS, export: { title: "Ön kontrol bulguları", file_slug: "b", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    "/api/import-findings/query": { body: { rows: [{ Id: 1, RowNo: 12, RowKey: "TRN-12", Message: "Zorunlu alan boş.", Severity: "Hata" }], filtered: 1, total: 900 } },
    "/api/import-findings/views": { body: { views: [], default_view_id: null } },
    "/api/imports/pending/Resource": reply(null),
    ...routes,
  });
}

async function openDialog(routes: Parameters<typeof backend>[0] = {}) {
  const user = userEvent.setup();
  backend(routes);
  renderApp("/veri/veri-yukleme", meAs("Key user"));
  await screen.findByText("Kaynak", {}, { timeout: 5000 });
  await user.click(screen.getByRole("button", { name: "Kaynak işlemleri" }));
  await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Excel'den yükle" }));
  return { user, dialog: await screen.findByRole("dialog") };
}

const file = (name = "kaynak.xlsx") => new File(["x"], name, { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });

const calls = () => vi.mocked(fetch).mock.calls.map(([url, init]) => ({ url: String(url), method: init?.method ?? "GET", init }));

async function choose(user: ReturnType<typeof userEvent.setup>, f = file()) {
  await user.upload(screen.getByLabelText("Dosya seç"), f);
  await user.click(screen.getByRole("button", { name: "Ön kontrole geç" }));
}

describe("Excel'den yükle", () => {
  it("kolon başlığı ipucu yalnız alanın açıklaması; açıklama yoksa ipucu yok, kullanım metni yok", async () => {
    backend();
    renderApp("/veri/veri-yukleme", meAs("Key user"));
    await screen.findByText("Kaynak", {}, { timeout: 5000 });
    const header = (name: string) => screen.getByRole("columnheader", { name: new RegExp(name) }).querySelector(".sc-table-sort")!;
    expect(header("Son yükleme zamanı")).toHaveAttribute("title", "Dosyanın ham veriye alındığı zaman.");
    expect(header("Tablo")).not.toHaveAttribute("title");
  });

  it("adımlar; dosya seçilmeden ilerlenmez; üçüncü adım pasif ve gerekçeli", async () => {
    await openDialog();
    expect(screen.getByRole("button", { name: "Ön kontrole geç" })).toBeDisabled();
    const steps = within(screen.getByRole("list", { name: "Adımlar" })).getAllByRole("listitem");
    expect(steps.map((s) => s.textContent)).toEqual(["1. Dosya", "2. Ön kontrol", "3. Doğrulama"]);
    expect(steps[0]).toHaveAttribute("aria-current", "step");
    expect(steps[2]).toHaveAttribute("aria-disabled", "true");
    expect(steps[2]).toHaveAttribute("title", "3.4 adımında gelecek.");
    expect(screen.getByRole("radio", { name: "Ekle / güncelle Sadece dosyadaki kayıtlar güncellenir, mevcut kayıtlar korunur" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Tam Mevcut kayıtlar silinir, yeni kayıtlar yüklenir" })).not.toBeChecked();
    expect(screen.getByText("Ekle / güncelle").tagName).toBe("STRONG");
    expect(screen.getByText("Kaynak", { selector: ".sc-dialog-subtitle" })).toBeInTheDocument();  // alt başlıkta yalnız tablo adı
  });

  it(".xlsx dışı dosya reddedilir", async () => {
    await openDialog();
    fireEvent.change(screen.getByLabelText("Dosya seç"), { target: { files: [file("notlar.txt")] } });
    expect(await screen.findByText("Yalnız .xlsx dosyası yüklenebilir.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ön kontrole geç" })).toBeDisabled();
  });

  it("sürükle-bırak dosyayı alır", async () => {
    await openDialog();
    fireEvent.drop(screen.getByText("Dosyayı buraya sürükleyin ya da seçin"), { dataTransfer: { files: [file()] } });
    expect(await screen.findByText("kaynak.xlsx")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ön kontrole geç" })).toBeEnabled();
  });

  it("yükleme: ham gövde, mod ve dosya adı; sonuç kartları ve bulgular; dosya bilgisi", async () => {
    const { user } = await openDialog({ "/api/imports/Resource": reply(SUMMARY) });
    await user.click(screen.getByRole("radio", { name: /Tam/ }));
    await user.upload(screen.getByLabelText("Dosya seç"), file("kaynak ş.xlsx"));
    await user.click(screen.getByRole("button", { name: "Ön kontrole geç" }));
    await screen.findByText("Ön kontrol · kaynak.xlsx");
    const post = calls().find((c) => c.method === "POST" && c.url.startsWith("/api/imports/Resource"))!;
    expect(post.url).toBe(`/api/imports/Resource?mode=${encodeURIComponent("Tam")}`);
    expect((post.init?.headers as Record<string, string>)["X-File-Name"]).toBe(encodeURIComponent("kaynak ş.xlsx"));
    expect(post.init?.body).toBeInstanceOf(File);
    expect(screen.getByText("Kaynak · şablon v3 · güncel")).toBeInTheDocument();
    for (const [label, value] of [["Okunan", "46"], ["Geçerli", "43"], ["Hatalı", "3"], ["Uyarı ve bilgi", "1"]]) {
      expect(screen.getByText(label).parentElement).toHaveTextContent(value);
    }
    expect(screen.queryByText("Tanınmayan kolon yok sayıldı: Hata.")).not.toBeInTheDocument();  // bant değil, tabloda satır
    expect(await screen.findByText("TRN-12", {}, { timeout: 5000 })).toBeInTheDocument();  // tablo üç istekle yüklenir
    expect(screen.getByText("Hata", { selector: ".sc-tag" })).toBeInTheDocument();
    expect(screen.getByText("3 satır hatalı, ham veriye alınmaz.")).toBeInTheDocument();
  });

  it("bulgu tablosu partiye sabit filtreyle bağlı; etiketlerde görünmez, sayaç parti içinde", async () => {
    const { user } = await openDialog({ "/api/imports/Resource": reply(SUMMARY) });
    await choose(user);
    await screen.findByText("TRN-12", {}, { timeout: 5000 });
    const query = calls().find((c) => c.url.startsWith("/api/import-findings/query"))!;
    expect(JSON.parse(String(query.init?.body)).filters).toEqual([{ field: "ImportBatchId", op: "eq", value: 41 }]);
    expect(screen.queryByText(/ImportBatchId/)).not.toBeInTheDocument();
    expect(screen.queryByText(/900/)).not.toBeInTheDocument();
  });

  it("devam: sonuç metni, tablo yenilenir", async () => {
    const { user } = await openDialog({ "/api/imports/Resource": reply(SUMMARY), "/api/imports/41/continue": reply({ ...SUMMARY, status: "Alındı" }) });
    await choose(user);
    const before = calls().filter((c) => c.url.startsWith("/api/data-entities/query")).length;
    await user.click(await screen.findByRole("button", { name: "43 satırla devam et" }));
    expect(await screen.findByText("43 satır ham veriye alındı. Doğrulama 3.4 adımında gelecek.")).toBeInTheDocument();
    await waitFor(() => expect(calls().filter((c) => c.url.startsWith("/api/data-entities/query")).length).toBeGreaterThan(before));
    await user.click(screen.getByRole("button", { name: "Kapat" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("vazgeç partiyi kapatır; hata raporu indirir", async () => {
    const created = vi.fn(() => "blob:x");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: created, revokeObjectURL: vi.fn() }));
    const { user } = await openDialog({
      "/api/imports/Resource": reply(SUMMARY), "/api/imports/41/cancel": reply({ ...SUMMARY, status: "Vazgeçildi" }),
      "/api/imports/41/error-report": reply({}),
    });
    await choose(user);
    await user.click(await screen.findByRole("button", { name: "Hata raporunu indir" }));
    await waitFor(() => expect(calls().some((c) => c.url === "/api/imports/41/error-report")).toBe(true));
    await user.click(screen.getByRole("button", { name: "Vazgeç" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls().some((c) => c.url === "/api/imports/41/cancel" && c.method === "POST")).toBe(true);
  });

  it("hatasızsa rapor düğmesi ve uyarı yok", async () => {
    const { user } = await openDialog({ "/api/imports/Resource": reply({ ...SUMMARY, errors: 0, valid: 46, file_findings: [] }) });
    await choose(user);
    await screen.findByRole("button", { name: "46 satırla devam et" });
    expect(screen.queryByRole("button", { name: "Hata raporunu indir" })).not.toBeInTheDocument();
    expect(screen.queryByText(/satır hatalı/)).not.toBeInTheDocument();
  });

  it("hepsi hatalıysa devam yok, rapor var", async () => {
    const { user } = await openDialog({ "/api/imports/Resource": reply({ ...SUMMARY, status: "Hatalı", valid: 0, errors: 46 }) });
    await choose(user);
    expect(await screen.findByRole("button", { name: "0 satırla devam et" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Hata raporunu indir" })).toBeEnabled();
    expect(screen.getByText("Geçerli satır yok, ham veriye alınmaz.")).toBeInTheDocument();
  });

  it.each([
    [413, "import_too_large", "Dosya çok büyük: en çok 100 MB yüklenebilir."],
    [422, "import_wrong_entity", "Bu dosya Kaynak tablosu içermemektedir."],
    [422, "import_bad_file", "Dosya okunamadı: geçerli bir Excel (.xlsx) dosyası değil."],
  ])("%s %s: mesaj görünür, dosya adımında kalır, hata varken ilerlenmez; yeni dosya açar", async (status, code, message) => {
    const { user } = await openDialog({ "/api/imports/Resource": reply({ error: { code, message, trace_id: "t", details: [] } }, status) });
    await choose(user);
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ön kontrole geç" })).toBeDisabled();
    await user.upload(screen.getByLabelText("Dosya seç"), file("baska.xlsx"));
    expect(screen.queryByText(message)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ön kontrole geç" })).toBeEnabled();
  });

  it("büyük dosya: 202, ilerleme, bitince sonuç", async () => {
    let done = false;
    const { user } = await openDialog({
      "/api/imports/Resource": reply({ batch_id: 41, job_id: 7 }, 202),
      "/api/imports/41": () => reply(done ? SUMMARY : RUNNING),
    });
    await choose(user);
    expect(await screen.findByText("Ön kontrol sürüyor: 120.000 satır.")).toBeInTheDocument();
    expect(screen.getByText("Pencereyi kapatabilirsiniz. İş tamamlanınca tekrar açabilirsiniz.")).toBeInTheDocument();
    done = true;
    expect(await screen.findByText("Ön kontrol · kaynak.xlsx", {}, { timeout: 4000 })).toBeInTheDocument();
  });

  it.each([
    ["Sırada", null, "Ön kontrol sırada."],
    ["Çalışıyor", null, "Ön kontrol sürüyor: dosya açılıyor."],
    ["Çalışıyor", "Dosya açılıyor", "Ön kontrol sürüyor: dosya açılıyor."],
    ["Çalışıyor", "5.000 satır", "Ön kontrol sürüyor: 5.000 satır."],
  ])("iş %s, ilerleme %s: %s (iş #535)", async (status, progress, text) => {
    const running = { ...RUNNING, job: { id: 7, status, progress } };
    await openDialog({ "/api/imports/pending/Resource": reply(running), "/api/imports/41": reply(running) });
    expect(await screen.findByText(text)).toBeInTheDocument();
  });

  it("uyarı bandı kalır, bilgi bandı çıkmaz", async () => {
    const both = { ...SUMMARY, file_findings: [{ severity: "Uyarı", message: "Dosya şablon v1 ile hazırlanmış." }, { severity: "Bilgi", message: "Tanınmayan kolon." }] };
    await openDialog({ "/api/imports/pending/Resource": reply(both) });
    expect(await screen.findByText("Dosya şablon v1 ile hazırlanmış.")).toBeInTheDocument();
    expect(screen.queryByText("Tanınmayan kolon.")).not.toBeInTheDocument();
  });

  it("açık ön kontrole döner", async () => {
    await openDialog({ "/api/imports/pending/Resource": reply(SUMMARY) });
    expect(await screen.findByText("Ön kontrol · kaynak.xlsx")).toBeInTheDocument();
  });

  it("iş sürerken kapatılır, iptal edilmez", async () => {
    const { user } = await openDialog({ "/api/imports/pending/Resource": reply(RUNNING), "/api/imports/41": reply(RUNNING) });
    await user.click(await screen.findByRole("button", { name: "Kapat" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(calls().some((c) => c.url.includes("/cancel"))).toBe(false);
  });

  describe("Sonucu aç (K-129)", () => {
    const open = (routes: Parameters<typeof backend>[0] = {}) => {
      backend(routes);
      renderApp("/veri/veri-yukleme?parti=41", meAs("Key user"));
    };

    it("adresteki partinin penceresi açılır, kapatınca adres temizlenir", async () => {
      const user = userEvent.setup();
      open({ "/api/imports/41": reply(SUMMARY), "/api/imports/41/cancel": reply({ ...SUMMARY, status: "Vazgeçildi" }) });
      expect(await screen.findByText("Ön kontrol · kaynak.xlsx", {}, { timeout: 5000 })).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Vazgeç" }));
      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    });

    it.each([
      ["Alındı", "43 satır ham veriye alındı. Doğrulama 3.4 adımında gelecek."],
      ["Vazgeçildi", "Bu yükleme kapatıldı."],
    ])("parti %s: %s", async (status, text) => {
      open({ "/api/imports/41": reply({ ...SUMMARY, status }) });
      expect(await screen.findByText(text, {}, { timeout: 5000 })).toBeInTheDocument();
    });

    it("parti yoksa hata", async () => {
      open({ "/api/imports/41": reply({ error: { code: "import_not_found", message: "Yükleme bulunamadı.", trace_id: "t", details: [] } }, 404) });
      expect(await screen.findByText("Yükleme bulunamadı.", {}, { timeout: 5000 })).toBeInTheDocument();
    });

    it("iş listesindeki bağlantı ve bitince bildirim o işin penceresini açar", async () => {
      const user = userEvent.setup();
      const job = (status: string) => ({ id: 7, job_type: "Excel ön kontrol", summary: "Kaynak · kaynak.xlsx", channel: "Excel", status, progress: null, queue_position: null,
                                         updated_at: "2026-11-05T10:00:00+00:00", requested_by: 1, import_batch_id: 41 });
      backend({ "/api/jobs": { body: { jobs: [job("Çalışıyor")], counters: {} } as unknown as Reply["body"] }, "/api/imports/41": reply(SUMMARY) });
      renderApp("/veri/veri-yukleme", { ...meAs("Key user"), id: 1 });
      await screen.findByText("Kaynak", {}, { timeout: 5000 });
      await waitFor(() => expect(FakeWebSocket.instances.some((s) => s.url.includes("/api/ws"))).toBe(true));
      expect(screen.queryByText("Ön kontrol bitti")).not.toBeInTheDocument();
      act(() => FakeWebSocket.instances.find((s) => s.url.includes("/api/ws"))!.send({ type: "job", job: job("Bitti") }));
      expect(await screen.findByText("Ön kontrol bitti")).toBeInTheDocument();
      await user.click(within(screen.getByRole("region", { name: "Bildirimler" })).getByRole("button", { name: "Sonucu aç" }));
      expect(await screen.findByText("Ön kontrol · kaynak.xlsx")).toBeInTheDocument();
      expect(screen.queryByText("Ön kontrol bitti")).not.toBeInTheDocument();
    });

    const endedJob = (extra = {}) => ({ id: 7, job_type: "Veri çekme", summary: "Veri çekme · 3 tablo", channel: "Veri çekme", status: "Bitti", progress: null, queue_position: null, created_at: "2026-11-05T10:00:00+00:00",
                                        updated_at: "2026-11-05T10:00:00+00:00", ended_at: new Date().toISOString(), requested_by: 1, ...extra });

    it("kapatılan bildirim işte saklanır, yeniden girişte çıkmaz; bildirimde iş numarası yok (K-132)", async () => {
      const user = userEvent.setup();
      const fetchMock = backend({ "/api/jobs": { body: { jobs: [endedJob()], counters: {} } as unknown as Reply["body"] }, "/api/jobs/7/dismiss": { status: 204, body: null } });
      renderApp("/veri/veri-yukleme", { ...meAs("Key user"), id: 1 });
      const toast = await screen.findByText("Çekim bitti", {}, { timeout: 5000 });
      const region = screen.getByRole("region", { name: "Bildirimler" });
      expect(region).not.toHaveTextContent("#7");
      expect(toast).toBeInTheDocument();
      await user.click(within(region).getByRole("button", { name: "Kapat" }));
      await waitFor(() => expect(fetchMock.mock.calls.some(([u, init]) => String(u) === "/api/jobs/7/dismiss" && (init as RequestInit).method === "POST")).toBe(true));
      expect(screen.queryByText("Çekim bitti")).not.toBeInTheDocument();
    });

    it("kapatılmış bildirim sayfa yenilenince gelmez", async () => {
      backend({ "/api/jobs": { body: { jobs: [endedJob({ dismissed: true })], counters: {} } as unknown as Reply["body"] } });
      renderApp("/veri/veri-yukleme", { ...meAs("Key user"), id: 1 });
      await screen.findByText("Kaynak", {}, { timeout: 5000 });
      await waitFor(() => expect(FakeWebSocket.instances.some((s) => s.url.includes("/api/ws"))).toBe(true));
      expect(screen.queryByText("Çekim bitti")).not.toBeInTheDocument();
    });
  });

  it("yarıda kalan ön kontrol anlatılır", async () => {
    await openDialog({ "/api/imports/pending/Resource": reply({ ...RUNNING, status: "Tamamlanmadı" }) });
    expect(await screen.findByText("Ön kontrol tamamlanamadı. Dosyayı yeniden yükleyin.")).toBeInTheDocument();
  });
});

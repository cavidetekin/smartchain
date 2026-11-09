// Validasyon çipi, çekmecesi ve iş paneli (ekran 02, fonksiyon 04; K-134, K-139): çip durumları, dört kart, kural bazında Bulgular,
// kurala süzülmüş Kayıtlar, yeniden validasyon (onay bandı yok), "Sonucu aç", çekim kartı.
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { type Job } from "../api/client";
import { buildCards, cardState, groupOutcomes } from "../shell/JobIndicator";
import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, FakeWebSocket, meAs, mockApi, renderApp, type Reply } from "../test/helpers";
import type { ValidationSummary } from "./validationApi";

useTableTestSetup();

const EXPORT = { title: "x", file_slug: "x", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const COLUMNS = [col("Name", "Tablo", "text", "text"), col("Validation", "Validasyon", "text", "list")];
const row = (Entity: string, Name: string, Validation: string | null, extra = {}) =>
  ({ Id: Name.length, Entity, Name, Validation, ValidationErrors: 0, ValidationWarnings: 0, Version: 1, ...extra });
const ROWS = [
  row("Resource", "Kaynak", "Uyarılı", { ValidationWarnings: 3 }),
  row("Material", "Malzeme", "Hatalı", { ValidationErrors: 2, ValidationWarnings: 5 }),
  row("BOM", "Ürün ağacı", "Valide ediliyor"),
  row("Stock", "Stok", null),
];
const SUMMARY: ValidationSummary = {
  entity: "Resource", name: "Kaynak", state: "Bitti", outcome: "Uyarılı",
  batch: { id: 41, received_at: "2026-11-06T09:30:00", method: "Excel", mode: "Tam", uploaded_by_name: "Cavide" },
  current_rows: 120, error_rows: 0, warning_rows: 3, info_rows: 1, error_rate: 0, threshold: null,
  rules: [
    { id: 12, name: "Kaynak tipi tek değil", severity: "Uyarı", rows: 2, message: null },
    { id: 15, name: "Fırın ya da kalıp Faz 1'de kullanılmaz", severity: "Bilgi", rows: 1, message: null },
  ],
};
const RECORD_COLUMNS = [col("Problems", "Sorun", "text", "text"), col("Severity", "Sınıf", "text", "list"), col("Code", "Kaynak kodu", "text", "text"),
                        col("RuleIds", "Kurallar", "text", "text")];
const listRoutes = (name: string, columns: ReturnType<typeof col>[], rows: Record<string, unknown>[] = []) => ({
  [`/api/${name}/columns`]: { body: { chunk_size: 100, columns, export: EXPORT } },
  [`/api/${name}/query`]: { body: { rows, filtered: rows.length, total: rows.length } },
  [`/api/${name}/views`]: { body: { views: [], default_view_id: null } },
});

function backend(routes: Record<string, Reply> = {}) {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/data-entities/columns": { body: { chunk_size: 100, columns: COLUMNS, export: EXPORT } },
    "/api/data-entities/query": { body: { rows: ROWS, filtered: ROWS.length, total: ROWS.length } },
    "/api/data-entities/views": { body: { views: [], default_view_id: null } },
    "/api/validation/Resource": { body: SUMMARY as unknown as Reply["body"] },
    ...listRoutes("validation-records-Resource", RECORD_COLUMNS,
                  [{ Id: 9, Code: "V-RES-2", Problems: "Makine: Kaynağın tek bir tipi olmalı.", Severity: "Uyarı", RuleIds: ",12," }]),
    ...listRoutes("validation-data-Resource", RECORD_COLUMNS, [{ Id: 9, Code: "V-RES-2", Problems: null, Severity: null }]),
    ...routes,
  });
}

const fetched = () => vi.mocked(fetch).mock.calls.map(([url, init]) => `${(init as RequestInit | undefined)?.method ?? "GET"} ${String(url)}`);
const queryBodies = (list: string) => vi.mocked(fetch).mock.calls
  .filter(([url]) => String(url) === `/api/${list}/query`).map(([, init]) => JSON.parse(String((init as RequestInit).body)));

describe("Validasyon çipi (K-134, K-139)", () => {
  it("sonuç ve sayı, süren durum, hiç çalışmamışsa çip yok", async () => {
    backend();
    renderApp("/veri/veri-yukleme", meAs("Key user"));
    expect(await screen.findByRole("button", { name: "Kaynak validasyonu: Uyarılı · 3. Bulguları aç" }, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Malzeme validasyonu: Hatalı · 2. Bulguları aç" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ürün ağacı validasyonu: Valide ediliyor. Bulguları aç" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Stok validasyonu/ })).not.toBeInTheDocument();
    expect(screen.getByText("Uyarılı · 3").className).toContain("sc-tag--risk");
    expect(screen.getByText("Hatalı · 2").className).toContain("sc-tag--critical");
  });

  it("çekmece: son parti, dört kart, kontrol türü kırılımı yok; Bulgular kural bazında; Esc kapatır", async () => {
    const user = userEvent.setup();
    backend();
    renderApp("/veri/veri-yukleme", meAs("Key user"));
    await user.click(await screen.findByRole("button", { name: /^Kaynak validasyonu/ }, { timeout: 5000 }));
    const drawer = await screen.findByRole("dialog", { name: /Validasyon · Kaynak/ });
    expect(drawer).toHaveClass("sc-drawer");
    expect(await within(drawer).findByText(/Excel · Cavide · 120 güncel kayıt/)).toBeInTheDocument();
    for (const label of ["Hatalı satır", "Uyarılı satır", "Bilgilendirme satırı", "Hata oranı"]) expect(within(drawer).getByText(label)).toBeInTheDocument();
    expect(within(drawer).getByText("%0,00")).toBeInTheDocument();
    expect(within(drawer).getByText("eşik yok")).toBeInTheDocument();
    expect(within(drawer).queryByText(/Yapısal|Mantıksal/)).not.toBeInTheDocument();
    const table = within(drawer).getByRole("table", { name: "Bulgular" });
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Kural", "Sınıf", "Satır sayısı"]);
    expect(within(table).getByText("Uyarı").className).toContain("sc-tag--soft");
    expect(within(table).getByRole("button", { name: "Kaynak tipi tek değil: kayıtları göster" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog", { name: /Validasyon · Kaynak/ })).not.toBeInTheDocument());
  });

  it("kurala tıklayınca Kayıtlar o kurala süzülmüş açılır; süzme kaldırılır", async () => {
    const user = userEvent.setup();
    backend();
    renderApp("/veri/veri-yukleme", meAs("Key user"));
    await user.click(await screen.findByRole("button", { name: /^Kaynak validasyonu/ }, { timeout: 5000 }));
    const drawer = await screen.findByRole("dialog", { name: /Validasyon · Kaynak/ });
    await user.click(await within(drawer).findByRole("button", { name: "Kaynak tipi tek değil: kayıtları göster" }));
    expect(within(drawer).getByRole("radio", { name: "Kayıtlar" })).toHaveAttribute("aria-checked", "true");
    expect(await within(drawer).findByText("V-RES-2", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(within(drawer).getByText("Kural: Kaynak tipi tek değil")).toBeInTheDocument();
    await waitFor(() => expect(queryBodies("validation-records-Resource").some((b) =>
      b.filters.some((f: { field: string; value: string }) => f.field === "RuleIds" && f.value === ",12,"))).toBe(true));
    await user.click(within(drawer).getByRole("button", { name: "Kural süzmesini kaldır" }));
    expect(within(drawer).queryByText("Kural: Kaynak tipi tek değil")).not.toBeInTheDocument();
  });

  it("eşik aşılırsa oran kartında eşik ve uyarı bandı", async () => {
    const user = userEvent.setup();
    backend({ "/api/validation/Resource": { body: { ...SUMMARY, error_rows: 12, error_rate: 0.97, threshold: 0.5 } as unknown as Reply["body"] } });
    renderApp("/veri/veri-yukleme", meAs("Key user"));
    await user.click(await screen.findByRole("button", { name: /^Kaynak validasyonu/ }, { timeout: 5000 }));
    expect(await screen.findByText("%0,97")).toBeInTheDocument();
    expect(screen.getByText("eşik %0,50")).toBeInTheDocument();
    expect(screen.getByText(/Hata oranı eşiği aşıyor/)).toBeInTheDocument();
  });

  it("Yeniden valide et sıraya koyar; onay bandı çıkmaz (K-139)", async () => {
    const user = userEvent.setup();
    backend({ "/api/validation/Resource/revalidate": { status: 202, body: { job_id: 5 } } });
    renderApp("/veri/veri-yukleme", meAs("Key user"));
    await user.click(await screen.findByRole("button", { name: /^Kaynak validasyonu/ }, { timeout: 5000 }));
    await user.click(await screen.findByRole("button", { name: "Yeniden valide et" }));
    await waitFor(() => expect(fetched()).toContain("POST /api/validation/Resource/revalidate"));
    expect(screen.queryByText(/sıraya girdi/)).not.toBeInTheDocument();
  });

  const job = (status: string, trigger = "Yükleme") => ({ id: 8, job_type: "Validasyon", summary: "Validasyon · Kaynak", channel: "Veri işleme", status,
    progress: status === "Bitti" ? "Kaynak · Uyarılı · 3" : "Valide ediliyor", queue_position: null, updated_at: "2026-11-06T10:00:00+00:00",
    requested_by: 1, validation: { entity: "Resource", trigger } });

  it("Kayıtlar üç seçenek: Bulgulu satırlar varsayılan, Kuralla değişenler, Tüm satırlar (K-143)", async () => {
    const user = userEvent.setup();
    backend();
    renderApp("/veri/veri-yukleme", meAs("Key user"));
    await user.click(await screen.findByRole("button", { name: /^Kaynak validasyonu/ }, { timeout: 5000 }));
    const drawer = await screen.findByRole("dialog", { name: /Validasyon · Kaynak/ });
    await user.click(within(drawer).getByRole("radio", { name: "Kayıtlar" }));
    expect(within(drawer).getByRole("radio", { name: "Bulgulu satırlar" })).toHaveAttribute("aria-checked", "true");
    const last = () => queryBodies("validation-records-Resource").at(-1)!.filters as { field: string; values?: unknown[] }[];
    await waitFor(() => expect(last()).toEqual([{ field: "HasFindings", op: "in", values: [true] }]));
    const lastData = () => queryBodies("validation-data-Resource").at(-1)!.filters as { field: string; values?: unknown[] }[];
    await user.click(within(drawer).getByRole("radio", { name: "Kuralla değişenler" }));  // Sorun ve Sınıf sonda olan liste (K-143)
    await waitFor(() => expect(lastData()).toEqual([{ field: "HasEffects", op: "in", values: [true] }]));
    await user.click(within(drawer).getByRole("radio", { name: "Tüm satırlar" }));
    await waitFor(() => expect(lastData()).toEqual([]));
  });

  it("satır menüsünde Veriyi gör: çekmece Kayıtlar · Tüm satırlar ile açılır, validasyonu olmayan tabloda da", async () => {
    const user = userEvent.setup();
    backend({ "/api/validation/Stock": { body: { ...SUMMARY, entity: "Stock", name: "Stok", state: null, outcome: null, rules: [] } as unknown as Reply["body"] },
              ...listRoutes("validation-data-Stock", RECORD_COLUMNS, [{ Id: 3, Code: "L-1", Problems: null, Severity: null, RuleIds: null }]) });
    renderApp("/veri/veri-yukleme", meAs("Key user"));
    await user.click(await screen.findByRole("button", { name: "Stok işlemleri" }, { timeout: 5000 }));
    await user.click(within(await screen.findByRole("menu")).getByRole("menuitem", { name: "Veriyi gör" }));
    const drawer = await screen.findByRole("dialog", { name: /Validasyon · Stok/ });
    expect(within(drawer).getByRole("radio", { name: "Kayıtlar" })).toHaveAttribute("aria-checked", "true");
    expect(within(drawer).getByRole("radio", { name: "Tüm satırlar" })).toHaveAttribute("aria-checked", "true");
    expect(await within(drawer).findByText("L-1", {}, { timeout: 5000 })).toBeInTheDocument();
  });

  it("çekim ya da validasyon işi değişince tablo kendiliğinden yenilenir (K-143)", async () => {
    backend({ "/api/jobs": { body: { jobs: [], counters: {} } as unknown as Reply["body"] } });
    renderApp("/veri/veri-yukleme", { ...meAs("Key user"), id: 1 });
    await screen.findByText("Kaynak", {}, { timeout: 5000 });
    await waitFor(() => expect(FakeWebSocket.instances.some((s) => s.url.includes("/api/ws"))).toBe(true));
    const before = queryBodies("data-entities").length;
    act(() => FakeWebSocket.instances.find((s) => s.url.includes("/api/ws"))!.send({ type: "job", job: { ...job("Bitti"), job_type: "Veri çekme", result: null, validation: null } }));
    await waitFor(() => expect(queryBodies("data-entities").length).toBeGreaterThan(before), { timeout: 3000 });
  });

  it("bitince bildirim; \"Sonucu aç\" çekmeceyi açar (tek tablo yolu)", async () => {
    const user = userEvent.setup();
    backend({ "/api/jobs": { body: { jobs: [job("Çalışıyor")], counters: {} } as unknown as Reply["body"] } });
    renderApp("/veri/veri-yukleme", { ...meAs("Key user"), id: 1 });
    await screen.findByText("Kaynak", {}, { timeout: 5000 });
    await waitFor(() => expect(FakeWebSocket.instances.some((s) => s.url.includes("/api/ws"))).toBe(true));
    act(() => FakeWebSocket.instances.find((s) => s.url.includes("/api/ws"))!.send({ type: "job", job: job("Bitti") }));
    const region = await screen.findByRole("region", { name: "Bildirimler" });
    expect(await within(region).findByText("Validasyon bitti")).toBeInTheDocument();
    expect(region).toHaveTextContent("Kaynak · Uyarılı · 3");
    await user.click(within(region).getByRole("button", { name: "Sonucu aç" }));
    expect(await screen.findByRole("dialog", { name: /Validasyon · Kaynak/ }, { timeout: 5000 })).toBeInTheDocument();
  });

  it("toplu çekimin tablo validasyonları bildirim vermez", async () => {
    backend({ "/api/jobs": { body: { jobs: [job("Çalışıyor", "Toplu çekim")], counters: {} } as unknown as Reply["body"] } });
    renderApp("/veri/veri-yukleme", { ...meAs("Key user"), id: 1 });
    await screen.findByText("Kaynak", {}, { timeout: 5000 });
    await waitFor(() => expect(FakeWebSocket.instances.some((s) => s.url.includes("/api/ws"))).toBe(true));
    act(() => FakeWebSocket.instances.find((s) => s.url.includes("/api/ws"))!.send({ type: "job", job: job("Bitti", "Toplu çekim") }));
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("Validasyon bitti")).not.toBeInTheDocument();
  });

  it("\"Sonucu aç\" çekmeceyi açar", async () => {
    backend();
    renderApp("/veri/veri-yukleme?validasyon=Resource", meAs("Admin"));
    expect(await screen.findByRole("dialog", { name: /Validasyon · Kaynak/ }, { timeout: 5000 })).toBeInTheDocument();  // ad özetten
    expect(await screen.findByText(/120 güncel kayıt/)).toBeInTheDocument();
  });
});

// ------------------------------------------------------------------ iş paneli (K-139)

const base = { channel: "Veri işleme", progress: null, queue_position: null, updated_at: "2026-11-06T12:41:00+00:00", created_at: "2026-11-06T12:41:00+00:00", requested_by: 1 };
const pull: Job = { ...base, id: 20, job_type: "Veri çekme", summary: "Veri çekme · 3 tablo", channel: "Veri çekme", status: "Bitti" };
const v = (id: number, entity: string, name: string, outcome: string | null, extra: Partial<Job> = {}, scope = "Tablo içi"): Job => ({
  ...base, id, job_type: "Validasyon", summary: `Validasyon · ${name}`, status: "Bitti",
  validation: { entity, name, trigger: "Toplu çekim", group: 20, scope, outcome, error_rows: 2, warning_rows: 3 }, ...extra,
});
const PULL_JOBS: Job[] = [pull, v(21, "Material", "Malzeme", "Hatalı"), v(22, "Stock", "Stok", "Geçti"), v(23, "BOM", "Ürün ağacı", "Uyarılı"),
  { ...v(24, "", "", null, {}, "Tablolar arası"), validation: { entity: null, trigger: "Toplu çekim", group: 20, scope: "Tablolar arası", outcome: null,
    tables: [{ entity: "BOM", name: "Ürün ağacı", outcome: "Uyarılı", error_rows: 0, warning_rows: 3 },
             { entity: "Material", name: "Malzeme", outcome: "Hatalı", error_rows: 2, warning_rows: 0 },
             { entity: "Stock", name: "Stok", outcome: "Uyarılı", error_rows: 0, warning_rows: 1 }] } }];

describe("İş paneli kartları (K-139)", () => {
  it("çekim ve validasyonları tek kart; tablolar arası en sonda", () => {
    const cards = buildCards(PULL_JOBS);
    expect(cards).toHaveLength(1);
    expect(cards[0].children!.map((c) => c.id)).toEqual([21, 22, 23, 24]);
  });

  it("özet tablolar arası validasyondan sonraki sonuçtan", () => {
    expect(groupOutcomes(PULL_JOBS.slice(1))).toEqual([{ outcome: "Hatalı", count: 1 }, { outcome: "Uyarılı", count: 2 }]);
    expect(groupOutcomes(PULL_JOBS.slice(1, 4))).toEqual([{ outcome: "Hatalı", count: 1 }, { outcome: "Uyarılı", count: 1 }, { outcome: "Geçti", count: 1 }]);
  });

  it("durum çipi: bitmiş validasyonda sonuç ve sayı, ötekiler gri", () => {
    expect(cardState(v(21, "Material", "Malzeme", "Hatalı"))).toEqual({ text: "Hatalı · 2", tone: "critical", running: false });
    expect(cardState(v(22, "Stock", "Stok", "Geçti"))).toEqual({ text: "Geçti", tone: "ok", running: false });
    expect(cardState({ ...pull, status: "Sırada", queue_position: 2 })).toEqual({ text: "Sırada · sıra 2", tone: "neutral", running: false });
  });

  it("panel: başlık, özet, açılınca tablo satırları ve Aç; son 5 kart; Tümünü gör", async () => {
    const user = userEvent.setup();
    const others = Array.from({ length: 6 }, (_, i): Job => ({ ...base, id: 30 + i, job_type: "Dışa aktarım", summary: `Excel ${i}`, status: "Bitti" }));
    backend({ "/api/jobs": { body: { jobs: [...PULL_JOBS, ...others], counters: {} } as unknown as Reply["body"] } });
    renderApp("/veri/veri-yukleme", { ...meAs("Admin"), id: 1 });
    await user.click(await screen.findByTestId("job-indicator"));
    const panel = screen.getByRole("dialog", { name: "Arka plandaki işler" });
    await waitFor(() => expect(within(panel).getAllByRole("listitem").length).toBeGreaterThan(0));
    expect(panel.querySelectorAll(".sc-job-list > li")).toHaveLength(5);
    expect(within(panel).queryByText(/Veri çekme · 3 tablo/)).not.toBeInTheDocument();  // en yeni 5 kart
    expect(within(panel).getByRole("button", { name: "Tümünü gör" })).toBeInTheDocument();
  });

  it("çekim kartı açılır: tablolar, çip ve Aç; tablolar arası satırı", async () => {
    const user = userEvent.setup();
    backend({ "/api/jobs": { body: { jobs: PULL_JOBS, counters: {} } as unknown as Reply["body"] } });
    renderApp("/veri/veri-yukleme", { ...meAs("Key user"), id: 1 });
    await user.click(await screen.findByTestId("job-indicator"));
    const panel = screen.getByRole("dialog", { name: "Arka plandaki işler" });
    const toggle = await within(panel).findByRole("button", { name: /Veri çekme · 3 tablo · \d\d:\d\d: tabloları göster/ });
    expect(panel).toHaveTextContent("1 Hatalı");
    expect(panel).toHaveTextContent("2 Uyarılı");
    await user.click(toggle);
    const rows = panel.querySelector(".sc-job-card-rows")!;
    expect(rows).toHaveTextContent("Malzeme");
    expect(rows).toHaveTextContent("Stok");
    expect(rows).toHaveTextContent("Uyarılı · 1");  // tablolar arası sonrası
    expect(rows.lastElementChild).toHaveTextContent("Tablolar arası");
    await user.click(within(rows as HTMLElement).getByRole("button", { name: "Malzeme: aç" }));
    expect(await screen.findByRole("dialog", { name: /Validasyon · / }, { timeout: 5000 })).toBeInTheDocument();
  });
});

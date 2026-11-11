// Sistem sağlığı (ekran 24; K-106, K-107) ve iş panelinde neden penceresi.
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, FakeWebSocket, ME, meAs, mockApi, renderApp, type Reply } from "../test/helpers";
import { formatBytes } from "./SystemHealth";
import type { HealthSummary } from "./systemHealthApi";

useTableTestSetup();

const SUMMARY: HealthSummary = {
  server_time: "2026-11-03T12:20:00+00:00",
  cards: {
    queue: { queued: 3, oldest_wait_minutes: 4, threshold: 10, warn: false },
    interactive: { running: 2, limit: 3 },
    errors: { last_7_days: 3, resolved: 2 },
    disk: { percent: 46, free_bytes: 212 * 1024 ** 3, threshold: 85, warn: false, database_bytes: 1.2 * 1024 ** 3, data_versions: 3 },
  },
  services: [
    { key: "app", status: "Çalışıyor", version: "0.19.0" },
    { key: "engine", status: "Çalışıyor", heartbeat_at: "2026-11-03T12:19:58+00:00", version: "0.19.0", busy: 2 },
    { key: "database", status: "Çalışıyor", ms: 12, pool_in_use: 6, pool_size: 20 },
    { key: "notifications", status: "Çalışıyor", connections: 14 },
    { key: "scheduler", status: "Gecikti", checked_at: "2026-11-03T12:19:58+00:00", late: "Hafta içi kısmi",
      next: { name: "Pazar tam", at: "2026-11-08T23:00:00+00:00" }, last: { name: "Hafta içi kısmi", state: "Durdu", at: "2026-11-02T23:14:00+00:00" } },
  ],
};

const EXPORT = { title: "İş kuyruğu", file_slug: "is-kuyrugu", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const JOB_COLUMNS = [col("Id", "No", "integer", "number"), col("JobType", "Tür", "text", "text"), col("Summary", "İş", "text", "text"), col("RequesterName", "Kullanıcı", "text", "text"),
                     col("Status", "Durum", "text", "text"), col("QueuePosition", "Sıra", "integer", "number")];
const EVENT_COLUMNS = [col("Message", "Hata", "text", "text"), col("Resolution", "Sistem aksiyonu", "text", "text")];
const job = (Id: number, extra = {}) => ({ Id, JobType: "Çalışma", Summary: null, Channel: "Hesaplama", RequesterName: "Mert", Status: "Sırada", QueuePosition: 1,
                                           RequestedBy: 77, IsProtected: false, ...extra });

function backend(routes: Record<string, Reply | ((url: string, init?: RequestInit) => Reply)> = {}, rows: object[] = [job(61)]) {
  const list = (name: string, columns: unknown[], data: object[]) => ({
    [`/api/${name}/columns`]: { body: { chunk_size: 100, columns, export: EXPORT } },
    [`/api/${name}/query`]: { body: { rows: data, filtered: data.length, total: data.length } },
    [`/api/${name}/views`]: { body: { views: [], default_view_id: null } },
  });
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/system-health": { body: SUMMARY as unknown as Reply["body"] },
    ...list("job-queue", JOB_COLUMNS, rows),
    ...list("job-runs", JOB_COLUMNS, [job(50, { Status: "Bitti" })]),
    ...list("system-events", EVENT_COLUMNS, [{ Id: 9, Message: "Örnek olay", Resolution: "Devam etti" }]),
    ...routes,
  });
}

const calls = (m: ReturnType<typeof mockApi>, url: string) => m.mock.calls.filter(([u]) => String(u) === url);

async function open(role = "Admin", routes = {}, rows?: object[]) {
  const m = backend(routes, rows);
  const me = role === "Admin" ? { ...meAs("Admin"), id: 5 } : meAs(role);
  renderApp("/yonetim/sistem-sagligi", me);
  // Dosyanın ilk testinde tablo soğuk çizilir; tam takımın paralel yükünde 5 sn yetmeyebiliyor.
  await screen.findByRole("button", { name: `#${(rows?.[0] as { Id: number } | undefined)?.Id ?? 61} işinin işlemleri` }, { timeout: 10_000 });
  return m;
}

const menuOf = async (user: ReturnType<typeof userEvent.setup>, id = 61) => {
  await user.click(screen.getByRole("button", { name: `#${id} işinin işlemleri` }));
  return screen.findByRole("menu", { name: `#${id} işinin işlemleri` });
};

describe("ekran", () => {
  it("kartlar, servis şeridi, bölümler", async () => {
    await open();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Sistem sağlığı");
    expect(screen.getByText("En uzun bekleyen 4 dk")).toBeInTheDocument();
    expect(screen.getByText("Aktif hesaplama")).toBeInTheDocument();
    expect(screen.getByText("2 / 3")).toBeInTheDocument();
    expect(screen.getByText("2 tanesi çözüldü")).toBeInTheDocument();
    expect(screen.getByText("%46")).toBeInTheDocument();
    expect(screen.getByText("212,0 GB boş · eşik %85")).toBeInTheDocument();
    expect(screen.getByTestId("service-app")).toHaveTextContent("UygulamaÇalışıyorSürüm 0.19.0");
    expect(screen.getByTestId("service-engine")).toHaveTextContent("2 iş çalışıyor");
    expect(screen.getByTestId("service-engine")).toHaveTextContent("son sinyal");
    expect(screen.getByTestId("service-database")).toHaveTextContent("12 ms · 6 / 20 bağlantı · 1,2 GB · 3 veri versiyonu");
    expect(screen.getByTestId("service-notifications")).toHaveTextContent("14 bağlantı");
    const scheduler = screen.getByTestId("service-scheduler");  // K-163
    expect(scheduler).toHaveTextContent("Zamanlayıcı");
    expect(within(scheduler).getByText("Gecikti")).toHaveClass("sc-tag--risk");
    expect(scheduler).toHaveTextContent(/son kontrol \d\d:\d\d:\d\d · Hafta içi kısmi saatinde başlamadı · sıradaki: Pazar tam, .+ · son akış: Hafta içi kısmi, Durdu/);
    expect(screen.getByRole("radio", { name: "İş kuyruğu" })).toBeChecked();
    expect(screen.getByText("Sırada")).toHaveClass("sc-tag--risk");
    expect(document.body.textContent).not.toMatch(/K-\d+/);
  });

  it("hata yoksa alt satır yok", async () => {
    await open("Admin", { "/api/system-health": { body: {
      ...SUMMARY, cards: { ...SUMMARY.cards, errors: { last_7_days: 0, resolved: 0 } },
    } as unknown as Reply["body"] } });
    expect(screen.getByText("Son 7 gün hata").closest(".sc-kpi")?.querySelector(".sc-kpi-note")).toBeNull();
    expect(screen.queryByText("0 tanesi çözüldü")).toBeNull();
  });

  it("eşik aşımı kırmızı; motor kapalı rozeti", async () => {
    await open("Admin", { "/api/system-health": { body: {
      ...SUMMARY,
      cards: { ...SUMMARY.cards, queue: { ...SUMMARY.cards.queue, warn: true }, disk: { ...SUMMARY.cards.disk, percent: 91, warn: true } },
      services: SUMMARY.services.map((s) => (s.key === "engine" ? { ...s, status: "Kapalı" } : s)),
    } as unknown as Reply["body"] } });
    expect([...document.querySelectorAll(".sc-kpi--over")].map((e) => e.textContent)).toEqual(["3", "%91"]);
    expect(within(screen.getByTestId("service-engine")).getByText("Kapalı")).toHaveClass("sc-tag--critical");
  });

  it.each(["Key user", "End user"])("%s açamaz", (role) => {
    backend();
    renderApp("/yonetim/sistem-sagligi", meAs(role));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Bu ekranı açma yetkiniz yok");
  });

  it("bölümler ortak tablolarla açılır", async () => {
    const user = userEvent.setup();
    const m = await open();
    await user.click(screen.getByRole("radio", { name: "Son çalışmalar" }));
    expect(await screen.findByText("Bitti", {}, { timeout: 5000 })).toBeInTheDocument();
    expect(calls(m, "/api/job-runs/query").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("radio", { name: "Hatalar" }));
    expect(await screen.findByText("Örnek olay", {}, { timeout: 5000 })).toBeInTheDocument();
  });

  it("boyut biçimi", () => {
    expect(formatBytes(1.5 * 1024 ** 3)).toBe("1,5 GB");
    expect(formatBytes(400 * 1024 ** 2)).toBe("400 MB");
  });
});

describe("canlılık", () => {
  it("health mesajı ekranı yeniler, satırlar yerinde kalır", async () => {
    const m = await open();
    const before = calls(m, "/api/system-health").length;
    await waitFor(() => expect(FakeWebSocket.instances.length).toBeGreaterThan(0));
    act(() => FakeWebSocket.instances[0].send({ type: "health" }));
    act(() => FakeWebSocket.instances[0].send({ type: "health" }));
    await waitFor(() => expect(calls(m, "/api/system-health").length).toBe(before + 1), { timeout: 4000 });
    await waitFor(() => expect(calls(m, "/api/job-queue/query").length).toBeGreaterThan(1));
    expect(screen.getByRole("button", { name: "#61 işinin işlemleri" })).toBeInTheDocument();
  });
});

describe("hata durumu", () => {
  it("sunucuya ulaşılamazsa son değerler kalır", async () => {
    let down = false;
    await open("Admin", { "/api/system-health": () => {
      if (down) throw new TypeError("Failed to fetch");
      return { body: SUMMARY as unknown as Reply["body"] };
    } });
    down = true;
    await waitFor(() => expect(FakeWebSocket.instances.length).toBeGreaterThan(0));
    act(() => FakeWebSocket.instances[0].send({ type: "health" }));
    expect(await screen.findByText(/Sunucuya ulaşılamıyor\. Son bilgi/, {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByText("%46")).toBeInTheDocument();
  });

  it("veritabanına ulaşılamazsa ayrı metin", async () => {
    backend({ "/api/system-health": { status: 503, body: { error: { code: "database_unavailable", message: "x", trace_id: "t", details: [] } } } });
    renderApp("/yonetim/sistem-sagligi", meAs("Admin"));
    expect(await screen.findByText("Veritabanına ulaşılamıyor.")).toBeInTheDocument();
  });
});

describe("iş işlemleri", () => {
  it("başkasının işini iptal: neden zorunlu, kiremit düğme", async () => {
    const user = userEvent.setup();
    const m = await open("Admin", { "/api/jobs/61/cancel": { body: {} } });
    const menu = await menuOf(user);
    await user.click(within(menu).getByRole("menuitem", { name: "İptal et" }));
    const dialog = await screen.findByRole("dialog", { name: "İşi iptal et" });
    expect(dialog).toHaveTextContent("Çalışma · Mert · sıra 1");
    expect(dialog).toHaveTextContent("İş sahibine bildirim gider.");
    const submit = within(dialog).getByRole("button", { name: "İptal et" });
    expect(submit).toHaveClass("sc-btn--danger");
    expect(submit).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/Neden/), "Kuyruk boşalıyor");
    await user.click(submit);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(JSON.parse(String(calls(m, "/api/jobs/61/cancel")[0][1]?.body))).toEqual({ reason: "Kuyruk boşalıyor" });
    expect(await screen.findByText("İş iptal edildi · #61")).toBeInTheDocument();
  });

  it("özetli iş: pencerede ve bildirimde özet", async () => {
    const user = userEvent.setup();
    await open("Admin", { "/api/jobs/61/cancel": { body: {} } }, [job(61, { JobType: "Dışa aktarım", Summary: "Malzeme listesi · 142.000 satır" })]);
    expect(screen.getByRole("columnheader", { name: /^İş/ })).toBeInTheDocument();
    const menu = await menuOf(user);
    await user.click(within(menu).getByRole("menuitem", { name: "İptal et" }));
    const dialog = await screen.findByRole("dialog", { name: "İşi iptal et" });
    expect(dialog).toHaveTextContent("Malzeme listesi · 142.000 satır · Mert · sıra 1");
    await user.type(within(dialog).getByLabelText(/Neden/), "x");
    await user.click(within(dialog).getByRole("button", { name: "İptal et" }));
    expect(await screen.findByText("İş iptal edildi · Malzeme listesi · 142.000 satır")).toBeInTheDocument();
  });

  it("kendi işi tek tık", async () => {
    const user = userEvent.setup();
    const m = await open("Admin", { "/api/jobs/61/cancel": { body: {} } }, [job(61, { RequestedBy: 5 })]);
    const menu = await menuOf(user);
    await user.click(within(menu).getByRole("menuitem", { name: "İptal et" }));
    await waitFor(() => expect(calls(m, "/api/jobs/61/cancel").length).toBe(1));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(JSON.parse(String(calls(m, "/api/jobs/61/cancel")[0][1]?.body))).toEqual({});
  });

  it("öne alma: bildirim, pencere yok", async () => {
    const user = userEvent.setup();
    const m = await open("Admin", { "/api/jobs/61/prioritize": { body: {} } });
    const menu = await menuOf(user);
    await user.click(within(menu).getByRole("menuitem", { name: "Öne al" }));
    await waitFor(() => expect(calls(m, "/api/jobs/61/prioritize").length).toBe(1));
    expect(await screen.findByText("İş öne alındı · #61")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it.each([
    ["çalışan iş", { Status: "Çalışıyor" }, "Yalnız sıradaki iş iptal edilebilir.", "Yalnız sıradaki iş öne alınabilir."],
    ["aktarım", { JobType: "Aktarım" }, "Aktarım işi iptal edilemez.", null],
    ["gece", { Channel: "Gece" }, null, "Gece işleri öne alınamaz."],
    ["System owner işi", { IsProtected: true, RequesterName: "Smartchain" },
     "Bu işlem için System owner yetkisi gerekir. Smartchain desteğine başvurun.", "Bu işlem için System owner yetkisi gerekir. Smartchain desteğine başvurun."],
  ])("%s: öğeler pasif ve nedenli", async (_name, extra, cancelReason, moveReason) => {
    const user = userEvent.setup();
    await open("Admin", {}, [job(61, extra)]);
    const menu = await menuOf(user);
    const check = (name: string, reason: string | null) => {
      const item = within(menu).getByRole("menuitem", { name });
      if (reason) {
        expect(item).toBeDisabled();
        expect(item).toHaveAttribute("title", reason);
      } else {
        expect(item).toBeEnabled();
      }
    };
    check("İptal et", cancelReason);
    check("Öne al", moveReason);
  });

  it("System owner kendi korumalı işinde pasif görmez", async () => {
    const user = userEvent.setup();
    await open("System owner", {}, [job(61, { IsProtected: true, RequestedBy: ME.id })]);
    const menu = await menuOf(user);
    expect(within(menu).getByRole("menuitem", { name: "İptal et" })).toBeEnabled();
  });
});

describe("hata detayı", () => {
  const detail = (extra = {}) => ({ id: 9, occurred_at: "2026-11-03T12:00:00+00:00", component: "Motor", message: "Örnek olay", resolution: "Devam etti",
                                    is_resolved: false, job_id: 61, trace_id: "abc123", detail: null, ...extra });

  async function openEvent(body: object) {
    const user = userEvent.setup();
    await open("Admin", { "/api/system-events/9": { body: body as Reply["body"] } });
    await user.click(screen.getByRole("radio", { name: "Hatalar" }));
    await user.click(await screen.findByRole("button", { name: "Hata detayı" }, { timeout: 5000 }));
    return screen.findByRole("dialog", { name: "Hata detayı" });
  }

  it("alanlar; teknik özet yoksa satır yok", async () => {
    const dialog = await openEvent(detail());
    expect(await within(dialog).findByText("Motor")).toBeInTheDocument();
    expect(dialog).toHaveTextContent("abc123");
    expect(dialog).not.toHaveTextContent("Teknik özet");
    expect(within(dialog).queryByRole("button", { name: "Vazgeç" })).toBeNull();
  });

  it("teknik özet gelirse görünür", async () => {
    const dialog = await openEvent(detail({ detail: "RuntimeError" }));
    expect(await within(dialog).findByText("RuntimeError")).toBeInTheDocument();
    expect(dialog).toHaveTextContent("Teknik özet");
  });
});

describe("iş paneli", () => {
  it("işiniz iptal edilince bildirim", async () => {
    backend({ "/api/jobs": { body: { jobs: [], counters: {} } } });
    renderApp("/ana-sayfa", meAs("Key user"));
    await waitFor(() => expect(FakeWebSocket.instances.length).toBeGreaterThan(0));
    const message = { type: "job", job: { id: 61, job_type: "Dışa aktarım", summary: "Malzeme listesi · 142.000 satır", channel: "Excel", status: "İptal", progress: null, queue_position: null,
                                           updated_at: "2026-11-03T12:00:00+00:00", cancel_reason: "Kuyruk boşalıyor" } };
    act(() => FakeWebSocket.instances[0].send(message));
    expect(await screen.findByText("İşiniz iptal edildi · Malzeme listesi · 142.000 satır: Kuyruk boşalıyor")).toBeInTheDocument();
  });
});

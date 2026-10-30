// Kabuk (docs/12, K-82): menü, arama, daraltma, boş ekranlar, bağlam çubuğu, iş göstergesi, yazı boyutu.
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { mockApi, mockSocket, renderApp } from "../test/helpers";

const menu = () => screen.getByRole("navigation", { name: "Ana menü" });

beforeEach(() => {
  mockApi();
  mockSocket();
});

describe("kenar menü", () => {
  it("grupları K-82 sırasıyla gösterir", () => {
    renderApp();
    const heads = within(menu()).getAllByRole("button", { expanded: true }).map((b) => b.textContent);
    expect(heads).toEqual(["Planlama", "Takip", "Veri", "Parametre", "Yönetim"]);
    expect(within(menu()).getByRole("link", { name: /Ana sayfa/ })).toHaveClass("is-active");
  });

  it("grup kapanır ve tercih hatırlanır", async () => {
    const user = userEvent.setup();
    const { unmount } = renderApp();
    await user.click(within(menu()).getByRole("button", { name: "Veri" }));
    expect(within(menu()).queryByRole("link", { name: /Ana veri/ })).toBeNull();
    unmount();
    renderApp();
    expect(within(menu()).getByRole("button", { name: "Veri" })).toHaveAttribute("aria-expanded", "false");
  });

  it("çalışma kapalıyken çalışmanın ekranları gri ve tıklanmaz", async () => {
    const user = userEvent.setup();
    renderApp();
    const gantt = within(menu()).getByText("Gantt").closest("[aria-disabled]")!;
    expect(gantt).toHaveAttribute("title", "Önce bir çalışma açın");
    // U-3: pasiflik yalnız renkle değil, kilit ikonuyla da gösterilir; açık ekranlarda kilit yok.
    expect(within(gantt as HTMLElement).getByTestId("lock")).toBeInTheDocument();
    expect(within(menu()).getAllByTestId("lock")).toHaveLength(10);
    const senaryolar = within(menu()).getByRole("link", { name: /Senaryolar/ });
    expect(within(senaryolar).queryByTestId("lock")).toBeNull();
    await user.click(gantt);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Ana sayfa");
  });

  it("ekrana tıklayınca boş sayfası ve adımı açılır", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(within(menu()).getByRole("link", { name: /Kullanıcılar/ }));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Kullanıcılar");
    expect(screen.getByText("Bu ekran 2.3 adımında gelecek.")).toBeInTheDocument();
  });
});

describe("menüde arama", () => {
  it("ekran adıyla bulur, Türkçe harfler doğru", async () => {
    const user = userEvent.setup();
    renderApp();
    const box = within(menu()).getByRole("searchbox", { name: "Ekran ara" });
    await user.type(box, "kayn");
    const names = within(menu()).getAllByRole("option").map((o) => o.textContent);
    expect(names).toEqual(["Kaynak doluluk", "Kaynak bazlı planlama"]);
    await user.clear(box);
    await user.type(box, "SİSTEM");
    expect(within(menu()).getAllByRole("option").map((o) => o.textContent)).toEqual(["Sistem sağlığı"]);
    await user.keyboard("{Enter}");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Sistem sağlığı");
  });

  it("Ctrl+K arama kutusuna odaklanır, menü daraltılmışsa açar", async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole("button", { name: "Menüyü daralt" }));
    expect(within(menu()).queryByRole("searchbox")).toBeNull();
    await user.keyboard("{Control>}k{/Control}");
    expect(within(menu()).getByRole("searchbox", { name: "Ekran ara" })).toHaveFocus();
  });
});

describe("daraltılmış menü", () => {
  it("yalnız ikonlar, ad üzerine gelince; hâl hatırlanır; grupta alt panel", async () => {
    const user = userEvent.setup();
    const { unmount } = renderApp();
    await user.click(screen.getByRole("button", { name: "Menüyü daralt" }));
    expect(within(menu()).queryByText("Senaryolar")).toBeNull();
    expect(within(menu()).getByRole("link", { name: "Ana sayfa" })).toHaveAttribute("title", "Ana sayfa");
    await user.hover(within(menu()).getByRole("button", { name: "Planlama" }));
    const panel = within(menu()).getByRole("menu", { name: "Planlama" });
    expect(within(panel).getByRole("menuitem", { name: "Senaryolar" })).toBeInTheDocument();
    const yayin = within(panel).getByText("Yayın").closest("[aria-disabled]")!;
    expect(yayin).toHaveAttribute("aria-disabled", "true");
    expect(within(yayin as HTMLElement).getByTestId("lock")).toBeInTheDocument();
    unmount();
    renderApp();
    expect(screen.getByRole("button", { name: "Menüyü aç" })).toBeInTheDocument();
  });
});

describe("sayfalar", () => {
  it("her ekran kendi adresinde açılır", () => {
    renderApp("/veri/ana-veri");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Ana veri");
    expect(screen.getByText("Bu ekran 6.1 adımında gelecek.")).toBeInTheDocument();
  });

  it("kök adres Ana sayfa'ya, bilinmeyen adres 'Sayfa bulunamadı'", () => {
    renderApp("/");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Ana sayfa");
    expect(screen.getByText("Bu ekran 9.1 adımında gelecek.")).toBeInTheDocument();
  });

  it("bilinmeyen adres", () => {
    renderApp("/yok/boyle-bir-ekran");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Sayfa bulunamadı");
  });
});

describe("bağlam çubuğu", () => {
  it("veri versiyonu yalnız 'Veri v35 · 27.10.2026 12:20' (sentetik etiketi yok)", async () => {
    renderApp();
    await waitFor(() => expect(screen.getByTestId("data-version")).toHaveTextContent("Veri v35 · 27.10.2026 12:20"));
    expect(screen.getByTestId("data-version").textContent).toBe("Veri v35 · 27.10.2026 12:20");
    expect(screen.queryByText(/sentetik/i)).toBeNull();
  });

  it("veri yoksa, API cevap vermiyorsa, veritabanına ulaşılamıyorsa", async () => {
    mockApi({ "/api/data-versions/current": { status: 404, body: { error: { code: "no_data_version", message: "", trace_id: "" } } } });
    const { unmount } = renderApp();
    await waitFor(() => expect(screen.getByTestId("data-version")).toHaveTextContent("Veri yüklenmedi"));
    unmount();
    mockApi({ "/api/data-versions/current": "offline" });
    const second = renderApp();
    await waitFor(() => expect(screen.getByTestId("data-version")).toHaveTextContent("API'ye ulaşılamıyor"));
    second.unmount();
    mockApi({ "/api/data-versions/current": { status: 503, body: { error: { code: "database_unavailable", message: "", trace_id: "" } } } });
    renderApp();
    await waitFor(() => expect(screen.getByTestId("data-version")).toHaveTextContent("Veritabanına ulaşılamıyor"));
  });

  it("senaryo, plan versiyonu ve dönem yerleri pasif", () => {
    renderApp();
    expect(screen.getByText("Senaryo: —")).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Dönem: —")).toHaveAttribute("title", "Senaryo ve dönem seçimi 8.1'de gelir");
  });
});

describe("iş göstergesi", () => {
  const job = (id: number, status: string, extra = {}) => ({
    id, job_type: "Çalışma", channel: "Etkileşim", status, progress: null, queue_position: null,
    updated_at: "2026-10-27T09:20:00+00:00", ...extra,
  });

  it("açılıştaki işler ve WebSocket mesajlarıyla canlı", async () => {
    mockApi({ "/api/jobs": { body: { jobs: [job(5, "Çalışıyor")], counters: {} } } });
    const Socket = mockSocket();
    renderApp();
    const indicator = screen.getByTestId("job-indicator");
    await waitFor(() => expect(indicator).toHaveTextContent("1 çalışıyor · 0 sırada"));
    expect(Socket.instances[0].url).toMatch(/\/api\/ws$/);  // kullanıcı oturumdan (çerez), adreste değil (K-97)
    act(() => {
      Socket.instances[0].open();
      Socket.instances[0].send({ type: "job", job: job(6, "Sırada", { queue_position: 1 }) });
    });
    expect(indicator).toHaveTextContent("1 çalışıyor · 1 sırada");
    act(() => Socket.instances[0].send({ type: "job", job: job(5, "Bitti") }));
    expect(indicator).toHaveTextContent("0 çalışıyor · 1 sırada");
    fireEvent.click(indicator);
    const panel = screen.getByRole("dialog", { name: "Arka plandaki işler" });
    expect(panel).toHaveTextContent("Bildirimler bağlı");
    expect(panel).toHaveTextContent("#6 Çalışma · Sırada · sıra 1");
  });

  it("bağlantı koparsa yedek moda geçer ve 10 sn sonra yeniden bağlanır", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = mockApi();
    const Socket = mockSocket();
    renderApp();
    act(() => Socket.instances[0].open());
    act(() => Socket.instances[0].drop());
    expect(screen.getByTestId("job-indicator")).toHaveAttribute("title", expect.stringContaining("Yedek mod"));
    const before = fetchMock.mock.calls.filter(([u]) => String(u).startsWith("/api/jobs")).length;
    await act(async () => vi.advanceTimersByTime(30_000));
    expect(Socket.instances.length).toBeGreaterThanOrEqual(2);
    const after = fetchMock.mock.calls.filter(([u]) => String(u).startsWith("/api/jobs")).length;
    expect(after).toBeGreaterThan(before);
  });
});

describe("kullanıcı menüsü", () => {
  it("oturumdaki kullanıcıyı ve yazı boyutunu gösterir; boyut ölçekler ve hatırlanır", async () => {
    const user = userEvent.setup();
    const { unmount } = renderApp();
    await user.click(screen.getByRole("button", { name: "Kullanıcı menüsü: Mert Planlama" }));
    expect(screen.getByRole("dialog", { name: "Kullanıcı menüsü" })).toHaveTextContent("Mert Planlamaplanlama · System owner");
    expect(document.documentElement.style.fontSize).toBe("13px");
    await user.click(screen.getByRole("radio", { name: /Büyük/ }));
    expect(document.documentElement.style.fontSize).toBe("16px");
    expect(screen.getByRole("button", { name: "Çıkış" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Şifre değiştir" })).toBeEnabled();
    unmount();
    renderApp();
    expect(document.documentElement.style.fontSize).toBe("16px");
  });
});

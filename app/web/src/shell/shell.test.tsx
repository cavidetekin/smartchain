// Kabuk (docs/12, K-82): menü, arama, daraltma, boş ekranlar, bağlam çubuğu, iş göstergesi, yazı boyutu.
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { Me } from "../auth/authApi";
import { ME, meAs, mockApi, mockSocket, renderApp } from "../test/helpers";

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
    await user.click(within(menu()).getByRole("link", { name: /Veri kalitesi/ }));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Veri kalitesi");
    expect(screen.getByText("Bu ekran 6.5 adımında gelecek.")).toBeInTheDocument();
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
    expect(within(menu()).getAllByRole("option").map((o) => o.textContent)).toEqual(["Sistem sağlığı", "Sistem ayarları"]);
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
  it("yalnız ikonlar, ad üzerine gelince; hâl hatırlanır; grup ikonuna basınca liste", async () => {
    const user = userEvent.setup();
    const { unmount } = renderApp();
    await user.click(screen.getByRole("button", { name: "Menüyü daralt" }));
    expect(within(menu()).queryByText("Senaryolar")).toBeNull();
    expect(within(menu()).getByRole("link", { name: "Ana sayfa" })).toHaveAttribute("title", "Ana sayfa");
    await user.hover(within(menu()).getByRole("button", { name: "Planlama" }));
    expect(within(menu()).queryByRole("menu")).toBeNull();  // yalnız basınca açılır
    await user.click(within(menu()).getByRole("button", { name: "Planlama" }));
    const panel = within(menu()).getByRole("menu", { name: "Planlama" });
    expect(within(panel).getByRole("menuitem", { name: "Senaryolar" })).toBeInTheDocument();
    const yayin = within(panel).getByText("Yayın").closest("[aria-disabled]")!;
    expect(yayin).toHaveAttribute("aria-disabled", "true");
    expect(within(yayin as HTMLElement).getByTestId("lock")).toBeInTheDocument();
    unmount();
    renderApp();
    expect(screen.getByRole("button", { name: "Menüyü aç" })).toBeInTheDocument();
  });

  async function collapsedMenu(path?: string, me?: Me) {
    const user = userEvent.setup();
    renderApp(path, me);
    await user.click(screen.getByRole("button", { name: "Menüyü daralt" }));
    return user;
  }

  it("ekran seçilince ekran açılır, liste kapanır, menü kapalı kalır", async () => {
    const user = await collapsedMenu();
    await user.click(within(menu()).getByRole("button", { name: "Veri" }));
    await user.click(within(menu()).getByRole("menuitem", { name: "Ana veri" }));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Ana veri");
    expect(within(menu()).queryByRole("menu")).toBeNull();
    expect(screen.getByRole("button", { name: "Menüyü aç" })).toBeInTheDocument();
  });

  it("Ana sayfa doğrudan ekrana gider", async () => {
    const user = await collapsedMenu("/veri/ana-veri");
    await user.click(within(menu()).getByRole("link", { name: "Ana sayfa" }));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Ana sayfa");
    expect(within(menu()).queryByRole("menu")).toBeNull();
  });

  it("grupta görünen tek ekran kaldıysa ikon doğrudan ona gider", async () => {
    const me = meAs("Admin");
    const user = await collapsedMenu(undefined, { ...me, permissions: { ...me.permissions, 88: "none", 91: "none", 92: "none", 98: "none" } });
    expect(within(menu()).queryByRole("button", { name: "Yönetim" })).toBeNull();
    await user.click(within(menu()).getByRole("link", { name: "Sistem sağlığı" }));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Sistem sağlığı");
  });

  it("dışarı tıklama ve Esc kapatır; ikona yeniden basmak da", async () => {
    const user = await collapsedMenu();
    const veri = within(menu()).getByRole("button", { name: "Veri" });
    await user.click(veri);
    await user.click(screen.getByRole("heading", { level: 1 }));
    expect(within(menu()).queryByRole("menu")).toBeNull();
    await user.click(veri);
    await user.keyboard("{Escape}");
    expect(within(menu()).queryByRole("menu")).toBeNull();
    expect(veri).toHaveFocus();
    await user.click(veri);
    await user.click(veri);
    expect(within(menu()).queryByRole("menu")).toBeNull();
    expect(veri).toHaveAttribute("aria-expanded", "false");
  });

  it("başka gruba basınca liste değişir", async () => {
    const user = await collapsedMenu();
    await user.click(within(menu()).getByRole("button", { name: "Veri" }));
    await user.click(within(menu()).getByRole("button", { name: "Takip" }));
    expect(within(menu()).getAllByRole("menu")).toHaveLength(1);
    expect(within(menu()).getByRole("menu", { name: "Takip" })).toBeInTheDocument();
  });

  it("klavyeyle gezilir: ok, Home, End, Enter; kilitli ekran atlanır", async () => {
    const user = await collapsedMenu();
    within(menu()).getByRole("button", { name: "Veri" }).focus();
    await user.keyboard("{ArrowDown}");
    const panel = within(menu()).getByRole("menu", { name: "Veri" });
    const item = (name: string) => within(panel).getByRole("menuitem", { name });
    expect(item("Veri yükleme")).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(item("Dünden bugüne")).toHaveFocus();
    await user.keyboard("{End}");
    expect(item("Veri kalitesi")).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(item("Veri yükleme")).toHaveFocus();
    await user.keyboard("{ArrowUp}");
    expect(item("Veri kalitesi")).toHaveFocus();
    await user.keyboard("{Home}{ArrowDown}{ArrowDown}{Enter}");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Veri kuralları");
    expect(within(menu()).queryByRole("menu")).toBeNull();
    expect(within(menu()).getByRole("button", { name: "Veri" })).toHaveFocus();
  });

  it("Enter ile açılır, ilk ekrana odaklanır; kilitli ekran seçilemez", async () => {
    const user = await collapsedMenu();
    within(menu()).getByRole("button", { name: "Planlama" }).focus();
    await user.keyboard("{Enter}");
    const panel = within(menu()).getByRole("menu", { name: "Planlama" });
    expect(within(panel).getByRole("menuitem", { name: "Senaryolar" })).toHaveFocus();
    expect(panel.querySelectorAll("a[role=menuitem]")).toHaveLength(2);  // Senaryolar, Çalışma; çalışmanın ekranları kilitli
    await user.click(within(panel).getByText("Yayın"));
    expect(within(menu()).getByRole("menu", { name: "Planlama" })).toBeInTheDocument();
  });

  it("yetkisiz ekran listede de görünmez", async () => {
    const user = await collapsedMenu(undefined, meAs("End user"));
    await user.click(within(menu()).getByRole("button", { name: "Veri" }));
    const panel = within(menu()).getByRole("menu", { name: "Veri" });
    expect(within(panel).queryByText("Veri yükleme")).toBeNull();
    expect(within(panel).getByRole("menuitem", { name: "Ana veri" })).toBeInTheDocument();
    expect(within(menu()).queryByRole("button", { name: "Yönetim" })).toBeNull();
  });
});

describe("sayfalar", () => {
  it("her ekran kendi adresinde açılır", () => {
    renderApp("/veri/veri-kalitesi");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Veri kalitesi");
    expect(screen.getByText("Bu ekran 6.5 adımında gelecek.")).toBeInTheDocument();
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
    await waitFor(() => expect(screen.getByTestId("data-version")).toHaveTextContent("Veri aktarılmadı"));
    unmount();
    mockApi({ "/api/data-versions/current": "offline" });
    const second = renderApp();
    await waitFor(() => expect(screen.getByTestId("data-version")).toHaveTextContent("Sunucuya ulaşılamıyor"));
    second.unmount();
    mockApi({ "/api/data-versions/current": { status: 503, body: { error: { code: "database_unavailable", message: "", trace_id: "" } } } });
    renderApp();
    await waitFor(() => expect(screen.getByTestId("data-version")).toHaveTextContent("Veriye ulaşılamıyor"));
  });

  it("senaryo, plan versiyonu ve dönem yerleri pasif", () => {
    renderApp();
    expect(screen.getByText("Senaryo: —")).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Dönem: —")).toHaveAttribute("title", "Senaryo ve dönem seçimi 8.1'de gelir");
  });
});

describe("iş göstergesi", () => {
  const job = (id: number, status: string, extra = {}) => ({
    id, job_type: "Çalışma", channel: "Hesaplama", status, progress: null, queue_position: null,
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
    expect(panel.textContent).not.toMatch(/Bildirimler/);  // sorun yokken metin yok
    expect(panel).toHaveTextContent("ÇalışmaSırada · sıra 1");  // kart: üstte iş, altta durum çipi (K-139)
    expect(panel).not.toHaveTextContent("#6");  // K-132
  });

  it("bağlantı koparsa yedek moda geçer ve 10 sn sonra yeniden bağlanır", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = mockApi();
    const Socket = mockSocket();
    renderApp();
    act(() => Socket.instances[0].open());
    act(() => Socket.instances[0].drop());
    expect(screen.getByTestId("job-indicator")).toHaveAttribute("title", "Bildirimler gecikebilir.");
    const before = fetchMock.mock.calls.filter(([u]) => String(u).startsWith("/api/jobs")).length;
    await act(async () => vi.advanceTimersByTime(30_000));
    expect(Socket.instances.length).toBeGreaterThanOrEqual(2);
    const after = fetchMock.mock.calls.filter(([u]) => String(u).startsWith("/api/jobs")).length;
    expect(after).toBeGreaterThan(before);
  });
});

describe("kullanıcı menüsü", () => {
  it("oturumdaki kullanıcıyı ve yazı boyutunu gösterir; boyut ölçekler, çıkışta standarda döner (kayıtta saklanır)", async () => {
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
    expect(document.documentElement.style.fontSize).toBe("13px");
    renderApp("/ana-sayfa", { ...ME, font_size: 16 });
    expect(document.documentElement.style.fontSize).toBe("16px");
  });

  it("altta küçük satırda sürüm (K-172)", async () => {
    mockApi({ "/api/health": { body: { status: "ok", app_version: "0.33.0" } } });
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole("button", { name: "Kullanıcı menüsü: Mert Planlama" }));
    expect(await within(screen.getByRole("dialog", { name: "Kullanıcı menüsü" })).findByText("Sürüm 0.33.0")).toBeInTheDocument();
  });
});

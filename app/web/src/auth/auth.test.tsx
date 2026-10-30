// Giriş ve oturum (fonksiyon 89; K-97, K-98): giriş sayfası, zorunlu şifre değişikliği, kullanıcı menüsü,
// hareketsizlik penceresi, oturum bitince giriş sayfasına dönüş.
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ME, mockApi, mockSocket, renderApp, type Reply } from "../test/helpers";
import type { Me } from "./authApi";
import { countdown } from "./IdleWatch";
import { safeNext } from "./LoginPage";
import { fold, policyRules } from "./PasswordDialog";

const MUST: Me = { ...ME, must_change_password: true, password_change_reason: "İlk giriş" };
const sent = (fetchMock: ReturnType<typeof mockApi>, path: string) =>
  fetchMock.mock.calls.filter(([u]) => String(u).startsWith(path)).map(([, init]) => JSON.parse(String(init?.body ?? "null")));
const error = (status: number, code: string, message: string, details: unknown[] = []): Reply =>
  ({ status, body: { error: { code, message, trace_id: "t", details } } });

beforeEach(() => {
  mockSocket();
});

describe("giriş sayfası (mockup m24f-0738)", () => {
  it("oturum yoksa istenen adresle giriş sayfasına; sade form, not satırı, sürüm", async () => {
    mockApi({ "/api/auth/me": error(401, "not_authenticated", "Oturum açmanız gerekiyor.") });
    renderApp("/veri/ana-veri", "ask");
    const form = await screen.findByRole("form", { name: "Giriş" });
    expect(within(form).getByLabelText("Kullanıcı adı")).toHaveAttribute("autocomplete", "username");
    expect(within(form).getByLabelText("Şifre")).toHaveAttribute("type", "password");
    expect(within(form).getByRole("button", { name: "Giriş" })).toBeDisabled();
    expect(form).toHaveTextContent("Şifrenizi unuttuysanız yöneticinize başvurun · beni hatırla yok");
    expect(within(form).queryByRole("checkbox")).toBeNull();  // "Beni hatırla" yok
    expect(await screen.findByText("şirket içi kurulum · v0.15.0")).toBeInTheDocument();
  });

  it("hatalı girişte genel mesaj ve kalan deneme; kilit ve kapalı hesapta sunucunun mesajı", async () => {
    const user = userEvent.setup();
    const replies = [
      error(401, "login_failed", "Kullanıcı adı ya da şifre hatalı.", [{ remaining_attempts: 2, lock_after: 5, lock_minutes: 15 }]),
      error(403, "account_locked", "Hesap kilitli. 12 dk sonra yeniden deneyin ya da yöneticinize başvurun.", [{ minutes_left: 12 }]),
      error(403, "account_inactive", "Hesap kapalı. Yöneticinize başvurun."),
    ];
    const fetchMock = mockApi({ "/api/auth/login": () => replies.shift()! });
    renderApp("/ana-sayfa", null);
    const password = await screen.findByLabelText("Şifre");
    for (const text of ["Kullanıcı adı ya da şifre hatalı. 2 deneme kaldı; 5 hatalı girişte hesap 15 dk kilitlenir.",
                        "Hesap kilitli. 12 dk sonra yeniden deneyin ya da yöneticinize başvurun.",
                        "Hesap kapalı. Yöneticinize başvurun."]) {
      await user.clear(screen.getByLabelText("Kullanıcı adı"));
      await user.type(screen.getByLabelText("Kullanıcı adı"), " planlama ");
      await user.type(password, "yanlis-sifre");
      await user.click(screen.getByRole("button", { name: "Giriş" }));
      expect(await screen.findByText(text)).toBeInTheDocument();
      expect(password).toHaveAttribute("aria-invalid", "true");
      expect(password).toHaveValue("");  // şifre alanı boşalır
    }
    expect(sent(fetchMock, "/api/auth/login")[0]).toEqual({ user_name: "planlama", password: "yanlis-sifre" });
  });

  it("başarılı girişte istenen ekrana döner", async () => {
    const user = userEvent.setup();
    mockApi({ "/api/auth/me": error(401, "not_authenticated", "x"), "/api/auth/login": { body: ME } });
    renderApp("/veri/ana-veri", "ask");
    await user.type(await screen.findByLabelText("Kullanıcı adı"), "planlama");
    await user.type(screen.getByLabelText("Şifre"), "Dogru-sifre-1");
    await user.click(screen.getByRole("button", { name: "Giriş" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Ana veri" })).toBeInTheDocument();
  });

  it("dönüş adresi yalnız uygulama içi", () => {
    expect(safeNext("/tablo?x=1")).toBe("/tablo?x=1");
    for (const bad of [null, "", "javascript:alert(1)", "//evil.example", "/giris"]) expect(safeNext(bad)).toBe("/ana-sayfa");
  });
});

describe("oturum biterse giriş sayfasına dönülür", () => {
  it("bir istek 401 session_expired dönerse bilgi kutusuyla giriş sayfası", async () => {
    mockApi({ "/api/data-versions/current": error(401, "session_expired", "Oturumunuz 30 dakika hareketsizlik nedeniyle kapandı.") });
    renderApp();
    expect(await screen.findByRole("form", { name: "Giriş" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Oturumunuz 30 dakika hareketsizlik nedeniyle kapandı.");
  });

  it("WebSocket 4401 ile kapanırsa yeniden bağlanmaz, oturum denetlenir", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let alive = true;
    mockApi({ "/api/auth/me": () => (alive ? { body: ME } : error(401, "not_authenticated", "x")) });
    const Socket = mockSocket();
    renderApp();
    act(() => Socket.instances[0].open());
    alive = false;
    act(() => Socket.instances[0].closeWith(4401));
    expect(await screen.findByRole("form", { name: "Giriş" })).toBeInTheDocument();
    await act(async () => vi.advanceTimersByTime(30_000));
    expect(Socket.instances).toHaveLength(1);
  });
});

describe("zorunlu şifre değişikliği (mockup m24f-0739)", () => {
  it("atlanamaz; kurallar yazarken ✓/✗; geçmiş kuralı kaydederken; sunucu reddederse ✗; başarıda kabuk", async () => {
    const user = userEvent.setup();
    let me = MUST;
    const replies: Reply[] = [
      error(422, "password_policy", "Yeni şifre politikaya uymuyor.", [{ field: "new_password", problem: "history" }]),
      { status: 204, body: null },
    ];
    const fetchMock = mockApi({
      "/api/auth/me": () => ({ body: me }),
      "/api/auth/password": () => {
        const r = replies.shift()!;
        if (r.status === 204) me = ME;
        return r;
      },
    });
    renderApp("/ana-sayfa", MUST);
    const dialog = screen.getByRole("dialog", { name: "Şifrenizi belirleyin" });
    expect(dialog).toHaveTextContent("İlk giriş · politika System owner tarafından belirlenir");
    expect(within(dialog).queryByRole("button", { name: "Vazgeç" })).toBeNull();
    expect(screen.queryByRole("navigation", { name: "Ana menü" })).toBeNull();  // kabuk açılmaz
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.getByRole("dialog", { name: "Şifrenizi belirleyin" })).toBeInTheDocument();

    const state = (rule: string) => dialog.querySelector(`[data-rule="${rule}"] [role="img"]`)!.getAttribute("aria-label");
    const save = within(dialog).getByRole("button", { name: "Kaydet ve devam et" });
    await user.type(within(dialog).getByLabelText("Geçici şifre"), "Gecici12345");
    await user.type(within(dialog).getByLabelText("Yeni şifre"), "kisa");
    expect([state("min_length"), state("letter_and_digit"), state("contains_user_name"), state("history"), state("match")])
      .toEqual(["sağlanmıyor", "sağlanmıyor", "sağlanıyor", "kaydederken denetlenir", "sağlanmıyor"]);
    await user.clear(within(dialog).getByLabelText("Yeni şifre"));
    await user.type(within(dialog).getByLabelText("Yeni şifre"), "PLANLAMA-2026x");  // kullanıcı adını içeriyor
    expect(state("contains_user_name")).toBe("sağlanmıyor");
    await user.clear(within(dialog).getByLabelText("Yeni şifre"));
    await user.type(within(dialog).getByLabelText("Yeni şifre"), "Fr3ze-Merkezi-H46");
    await user.type(within(dialog).getByLabelText("Yeni şifre (tekrar)"), "Fr3ze-Merkezi-H4");
    expect(dialog).toHaveTextContent("Şifreler henüz eşleşmiyor.");
    expect(state("match")).toBe("sağlanmıyor");
    expect(save).toBeDisabled();
    await user.type(within(dialog).getByLabelText("Yeni şifre (tekrar)"), "6");
    expect([state("min_length"), state("letter_and_digit"), state("match")]).toEqual(["sağlanıyor", "sağlanıyor", "sağlanıyor"]);
    expect(save).toBeEnabled();

    await user.click(save);
    await waitFor(() => expect(state("history")).toBe("sağlanmıyor"));
    expect(save).toBeDisabled();
    await user.clear(within(dialog).getByLabelText("Yeni şifre"));
    await user.type(within(dialog).getByLabelText("Yeni şifre"), "Yeni-Sifre-2027");
    await user.clear(within(dialog).getByLabelText("Yeni şifre (tekrar)"));
    await user.type(within(dialog).getByLabelText("Yeni şifre (tekrar)"), "Yeni-Sifre-2027");
    expect(state("history")).toBe("kaydederken denetlenir");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet ve devam et" }));
    expect(await screen.findByRole("navigation", { name: "Ana menü" })).toBeInTheDocument();
    expect(sent(fetchMock, "/api/auth/password").at(-1)).toEqual({ current_password: "Gecici12345", new_password: "Yeni-Sifre-2027" });
  });

  it("süre dolduysa alt başlık ve 'Mevcut şifre'", () => {
    mockApi();
    renderApp("/ana-sayfa", { ...MUST, password_change_reason: "Süre doldu" });
    const dialog = screen.getByRole("dialog", { name: "Şifrenizi belirleyin" });
    expect(dialog).toHaveTextContent("Şifrenizin süresi doldu · politika");
    expect(within(dialog).getByLabelText("Mevcut şifre")).toBeInTheDocument();
  });

  it("kurallar politikadan; harf ve rakam kapalıysa listede yok; Türkçe harf duyarsız", () => {
    const me = { ...ME, user_name: "ışık", policy: { ...ME.policy, min_length: 12, require_letter_and_digit: false, history_count: 0 } };
    const rules = policyRules(me, "IŞIK-parola-12", "", new Set());
    expect(rules.map((r) => r.key)).toEqual(["min_length", "contains_user_name", "match"]);
    expect(rules[0].label).toBe("En az 12 karakter");
    expect(rules[1].state).toBe("fail");
    expect(fold("İLKER")).toBe(fold("ilker"));
  });
});

describe("kullanıcı menüsü: şifre değiştir ve çıkış", () => {
  it("şifre değiştir: Vazgeç'li pencere; yanlış mevcut şifre alanın altında; başarıda bilgi", async () => {
    const user = userEvent.setup();
    const replies: Reply[] = [error(401, "current_password_wrong", "Mevcut şifre hatalı."), { status: 204, body: null }];
    mockApi({ "/api/auth/password": () => replies.shift()! });
    renderApp();
    const open = async () => {
      await user.click(screen.getByRole("button", { name: "Kullanıcı menüsü: Mert Planlama" }));
      await user.click(screen.getByRole("button", { name: "Şifre değiştir" }));
      return screen.getByRole("dialog", { name: "Şifre değiştir" });
    };
    let dialog = await open();
    await user.click(within(dialog).getByRole("button", { name: "Vazgeç" }));
    expect(screen.queryByRole("dialog", { name: "Şifre değiştir" })).toBeNull();
    dialog = await open();
    await user.type(within(dialog).getByLabelText("Mevcut şifre"), "Yanlis-1234");
    await user.type(within(dialog).getByLabelText("Yeni şifre"), "Yeni-Sifre-2027");
    await user.type(within(dialog).getByLabelText("Yeni şifre (tekrar)"), "Yeni-Sifre-2027");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    expect(await within(dialog).findByText("Mevcut şifre hatalı.")).toBeInTheDocument();
    expect(screen.queryByRole("form", { name: "Giriş" })).toBeNull();  // oturum açık kalır
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Şifreniz değiştirildi.")).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Şifre değiştir" })).toBeNull();
  });

  it("çıkış: sunucuda oturum kapanır, giriş sayfası ve bilgi", async () => {
    const user = userEvent.setup();
    const fetchMock = mockApi();
    renderApp();
    await user.click(screen.getByRole("button", { name: "Kullanıcı menüsü: Mert Planlama" }));
    await user.click(screen.getByRole("button", { name: "Çıkış" }));
    expect(await screen.findByRole("form", { name: "Giriş" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Oturumunuz kapandı.");
    expect(sent(fetchMock, "/api/auth/logout")).toHaveLength(1);
  });
});

describe("hareketsizlik (mockup m24f-0740)", () => {
  const MIN = 60_000;

  it("25. dakikada geri sayımlı pencere; 'Devam et' etkinlik bildirir; 30'da giriş sayfası", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let serverLeft = 1800;
    const fetchMock = mockApi({ "/api/auth/me": () => ({ body: { ...ME, idle_seconds_left: serverLeft } }) });
    renderApp();
    serverLeft = 300;
    await act(async () => vi.advanceTimersByTime(25 * MIN + 1000));
    const dialog = await screen.findByRole("dialog", { name: "Oturumunuz kapanmak üzere" });
    expect(dialog).toHaveTextContent("25 dakikadır işlem yapılmadı");
    expect(dialog).toHaveTextContent("hareketsizlik · 30 dk sınırı");
    expect(within(dialog).getByRole("timer")).toHaveTextContent(/^4:5\d$/);
    expect(within(dialog).getByRole("button", { name: "Devam et" })).toHaveFocus();
    fireEvent.keyDown(dialog, { key: "Escape" });  // atlanamaz: Esc kapatmaz
    fireEvent.keyDown(window, { key: "a" });        // pencere açıkken girdi süreyi uzatmaz
    expect(screen.getByRole("dialog", { name: "Oturumunuz kapanmak üzere" })).toBeInTheDocument();
    expect(sent(fetchMock, "/api/auth/activity")).toHaveLength(0);

    fireEvent.click(within(dialog).getByRole("button", { name: "Devam et" }));
    expect(screen.queryByRole("dialog", { name: "Oturumunuz kapanmak üzere" })).toBeNull();
    expect(sent(fetchMock, "/api/auth/activity")).toHaveLength(1);

    await act(async () => vi.advanceTimersByTime(30 * MIN + 1000));
    expect(await screen.findByRole("form", { name: "Giriş" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Oturumunuz 30 dakika hareketsizlik nedeniyle kapandı.");
  });

  it("tuş etkinliktir, fare gezdirmek değil; etkinlik en çok dakikada bir bildirilir", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = mockApi();
    renderApp();
    await act(async () => vi.advanceTimersByTime(2 * MIN));
    fireEvent.mouseMove(window);
    expect(sent(fetchMock, "/api/auth/activity")).toHaveLength(0);
    fireEvent.keyDown(window, { key: "a" });
    fireEvent.keyDown(window, { key: "b" });
    fireEvent.mouseDown(window);
    expect(sent(fetchMock, "/api/auth/activity")).toHaveLength(1);
    await act(async () => vi.advanceTimersByTime(MIN + 1000));  // bekleyen girdi dakika dolunca bildirilir
    expect(sent(fetchMock, "/api/auth/activity")).toHaveLength(2);
  });

  it("başka sekmede çalışılıyorsa (sunucuda süre var) pencere açılmaz", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockApi({ "/api/auth/me": { body: { ...ME, idle_seconds_left: 1700 } } });
    renderApp();
    await act(async () => vi.advanceTimersByTime(25 * MIN + 2000));
    await act(async () => vi.advanceTimersByTime(2000));
    expect(screen.queryByRole("dialog", { name: "Oturumunuz kapanmak üzere" })).toBeNull();
  });

  it("geri sayım biçimi", () => {
    expect([countdown(272), countdown(60), countdown(5), countdown(-3)]).toEqual(["4:32", "1:00", "0:05", "0:00"]);
  });
});

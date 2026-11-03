// Kullanıcılar ekranı (ekran 22, fonksiyon 88; K-101): liste, satır menüsü, pencereler, geçici şifre; yazı boyutu (U-23).
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DATA_VERSION, ME, meAs, mockApi, renderApp, type Reply } from "../test/helpers";
import { col, useTableTestSetup } from "../table/testBackend";
import type { ActionState, UserDetail, UserRecord } from "./usersApi";

useTableTestSetup();

const COLUMNS = [
  col("FullName", "Ad soyad", "text", "text"), col("UserName", "Kullanıcı adı", "text", "text"),
  col("Role", "Rol", "text", "list", { values_from_server: true }),
  col("Status", "Durum", "text", "list", { values: ["Aktif", "Pasif", "Kilitli", "İlk giriş bekliyor"] }),
  col("LastLoginAt", "Son giriş", "datetime", "date"),
];

const ROWS = [
  { Id: 5, FullName: "Burak D.", UserName: "burak", Role: "End user", Status: "İlk giriş bekliyor", LastLoginAt: null },
  { Id: 6, FullName: "Okan Y.", UserName: "okan", Role: "End user", Status: "Pasif", LastLoginAt: "2026-09-02T08:00:00+00:00" },
  { Id: 7, FullName: "Selin K.", UserName: "selin", Role: "Key user", Status: "Kilitli", LastLoginAt: null },
];

const allow: ActionState = { allowed: true, reason: null, required_role: null };
const deny = (reason: string, required_role: string | null = null): ActionState => ({ allowed: false, reason, required_role });

const record = (extra: Partial<UserRecord> = {}): UserRecord => ({
  id: 5, user_name: "burak", full_name: "Burak D.", role: "End user", status: "Aktif", is_active: true,
  last_login_at: null, open_sessions: 2, ...extra,
});

const detail = (actions: Partial<UserDetail["actions"]> = {}, user: Partial<UserRecord> = {},
                roles = ["Admin", "Key user", "End user"]): UserDetail => ({
  user: record(user),
  actions: { role: allow, name: allow, reset: allow, unlock: deny("Hesap kilitli değil."), close: allow,
             reopen: deny("Hesap zaten açık."), ...actions },
  assignable_roles: roles,
});

const TEMP = { user: record({ status: "İlk giriş bekliyor" }), temporary_password: "K9veT2qmL4xy" };

interface Options { routes?: Record<string, Reply | ((url: string, init?: RequestInit) => Reply)>; detail?: UserDetail }

function backend({ routes = {}, detail: d = detail() }: Options = {}) {
  const queries: unknown[] = [];
  const fetchMock = mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/users/columns": { body: { chunk_size: 100, columns: COLUMNS, export: { title: "Kullanıcı listesi", file_slug: "kullanici",
                                                                                 sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    "/api/users/query": (_u, init) => {
      queries.push(JSON.parse(String(init?.body)));
      return { body: { rows: ROWS, filtered: ROWS.length, total: ROWS.length } };
    },
    "/api/users/views": { body: { views: [], default_view_id: null } },
    "/api/users/5": { body: d },
    ...routes,
  });
  return { queries, fetchMock };
}

const conflict = (code: string, message: string, details: unknown[] = [], status = 409): Reply =>
  ({ status, body: { error: { code, message, trace_id: "t", details } } });

const calledWith = (m: ReturnType<typeof mockApi>, url: string, method = "POST") =>
  m.mock.calls.find(([u, init]) => String(u) === url && init?.method === method);

async function openScreen(me = meAs("Admin"), options?: Options) {
  const b = backend(options);
  renderApp("/yonetim/kullanicilar", me);
  await screen.findByText("Burak D.", {}, { timeout: 5000 });  // dosyanın ilk testinde tablo soğuk çizilir (testBackend.openTable)
  return b;
}

async function openMenu(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "burak işlemleri" }));
  const menu = await screen.findByRole("menu", { name: "burak işlemleri" });
  await within(menu).findByRole("menuitem", { name: "Rol değiştir" });
  return menu;
}

afterEach(() => vi.unstubAllGlobals());

describe("ekran ve liste", () => {
  it.each(["System owner", "Admin"])("%s açar: başlık, ekle, satırlar, durum rozetleri", async (role) => {
    await openScreen(meAs(role));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Kullanıcılar");
    expect(screen.getByRole("button", { name: "+ Kullanıcı ekle" })).toBeEnabled();
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0]).getByText("İlk giriş bekliyor")).toHaveClass("sc-tag", "sc-tag--risk");
    expect(within(rows[1]).getByText("Pasif")).toHaveClass("sc-tag--neutral");
    expect(within(rows[2]).getByText("Kilitli")).toHaveClass("sc-tag--critical");
  });

  it.each(["Key user", "End user"])("%s: menüde yok, adresle açıklama sayfası", (role) => {
    backend();
    renderApp("/yonetim/kullanicilar", meAs(role));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Bu ekranı açma yetkiniz yok");
    expect(screen.queryByRole("link", { name: "Kullanıcılar" })).toBeNull();
  });

  it("⋯ kolonu alan listesinde ve istekte yok", async () => {
    const { queries } = await openScreen();
    expect(screen.getByRole("columnheader", { name: "Satır işlemleri" })).toBeInTheDocument();
    expect((queries[0] as { fields: string[] }).fields).toEqual(["FullName", "UserName", "Role", "Status", "LastLoginAt"]);
  });
});

describe("satır menüsü", () => {
  it("izin ve neden sunucudan: pasif öğe, ipucu ve ekran okuyucu", async () => {
    const user = userEvent.setup();
    await openScreen(meAs("Admin"), { detail: detail({
      role: deny("Kendi rolünüzü değiştiremezsiniz."), reset: deny("Bu işlem için System owner yetkisi gerekir.", "System owner"),
    }) });
    const menu = await openMenu(user);
    const role = within(menu).getByRole("menuitem", { name: "Rol değiştir" });
    expect(role).toBeDisabled();
    expect(role).toHaveAttribute("title", "Kendi rolünüzü değiştiremezsiniz.");
    expect(role).toHaveAccessibleDescription("Kendi rolünüzü değiştiremezsiniz.");
    expect(within(menu).getByRole("menuitem", { name: "Şifre sıfırla" })).toBeDisabled();
    expect(within(menu).getByRole("menuitem", { name: "Kilidi aç" })).toBeDisabled();
    expect(within(menu).getByRole("menuitem", { name: "Ad soyad düzelt" })).toBeEnabled();
    expect(within(menu).getByRole("menuitem", { name: "Kapat" })).toBeEnabled();
    expect(within(menu).queryByRole("menuitem", { name: "Geri aç" })).toBeNull();
  });

  it("pasif hesapta Kapat yerine Geri aç; Esc kapatır", async () => {
    const user = userEvent.setup();
    await openScreen(meAs("Admin"), { detail: detail({ reopen: allow, close: deny("Hesap zaten kapalı.") }, { is_active: false, status: "Pasif" }) });
    const menu = await openMenu(user);
    expect(within(menu).getByRole("menuitem", { name: "Geri aç" })).toBeEnabled();
    expect(within(menu).queryByRole("menuitem", { name: "Kapat" })).toBeNull();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu", { name: "burak işlemleri" })).toBeNull();
  });
});

describe("kullanıcı ekle", () => {
  const form = () => screen.getByRole("dialog", { name: "Kullanıcı ekle" });

  it("rol kapsamı seçilen role göre; Admin'de System owner yok, System owner'da var", async () => {
    const user = userEvent.setup();
    await openScreen(meAs("Admin"));
    await user.click(screen.getByRole("button", { name: "+ Kullanıcı ekle" }));
    const role = within(form()).getByRole("combobox", { name: "Rol" });
    expect(within(role).getAllByRole("option").map((o) => o.textContent)).toEqual(["Admin", "Key user", "End user"]);
    expect(form()).toHaveTextContent("Verileri ve raporları görür, Excel'e aktarır; veri değiştiremez.");
    await user.selectOptions(role, "Admin");
    expect(form()).toHaveTextContent("Key user yetkileri ile kullanıcı ve sistem yönetimi.");
    await user.selectOptions(role, "Key user");
    expect(form()).toHaveTextContent("Veri, parametre ve planlama.");
    expect(form().textContent).not.toMatch(/Lisans|Birim|e-posta|Yerel/);
    await user.click(within(form()).getByRole("button", { name: "Vazgeç" }));
  });

  it("System owner rolü verebilir ve uyarı görür", async () => {
    const user = userEvent.setup();
    await openScreen(meAs("System owner"));
    await user.click(screen.getByRole("button", { name: "+ Kullanıcı ekle" }));
    await user.selectOptions(within(form()).getByRole("combobox", { name: "Rol" }), "System owner");
    expect(form()).toHaveTextContent("Bütün yetkiler.");
    expect(form()).toHaveTextContent("Bu hesap bir daha kapatılamaz, rolü değiştirilemez.");
  });

  it("kullanıcı adı yazarken küçülür, biçim denetlenir; çakışmada hata ve öneri", async () => {
    const user = userEvent.setup();
    const { fetchMock } = await openScreen(meAs("Admin"), { routes: {
      "/api/users": (_u, init) => {
        const body = JSON.parse(String(init?.body));
        return body.user_name === "burak"
          ? conflict("user_name_taken", "Bu kullanıcı adı kullanılıyor.", [{ field: "user_name", problem: "x", suggestion: "burak2" }])
          : { status: 201, body: { ...TEMP, user: record({ user_name: body.user_name }) } };
      },
    } });
    await user.click(screen.getByRole("button", { name: "+ Kullanıcı ekle" }));
    await user.type(within(form()).getByRole("textbox", { name: /Ad soyad/ }), "Burak D.");
    const name = within(form()).getByRole("textbox", { name: /Kullanıcı adı/ });
    const submit = within(form()).getByRole("button", { name: "Oluştur" });
    await user.type(name, "1a");
    expect(form()).toHaveTextContent("harfle başlayın");
    expect(submit).toBeDisabled();
    await user.clear(name);
    await user.type(name, "BURAK");
    expect(name).toHaveValue("burak");
    await user.click(submit);
    expect(await within(form()).findByText("Bu kullanıcı adı kullanılıyor.")).toBeInTheDocument();
    expect(submit).toBeDisabled();
    await user.click(within(form()).getByRole("button", { name: "burak2 kullan" }));
    expect(name).toHaveValue("burak2");
    await user.click(submit);
    const done = await screen.findByRole("dialog", { name: "Kullanıcı oluşturuldu" });
    expect(done).toHaveTextContent("Burak D. · burak2 · End user");
    expect(JSON.parse(String(calledWith(fetchMock, "/api/users")?.[1]?.body))).toEqual({ full_name: "Burak D.", user_name: "burak", role: "End user" });
  });
});

describe("geçici şifre", () => {
  async function showPassword(user: ReturnType<typeof userEvent.setup>) {
    const b = await openScreen(meAs("Admin"), { routes: { "/api/users/5/reset-password": { body: TEMP } } });
    const menu = await openMenu(user);
    await user.click(within(menu).getByRole("menuitem", { name: "Şifre sıfırla" }));
    const confirm = screen.getByRole("dialog", { name: "Şifre sıfırla" });
    expect(within(confirm).getByText("Burak D. için yeni geçici şifre üretilecek. Mevcut şifre geçersiz olur.")).toBeInTheDocument();
    expect(within(confirm).getAllByRole("button").map((b) => b.textContent)).toEqual(["Vazgeç", "Sıfırla"]);
    await user.click(within(confirm).getByRole("button", { name: "Sıfırla" }));
    return { ...b, dialog: await screen.findByRole("dialog", { name: "Şifre sıfırlandı" }) };
  }

  it("bir kez gösterilir, Esc kapatmaz, kapanınca şifre kalmaz, tablo yenilenir", async () => {
    const user = userEvent.setup();
    const { dialog, queries } = await showPassword(user);
    expect(within(dialog).getByRole("textbox", { name: /Geçici şifre/ })).toHaveValue("K9veT2qmL4xy");
    expect(dialog).toHaveTextContent("Burak D. · burak · End user");
    expect(within(dialog).getByText("Bu şifre bir daha gösterilmez.")).toBeInTheDocument();
    expect(dialog.textContent).not.toMatch(/İlk girişte|Teslim|Denetim izi/);
    expect(within(dialog).getAllByRole("button").map((b) => b.textContent)).toEqual(["Kopyala", "Kapat"]);
    await user.keyboard("{Escape}");
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Vazgeç" })).toBeNull();
    await waitFor(() => expect(queries.length).toBeGreaterThan(1));
    await user.click(within(dialog).getByRole("button", { name: "Kapat" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.body.innerHTML).not.toContain("K9veT2qmL4xy");
    expect(JSON.stringify(window.localStorage)).not.toContain("K9veT2qmL4xy");
  });

  it("Kopyala: clipboard varsa onunla", async () => {
    const user = userEvent.setup();
    const { dialog } = await showPassword(user);
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
    await user.click(within(dialog).getByRole("button", { name: "Kopyala" }));
    expect(writeText).toHaveBeenCalledWith("K9veT2qmL4xy");
    expect(await within(dialog).findByRole("button", { name: "Kopyalandı" })).toBeInTheDocument();
  });

  it("Kopyala: HTTPS dışında clipboard yoksa seçili alandan", async () => {
    const user = userEvent.setup();
    const { dialog } = await showPassword(user);
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: undefined });
    const exec = vi.fn().mockReturnValue(true);
    Object.defineProperty(document, "execCommand", { configurable: true, value: exec });
    await user.click(within(dialog).getByRole("button", { name: "Kopyala" }));
    expect(exec).toHaveBeenCalledWith("copy");
    expect(await within(dialog).findByRole("button", { name: "Kopyalandı" })).toBeInTheDocument();
  });
});

describe("satır işlemleri", () => {
  it("rol değiştir: alt satır, kapsam, System owner uyarısı; istek ve yenileme", async () => {
    const user = userEvent.setup();
    const { fetchMock, queries } = await openScreen(meAs("System owner"), {
      detail: detail({}, {}, ["System owner", "Admin", "Key user", "End user"]),
      routes: { "/api/users/5/role": { body: { user: record({ role: "Admin" }) } } },
    });
    await user.click(within(await openMenu(user)).getByRole("menuitem", { name: "Rol değiştir" }));
    const dialog = screen.getByRole("dialog", { name: "Rol değiştir" });
    expect(within(dialog).getByRole("button", { name: "Değiştir" })).toBeDisabled();
    expect(dialog).toHaveTextContent("Burak D. · burak");
    expect(dialog.textContent).not.toMatch(/istek|oturum/);
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Yeni rol" }), "System owner");
    expect(dialog).toHaveTextContent("Bütün yetkiler.");
    expect(dialog).toHaveTextContent("Bu hesap bir daha kapatılamaz, rolü değiştirilemez.");
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Yeni rol" }), "Admin");
    await user.click(within(dialog).getByRole("button", { name: "Değiştir" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(JSON.parse(String(calledWith(fetchMock, "/api/users/5/role", "PUT")?.[1]?.body))).toEqual({ role: "Admin" });
    expect(await screen.findByText("Rol değiştirildi · burak: Admin")).toBeInTheDocument();
    await waitFor(() => expect(queries.length).toBeGreaterThan(1));
  });

  it("sunucu reddederse hata pencerede kalır", async () => {
    const user = userEvent.setup();
    await openScreen(meAs("Admin"), { routes: { "/api/users/5/role": conflict("user_protected", "Son aktif Admin'in rolü değiştirilemez.") } });
    await user.click(within(await openMenu(user)).getByRole("menuitem", { name: "Rol değiştir" }));
    const dialog = screen.getByRole("dialog", { name: "Rol değiştir" });
    await user.selectOptions(within(dialog).getByRole("combobox", { name: "Yeni rol" }), "Key user");
    await user.click(within(dialog).getByRole("button", { name: "Değiştir" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Son aktif Admin'in rolü değiştirilemez.");
  });

  it("kapat: sade metin, açık oturum varsa ek cümle; kiremit düğme, Vazgeç önce", async () => {
    const user = userEvent.setup();
    const { fetchMock } = await openScreen(meAs("Admin"), { routes: { "/api/users/5/close": { body: { user: record({ is_active: false }) } } } });
    await user.click(within(await openMenu(user)).getByRole("menuitem", { name: "Kapat" }));
    const dialog = screen.getByRole("dialog", { name: "Kullanıcıyı kapat" });
    expect(within(dialog).getByText("Burak D. artık giriş yapamaz. Geçmiş kayıtları korunur; hesabı sonra geri açabilirsiniz. Açık oturumu kapanır.")).toBeInTheDocument();
    expect(dialog.textContent).not.toMatch(/uyarı|çalışma|lisans|devret|yıkıcı|onay/i);
    const buttons = within(dialog).getAllByRole("button");
    expect(buttons.map((b) => b.textContent)).toEqual(["Vazgeç", "Kapat"]);
    expect(buttons[1]).toHaveClass("sc-btn--danger");
    await user.click(buttons[1]);
    await waitFor(() => expect(calledWith(fetchMock, "/api/users/5/close")).toBeTruthy());
    expect(await screen.findByText("Kullanıcı kapatıldı · burak")).toBeInTheDocument();
  });

  it("açık oturumu yoksa kapatma metninde oturum geçmez", async () => {
    const user = userEvent.setup();
    await openScreen(meAs("Admin"), { detail: detail({}, { open_sessions: 0 }) });
    await user.click(within(await openMenu(user)).getByRole("menuitem", { name: "Kapat" }));
    expect(screen.getByRole("dialog", { name: "Kullanıcıyı kapat" }).textContent).not.toMatch(/oturum/i);
  });

  it("kilidi aç, geri aç, ad soyad düzelt", async () => {
    const user = userEvent.setup();
    const { fetchMock } = await openScreen(meAs("Admin"), {
      detail: detail({ unlock: allow, reopen: allow }, { is_active: false }),
      routes: { "/api/users/5/unlock": { body: { user: record() } }, "/api/users/5/reopen": { body: { user: record() } },
                "/api/users/5/name": { body: { user: record({ full_name: "Burak Demir" }) } } },
    });
    await user.click(within(await openMenu(user)).getByRole("menuitem", { name: "Kilidi aç" }));
    const unlock = screen.getByRole("dialog", { name: "Kilidi aç" });
    expect(within(unlock).getByText("Burak D. yeniden giriş yapabilir.")).toBeInTheDocument();
    await user.click(within(unlock).getByRole("button", { name: "Kilidi aç" }));
    await waitFor(() => expect(calledWith(fetchMock, "/api/users/5/unlock")).toBeTruthy());

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await user.click(within(await openMenu(user)).getByRole("menuitem", { name: "Geri aç" }));
    const reopen = screen.getByRole("dialog", { name: "Geri aç" });
    expect(within(reopen).getByText("Burak D. yeniden giriş yapabilir. Şifresi değişmez.")).toBeInTheDocument();
    await user.click(within(reopen).getByRole("button", { name: "Geri aç" }));
    await waitFor(() => expect(calledWith(fetchMock, "/api/users/5/reopen")).toBeTruthy());

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await user.click(within(await openMenu(user)).getByRole("menuitem", { name: "Ad soyad düzelt" }));
    const nameDialog = screen.getByRole("dialog", { name: "Ad soyad düzelt" });
    const input = within(nameDialog).getByRole("textbox", { name: /Ad soyad/ });
    expect(within(nameDialog).getByRole("button", { name: "Kaydet" })).toBeDisabled();
    await user.clear(input);
    await user.type(input, "Burak Demir");
    await user.click(within(nameDialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(calledWith(fetchMock, "/api/users/5/name", "PUT")).toBeTruthy());
  });
});

describe("yazı boyutu (U-23)", () => {
  const rootSize = () => document.documentElement.style.fontSize;
  const legacyKey = (id: number) => `smartchain.u${id}.fontSize`;
  afterEach(() => window.localStorage.clear());

  it("kullanıcı kaydından gelir; tarayıcıdaki eski değer dikkate alınmaz ve silinir", async () => {
    window.localStorage.setItem(legacyKey(ME.id), "12");
    const fetchMock = mockApi();
    renderApp("/ana-sayfa", meAs("Admin", { font_size: 16 }));
    await waitFor(() => expect(rootSize()).toBe("16px"));
    expect(window.localStorage.getItem(legacyKey(ME.id))).toBeNull();
    expect(calledWith(fetchMock, "/api/auth/preferences", "PUT")).toBeUndefined();
  });

  it("kayıtta yoksa tarayıcıdaki değer bir kez sunucuya taşınır", async () => {
    window.localStorage.setItem(legacyKey(ME.id), "14");
    const fetchMock = mockApi();
    renderApp("/ana-sayfa", meAs("Admin", { font_size: null }));
    await waitFor(() => expect(rootSize()).toBe("14px"));
    await waitFor(() => expect(window.localStorage.getItem(legacyKey(ME.id))).toBeNull());
    expect(JSON.parse(String(calledWith(fetchMock, "/api/auth/preferences", "PUT")?.[1]?.body))).toEqual({ font_size: 14 });
  });

  it("başka kullanıcının tarayıcı değeri taşınmaz; hiçbiri yoksa standart", async () => {
    window.localStorage.setItem(legacyKey(999), "16");
    const fetchMock = mockApi();
    renderApp("/ana-sayfa", meAs("Admin", { font_size: null }));
    await waitFor(() => expect(rootSize()).toBe("13px"));
    expect(calledWith(fetchMock, "/api/auth/preferences", "PUT")).toBeUndefined();
    expect(window.localStorage.getItem(legacyKey(999))).toBe("16");
  });

  it("menüden değişir, sunucuya yazılır, tarayıcıya yazılmaz; yazılamazsa bildirim", async () => {
    const user = userEvent.setup();
    let fail = false;
    const fetchMock = mockApi({ "/api/auth/preferences": () => (fail ? conflict("database_unavailable", "x", [], 503) : { status: 204, body: null }) });
    renderApp("/ana-sayfa", meAs("Admin", { font_size: 13 }));
    await user.click(screen.getByRole("button", { name: /Kullanıcı menüsü/ }));
    await user.click(screen.getByRole("radio", { name: /Büyük/ }));
    expect(rootSize()).toBe("16px");
    await waitFor(() => expect(calledWith(fetchMock, "/api/auth/preferences", "PUT")).toBeTruthy());
    expect(window.localStorage.getItem(legacyKey(ME.id))).toBeNull();
    fail = true;
    await user.click(screen.getByRole("radio", { name: /Rahat/ }));
    expect(rootSize()).toBe("14px");
    expect(await screen.findByText("Yazı boyutu kaydedilemedi.")).toBeInTheDocument();
  });
});

describe("rol değişince bildirim", () => {
  it("X-Smartchain-Role farklıysa kullanıcıya söylenir", async () => {
    mockApi({
      "/api/data-versions/current": { body: DATA_VERSION, headers: { "X-Smartchain-Role": "Key user" } },
      "/api/auth/me": { body: meAs("Key user") },
    });
    renderApp("/ana-sayfa", meAs("Admin"));
    expect(await screen.findByText("Rolünüz Key user olarak değiştirildi.")).toBeInTheDocument();
  });
});

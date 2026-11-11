// Sistem ayarları (ekran 25; K-104, K-105, K-164) ve yetki matrisi penceresi (ekran 22; K-100). Zamanlanmış işler sekmesi Flows.test.tsx'te.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import matrix from "../../../shared/permissions.json";
import { col, useTableTestSetup } from "../table/testBackend";
import { DATA_VERSION, meAs, mockApi, renderApp, type Reply } from "../test/helpers";
import type { FieldDetail, LoginPolicy } from "./systemOwnerApi";

useTableTestSetup();

const COLUMNS = [
  col("TableName", "Tablo", "text", "list", { values_from_server: true }), col("FieldName", "Alan", "text", "text"),
  col("DisplayLabel", "Etiket", "text", "text"), col("FieldClass", "Sınıf", "text", "list", { values: ["Ana veri", "Parametre", "İşlem verisi"] }),
  col("IsAdditional", "Ek alan", "bool", "list", { values: [true, false] }),
];
const ROWS = [{ Id: 1, TableName: "Material", FieldName: "AdditionalText2", DisplayLabel: "Müşteri grubu", FieldClass: "Ana veri", IsAdditional: true }];

const field = (extra: Partial<FieldDetail> = {}): FieldDetail => ({
  table: "Material", field: "AdditionalText2", label: "Müşteri grubu", standard_label: "Ek metin alanı 2", description: "Ek metin alanları", is_additional: true,
  field_class: "Ana veri", value_priority: "ERP ezer", manual_overrides: true, editable_in_workspace: false, is_required: false,
  if_empty: "yok", options: { field_class: ["Ana veri", "Parametre", "İşlem verisi"], value_priority: ["ERP ezer", "Kural ezer"] },
  used_in_views: 0, used_in_rules: 0, ...extra,
});

const POLICY: LoginPolicy = {
  values: { PasswordMinLength: 10, PasswordRequireLetterAndDigit: true, PasswordHistoryCount: 5, PasswordMaxAgeDays: 90,
            LoginMaxFailedAttempts: 5, LoginLockMinutes: 15, SessionIdleMinutes: 30, SessionWarningMinutes: 5 },
  defaults: { PasswordMinLength: 10, PasswordRequireLetterAndDigit: true, PasswordHistoryCount: 5, PasswordMaxAgeDays: 90,
              LoginMaxFailedAttempts: 5, LoginLockMinutes: 15, SessionIdleMinutes: 30, SessionWarningMinutes: 5 },
  limits: { PasswordMinLength: { min: 8, max: 128 }, PasswordHistoryCount: { min: 1, max: 24 }, PasswordMaxAgeDays: { min: 1, max: 3650 },
            LoginMaxFailedAttempts: { min: 1, max: 20 }, LoginLockMinutes: { min: 1, max: 1440 }, SessionIdleMinutes: { min: 1, max: 1440 },
            SessionWarningMinutes: { min: 1, max: 1439 } },
};

function backend(routes: Record<string, Reply | ((url: string, init?: RequestInit) => Reply)> = {}, detail = field()) {
  return mockApi({
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/health": { body: { status: "ok", app_version: "0.18.0" } },
    "/api/field-definitions/columns": { body: { chunk_size: 100, columns: COLUMNS, export: { title: "Veri sözlüğü", file_slug: "veri-sozlugu",
                                                                                            sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    "/api/field-definitions/query": { body: { rows: ROWS, filtered: 1, total: 1 } },
    "/api/field-definitions/views": { body: { views: [], default_view_id: null } },
    "/api/field-definitions/Material/AdditionalText2": { body: detail },
    "/api/settings/login-policy": { body: POLICY },
    ...routes,
  });
}

const called = (m: ReturnType<typeof mockApi>, url: string, method = "PUT") =>
  m.mock.calls.find(([u, init]) => String(u) === url && init?.method === method);

async function openScreen(routes = {}, detail = field()) {
  const m = backend(routes, detail);
  renderApp("/yonetim/sistem-ayarlari", meAs("System owner"));
  await screen.findByText("Müşteri grubu", {}, { timeout: 5000 });
  return m;
}

async function openField(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Material AdditionalText2 düzenle" }));
  const dialog = await screen.findByRole("dialog", { name: "Alan" });
  await within(dialog).findByLabelText("Etiket");
  return dialog;
}

describe("ekran", () => {
  it("başlık, sürüm, bölümler, tablo", async () => {
    await openScreen();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Sistem ayarları");
    expect(await screen.findByText("Sürüm 0.18.0")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Veri sözlüğü" })).toBeChecked();
    expect(screen.getAllByRole("radio").map((r) => r.textContent)).toEqual(["Veri sözlüğü", "Giriş ve oturum", "Sistem sağlığı", "Zamanlanmış işler"]);
    expect(screen.getByRole("columnheader", { name: "Satır işlemleri" })).toBeInTheDocument();
  });

  it("eski adres yeni adrese yönlenir", async () => {
    backend();
    renderApp("/yonetim/system-owner", meAs("System owner"));
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Sistem ayarları");
    expect(screen.getByRole("link", { name: "Sistem ayarları" })).toHaveClass("is-active");
  });

  it.each(["Key user", "End user"])("%s açamaz", (role) => {
    backend();
    renderApp("/yonetim/sistem-ayarlari", meAs(role));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Bu ekranı açma yetkiniz yok");
    expect(screen.getByText("Bu ekran için System owner yetkisi gerekir. Smartchain desteğine başvurun.")).toBeInTheDocument();
  });
});

describe("alan penceresi", () => {
  it("etiket düzenlenir, öteki alanlar pasif form öğesi; kaydedince tablo yenilenir", async () => {
    const user = userEvent.setup();
    const m = await openScreen({ "/api/field-definitions/Material/AdditionalText2/label": { body: field({ label: "Yeni ad" }) } });
    const dialog = await openField(user);
    expect(dialog).toHaveTextContent("Material · AdditionalText2");
    expect(dialog.querySelector(".sc-dialog-subtitle-line")).toHaveTextContent(/^Ek metin alanları$/);
    expect(dialog).toHaveTextContent("Boşsa alan listelerde görünmez.");
    const fieldClass = within(dialog).getByLabelText("Sınıf");
    expect(fieldClass).toBeDisabled();
    expect(fieldClass).toHaveValue("Ana veri");
    expect(within(fieldClass).getAllByRole("option").map((o) => o.textContent)).toEqual(["Ana veri", "Parametre", "İşlem verisi"]);
    expect(within(dialog).getByLabelText("Değer önceliği")).toBeDisabled();
    expect(within(dialog).getByLabelText("Değer önceliği")).toHaveValue("ERP ezer");
    expect(within(dialog).getByLabelText("Manuel")).toBeDisabled();
    expect(within(dialog).getByLabelText("Manuel")).toBeChecked();
    expect(within(dialog).getByLabelText("Senaryo")).toBeDisabled();
    expect(within(dialog).getByLabelText("Senaryo")).not.toBeChecked();
    expect(within(dialog).getByLabelText("Zorunlu")).toBeDisabled();
    expect(within(dialog).getByLabelText("Boşsa")).toBeDisabled();
    expect(within(dialog).getByLabelText("Boşsa")).toHaveValue("yok");
    expect(within(dialog).getByLabelText("Etiket")).toBeEnabled();
    expect(dialog.querySelectorAll(".sc-field-rows > *")).toHaveLength(7);
    const save = within(dialog).getByRole("button", { name: "Kaydet" });
    expect(save).toBeDisabled();

    const input = within(dialog).getByLabelText("Etiket");
    await user.clear(input);
    await user.type(input, "Yeni ad");
    await user.click(save);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(JSON.parse(String(called(m, "/api/field-definitions/Material/AdditionalText2/label")?.[1]?.body))).toEqual({ label: "Yeni ad" });
    expect(await screen.findByText("Etiket kaydedildi · Material.AdditionalText2")).toBeInTheDocument();
    const queries = m.mock.calls.filter(([u]) => String(u) === "/api/field-definitions/query");
    expect(queries.length).toBeGreaterThan(1);
  });

  it("standart alanda yardım standart etiketi söyler; 40 karakter sınırı", async () => {
    const user = userEvent.setup();
    await openScreen({}, field({ is_additional: false, standard_label: "Malzeme adı" }));
    const dialog = await openField(user);
    expect(dialog).toHaveTextContent("Boşsa: Malzeme adı");
    expect(within(dialog).getByLabelText("Etiket")).toHaveAttribute("maxlength", "40");
  });

  it("kullanılan ek alanın etiketi silinirken uyarı ve kiremit düğme", async () => {
    const user = userEvent.setup();
    await openScreen({}, field({ used_in_views: 3, used_in_rules: 1 }));
    const dialog = await openField(user);
    expect(within(dialog).queryByRole("button", { name: "Etiketi sil" })).toBeNull();
    await user.clear(within(dialog).getByLabelText("Etiket"));
    expect(dialog).toHaveTextContent("Bu alan 3 görünümde ve 1 kuralda kullanılıyor. Etiket silinirse bu görünümlerde görünmez; etiket yeniden yazılınca geri gelir.");
    expect(within(dialog).getByRole("button", { name: "Etiketi sil" })).toHaveClass("sc-btn--danger");
  });

  it("kullanılmayan ek alanda uyarı yok", async () => {
    const user = userEvent.setup();
    await openScreen();
    const dialog = await openField(user);
    await user.clear(within(dialog).getByLabelText("Etiket"));
    expect(within(dialog).queryByRole("button", { name: "Etiketi sil" })).toBeNull();
    expect(within(dialog).getByRole("button", { name: "Kaydet" })).toBeEnabled();
  });

  it("sunucu reddederse hata pencerede kalır", async () => {
    const user = userEvent.setup();
    await openScreen({ "/api/field-definitions/Material/AdditionalText2/label": {
      status: 409, body: { error: { code: "label_taken", message: "Bu tabloda aynı etiketli bir alan var.", trace_id: "t", details: [] } } } });
    const dialog = await openField(user);
    await user.type(within(dialog).getByLabelText("Etiket"), "x");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Bu tabloda aynı etiketli bir alan var.");
  });
});

describe("giriş ve oturum formu", () => {
  async function openForm(routes = {}) {
    const user = userEvent.setup();
    const m = await openScreen(routes);
    await user.click(screen.getByRole("radio", { name: "Giriş ve oturum" }));
    await screen.findByLabelText("En az karakter");
    return { user, m };
  }
  const nav = () => screen.getByRole("navigation", { name: "Giriş ve oturum bölümleri" });
  const setNumber = (label: string, value: string) => {
    const input = screen.getByLabelText(label);
    fireEvent.change(input, { target: { value } });
    fireEvent.blur(input);
  };

  it("solda alt menü (Şifre, Oturum), sağda yalnız seçili bölüm; tek kartta ad, Vazgeç ve Kaydet, değişiklik yoksa pasif; Evet/Hayır anahtar", async () => {
    const { user } = await openForm();
    expect(within(nav()).getAllByRole("button").map((b) => b.textContent)).toEqual(["Şifre", "Oturum"]);
    expect(within(nav()).getByRole("button", { name: "Şifre" })).toHaveAttribute("aria-current", "true");
    for (const [label, value] of [["En az karakter", "10"], ["Son kaç şifreden farklı", "5"], ["Geçerlilik süresi (gün)", "90"]]) {
      expect(screen.getByLabelText(label)).toHaveValue(value);
    }
    expect(screen.getByRole("switch", { name: "Harf ve rakam zorunlu" })).toBeChecked();
    expect(screen.queryByLabelText("Kilit süresi (dk)")).toBeNull();
    const card = screen.getByRole("region", { name: "Şifre" });
    expect(card).toHaveClass("sc-settings-card");
    expect(within(card).queryByRole("heading")).toBeNull();  // alt menüdeki ad kartta yinelenmez (K-166)
    expect(within(card).getByLabelText("En az karakter")).toBeInTheDocument();  // alanlar başlıkla aynı kartta
    const save = within(card).getByRole("button", { name: "Kaydet" });
    expect(save).toBeDisabled();
    expect(save.className).toContain("sc-btn--primary");
    expect(within(card).getByRole("button", { name: "Vazgeç" }).className).toContain("sc-btn--ghost");
    await user.click(screen.getByRole("switch", { name: "Harf ve rakam zorunlu" }));
    expect(save).toBeEnabled();
    await user.click(within(card).getByRole("button", { name: "Vazgeç" }));
    expect(screen.getByRole("switch", { name: "Harf ve rakam zorunlu" })).toBeChecked();
    await user.click(within(nav()).getByRole("button", { name: "Oturum" }));
    for (const [label, value] of [["Kilit için hatalı giriş sayısı", "5"], ["Kilit süresi (dk)", "15"],
                                  ["Oturumun kapandığı süre (dk)", "30"], ["Kapanmadan önce uyarı (dk)", "5"]]) {
      expect(screen.getByLabelText(label)).toHaveValue(value);
    }
    expect(screen.queryByLabelText("En az karakter")).toBeNull();
  });

  it("kaydedilmemiş değişiklikle bölüm ya da sekme değişince uyarı; Vazgeç geri alır", async () => {
    const { user } = await openForm();
    setNumber("En az karakter", "12");
    expect(screen.getByRole("button", { name: "Vazgeç" })).toBeEnabled();
    await user.click(within(nav()).getByRole("button", { name: "Oturum" }));
    let dialog = screen.getByRole("dialog", { name: "Kaydedilmemiş değişiklikler var" });
    await user.click(within(dialog).getByRole("button", { name: "Vazgeç" }));
    expect(screen.getByLabelText("En az karakter")).toHaveValue("12");
    await user.click(screen.getByRole("radio", { name: "Sistem sağlığı" }));
    dialog = screen.getByRole("dialog", { name: "Kaydedilmemiş değişiklikler var" });
    await user.click(within(dialog).getByRole("button", { name: "Vazgeç" }));
    expect(screen.getByRole("radio", { name: "Giriş ve oturum" })).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Vazgeç" }));
    expect(screen.getByLabelText("En az karakter")).toHaveValue("10");
    await user.click(within(nav()).getByRole("button", { name: "Oturum" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByLabelText("Kilit süresi (dk)")).toBeInTheDocument();
  });

  it("yalnız değişenler gider", async () => {
    const { user, m } = await openForm();
    setNumber("En az karakter", "12");
    await user.click(screen.getByRole("switch", { name: "Harf ve rakam zorunlu" }));
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(called(m, "/api/settings/login-policy")).toBeTruthy());
    expect(JSON.parse(String(called(m, "/api/settings/login-policy")?.[1]?.body)))
      .toEqual({ PasswordMinLength: 12, PasswordRequireLetterAndDigit: false });
    expect(await screen.findByText("Ayarlar kaydedildi.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeDisabled();  // Vazgeç ve Kaydet birlikte (K-166)
    expect(screen.getByRole("button", { name: "Vazgeç" })).toBeDisabled();
  });

  it("sınır dışı ve uyarı süresi denetimi Kaydet'i kapatır", async () => {
    const { user } = await openForm();
    setNumber("En az karakter", "5");
    expect(screen.getByText("En az 8, en çok 128.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Vazgeç" }));
    await user.click(within(nav()).getByRole("button", { name: "Oturum" }));
    setNumber("Kapanmadan önce uyarı (dk)", "30");
    expect(screen.getByText("Uyarı süresi oturumun kapandığı süreden kısa olmalı.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeDisabled();
  });
});

// Ham verinin saklama süresi (K-156): varsayılanı yok, boş bırakılabilir; boşsa temizlik çalışmaz.
describe("ham veri temizliği ayarı", () => {
  const HEALTH = {
    values: { DiskWarnPercent: 85, QueueWaitWarnMinutes: 10, SystemEventRetentionDays: 90, ImportSyncMaxMb: 5, ImportMaxMb: 100, ImportMaxRows: 200000,
              RawDataRetentionDays: 7 },
    defaults: { DiskWarnPercent: 85, QueueWaitWarnMinutes: 10, SystemEventRetentionDays: 90, ImportSyncMaxMb: 5, ImportMaxMb: 100, ImportMaxRows: 200000,
                RawDataRetentionDays: null },
    limits: { DiskWarnPercent: { min: 1, max: 99 }, QueueWaitWarnMinutes: { min: 1, max: 1440 }, SystemEventRetentionDays: { min: 7, max: 3650 },
              ImportSyncMaxMb: { min: 1, max: 100 }, ImportMaxMb: { min: 1, max: 100 }, ImportMaxRows: { min: 1000, max: 1000000 },
              RawDataRetentionDays: { min: 1, max: 30 } },
    optional: ["RawDataRetentionDays"],
  };

  it("boşaltılınca hata yok, boş değer gider; sınır dışı Kaydet'i kapatır", async () => {
    const user = userEvent.setup();
    const m = await openScreen({ "/api/settings/health": (_url: string, init?: RequestInit) =>
      ({ body: init?.method === "PUT" ? { ...HEALTH, values: { ...HEALTH.values, RawDataRetentionDays: null } } : HEALTH }) });
    await user.click(screen.getByRole("radio", { name: "Sistem sağlığı" }));
    const nav = await screen.findByRole("navigation", { name: "Sistem sağlığı bölümleri" });
    expect(within(nav).getAllByRole("button").map((b) => b.textContent)).toEqual(["İzleme eşikleri", "Excel yükleme", "Ham veri temizliği"]);
    expect(screen.getByLabelText("Disk uyarı eşiği (%)")).toHaveValue("85");
    await user.click(within(nav).getByRole("button", { name: "Ham veri temizliği" }));
    const input = await screen.findByLabelText("Ham verinin saklama süresi (gün)");
    expect(input).toHaveValue("7");
    expect(input).toHaveAccessibleDescription("Boşsa temizlik çalışmaz.");  // açıklama ipucunda, formda metin yok (K-166)
    expect(document.querySelector(".sc-settings-card .sc-field-help")).toBeNull();
    fireEvent.change(input, { target: { value: "45" } });
    fireEvent.blur(input);
    expect(screen.getByText("En az 1, en çok 30.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kaydet" })).toBeDisabled();
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.blur(input);
    expect(screen.queryByText("En az 1, en çok 30.")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(called(m, "/api/settings/health")).toBeTruthy());
    expect(JSON.parse(String(called(m, "/api/settings/health")?.[1]?.body))).toEqual({ RawDataRetentionDays: null });
  });
});

describe("yetki matrisi (ekran 22)", () => {
  const usersBackend = () => backend({
    "/api/users/columns": { body: { chunk_size: 100, columns: [col("UserName", "Kullanıcı adı", "text", "text")], export: { title: "Kullanıcı listesi", file_slug: "kullanici", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    "/api/users/query": { body: { rows: [{ Id: 5, UserName: "burak" }], filtered: 1, total: 1 } },
    "/api/users/views": { body: { views: [], default_view_id: null } },
    "/api/permissions/matrix": { body: matrix as unknown as Reply["body"] },
    "/api/permissions/matrix/export": { body: {}, headers: { "Content-Disposition": "attachment; filename*=UTF-8''smartchain_yetki-matrisi_x.xlsx" } },
  });

  it.each(["System owner", "Admin"])("%s açar: 18 grup (başlık dahil 19 satır), 4 rol, Excel; istisna bölümü yok", async (role) => {
    const user = userEvent.setup();
    const m = usersBackend();
    renderApp("/yonetim/kullanicilar", meAs(role));
    await screen.findByText("burak", {}, { timeout: 5000 });
    await user.click(screen.getByRole("button", { name: "Yetki matrisi" }));
    const dialog = await screen.findByRole("dialog", { name: "Yetki matrisi" });
    expect(dialog).toHaveClass("sc-dialog--xwide");
    const table = await within(dialog).findByRole("table", { name: "Yetki matrisi" });
    expect(within(table).getAllByRole("row")).toHaveLength(19);
    expect(within(table).getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Fonksiyon grubu", "System owner", "Admin", "Key user", "End user"]);
    const parameter = within(table).getByRole("row", { name: /^Parametre / });
    expect(within(parameter).getAllByRole("cell").map((c) => c.textContent)).toEqual(["Tam", "Tam", "Tam", "Yok"]);
    expect(within(table).getAllByRole("rowheader")[1]).toHaveTextContent(/^Ana veri$/);
    expect(dialog.textContent).not.toMatch(/\d+–\d+/);
    expect(within(dialog).getAllByRole("table")).toHaveLength(1);
    expect(dialog).not.toHaveTextContent("İstisnalar");
    expect(dialog.textContent).not.toMatch(/K-\d+/);

    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    await user.click(within(dialog).getByRole("button", { name: "Excel'e aktar" }));
    await waitFor(() => expect(m.mock.calls.some(([u]) => String(u) === "/api/permissions/matrix/export")).toBe(true));
    expect(within(dialog).queryByRole("button", { name: "Vazgeç" })).toBeNull();
    await user.click(within(dialog).getByRole("button", { name: "Kapat" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

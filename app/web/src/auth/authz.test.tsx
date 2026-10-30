// Rol bazlı yetki arayüzde (fonksiyon 90; K-99, K-100): menü, yetkisiz ekran, pasif düğme ipucu,
// 403 bildirimi, rol değişikliği, iş panelinde iptal ve herkesin işleri.
import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { DATA_VERSION, meAs, mockApi, mockSocket, renderApp, type Reply } from "../test/helpers";
import { Button } from "../ui";
import { forbiddenReason, requiredRole } from "./permissions";

const menu = () => screen.getByRole("navigation", { name: "Ana menü" });
const groups = () => within(menu()).getAllByRole("button", { expanded: true }).map((b) => b.textContent);
const links = () => within(menu()).getAllByRole("link").map((a) => a.textContent?.trim());
const forbidden = (message: string): Reply => ({ status: 403, body: { error: { code: "forbidden", message, trace_id: "t", details: [] } } });

beforeEach(() => {
  mockSocket();
});

describe("menü role göre (K-100)", () => {
  it.each([
    ["System owner", ["Planlama", "Takip", "Veri", "Parametre", "Yönetim"], ["Veri yükleme", "Kullanıcılar", "System owner"], []],
    ["Admin", ["Planlama", "Takip", "Veri", "Parametre", "Yönetim"], ["Kullanıcılar", "Sistem sağlığı"], ["System owner"]],
    ["Key user", ["Planlama", "Takip", "Veri", "Parametre"], ["Senaryolar", "Veri yükleme", "Gece senaryoları"], ["Kullanıcılar"]],
    ["End user", ["Takip", "Veri"], ["Uyarılar", "Ana veri", "Veri kuralları"],
     ["Senaryolar", "Çalışma", "Veri yükleme", "Parametre setleri", "Gece senaryoları", "Kullanıcılar"]],
  ])("%s", (role, expectedGroups, shown, hidden) => {
    mockApi();
    renderApp("/ana-sayfa", meAs(role));
    expect(groups()).toEqual(expectedGroups);
    for (const name of shown) expect(links()).toContain(name);
    for (const name of hidden) expect(links()).not.toContain(name);
  });

  it("arama yalnız görünen ekranlarda", async () => {
    const user = userEvent.setup();
    mockApi();
    renderApp("/ana-sayfa", meAs("End user"));
    await user.type(within(menu()).getByRole("searchbox", { name: "Ekran ara" }), "veri");
    expect(within(menu()).getAllByRole("option").map((o) => o.textContent)).toEqual(["Ana veri", "Veri kuralları", "Veri kalitesi"]);
  });
});

describe("yetkisiz ekran", () => {
  it("adres çubuğundan açılınca neden ve kimden isteneceği", () => {
    mockApi();
    renderApp("/yonetim/kullanicilar", meAs("End user"));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Bu ekranı açma yetkiniz yok");
    expect(screen.getByText("Bu ekran için Admin yetkisi gerekir. Yetki için yöneticinize başvurun.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ana sayfaya dön" })).toHaveAttribute("href", "/ana-sayfa");
  });

  it("System owner ekranı Admin'e kapalı; destek yazar", () => {
    mockApi();
    renderApp("/yonetim/system-owner", meAs("Admin"));
    expect(screen.getByText("Bu ekran için System owner yetkisi gerekir. Smartchain desteğine başvurun.")).toBeInTheDocument();
  });

  it("End user tablo ekranını açar (raporlama serbest, K-99)", () => {
    mockApi();
    renderApp("/tablo", meAs("End user"));
    expect(screen.queryByText("Bu ekranı açma yetkiniz yok")).toBeNull();
  });
});

it("bağlam çubuğunda ayrı rol etiketi yok; rol kullanıcı menüsünde", async () => {
  const user = userEvent.setup();
  mockApi();
  renderApp("/ana-sayfa", meAs("End user"));
  expect(screen.queryByTestId("role-badge")).toBeNull();
  await user.click(screen.getByRole("button", { name: /Kullanıcı menüsü/ }));
  expect(screen.getByRole("dialog", { name: "Kullanıcı menüsü" })).toHaveTextContent("End user");
});

describe("403 ve rol değişikliği", () => {
  it("sunucunun yetki reddi sağ altta bildirilir", async () => {
    mockApi({ "/api/data-versions/current": forbidden("Bu işlem için Key user yetkisi gerekir. Yetki için yöneticinize başvurun.") });
    renderApp();
    const notice = await screen.findByRole("region", { name: "Yetki" });
    expect(within(notice).getByRole("alert")).toHaveTextContent("Bu işlem için Key user yetkisi gerekir.");
  });

  it("X-Smartchain-Role farklıysa me yenilenir: menü değişir, oturum kapanmaz", async () => {
    mockApi({
      "/api/data-versions/current": { body: DATA_VERSION, headers: { "X-Smartchain-Role": "End user" } },
      "/api/auth/me": { body: meAs("End user") },
    });
    renderApp("/ana-sayfa", meAs("Admin"));
    await waitFor(() => expect(groups()).toEqual(["Takip", "Veri"]));
    expect(screen.queryByRole("form", { name: "Giriş" })).toBeNull();
  });
});

describe("pasif düğme ipucu", () => {
  it("disabledReason: pasif, title ve ekran okuyucu açıklaması", () => {
    render(<Button disabledReason={forbiddenReason(83, "write")}>Kapat</Button>);
    const button = screen.getByRole("button", { name: "Kapat" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("title", "Bu işlem için Key user yetkisi gerekir. Yetki için yöneticinize başvurun.");
    expect(button).toHaveAccessibleDescription("Bu işlem için Key user yetkisi gerekir. Yetki için yöneticinize başvurun.");
    expect([requiredRole(10, "read"), requiredRole(93, "write"), requiredRole(96, "read")])
      .toEqual(["End user", "Admin", "System owner"]);
  });
});

describe("iş paneli: iptal ve herkesin işleri", () => {
  const job = (id: number, requested_by: number, extra = {}) => ({
    id, job_type: "Dışa aktarım", channel: "Dışa aktarım", status: "Sırada", progress: null, queue_position: 1,
    updated_at: "2026-10-27T09:20:00+00:00", requested_by, requested_by_name: requested_by === 3 ? "Mert Planlama" : "Ayşe Yönetici",
    ...extra,
  });

  it("kendi sıradaki işinde İptal; Key user'da herkesin işleri pasif ve ipuçlu", async () => {
    const user = userEvent.setup();
    const cancelled: string[] = [];
    mockApi({
      "/api/jobs": { body: { jobs: [job(5, 3)], counters: {} } },
      "/api/jobs/5/cancel": (url) => {
        cancelled.push(url);
        return { body: job(5, 3, { status: "İptal" }) };
      },
    });
    renderApp("/ana-sayfa", meAs("Key user"));
    await user.click(await screen.findByTestId("job-indicator"));
    const panel = screen.getByRole("dialog", { name: "Arka plandaki işler" });
    const all = within(panel).getByRole("checkbox", { name: "Herkesin işleri" });
    expect(all).toBeDisabled();
    expect(all.closest("[title]")).toHaveAttribute("title", "Bu işlem için Admin yetkisi gerekir. Yetki için yöneticinize başvurun.");
    await user.click(await within(panel).findByRole("button", { name: "#5 işini iptal et" }));
    expect(cancelled).toEqual(["/api/jobs/5/cancel"]);
  });

  it("Admin herkesin işlerini görür ve başkasının sıradaki işini iptal eder", async () => {
    const user = userEvent.setup();
    const fetchMock = mockApi({
      "/api/jobs?scope=all": { body: { jobs: [job(5, 3), job(7, 9)], counters: {} } },
      "/api/jobs/7/cancel": { body: job(7, 9, { status: "İptal" }) },
    });
    renderApp("/ana-sayfa", meAs("Admin"));
    await user.click(await screen.findByTestId("job-indicator"));
    const panel = screen.getByRole("dialog", { name: "Arka plandaki işler" });
    await user.click(within(panel).getByRole("checkbox", { name: "Herkesin işleri" }));
    expect(await within(panel).findByText(/sahibi Ayşe Yönetici/)).toBeInTheDocument();
    await act(async () => {
      await user.click(within(panel).getByRole("button", { name: "#7 işini iptal et" }));
    });
    expect(fetchMock.mock.calls.some(([u, init]) => String(u) === "/api/jobs/7/cancel" && init?.method === "POST")).toBe(true);
  });
});

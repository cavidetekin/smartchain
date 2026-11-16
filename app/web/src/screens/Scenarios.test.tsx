// Senaryolar (ekran 07; fonksiyon 27, 28; K-177): liste, yönetim işlemleri (Admin ve üstü), "Gece çalışsın" ve gece sırası (Key user ve üstü),
// bağlam çubuğundan geçiş, Parametreler'in seçili senaryoyla yüklenmesi, kaydedilmemiş değişiklik onayı.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { meAs, mockApi, renderApp, type Reply, type Routes } from "../test/helpers";

useTableTestSetup();

const EXPORT = { title: "Senaryolar", file_slug: "senaryolar", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 };
const COLUMNS = [
  col("NightlyPriority", "Gece sırası", "number", "number"), col("Name", "Senaryo", "text", "text"), col("ModelType", "Model", "text", "list"),
  col("FollowsBase", "Baz'ı izler", "text", "list"), col("RunsNightly", "Gece çalışsın", "bool", "list"),
  col("BudgetSeconds", "Süre bütçesi (sn)", "number", "number"), col("LastRunAt", "Son çalışma", "datetime", "date"), col("ActiveLabel", "Aktif", "text", "list"),
];
const row = (Id: number, Name: string, extra: Record<string, unknown> = {}) => ({
  Id, Name, IsBase: false, IsActive: true, RunsNightly: false, FollowsBase: "Evet", NightlyPriority: null, ModelType: "LP", BudgetSeconds: 660,
  LastRunAt: null, LastRunStatus: null, ActiveLabel: "Evet", ...extra,
});
const ROWS = [
  row(1, "Baz", { IsBase: true, RunsNightly: true, NightlyPriority: 1, FollowsBase: null, LastRunAt: "2026-11-16T02:31:00", LastRunStatus: "Bitti" }),
  row(2, "Fazla mesaili", { RunsNightly: true, NightlyPriority: 2 }),
  row(3, "Kısıtsız kapasite", { RunsNightly: true, NightlyPriority: 3 }),
  row(4, "MILP deneme", { FollowsBase: "Hayır", ModelType: "MILP" }),
  row(5, "Eski deneme", { IsActive: false, ActiveLabel: "Hayır", FollowsBase: "Hayır" }),
];
const OPTIONS = ROWS.filter((r) => r.IsActive).map((r) => ({ id: r.Id, name: r.Name, is_base: r.IsBase }));
const raw = (id: number) => { const r = ROWS.find((x) => x.Id === id)!; return { id, name: r.Name, is_base: r.IsBase, is_active: r.IsActive }; };
const PARAMS = { sections: [], values: {}, computed: { fix_period_end: null } };

function backend(routes: Routes = {}, currentId = 1) {
  let current = currentId;
  return mockApi({
    "/api/scenarios/columns": { body: { chunk_size: 100, columns: COLUMNS, export: EXPORT } },
    "/api/scenarios/query": { body: { rows: ROWS, filtered: ROWS.length, total: ROWS.length } },
    "/api/scenarios/views": { body: { views: [], default_view_id: null } },
    "/api/scenarios/options": { body: { scenarios: OPTIONS } },
    "/api/scenarios/current": (_u: string, init?: RequestInit): Reply => {
      if (init?.method === "PUT") current = JSON.parse(String(init.body)).id;
      return { body: raw(current) };
    },
    "/api/scenarios/nightly": { body: { changed: 1 } },
    "/api/scenarios": { body: raw(2) },
    "/api/parameters": (url: string): Reply => ({ body: { ...PARAMS, scenario: { id: Number(url.split("scenario_id=")[1]), name: "x" } } }),
    ...routes,
  });
}

const calls = () => vi.mocked(fetch).mock.calls.map(([url, init]) => ({ url: String(url), method: (init as RequestInit | undefined)?.method ?? "GET",
                                                                       body: (init as RequestInit | undefined)?.body ? JSON.parse(String((init as RequestInit).body)) : null }));
const sent = (method: string, url: string) => calls().filter((c) => c.method === method && c.url === url);
const PATH = "/parametre/senaryolar";
const rowOf = (name: string) => screen.getByText(name).closest("tr")!;

async function open(role = "Admin", routes: Routes = {}, currentId = 1) {
  const user = userEvent.setup();
  backend(routes, currentId);
  const view = renderApp(PATH, meAs(role));
  await screen.findByText("Fazla mesaili", {}, { timeout: 5000 });
  return { user, router: view.router };
}
const menuOf = async (user: ReturnType<typeof userEvent.setup>, name: string) => {
  await user.click(screen.getByRole("button", { name: `${name} işlemleri` }));
  return screen.getByRole("menu", { name: `${name} işlemleri` });
};
const items = (menu: HTMLElement) => within(menu).getAllByRole("menuitem").map((i) => i.textContent);

describe("ekran 07 · Senaryolar", () => {
  it("End user ekranı açamaz; bağlam çubuğundan senaryo değiştirir", async () => {
    const user = userEvent.setup();
    backend();
    renderApp(PATH, meAs("End user"));
    expect(await screen.findByText(/Bu ekranı açma yetkiniz yok/)).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: /Senaryo: Baz/ }));
    await user.click(await screen.findByRole("menuitemradio", { name: "Fazla mesaili" }));
    await waitFor(() => expect(screen.getByTestId("scenario")).toHaveTextContent("Senaryo: Fazla mesaili"));
    expect(sent("PUT", "/api/scenarios/current")[0].body).toEqual({ id: 2 });
  });

  it("liste: kolonlar, Baz yıldızlı ve Baz'ı izler boş, pasif satır soluk, seçili senaryonun satırında işaret yok, son çalışma durumuyla", async () => {
    await open("Admin", {}, 2);
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent).filter(Boolean).slice(0, 8))
      .toEqual(["Gece sırası", "Senaryo", "Model", "Baz'ı izler", "Gece çalışsın", "Süre bütçesi (sn)", "Son çalışma", "Aktif"]);
    expect(rowOf("Baz *")).toHaveTextContent("16.11.2026");
    expect(rowOf("Baz *")).toHaveTextContent("· Bitti");
    expect(rowOf("Eski deneme").className).toContain("is-off");
    await waitFor(() => expect(screen.getByTestId("scenario")).toHaveTextContent("Senaryo: Fazla mesaili"));
    expect(rowOf("Fazla mesaili").className ?? "").toBe(rowOf("Kısıtsız kapasite").className ?? "");  // seçili senaryo yalnız bağlam çubuğunda; listede işaret yok
    expect(screen.getByRole("switch", { name: "Baz gece çalışsın" })).toBeChecked();
    expect(screen.getByRole("switch", { name: "MILP deneme gece çalışsın" })).not.toBeChecked();
    expect(screen.getByRole("switch", { name: "Eski deneme gece çalışsın" })).toBeDisabled();  // pasif senaryo gece çalışmaz
  });

  it("Admin: Yeni senaryo şeridin solunda (indigo); satır menüsü tam; Baz'da Yeniden adlandır, Baz'dan ayır, Pasif yap ve Sil pasif", async () => {
    const { user } = await open();
    const add = screen.getByRole("button", { name: "Yeni senaryo" });
    expect(add.className).toContain("sc-btn--primary");
    expect(add.closest(".sc-table-toolbar-main")).not.toBeNull();
    let menu = await menuOf(user, "Fazla mesaili");
    expect(items(menu).slice(-6)).toEqual(["Parametreler", "Kopyala", "Yeniden adlandır", "Baz'dan ayır", "Pasif yap", "Sil"]);
    for (const name of ["Kopyala", "Yeniden adlandır", "Baz'dan ayır", "Pasif yap", "Sil"]) expect(within(menu).getByRole("menuitem", { name })).toBeEnabled();
    await user.keyboard("{Escape}");
    menu = await menuOf(user, "Baz");
    expect(within(menu).getByRole("menuitem", { name: "Parametreler" })).toBeEnabled();
    expect(within(menu).getByRole("menuitem", { name: "Kopyala" })).toBeEnabled();
    for (const name of ["Yeniden adlandır", "Baz'dan ayır", "Pasif yap", "Sil"]) expect(within(menu).getByRole("menuitem", { name })).toBeDisabled();
    await user.keyboard("{Escape}");
    menu = await menuOf(user, "MILP deneme");
    expect(within(menu).getByRole("menuitem", { name: "Baz'dan ayır" })).toBeDisabled();  // Baz'ı izlemiyor
    await user.keyboard("{Escape}");
    menu = await menuOf(user, "Eski deneme");
    expect(within(menu).getByRole("menuitem", { name: "Aktif yap" })).toBeEnabled();
    expect(within(menu).queryByRole("menuitem", { name: "Pasif yap" })).toBeNull();
    expect(within(menu).getByRole("menuitem", { name: "Parametreler" })).toBeEnabled();  // pasif senaryonun parametreleri de açılır
  });

  it("Key user: listeyi görür, gece ayarını değiştirir; Yeni senaryo ve yönetim öğeleri görünmez", async () => {
    const { user } = await open("Key user");
    expect(screen.queryByRole("button", { name: "Yeni senaryo" })).toBeNull();
    expect(screen.getByRole("switch", { name: "MILP deneme gece çalışsın" })).toBeEnabled();
    const menu = await menuOf(user, "Fazla mesaili");
    expect(items(menu).slice(-1)).toEqual(["Parametreler"]);
    for (const name of ["Kopyala", "Yeniden adlandır", "Baz'dan ayır", "Pasif yap", "Sil"]) expect(within(menu).queryByRole("menuitem", { name })).toBeNull();
  });

  it("Yeni senaryo: ad zorunlu, kaynak seçili senaryo, Baz'ı izler kaynağa göre; Kaydet gönderir ve liste yenilenir; ad hatası alanda", async () => {
    let reply: Reply = { status: 422, body: { error: { code: "validation", message: "Geçersiz.", details: [{ field: "name", problem: "Bu adla bir senaryo var." }] } } };
    const { user } = await open("Admin", { "/api/scenarios": () => reply });
    await user.click(screen.getByRole("button", { name: "Yeni senaryo" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni senaryo" });
    const save = within(dialog).getByRole("button", { name: "Kaydet" });
    expect(save).toBeDisabled();
    const source = within(dialog).getByRole("combobox", { name: "Kopyalanacak senaryo" });
    expect(source).toHaveValue("1");
    expect(within(source).getAllByRole("option").map((o) => o.textContent)).toEqual(["Baz *", "Fazla mesaili", "Kısıtsız kapasite", "MILP deneme", "Eski deneme"]);
    expect(within(dialog).getByRole("switch", { name: "Baz'ı izler" })).toBeChecked();
    await user.selectOptions(source, "4");
    expect(within(dialog).getByRole("switch", { name: "Baz'ı izler" })).not.toBeChecked();  // kaynağınki
    await user.type(within(dialog).getByRole("textbox", { name: /Senaryo adı/ }), "Fazla mesaili");
    await user.click(save);
    expect(await within(dialog).findByText("Bu adla bir senaryo var.")).toBeInTheDocument();
    reply = { body: raw(2) };
    await user.type(within(dialog).getByRole("textbox", { name: /Senaryo adı/ }), " 2");
    const queries = sent("POST", "/api/scenarios/query").length;
    await user.click(save);
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(sent("POST", "/api/scenarios").pop()!.body).toEqual({ name: "Fazla mesaili 2", source_id: 4, follows_base: false });
    await waitFor(() => expect(sent("POST", "/api/scenarios/query").length).toBeGreaterThan(queries));
    expect(document.querySelector(".sc-toast")).toBeNull();  // başarılı işlemde bildirim yok
  });

  it("Kopyala kaynağı satırla doldurur; Yeniden adlandır aynı adla kaydetmez", async () => {
    const { user } = await open();
    await user.click(within(await menuOf(user, "Kısıtsız kapasite")).getByRole("menuitem", { name: "Kopyala" }));
    let dialog = await screen.findByRole("dialog", { name: "Yeni senaryo" });
    expect(within(dialog).getByRole("combobox", { name: "Kopyalanacak senaryo" })).toHaveValue("3");
    await user.click(within(dialog).getByRole("button", { name: "Vazgeç" }));
    await user.click(within(await menuOf(user, "Kısıtsız kapasite")).getByRole("menuitem", { name: "Yeniden adlandır" }));
    dialog = await screen.findByRole("dialog", { name: "Yeniden adlandır · Kısıtsız kapasite" });
    const name = within(dialog).getByRole("textbox", { name: /Senaryo adı/ });
    expect(name).toHaveValue("Kısıtsız kapasite");
    expect(within(dialog).getByRole("button", { name: "Kaydet" })).toBeDisabled();
    await user.clear(name);
    await user.type(name, "Kısıtsız");
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(sent("PUT", "/api/scenarios/3")[0]?.body).toEqual({ name: "Kısıtsız" }));
  });

  it("Baz'dan ayır ve Pasif yap onay ister; Aktif yap sormaz; Sil plan versiyonu sayısını söyler, yayınlanmış planda kapalı", async () => {
    let info = { name: "Fazla mesaili", plan_versions: 3, deletable: true, reason: null as string | null };
    const { user } = await open("Admin", { "/api/scenarios/2/delete-info": () => ({ body: info }) });
    await user.click(within(await menuOf(user, "Fazla mesaili")).getByRole("menuitem", { name: "Baz'dan ayır" }));
    let dialog = await screen.findByRole("dialog", { name: "Senaryoyu Baz'dan ayır · Fazla mesaili" });
    expect(dialog).toHaveTextContent("Bu senaryo Baz'dan ayrılacak: Baz'daki değişiklikler artık yansımaz. Bu işlem geri alınamaz.");
    expect(within(dialog).getAllByRole("button").map((b) => b.textContent)).toEqual(["Vazgeç", "Ayır"]);
    await user.click(within(dialog).getByRole("button", { name: "Vazgeç" }));
    expect(sent("POST", "/api/scenarios/2/detach")).toHaveLength(0);
    await user.click(within(await menuOf(user, "Fazla mesaili")).getByRole("menuitem", { name: "Baz'dan ayır" }));
    await user.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Ayır" }));
    await waitFor(() => expect(sent("POST", "/api/scenarios/2/detach")).toHaveLength(1));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    await user.click(within(await menuOf(user, "Fazla mesaili")).getByRole("menuitem", { name: "Pasif yap" }));
    dialog = await screen.findByRole("dialog", { name: "Senaryoyu pasif yap · Fazla mesaili" });
    expect(dialog).toHaveTextContent("Bu senaryo pasif yapılacak: gece çalışmaz ve bağlam çubuğundaki listede görünmez. Bu işlem geri alınabilir.");
    expect(within(dialog).getAllByRole("button").map((b) => b.textContent)).toEqual(["Vazgeç", "Pasif yap"]);
    await user.click(within(dialog).getByRole("button", { name: "Pasif yap" }));
    await waitFor(() => expect(sent("POST", "/api/scenarios/2/deactivate")).toHaveLength(1));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await user.click(within(await menuOf(user, "Eski deneme")).getByRole("menuitem", { name: "Aktif yap" }));
    await waitFor(() => expect(sent("POST", "/api/scenarios/5/activate")).toHaveLength(1));
    expect(screen.queryByRole("dialog")).toBeNull();

    await user.click(within(await menuOf(user, "Fazla mesaili")).getByRole("menuitem", { name: "Sil" }));
    dialog = await screen.findByRole("dialog", { name: "Senaryoyu sil · Fazla mesaili" });
    expect(await within(dialog).findByText("Bu senaryo, parametreleri ve 3 plan versiyonu silinecek. Bu işlem geri alınamaz.")).toBeInTheDocument();
    expect(within(dialog).getAllByRole("button").map((b) => b.textContent)).toEqual(["Vazgeç", "Sil"]);
    await user.click(within(dialog).getByRole("button", { name: "Sil" }));
    await waitFor(() => expect(sent("DELETE", "/api/scenarios/2")).toHaveLength(1));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    info = { ...info, plan_versions: 0 };
    await user.click(within(await menuOf(user, "Fazla mesaili")).getByRole("menuitem", { name: "Sil" }));
    dialog = await screen.findByRole("dialog", { name: "Senaryoyu sil · Fazla mesaili" });
    expect(await within(dialog).findByText("Bu senaryo ve parametreleri silinecek. Bu işlem geri alınamaz.")).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Vazgeç" }));
    info = { ...info, deletable: false, reason: "Yayınlanmış planı olan senaryo silinemez; pasif yapılabilir." };
    await user.click(within(await menuOf(user, "Fazla mesaili")).getByRole("menuitem", { name: "Sil" }));
    dialog = await screen.findByRole("dialog", { name: "Senaryoyu sil · Fazla mesaili" });
    await waitFor(() => expect(dialog.querySelector(".sc-dialog-message")).toHaveTextContent("Yayınlanmış planı olan senaryo silinemez; pasif yapılabilir."));
    expect(within(dialog).getByRole("button", { name: "Sil" })).toBeDisabled();
  });

  it("gece ayarı: anahtar taslaktır, açılan sona girer; yalnız gece çalışan satır sürüklenir; Kaydet sırayı gönderir, Vazgeç geri alır", async () => {
    const { user } = await open("Key user");
    expect(screen.queryByRole("button", { name: "Kaydet" })).toBeNull();
    expect(rowOf("Fazla mesaili")).toHaveAttribute("draggable", "true");
    expect(rowOf("MILP deneme")).not.toHaveAttribute("draggable");
    await user.click(screen.getByRole("switch", { name: "MILP deneme gece çalışsın" }));
    expect(rowOf("MILP deneme")).toHaveAttribute("draggable", "true");
    expect(within(rowOf("MILP deneme")).getByText("4")).toBeInTheDocument();  // sıranın sonuna
    await user.click(screen.getByRole("button", { name: "Vazgeç" }));
    expect(screen.getByRole("switch", { name: "MILP deneme gece çalışsın" })).not.toBeChecked();

    await user.click(screen.getByRole("switch", { name: "MILP deneme gece çalışsın" }));
    await user.click(screen.getByRole("switch", { name: "Kısıtsız kapasite gece çalışsın" }));  // kapandı: sırası boşalır
    fireEvent.dragStart(rowOf("Baz *"));
    fireEvent.dragOver(rowOf("MILP deneme"), { clientY: 10 });  // alt yarı: arkasına
    fireEvent.drop(rowOf("MILP deneme"));
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(sent("PUT", "/api/scenarios/nightly")).toHaveLength(1));
    expect(sent("PUT", "/api/scenarios/nightly")[0].body).toEqual({ rows: [
      { id: 2, runs_nightly: true }, { id: 4, runs_nightly: true }, { id: 1, runs_nightly: true },
      { id: 3, runs_nightly: false }, { id: 5, runs_nightly: false },
    ] });
  });

  it("⋯ › Parametreler senaryoyu seçer ve Parametreler'i o senaryoyla açar; bağlam çubuğundan geçince ekran yeni senaryoyla yeniden yüklenir", async () => {
    const { user, router } = await open();
    await user.click(within(await menuOf(user, "Fazla mesaili")).getByRole("menuitem", { name: "Parametreler" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/parametre/parametreler"));
    expect(sent("PUT", "/api/scenarios/current")[0].body).toEqual({ id: 2 });
    await waitFor(() => expect(sent("GET", "/api/parameters?scenario_id=2")).not.toHaveLength(0));
    expect(screen.getByTestId("scenario")).toHaveTextContent("Senaryo: Fazla mesaili");
    await user.click(screen.getByTestId("scenario"));
    const list = await screen.findByRole("menu", { name: "Senaryolar" });
    await waitFor(() => expect(within(list).getAllByRole("menuitemradio").map((i) => i.textContent)).toEqual(["Baz *", "Fazla mesaili", "Kısıtsız kapasite", "MILP deneme"]));  // pasif yok
    await user.click(within(list).getByRole("menuitemradio", { name: "Kısıtsız kapasite" }));
    await waitFor(() => expect(sent("GET", "/api/parameters?scenario_id=3")).not.toHaveLength(0));
  });

  it("pasif senaryonun parametreleri açıkken bağlam çubuğu adını gösterir", async () => {
    const { user, router } = await open();
    await user.click(within(await menuOf(user, "Eski deneme")).getByRole("menuitem", { name: "Parametreler" }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/parametre/parametreler"));
    const pill = screen.getByTestId("scenario");
    expect(pill).toHaveTextContent("Senaryo: Eski deneme");
    expect(pill).toHaveAttribute("title", "Pasif senaryo: bağlam çubuğundaki listede görünmez");
  });

  it("kaydedilmemiş değişiklik varken senaryo geçişi onay ister; vazgeçilirse senaryo değişmez", async () => {
    const { user } = await open("Key user");
    await user.click(screen.getByRole("switch", { name: "MILP deneme gece çalışsın" }));
    const pick = async () => {
      await user.click(screen.getByTestId("scenario"));
      await user.click(await screen.findByRole("menuitemradio", { name: "Fazla mesaili" }));
      return screen.findByRole("dialog", { name: "Kaydedilmemiş değişiklikler var" });
    };
    await user.click(within(await pick()).getByRole("button", { name: "Vazgeç" }));
    expect(sent("PUT", "/api/scenarios/current")).toHaveLength(0);
    expect(screen.getByTestId("scenario")).toHaveTextContent("Senaryo: Baz");
    await user.click(within(await pick()).getByRole("button", { name: "Kaydetmeden çık" }));
    await waitFor(() => expect(screen.getByTestId("scenario")).toHaveTextContent("Senaryo: Fazla mesaili"));
  });

  it("girişte hatırlanan senaryo açılır", async () => {
    await open("Key user", {}, 3);
    await waitFor(() => expect(screen.getByTestId("scenario")).toHaveTextContent("Senaryo: Kısıtsız kapasite"));
  });
});

// Parametreler › Pegging (K-201): sekmenin yeri (Hedefler'in yanında), yöntem ve iki ölçüt listesi; sürükleyerek, klavyeyle (Alt + ↑ / ↓) ve
// düğmeyle sıralama; yön seçimi ve ölçüte göre ipucu; Kaydet ve Vazgeç altta (K-166), tek Kaydet yöntemi ve iki listeyi birlikte gönderir;
// kaydedilmemiş değişiklik uyarısı; "Başlangıç düzenine getir" yok; Model › Çözüm'de Özel alokasyon; sıralanabilir liste bileşeni.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { meAs, mockApi, renderApp } from "../test/helpers";
import { moveItem, SortableList } from "../ui/SortableList";

const TIME = [{ value: "Artan", hint: "erken önce" }, { value: "Azalan", hint: "geç önce" }];
const C = (criterion: string, directions: { value: string; hint: string }[] = []): { criterion: string; direction: string | null; directions: { value: string; hint: string }[] } =>
  ({ criterion, direction: directions[0]?.value ?? null, directions });
const NEED = [C("Dönem", TIME), C("Kesin sipariş"), C("Teklif"), C("Beklemedeki sipariş"), C("Tahmin"), C("Üretim siparişi ihtiyacı"), C("Üretim planı ihtiyacı"),
              C("Öncelik grubu", [{ value: "Artan", hint: "1 önce" }, { value: "Azalan", hint: "5 önce" }]), C("İhtiyaç tarihi", TIME),
              C("Sipariş no", [{ value: "Artan", hint: "küçük numara önce" }, { value: "Azalan", hint: "büyük numara önce" }])];
const SUPPLY = [C("Dönem", [...TIME, { value: "İhtiyaca en yakın", hint: "ihtiyacın döneminden geriye, yetmezse ileriye" }]), C("Stok"), C("Kalitedeki stok"), C("Üretim siparişi"),
                C("Satın alma siparişi"), C("Arz tarihi", TIME), C("Üretim planı"), C("Satın alma planı"), C("Son kullanma tarihi", TIME)];
const P = (key: string, label: string, options: string[]) => ({ key, label, kind: "choice", options });
const SECTIONS = [
  { key: "model", title: "Model", table: null, subs: [
    { key: "model-tipi", title: "Model tipi", table: null, params: [P("ModelType", "Model tipi", ["LP", "MILP"])] },
    { key: "cozum", title: "Çözüm", table: null, params: [
      { ...P("CustomAllocation", "Özel alokasyon", ["Dikkate al", "Dikkate alma"]), hint: "Dikkate alma seçilirse sahibine ayrılmış arz da genele girer; model de pegging de anahtarlara bakmaz." },
      { key: "OptimalityGapPct", label: "Optimality gap (%)", kind: "number", min: 0, max: 100 }] }] },
  { key: "hedefler", title: "Hedefler", table: "objectives", subs: [] },
  { key: "pegging", title: "Pegging", table: null, subs: [{ key: "pegging", title: "Pegging", table: "pegging", params: [P("FullPeggingMethod", "Full pegging yöntemi", ["FIFO", "Talep termini"])] }] },
  { key: "talep", title: "Talep", table: null, subs: [{ key: "kapsam", title: "Plana giren talep", table: null, params: [{ key: "IncludeQuotes", label: "Teklif", kind: "bool" }] }] },
];
type Item = { criterion: string; direction: string | null };
type Body = { method?: string; need?: Item[]; supply?: Item[]; changes?: Record<string, unknown> };

function backend() {
  const sent: { url: string; body: Body }[] = [];
  let state = { method: "FIFO", need: NEED, supply: SUPPLY };
  let values: Record<string, string | null> = { ModelType: "LP", CustomAllocation: "Dikkate al", OptimalityGapPct: "1", FullPeggingMethod: "FIFO", IncludeQuotes: "0" };
  const full = (list: Item[], defs: typeof NEED) => list.map((x) => ({ ...defs.find((d) => d.criterion === x.criterion)!, direction: x.direction }));
  mockApi({
    "/api/scenarios/current": { body: { id: 1, name: "Baz", is_base: true, is_active: true } },
    "/api/parameters/objectives": { body: { rows: [], total_seconds: 0, catalog: [] } },
    "/api/parameters/pegging": (url, init) => {
      if (init?.method === "PUT") {
        const body = JSON.parse(String(init.body)) as Body;
        sent.push({ url, body });
        state = { method: body.method ?? state.method, need: body.need ? full(body.need, NEED) : state.need, supply: body.supply ? full(body.supply, SUPPLY) : state.supply };
      }
      return { body: { method: { key: "FullPeggingMethod", label: "Full pegging yöntemi", value: state.method, options: ["FIFO", "Talep termini"] }, need: state.need, supply: state.supply } };
    },
    "/api/parameters": (url, init) => {
      if (init?.method === "PUT") {
        const body = JSON.parse(String(init.body)) as Body;
        sent.push({ url, body });
        values = { ...values, ...(body.changes as Record<string, string>) };
      }
      return { body: { scenario: { id: 1, name: "Baz" }, sections: SECTIONS, values, computed: { fix_period_end: null } } };
    },
  });
  return sent;
}

async function open(path = "/parametre/parametreler?sekme=pegging", role = "Key user") {
  const user = userEvent.setup();
  const sent = backend();
  renderApp(path, meAs(role));
  await screen.findByRole("heading", { name: "Parametreler" }, { timeout: 5000 });
  return { user, sent };
}
const list = (name: string) => screen.getByRole("list", { name });
const names = (name: string) => within(list(name)).getAllByRole("listitem").map((li) => li.querySelector(".sc-sortable-name")!.textContent);
const row = (name: string, criterion: string) => within(list(name)).getAllByRole("listitem").find((li) => li.querySelector(".sc-sortable-name")!.textContent === criterion)!;
const save = () => screen.getByRole("button", { name: "Kaydet" });
const cancel = () => screen.getByRole("button", { name: "Vazgeç" });
/** Tarayıcının sürüklemesi: tut, hedefin üstüne getir, bırak. jsdom'da ölçü olmadığı için bırakma hedefin altına sayılır (üst ve alt yarı ayrımı tarayıcıda, görsel kontrolde). */
function drag(from: HTMLElement, to: HTMLElement) {
  const dataTransfer = { setData: vi.fn(), effectAllowed: "" };
  fireEvent.dragStart(from, { dataTransfer });
  fireEvent.dragOver(to, { dataTransfer });
  fireEvent.drop(to, { dataTransfer });
  fireEvent.dragEnd(from, { dataTransfer });
}

describe("Parametreler › Pegging", () => {
  it("sekme Hedefler'in yanında; yöntem ve iki liste başlangıç sırasıyla; Kaydet ve Vazgeç altta, değişiklik yokken pasif; sıfırlama düğmesi yok", async () => {
    await open();
    expect(within(screen.getByRole("radiogroup", { name: "Parametre başlıkları" })).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Model", "Hedefler", "Pegging", "Talep"]);
    await screen.findByRole("list", { name: "İhtiyaç sırası" });
    expect(names("İhtiyaç sırası")).toEqual(NEED.map((c) => c.criterion));
    expect(names("Arz sırası")).toEqual(SUPPLY.map((c) => c.criterion));
    expect(within(list("İhtiyaç sırası")).getAllByRole("listitem").map((li) => li.querySelector(".sc-sortable-no")!.textContent)).toEqual(["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]);
    expect(within(screen.getByRole("radiogroup", { name: "Full pegging yöntemi" })).getByRole("radio", { name: "FIFO" })).toHaveAttribute("aria-checked", "true");
    // yön yalnız yönlü ölçütte; arzda Dönem'in üç seçeneği
    expect(within(row("İhtiyaç sırası", "Kesin sipariş")).queryByRole("radiogroup")).toBeNull();
    expect(within(row("Arz sırası", "Dönem")).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Artan", "Azalan", "İhtiyaca en yakın"]);
    expect(within(row("İhtiyaç sırası", "Dönem")).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Artan", "Azalan"]);
    expect(save()).toBeDisabled();
    expect(cancel()).toBeDisabled();
    expect(save().closest(".sc-settings-foot")).not.toBeNull();
    expect(screen.queryByRole("button", { name: /Başlangıç düzenine getir/ })).toBeNull();
    expect(screen.queryByRole("navigation", { name: "Pegging bölümleri" })).toBeNull();          // tek alt başlık: sol menü yok
    // satırda taşı düğmesi yok (K-201 demo): sıralama sürükleyerek ve klavyeyle
    expect(within(list("İhtiyaç sırası")).queryAllByRole("button")).toEqual([]);
    expect(document.querySelector(".sc-sortable-moves")).toBeNull();
    // yöntem satırı: etiket ve seçenekler yan yana, ayar satırı (sc-field) değil
    expect(screen.getByRole("radiogroup", { name: "Full pegging yöntemi" }).closest(".sc-pegging-method")).not.toBeNull();
    expect(screen.getByRole("radiogroup", { name: "Full pegging yöntemi" }).closest(".sc-field")).toBeNull();
    expect(document.querySelector(".sc-pegging-head")!.tagName).toBe("H2");
  });

  it("sürükleyerek, klavyeyle ve düğmeyle sıralama; yön; tek Kaydet yöntemi ve iki listeyi birlikte gönderir", async () => {
    const { user, sent } = await open();
    await screen.findByRole("list", { name: "İhtiyaç sırası" });
    drag(row("İhtiyaç sırası", "Tahmin"), row("İhtiyaç sırası", "Dönem"));                       // Tahmin, Dönem'in altına
    expect(names("İhtiyaç sırası").slice(0, 5)).toEqual(["Dönem", "Tahmin", "Kesin sipariş", "Teklif", "Beklemedeki sipariş"]);
    expect(save()).toBeEnabled();
    expect(cancel()).toBeEnabled();
    drag(row("Arz sırası", "Stok"), row("İhtiyaç sırası", "Dönem"));                             // listeler arası sürükleme yok
    expect(names("İhtiyaç sırası")[0]).toBe("Dönem");
    expect(names("Arz sırası")[1]).toBe("Stok");
    row("Arz sırası", "Stok").focus();
    await user.keyboard("{Alt>}{ArrowDown}{/Alt}");                                              // klavye: Alt + ↓
    expect(names("Arz sırası").slice(0, 3)).toEqual(["Dönem", "Kalitedeki stok", "Stok"]);
    expect(row("Arz sırası", "Stok")).toHaveFocus();                                             // odak satırla birlikte gider
    row("Arz sırası", "Arz tarihi").focus();
    await user.keyboard("{Alt>}{ArrowUp}{/Alt}");
    expect(names("Arz sırası").slice(3, 6)).toEqual(["Üretim siparişi", "Arz tarihi", "Satın alma siparişi"]);
    await user.click(within(row("Arz sırası", "Dönem")).getByRole("radio", { name: "İhtiyaca en yakın" }));
    await user.click(within(screen.getByRole("radiogroup", { name: "Full pegging yöntemi" })).getByRole("radio", { name: "Talep termini" }));
    await user.click(save());
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0].url).toBe("/api/parameters/pegging?scenario_id=1");
    expect(sent[0].body.method).toBe("Talep termini");
    expect(sent[0].body.need!.slice(0, 3)).toEqual([{ criterion: "Dönem", direction: "Artan" }, { criterion: "Tahmin", direction: null }, { criterion: "Kesin sipariş", direction: null }]);
    expect(sent[0].body.supply!.map((x) => x.criterion)).toEqual(["Dönem", "Kalitedeki stok", "Stok", "Üretim siparişi", "Arz tarihi", "Satın alma siparişi", "Üretim planı", "Satın alma planı", "Son kullanma tarihi"]);
    expect(sent[0].body.supply![0]).toEqual({ criterion: "Dönem", direction: "İhtiyaca en yakın" });
    expect(sent[0].body.need).toHaveLength(10);                                                  // ölçüt eklenmez, silinmez
    await waitFor(() => expect(save()).toBeDisabled());
    expect(names("İhtiyaç sırası")[1]).toBe("Tahmin");
  });

  it("Vazgeç taslağı atar; kaydedilmemiş değişiklikle sekme değişirken uyarı", async () => {
    const { user, sent } = await open();
    await screen.findByRole("list", { name: "Arz sırası" });
    row("Arz sırası", "Stok").focus();
    await user.keyboard("{Alt>}{ArrowDown}{/Alt}");
    expect(names("Arz sırası")[2]).toBe("Stok");
    await user.click(cancel());
    expect(names("Arz sırası")[1]).toBe("Stok");
    expect(save()).toBeDisabled();
    await user.click(within(row("İhtiyaç sırası", "Sipariş no")).getByRole("radio", { name: "Azalan" }));
    await user.click(within(screen.getByRole("radiogroup", { name: "Parametre başlıkları" })).getByRole("radio", { name: "Talep" }));
    expect(await screen.findByRole("dialog")).toHaveTextContent(/[Kk]aydedilmemiş/);
    expect(sent).toHaveLength(0);
  });

  it("yön seçeneğinin ipucu ölçüte göre; ekranda açıklama yazısı yok", async () => {
    const { user } = await open();
    await screen.findByRole("list", { name: "İhtiyaç sırası" });
    const tip = async (listName: string, criterion: string, option: string) => {
      await user.hover(within(row(listName, criterion)).getByText(option));
      const text = (await screen.findByRole("tooltip")).textContent;
      await user.unhover(within(row(listName, criterion)).getByText(option));
      return text;
    };
    expect(await tip("İhtiyaç sırası", "Dönem", "Artan")).toBe("erken önce");
    expect(await tip("İhtiyaç sırası", "Öncelik grubu", "Azalan")).toBe("5 önce");
    expect(await tip("İhtiyaç sırası", "Sipariş no", "Artan")).toBe("küçük numara önce");
    expect(await tip("Arz sırası", "Dönem", "İhtiyaca en yakın")).toBe("ihtiyacın döneminden geriye, yetmezse ileriye");
    expect(document.querySelector(".sc-pegging")!.textContent).not.toMatch(/erken önce|yukarıdan aşağı|uygulanır/);
  });

  it("Özel alokasyon Model › Çözüm'de, Pegging sekmesinde değil; genel formla kaydedilir", async () => {
    const { user, sent } = await open("/parametre/parametreler?sekme=model&bolum=cozum");
    const group = await screen.findByRole("radiogroup", { name: "Özel alokasyon" });
    expect(within(group).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Dikkate al", "Dikkate alma"]);
    expect(within(group).getByRole("radio", { name: "Dikkate al" })).toHaveAttribute("aria-checked", "true");
    expect(within(screen.getByRole("navigation", { name: "Model bölümleri" })).getAllByRole("button").map((b) => b.textContent)).toEqual(["Model tipi", "Çözüm"]);
    await user.click(within(group).getByRole("radio", { name: "Dikkate alma" }));
    await user.click(save());
    await waitFor(() => expect(sent).toHaveLength(1));
    expect(sent[0].body.changes).toEqual({ CustomAllocation: "Dikkate alma" });
    await user.click(within(screen.getByRole("radiogroup", { name: "Parametre başlıkları" })).getByRole("radio", { name: "Pegging" }));
    await screen.findByRole("list", { name: "İhtiyaç sırası" });
    expect(screen.queryByRole("radiogroup", { name: "Özel alokasyon" })).toBeNull();
  });
});

describe("SortableList", () => {
  const items = [{ id: "a", label: "A" }, { id: "b", label: "B" }, { id: "c", label: "C" }];

  it("moveItem: hedefin üstüne ya da altına; kendine taşıma değiştirmez", () => {
    expect(moveItem(["a", "b", "c"], "c", "a", "before")).toEqual(["c", "a", "b"]);
    expect(moveItem(["a", "b", "c"], "a", "c", "after")).toEqual(["b", "c", "a"]);
    expect(moveItem(["a", "b", "c"], "a", "b", "after")).toEqual(["b", "a", "c"]);
    expect(moveItem(["a", "b", "c"], "b", "b", "before")).toEqual(["a", "b", "c"]);
  });

  it("taşı düğmeleri varsayılan kapalı; satırda sıra no ve ad", () => {
    render(<SortableList label="Liste" items={items} onOrder={vi.fn()} />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(within(screen.getByRole("list", { name: "Liste" })).getAllByRole("listitem").map((li) => li.getAttribute("aria-label"))).toEqual(["1. A", "2. B", "3. C"]);
  });

  it("taşı düğmeleri açıkken (seçenek): yeni sırayı bildirir, kendisi kaydetmez", async () => {
    const user = userEvent.setup();
    const onOrder = vi.fn();
    render(<SortableList label="Liste" items={items} onOrder={onOrder} moveButtons />);
    expect(screen.getByRole("button", { name: "A: yukarı taşı" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "C: aşağı taşı" })).toBeDisabled();
    expect(within(screen.getByRole("list", { name: "Liste" })).getAllByRole("listitem").map((li) => li.getAttribute("aria-label"))).toEqual(["1. A", "2. B", "3. C"]);
    await user.click(screen.getByRole("button", { name: "B: yukarı taşı" }));
    expect(onOrder).toHaveBeenLastCalledWith(["b", "a", "c"]);
    screen.getAllByRole("listitem")[0].focus();
    await user.keyboard("{Alt>}{ArrowUp}{/Alt}");                                                // ilk satır yukarı gitmez
    expect(onOrder).toHaveBeenCalledTimes(1);
    await user.keyboard("{ArrowDown}");                                                          // Alt'sız ok taşımaz
    expect(onOrder).toHaveBeenCalledTimes(1);
    expect(screen.getAllByRole("listitem").map((li) => li.querySelector(".sc-sortable-name")!.textContent)).toEqual(["A", "B", "C"]);   // sıra dışarıdan gelir
  });

  it("salt okunur: tutamak ve düğme yok, sürüklenmez", () => {
    render(<SortableList label="Liste" items={items} onOrder={vi.fn()} readOnly moveButtons />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getAllByRole("listitem").every((li) => li.getAttribute("draggable") === "false" && !li.hasAttribute("tabindex"))).toBe(true);
    expect(document.querySelector(".sc-sortable-grip")).toBeNull();
  });
});

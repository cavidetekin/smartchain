// Görünüm (1.4, docs/12): kayıtlı görünüm (U-9, K-89), kolon düzeni (U-10), gruplama (U-11, K-90),
// aktif filtre etiketleri (U-12), boş değer (U-13).
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ROW_REM } from "./DataTable";
import { describeFilter } from "./filters";
import {
  calls, COLUMNS, dataRows, group, lastQuery, openTable, savedView, STANDARD_FIELDS, useTableTestSetup, VIEW_PX,
} from "./testBackend";
import type { ListColumn } from "./types";

useTableTestSetup();

const header = (label: string) => screen.getByRole("columnheader", { name: new RegExp(`^${label}`) });
const sortButton = (label: string) => within(header(label)).getAllByRole("button")[0];
const viewSelect = () => screen.getByRole("combobox", { name: "Görünüm" }) as HTMLSelectElement;
const selectedText = () => viewSelect().selectedOptions[0].textContent;
const lastViewCall = (method: string) => [...calls.views].reverse().find((c) => c.method === method);
const columnByField = (f: string) => COLUMNS.find((c) => c.field === f) as ListColumn;

async function saveAs(user: ReturnType<typeof userEvent.setup>, name: string, shared = false) {
  await user.click(screen.getByRole("button", { name: "Farklı kaydet" }));
  const dialog = screen.getByRole("dialog", { name: "Farklı kaydet" });
  await user.type(within(dialog).getByLabelText(/Görünüm adı/), name);
  if (shared) await user.click(within(dialog).getByRole("checkbox", { name: /Paylaşılan/ }));
  await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
}

describe("kayıtlı görünüm (U-9, K-89)", () => {
  const mine = savedView(5, "Benim", { columns: [{ field: "Name" }, { field: "Code", width: 8 }], sort: [{ field: "Code", dir: "desc" }] });

  it("açılışta kullanıcının varsayılan görünümü uygulanır; Standart istenmeden", async () => {
    await openTable({ views: { views: [mine], default_view_id: 5 } });
    expect(calls.queries[0]).toMatchObject({ fields: ["Name", "Code"], sort: [{ field: "Code", dir: "desc" }] });
    expect(selectedText()).toBe("Benim (varsayılan)");
    expect(calls.views[0].url).toContain("user_id=3");
  });

  it("varsayılan yoksa Standart; değişince • çıkar, Kaydet yeni içeriği gönderir", async () => {
    const user = userEvent.setup();
    await openTable({ views: { views: [mine], default_view_id: null } });
    expect(selectedText()).toBe("Standart (varsayılan)");
    expect(calls.queries[0].fields).toEqual(STANDARD_FIELDS);
    expect(screen.queryByRole("img", { name: "Kaydedilmemiş değişiklik" })).toBeNull();
    await user.selectOptions(viewSelect(), "5");
    await user.click(sortButton("Malzeme adı"));
    expect(screen.getByRole("img", { name: "Kaydedilmemiş değişiklik" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(lastViewCall("PUT")?.body).toMatchObject({ definition: { sort: [{ field: "Name", dir: "asc" }] } }));
    expect(lastViewCall("PUT")?.url).toMatch(/\/views\/5\?user_id=3/);
    await waitFor(() => expect(screen.queryByRole("img", { name: "Kaydedilmemiş değişiklik" })).toBeNull());
  });

  it("Farklı kaydet: ad ve paylaşım; yeni görünüm seçilir; aynı ad hatası pencerede", async () => {
    const user = userEvent.setup();
    await openTable({ views: { views: [mine], default_view_id: null } });
    await user.click(sortButton("Malzeme kodu"));
    await saveAs(user, "Yeni", true);
    await waitFor(() => expect(lastViewCall("POST")?.body).toMatchObject({ name: "Yeni", is_shared: true }));
    expect((lastViewCall("POST")?.body as { definition: unknown }).definition).toMatchObject({
      v: 1, columns: STANDARD_FIELDS.map((field) => ({ field, width: null })), pinned: 0, sort: [{ field: "Code", dir: "asc" }],
    });
    await waitFor(() => expect(selectedText()).toBe("Yeni"));
    await saveAs(user, "Benim");
    expect(await screen.findByText("Bu adda bir görünümünüz zaten var.")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Farklı kaydet" })).toBeInTheDocument();
  });

  it("başkasının paylaştığı görünümde Kaydet yok, Farklı kaydet var", async () => {
    const user = userEvent.setup();
    const shared = savedView(7, "Ekip", {}, { is_owner: false, is_shared: true, owner_user_id: 9, owner_name: "Ayşe" });
    await openTable({ views: { views: [shared], default_view_id: 7 } });
    expect(selectedText()).toBe("Ekip · Ayşe paylaştı (varsayılan)");
    await user.click(sortButton("Malzeme kodu"));
    expect(screen.getByRole("img", { name: "Kaydedilmemiş değişiklik" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Kaydet" })).toBeNull();
    expect(screen.getByRole("button", { name: "Farklı kaydet" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Görünüm işlemleri" }));
    expect(screen.queryByRole("menuitem", { name: "Sil" })).toBeNull();
  });

  it("değişiklik varken başka görünüme geçince onay; Vazgeç kalır, onaylayınca geçer", async () => {
    const user = userEvent.setup();
    const other = savedView(6, "Diğer", { columns: [{ field: "MaterialLevel" }] });
    await openTable({ views: { views: [mine, other], default_view_id: 5 } });
    await user.click(sortButton("Malzeme adı"));
    await user.selectOptions(viewSelect(), "6");
    const dialog = screen.getByRole("dialog", { name: "Kaydedilmemiş değişiklik" });
    await user.click(within(dialog).getByRole("button", { name: "Vazgeç" }));
    expect(selectedText()).toBe("Benim (varsayılan)");
    await user.selectOptions(viewSelect(), "6");
    await user.click(screen.getByRole("button", { name: "Değişiklikleri bırak" }));
    await waitFor(() => expect(lastQuery().fields).toEqual(["MaterialLevel"]));
    expect(selectedText()).toBe("Diğer");
  });

  it("varsayılan yap, varsayılanı kaldır ve sil (onaylı)", async () => {
    const user = userEvent.setup();
    await openTable({ views: { views: [mine], default_view_id: null } });
    await user.selectOptions(viewSelect(), "5");
    await user.click(screen.getByRole("button", { name: "Görünüm işlemleri" }));
    await user.click(screen.getByRole("menuitem", { name: "Varsayılan yap" }));
    await waitFor(() => expect(lastViewCall("PUT")?.body).toEqual({ view_id: 5 }));
    await waitFor(() => expect(selectedText()).toBe("Benim (varsayılan)"));
    await user.click(screen.getByRole("button", { name: "Görünüm işlemleri" }));
    await user.click(screen.getByRole("menuitem", { name: "Sil" }));
    const dialog = screen.getByRole("dialog", { name: "Görünümü sil" });
    expect(within(dialog).getByText(/"Benim" görünümü silinsin mi/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Sil" }));
    await waitFor(() => expect(lastViewCall("DELETE")?.url).toMatch(/\/views\/5\?user_id=3/));
    await waitFor(() => expect(selectedText()).toBe("Standart (varsayılan)"));
    expect(lastQuery().fields).toEqual(STANDARD_FIELDS);
  });

  it("göreli tarih filtresi göreli kaydedilir (tarih yok); açılınca etiket 'bu hafta' yazar", async () => {
    const user = userEvent.setup();
    await openTable();
    await user.click(screen.getByRole("button", { name: "Son değişiklik zamanı filtresi" }));
    const menu = screen.getByRole("dialog", { name: "Son değişiklik zamanı filtresi" });
    await user.click(within(menu).getByRole("radio", { name: "Göreli" }));
    await user.click(within(menu).getByRole("button", { name: "Uygula" }));
    await saveAs(user, "Bu hafta");
    await waitFor(() => expect(lastViewCall("POST")).toBeDefined());
    const definition = (lastViewCall("POST")?.body as { definition: { filters: unknown[] } }).definition;
    expect(definition.filters).toEqual([{ field: "UpdatedAt", op: "relative", value: "this_week" }]);
    expect(JSON.stringify(definition)).not.toMatch(/\d{4}-\d{2}-\d{2}/);

    const stored = savedView(8, "Bu hafta", { filters: [{ field: "UpdatedAt", op: "relative", value: "this_week" }] });
    await openTable({ views: { views: [stored], default_view_id: 8 } });
    expect(screen.getAllByRole("button", { name: /Son değişiklik zamanı: bu hafta/ }).length).toBeGreaterThan(0);
  });

  it("artık olmayan alan için uyarı gösterilir", async () => {
    const warned = savedView(9, "Eski", {}, { warnings: ["'OldField' alanı artık listede yok; görünümden çıkarıldı."] });
    await openTable({ views: { views: [warned], default_view_id: 9 } });
    expect(screen.getByText(/OldField/)).toBeInTheDocument();
  });
});

describe("kolon düzeni (U-10)", () => {
  it("genişlik: tutamak klavyeyle ve fareyle (rem); görünüme girer", async () => {
    const user = userEvent.setup();
    await openTable();
    const handle = screen.getByRole("separator", { name: "Malzeme kodu genişliği" });
    expect(handle).toHaveAttribute("aria-valuenow", "13.85");
    handle.focus();
    await user.keyboard("{ArrowRight}{ArrowRight}");
    expect(handle).toHaveAttribute("aria-valuenow", "14.85");
    fireEvent.mouseDown(handle, { clientX: 100 });
    fireEvent.mouseMove(document, { clientX: 126 });  // 26 px = 2 rem (13 px)
    fireEvent.mouseUp(document);
    expect(handle).toHaveAttribute("aria-valuenow", "16.85");
    fireEvent.mouseDown(handle, { clientX: 500 });
    fireEvent.mouseMove(document, { clientX: 0 });
    fireEvent.mouseUp(document);
    expect(handle).toHaveAttribute("aria-valuenow", "4");  // en az 4rem
    await saveAs(user, "Dar");
    await waitFor(() => expect(lastViewCall("POST")).toBeDefined());
    expect((lastViewCall("POST")?.body as { definition: { columns: { width: number }[] } }).definition.columns[0])
      .toEqual({ field: "Code", width: 4 });
  });

  it("sıra: Alt+← / Alt+→, kolon menüsü ve sürükle-bırak", async () => {
    const user = userEvent.setup();
    await openTable();
    sortButton("Malzeme adı").focus();
    await user.keyboard("{Alt>}{ArrowLeft}{/Alt}");
    await waitFor(() => expect(lastQuery().fields.slice(0, 2)).toEqual(["Name", "Code"]));
    expect(sortButton("Malzeme adı")).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Malzeme adı kolon işlemleri" }));
    await user.click(screen.getByRole("menuitem", { name: "Sağa taşı" }));
    await waitFor(() => expect(lastQuery().fields.slice(0, 3)).toEqual(["Code", "Name", "MaterialLevel"]));
    fireEvent.dragStart(header("Malzeme kodu"));
    fireEvent.dragOver(header("Malzeme seviyesi"), { clientX: 10 });
    expect(header("Malzeme seviyesi")).toHaveClass("is-drop-after");
    fireEvent.drop(header("Malzeme seviyesi"));
    await waitFor(() => expect(lastQuery().fields.slice(0, 3)).toEqual(["Name", "MaterialLevel", "Code"]));
  });

  it("sabitleme: ilk kolonlar sticky, sol konum genişliklerden; kaldırılabilir; görünüme girer", async () => {
    const user = userEvent.setup();
    await openTable();
    await user.click(screen.getByRole("button", { name: "Malzeme adı kolon işlemleri" }));
    await user.click(screen.getByRole("menuitem", { name: "Buraya kadar sabitle" }));
    expect(header("Malzeme kodu")).toHaveClass("is-pinned");
    expect(header("Malzeme kodu").style.left).toBe("0rem");
    expect(header("Malzeme adı")).toHaveClass("is-pinned", "is-pinned-last");
    expect(header("Malzeme adı").style.left).toBe("13.8462rem");
    expect(header("Malzeme seviyesi")).not.toHaveClass("is-pinned");
    await screen.findByText("M-0");
    expect(within(dataRows()[0] as HTMLElement).getAllByRole("cell")[1]).toHaveClass("is-pinned");
    await saveAs(user, "Sabit");
    await waitFor(() => expect(lastViewCall("POST")).toBeDefined());
    expect((lastViewCall("POST")?.body as { definition: { pinned: number } }).definition.pinned).toBe(2);
    await user.click(screen.getByRole("button", { name: "Malzeme kodu kolon işlemleri" }));
    await user.click(screen.getByRole("menuitem", { name: "Sabitlemeyi kaldır" }));
    expect(header("Malzeme kodu")).not.toHaveClass("is-pinned");
  });

  it("kolon menüsünden gizle ve genişliği sıfırla", async () => {
    const user = userEvent.setup();
    await openTable();
    await user.click(screen.getByRole("button", { name: "Malzeme adı kolon işlemleri" }));
    expect(screen.getByRole("menuitem", { name: "Genişliği sıfırla" })).toBeDisabled();
    await user.click(screen.getByRole("menuitem", { name: "Alanı gizle" }));
    await waitFor(() => expect(lastQuery().fields).not.toContain("Name"));
  });
});

describe("gruplama ve ara toplam (U-11, K-90)", () => {
  const groups = [
    group(["Hammadde"], 2, { aggregates: { SafetyStock: 1234.5 }, unit_decimals: { SafetyStock: 3 } }),
    group(["Yarı mamul"], 3, { aggregates: { SafetyStock: null }, mixed_units: ["SafetyStock"] }),
    group([null], 1),
  ];

  it("Grupla paneli: istek, grup satırı, sayı ve ara toplam; satırlar grup anahtarıyla", async () => {
    const user = userEvent.setup();
    await openTable({ groups });
    await user.click(screen.getByRole("button", { name: "Grupla" }));
    await user.selectOptions(screen.getByLabelText("Alan ekle"), "MaterialLevel");
    await waitFor(() => expect(calls.groups[0]).toEqual({ group_by: ["MaterialLevel"], fields: STANDARD_FIELDS, filters: [], sort: [] }));
    expect(screen.getByText("Malzeme seviyesi ile gruplu")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Grupla (1)" })).toBeInTheDocument();
    const rows = await screen.findAllByRole("row", { expanded: true });
    expect(rows[0]).toHaveTextContent("Hammadde· 2 satır");
    expect(within(rows[0]).getByText("1.234,500")).toBeInTheDocument();      // KG: 3 ondalık
    expect(within(rows[1]).getByLabelText("Birimler farklı; toplam yok")).toBeInTheDocument();
    expect(rows[2]).toHaveTextContent("(Boş)· 1 satır");
    expect(await screen.findByText("Hammadde-0")).toBeInTheDocument();
    expect(calls.queries.some((q) => JSON.stringify(q.group_key) === JSON.stringify([{ field: "MaterialLevel", value: "Hammadde" }]))).toBe(true);
    expect(calls.queries.some((q) => JSON.stringify(q.group_key) === JSON.stringify([{ field: "MaterialLevel", value: null }]))).toBe(true);
    expect(screen.getByLabelText("Kayıt sayısı (gösterilen / toplam)")).toHaveTextContent("6 / 50.000");
  });

  it("daralt ve aç: tıklama, Enter, Tümünü daralt / aç", async () => {
    const user = userEvent.setup();
    await openTable({ groups, views: { views: [savedView(3, "G", { columns: [{ field: "Code" }], group_by: ["MaterialLevel"] })], default_view_id: 3 } });
    await screen.findByText("Hammadde-0");
    const ham = screen.getAllByRole("row", { expanded: true })[0];
    await user.click(ham);
    expect(ham).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Hammadde-0")).toBeNull();
    ham.focus();
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Hammadde-0")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Tümünü daralt" }));
    expect(screen.queryAllByRole("row", { expanded: true })).toHaveLength(0);
    expect(screen.getAllByRole("row", { expanded: false })).toHaveLength(3);
    await user.click(screen.getByRole("button", { name: "Tümünü aç" }));
    expect(screen.getAllByRole("row", { expanded: true })).toHaveLength(3);
  });

  it("iki düzey ve ortalama (bir ondalık fazla); kolon menüsünden gruplama", async () => {
    const user = userEvent.setup();
    const tree = [group(["Hammadde"], 2, {
      aggregates: { ProductionLeadTimeDays: 2.7833 },
      children: [group(["Hammadde", "Çubuk"], 2, { aggregates: { ProductionLeadTimeDays: 3 } })],
    })];
    const view = savedView(4, "Süre", { columns: [{ field: "Code" }, { field: "ProductionLeadTimeDays" }] });
    await openTable({ groups: tree, views: { views: [view], default_view_id: 4 } });
    await user.click(screen.getByRole("button", { name: "Malzeme kodu kolon işlemleri" }));
    expect(screen.getByRole("menuitem", { name: "Bu alana göre grupla" })).toBeEnabled();
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Grupla" }));
    await user.selectOptions(screen.getByLabelText("Alan ekle"), "MaterialLevel");
    await user.selectOptions(screen.getByLabelText("Alan ekle"), "MaterialGroup");
    await waitFor(() => expect(calls.groups[calls.groups.length - 1].group_by).toEqual(["MaterialLevel", "MaterialGroup"]));
    const [top, sub] = await screen.findAllByRole("row", { expanded: true });
    expect(top).toHaveAttribute("aria-level", "1");
    expect(within(top).getByText("2,8")).toBeInTheDocument();
    expect(sub).toHaveAttribute("aria-level", "2");
    expect(within(sub).getByText("3,0")).toBeInTheDocument();
    expect(screen.getByText("Malzeme seviyesi › Malzeme grubu ile gruplu")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Malzeme seviyesi: Kaldır" }));
    await waitFor(() => expect(calls.groups[calls.groups.length - 1].group_by).toEqual(["MaterialGroup"]));
  });

  it("1.000 grup ve 100.000 satırda DOM sınırı; parçalar bir kez", async () => {
    const many = Array.from({ length: 1000 }, (_, i) => group([`G${String(i).padStart(4, "0")}`], 100));
    await openTable({ groups: many, views: { views: [savedView(2, "Çok", { columns: [{ field: "Code" }], group_by: ["MaterialGroup"] })], default_view_id: 2 } });
    await screen.findByText("G0000-0");
    const visible = Math.ceil(VIEW_PX / Math.round(13 * ROW_REM));
    expect(dataRows().length).toBeLessThanOrEqual(visible + 2 * 10);
    const scroller = screen.getByTestId("table-scroll");
    await act(async () => {
      scroller.scrollTop = 50_500 * Math.round(13 * ROW_REM);
      fireEvent.scroll(scroller);
    });
    expect((await screen.findAllByText(/^G0500-/)).length).toBeGreaterThan(0);
    expect(dataRows().length).toBeLessThanOrEqual(visible + 2 * 10);
    const keys = calls.queries.map((q) => `${JSON.stringify(q.group_key)}|${q.offset}`);
    expect(new Set(keys).size).toBe(keys.length);
    expect(calls.queries.length).toBeLessThan(10);
  });
});

describe("aktif filtre etiketleri (U-12)", () => {
  it("etiket metni her filtre tipinde", () => {
    const c = columnByField;
    expect(describeFilter({ field: "Name", op: "contains", value: "mil" }, c("Name"))).toBe("içerir 'mil'");
    expect(describeFilter({ field: "MaterialLevel", op: "in", values: ["Hammadde", "Yarı mamul", "Nihai ürün"] }, c("MaterialLevel")))
      .toBe("Hammadde, Yarı mamul +1");
    expect(describeFilter({ field: "MaterialGroup", op: "in", values: ["Çubuk"], empty: true }, c("MaterialGroup"))).toBe("Çubuk, boş");
    expect(describeFilter({ field: "IsSellable", op: "in", values: [true] }, c("IsSellable"))).toBe("Evet");
    expect(describeFilter({ field: "ProductionLeadTimeDays", op: "between", min: 10, max: 1000 }, c("ProductionLeadTimeDays"))).toBe("10–1.000");
    expect(describeFilter({ field: "ProductionLeadTimeDays", op: "between", min: 10 }, c("ProductionLeadTimeDays"))).toBe("≥ 10");
    expect(describeFilter({ field: "ProductionLeadTimeDays", op: "gt", value: 5 }, c("ProductionLeadTimeDays"))).toBe("> 5");
    expect(describeFilter({ field: "UpdatedAt", op: "between", from: "2026-10-27", to: "2026-11-03" }, c("UpdatedAt"))).toBe("27.10.2026–03.11.2026");
    expect(describeFilter({ field: "UpdatedAt", op: "between", from: "2026-10-27" }, c("UpdatedAt"))).toBe("27.10.2026 ve sonrası");
    expect(describeFilter({ field: "UpdatedAt", op: "relative", value: "next_4_weeks" }, c("UpdatedAt"))).toBe("sonraki 4 hafta");
    expect(describeFilter({ field: "Name", op: "empty" }, c("Name"))).toBe("boş");
  });

  it("sayacın yanında etiket; × kaldırır, etikete tıklayınca menü açılır", async () => {
    const user = userEvent.setup();
    await openTable();
    await user.click(screen.getByRole("button", { name: "Malzeme adı filtresi" }));
    await user.type(within(screen.getByRole("dialog", { name: "Malzeme adı filtresi" })).getByLabelText("Değer"), "mil{Enter}");
    const chips = screen.getByRole("list", { name: "Aktif filtreler" });
    expect(within(chips).getByRole("button", { name: "Malzeme adı: içerir 'mil'" })).toBeInTheDocument();
    await user.click(within(chips).getByRole("button", { name: "Malzeme adı: içerir 'mil'" }));
    expect(screen.getByRole("dialog", { name: "Malzeme adı filtresi" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    await user.click(within(chips).getByRole("button", { name: "Malzeme adı filtresini kaldır" }));
    await waitFor(() => expect(lastQuery().filters).toEqual([]));
    expect(screen.queryByRole("list", { name: "Aktif filtreler" })).toBeNull();
  });
});

describe("boş değer (U-13)", () => {
  const openFilter = async (user: ReturnType<typeof userEvent.setup>, label: string) => {
    await user.click(screen.getByRole("button", { name: `${label} filtresi` }));
    return screen.getByRole("dialog", { name: `${label} filtresi` });
  };

  it("metin, sayı ve tarihte 'boş'", async () => {
    const user = userEvent.setup();
    await openTable();
    let menu = await openFilter(user, "Malzeme adı");
    await user.selectOptions(within(menu).getByLabelText("Koşul"), "empty");
    expect(within(menu).queryByLabelText("Değer")).toBeNull();
    await user.click(within(menu).getByRole("button", { name: "Uygula" }));
    menu = await openFilter(user, "Güvenlik stoğu");
    await user.click(within(menu).getByRole("radio", { name: "Boş" }));
    await user.click(within(menu).getByRole("button", { name: "Uygula" }));
    menu = await openFilter(user, "Son değişiklik zamanı");
    await user.click(within(menu).getByRole("radio", { name: "Boş" }));
    await user.click(within(menu).getByRole("button", { name: "Uygula" }));
    await waitFor(() => expect(lastQuery().filters).toEqual([
      { field: "Name", op: "empty" }, { field: "SafetyStock", op: "empty" }, { field: "UpdatedAt", op: "empty" },
    ]));
  });

  it("listede '(Boş)' sayısıyla; değerle birlikte ya da yalnız", async () => {
    const user = userEvent.setup();
    await openTable();
    let menu = await openFilter(user, "Malzeme grubu");
    const empty = await within(menu).findByRole("checkbox", { name: "(Boş)" });
    expect(empty.closest(".sc-table-pop-option")).toHaveTextContent("4");
    await user.click(empty);
    await user.click(within(menu).getByRole("checkbox", { name: "Çubuk" }));
    await user.click(within(menu).getByRole("button", { name: "Uygula" }));
    await waitFor(() => expect(lastQuery().filters).toEqual([{ field: "MaterialGroup", op: "in", values: ["Çubuk"], empty: true }]));
    menu = await openFilter(user, "Malzeme seviyesi");
    await user.click(within(menu).getByRole("checkbox", { name: "(Boş)" }));
    await user.click(within(menu).getByRole("button", { name: "Uygula" }));
    await waitFor(() => expect(lastQuery().filters[1]).toEqual({ field: "MaterialLevel", op: "empty" }));
  });
});

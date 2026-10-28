// Görünüm (1.4, docs/12): kayıtlı görünüm (U-9, K-89), kolon düzeni (U-10), gruplama (U-11, K-90),
// aktif filtre etiketleri (U-12), boş değer (U-13).
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

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
    await waitFor(() => expect(calls.groups[0]).toEqual({ group_by: ["MaterialLevel"], fields: STANDARD_FIELDS,
                                                         aggregates: { SafetyStock: { fn: "sum" } }, filters: [], sort: [] }));
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

  it("satır tonları: 1. düzey ve alt düzey grup ayrı sınıf, veri satırı grup sınıfı taşımaz", async () => {
    const tree = [group(["Hammadde"], 2, { children: [group(["Hammadde", "Çubuk"], 2)] })];
    await openTable({ groups: tree, views: { views: [savedView(3, "G", { columns: [{ field: "Code" }], group_by: ["MaterialLevel", "MaterialGroup"] })], default_view_id: 3 } });
    const [top, sub] = await screen.findAllByRole("row", { expanded: true });
    expect(top).toHaveClass("sc-table-group", "sc-table-group--1");
    expect(sub).toHaveClass("sc-table-group", "sc-table-group--2");
    expect((await screen.findByText("Hammadde/Çubuk-0")).closest("tr")).not.toHaveClass("sc-table-group");
  });

  it("araç çubuğunda toplu daralt / aç; iki düzeyde '1. düzeye kadar aç'; Alt+tıklama bütün düzey", async () => {
    const user = userEvent.setup();
    const tree = [group(["Hammadde"], 2, { children: [group(["Hammadde", "Çubuk"], 1), group(["Hammadde", "Levha"], 1)] }),
                  group(["Yarı mamul"], 1, { children: [group(["Yarı mamul", "Alt montaj"], 1)] })];
    await openTable({ groups: tree, views: { views: [savedView(3, "G", { columns: [{ field: "Code" }], group_by: ["MaterialLevel"] })], default_view_id: 3 } });
    expect(await screen.findByRole("button", { name: "Tümünü daralt" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "1. düzeye kadar aç" })).toBeNull();  // tek düzey
    await user.click(screen.getByRole("button", { name: "Grupla (1)" }));
    await user.selectOptions(screen.getByLabelText("Alan ekle"), "MaterialGroup");
    await user.click(await screen.findByRole("button", { name: "1. düzeye kadar aç" }));
    const level = (n: number) => screen.getAllByRole("row").filter((r) => r.getAttribute("aria-level") === String(n));
    expect(level(1).map((r) => r.getAttribute("aria-expanded"))).toEqual(["true", "true"]);
    expect(level(2).map((r) => r.getAttribute("aria-expanded"))).toEqual(["false", "false", "false"]);
    await user.click(screen.getByRole("button", { name: "Tümünü aç" }));
    expect(level(2).every((r) => r.getAttribute("aria-expanded") === "true")).toBe(true);
    await user.keyboard("{Alt>}");
    await user.click(level(2)[0]);  // Alt+tıklama: 2. düzeyin hepsi kapanır
    await user.keyboard("{/Alt}");
    expect(level(2).map((r) => r.getAttribute("aria-expanded"))).toEqual(["false", "false", "false"]);
    expect(level(1).every((r) => r.getAttribute("aria-expanded") === "true")).toBe(true);
    level(1)[0].focus();
    await user.keyboard("{Alt>}{Enter}{/Alt}");  // Alt+Enter: 1. düzeyin hepsi kapanır
    expect(level(1).map((r) => r.getAttribute("aria-expanded"))).toEqual(["false", "false"]);
    await user.click(screen.getByRole("button", { name: "Grupla (2)" }));
    await user.click(screen.getByRole("button", { name: "Gruplamayı kaldır" }));
    expect(screen.queryByRole("button", { name: "Tümünü daralt" })).toBeNull();
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

describe("ara toplam türü (K-90)", () => {
  const view = savedView(4, "Süre", { columns: [{ field: "Code" }, { field: "SafetyStock" }, { field: "ProductionLeadTimeDays" }],
                                       group_by: ["MaterialLevel"] });
  const tree = [group(["Hammadde"], 4, { aggregates: { SafetyStock: 7, ProductionLeadTimeDays: 2.7833 },
                                        unit_decimals: { SafetyStock: 0 } })];
  const openMenu = async (user: ReturnType<typeof userEvent.setup>, label: string) => {
    await user.click(screen.getByRole("button", { name: `${label} kolon işlemleri` }));
    await user.click(screen.getByRole("menuitem", { name: /Ara toplam/ }));
    return screen.getByRole("group", { name: "Ara toplam" });
  };
  const lastGroups = () => calls.groups[calls.groups.length - 1];

  it("varsayılan liste tanımından; menüden her tür seçilir ve sunucuya gider", async () => {
    const user = userEvent.setup();
    await openTable({ groups: tree, views: { views: [view], default_view_id: 4 } });
    await waitFor(() => expect(lastGroups().aggregates).toEqual({ SafetyStock: { fn: "sum" }, ProductionLeadTimeDays: { fn: "avg" } }));
    let menu = await openMenu(user, "Güvenlik stoğu");
    expect(within(menu).getAllByRole("menuitemradio").map((b) => b.textContent)).toEqual([
      "Toplam", "Ortalama (boşlar hariç)", "Ortalama (sıfırlar hariç)", "Ağırlıklı ortalama…", "En küçük", "En büyük",
      "Sayı (dolu satır)", "Yok"]);
    expect(within(menu).getByRole("menuitemradio", { name: "Toplam" })).toHaveAttribute("aria-checked", "true");
    for (const [name, fn] of [["En büyük", "max"], ["En küçük", "min"], ["Ortalama (sıfırlar hariç)", "avg_nonzero"],
                              ["Sayı (dolu satır)", "count"]] as const) {
      menu = await openMenu(user, "Güvenlik stoğu");
      await user.click(within(menu).getByRole("menuitemradio", { name }));
      await waitFor(() => expect(lastGroups().aggregates.SafetyStock).toEqual({ fn }));
    }
    const row = (await screen.findAllByRole("row", { expanded: true }))[0];
    expect(within(row).getByTitle("Sayı (dolu satır)")).toHaveTextContent(/^n7$/);  // tür öneki "n", sayı ondalıksız
    menu = await openMenu(user, "Güvenlik stoğu");
    await user.click(within(menu).getByRole("menuitemradio", { name: "Yok" }));
    await waitFor(() => expect(lastGroups().aggregates).toEqual({ ProductionLeadTimeDays: { fn: "avg" } }));
  });

  it("ağırlıklı ortalama: ağırlık alanı seçilir; ortalama bir ondalık fazla; görünümle kaydedilir", async () => {
    const user = userEvent.setup();
    await openTable({ groups: tree, views: { views: [view], default_view_id: 4 } });
    const menu = await openMenu(user, "Üretim süresi (gün)");
    await user.click(within(menu).getByRole("menuitemradio", { name: "Ağırlıklı ortalama…" }));
    const weight = within(menu).getByLabelText("Ağırlık alanı");
    expect([...(weight as HTMLSelectElement).options].map((o) => o.textContent)).toEqual(["Alan seçin", "Güvenlik stoğu"]);
    await user.selectOptions(weight, "SafetyStock");
    await waitFor(() => expect(lastGroups().aggregates.ProductionLeadTimeDays).toEqual({ fn: "wavg", weight: "SafetyStock" }));
    const row = (await screen.findAllByRole("row", { expanded: true }))[0];
    expect(within(row).getByTitle("Ağırlıklı ortalama (ağırlık: Güvenlik stoğu)")).toHaveTextContent("2,8");
    expect(screen.getByRole("img", { name: "Kaydedilmemiş değişiklik" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect((lastViewCall("PUT")?.body as { definition: { aggregates: unknown } }).definition.aggregates)
      .toEqual({ ProductionLeadTimeDays: { fn: "wavg", weight: "SafetyStock" } }));
  });

  it("kayıtlı görünümdeki seçim açılışta uygulanır; metin alanında Ara toplam yok", async () => {
    const user = userEvent.setup();
    const saved = savedView(6, "Max", { ...view.definition, aggregates: { SafetyStock: { fn: "max" } } });
    await openTable({ groups: tree, views: { views: [saved], default_view_id: 6 } });
    await waitFor(() => expect(lastGroups().aggregates.SafetyStock).toEqual({ fn: "max" }));
    await user.click(screen.getByRole("button", { name: "Malzeme kodu kolon işlemleri" }));
    expect(screen.queryByRole("menuitem", { name: /Ara toplam/ })).toBeNull();
  });
});

describe("satır seçimi (K-85)", () => {
  it("veri satırına tıklayınca seçilir; başka satır seçilince seçim taşınır", async () => {
    const user = userEvent.setup();
    await openTable();
    const first = (await screen.findByText("M-0")).closest("tr")!;
    expect(first).toHaveClass("sc-table-row");
    await user.click(first);
    expect(first).toHaveClass("is-selected");
    expect(first).toHaveAttribute("aria-current", "true");
    const second = screen.getByText("M-1").closest("tr")!;
    await user.click(second);
    expect(second).toHaveClass("is-selected");
    expect(first).not.toHaveClass("is-selected");
  });
});

describe("açılır menülerin yerleşimi (docs/12, ui/popover)", () => {
  type R = { left: number; top: number; width: number; height: number };
  const rect = ({ left, top, width, height }: R) =>
    ({ left, top, width, height, right: left + width, bottom: top + height, x: left, y: top, toJSON: () => ({}) }) as DOMRect;
  /** jsdom ölçü vermez: açan öğelerin yeri ve menülerin boyu test içinde verilir (görünür alan 1024 × 768). */
  const mockRects = (place: (el: Element) => R | undefined) =>
    vi.spyOn(Element.prototype, "getBoundingClientRect").mockImplementation(function (this: Element) {
      return rect(place(this) ?? { left: 0, top: 0, width: 0, height: 0 });
    });
  const px = (el: Element) => ({ left: parseFloat((el as HTMLElement).style.left), top: parseFloat((el as HTMLElement).style.top) });

  it("en sağdaki kolonun menüsü ve 'Ara toplam' alt menüsü ekrandan taşmaz: sola açılır", async () => {
    const user = userEvent.setup();
    const view = savedView(4, "Sağ", { columns: [{ field: "Code" }, { field: "SafetyStock" }] });
    await openTable({ views: { views: [view], default_view_id: 4 } });
    mockRects((el) => {
      if (el.getAttribute("aria-label") === "Güvenlik stoğu kolon işlemleri") return { left: 1000, top: 40, width: 18, height: 28 };
      if (el.classList.contains("sc-popmenu-subpanel")) return { left: 0, top: 0, width: 220, height: 300 };
      if (el.classList.contains("sc-floating")) return { left: 0, top: 0, width: 200, height: 260 };
      if (el.getAttribute("aria-haspopup") === "menu" && el.getAttribute("role") === "menuitem") {
        return { left: 818, top: 180, width: 198, height: 28 };
      }
    });
    await user.click(screen.getByRole("button", { name: "Güvenlik stoğu kolon işlemleri" }));
    const menu = screen.getByRole("menu", { name: "Güvenlik stoğu kolon işlemleri" }).closest(".sc-floating")!;
    expect(px(menu)).toEqual({ left: 1024 - 8 - 200, top: 72 });  // sola açılır; ekran kenarından 8 px içeride
    await user.click(screen.getByRole("menuitem", { name: /Ara toplam/ }));
    const sub = screen.getByRole("group", { name: "Ara toplam" });
    expect(sub).toHaveClass("sc-floating");
    expect(px(sub)).toEqual({ left: 818 - 220, top: 180 });  // sağda yer yok: ana menünün soluna
  });

  it("alta yakın açan öğede menü yukarı açılır; alt menü alttan taşmaz", async () => {
    const user = userEvent.setup();
    const view = savedView(4, "Alt", { columns: [{ field: "Code" }, { field: "SafetyStock" }] });
    await openTable({ views: { views: [view], default_view_id: 4 } });
    mockRects((el) => {
      if (el.tagName === "BUTTON" && el.getAttribute("aria-label") === "Malzeme kodu filtresi") {
        return { left: 100, top: 700, width: 18, height: 28 };
      }
      if (el.getAttribute("aria-label") === "Güvenlik stoğu kolon işlemleri") return { left: 300, top: 700, width: 18, height: 28 };
      if (el.classList.contains("sc-popmenu-subpanel")) return { left: 0, top: 0, width: 220, height: 300 };
      if (el.classList.contains("sc-floating")) return { left: 0, top: 0, width: 260, height: 260 };
      if (el.getAttribute("aria-haspopup") === "menu" && el.getAttribute("role") === "menuitem") {
        return { left: 300, top: 600, width: 200, height: 28 };
      }
    });
    await user.click(screen.getByRole("button", { name: "Malzeme kodu filtresi" }));
    expect(px(screen.getByRole("dialog", { name: "Malzeme kodu filtresi" }))).toEqual({ left: 100, top: 700 - 4 - 260 });
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Güvenlik stoğu kolon işlemleri" }));
    await user.click(screen.getByRole("menuitem", { name: /Ara toplam/ }));
    expect(px(screen.getByRole("group", { name: "Ara toplam" }))).toEqual({ left: 500, top: 768 - 8 - 300 });
  });

  it("Alanlar, Grupla ve görünüm menüsü de aynı yardımcıyla görünür alana sığar", async () => {
    const user = userEvent.setup();
    await openTable({ views: { views: [savedView(5, "Benim", {})], default_view_id: 5 } });
    mockRects((el) => {
      const label = el.textContent ?? "";
      if (el.tagName === "BUTTON" && label.startsWith("Alanlar")) return { left: 960, top: 10, width: 60, height: 30 };
      if (el.tagName === "BUTTON" && label.startsWith("Grupla")) return { left: 880, top: 10, width: 70, height: 30 };
      if (el.tagName === "BUTTON" && el.getAttribute("aria-label") === "Görünüm işlemleri") return { left: 1000, top: 10, width: 20, height: 20 };
      if (el.classList.contains("sc-floating")) return { left: 0, top: 0, width: 300, height: 200 };
    });
    await user.click(screen.getByRole("button", { name: /^Alanlar/ }));
    expect(px(screen.getByRole("dialog", { name: /^Alanlar/ }))).toEqual({ left: 1024 - 8 - 300, top: 44 });
    await user.click(screen.getByRole("button", { name: /^Grupla/ }));
    expect(px(screen.getByRole("dialog", { name: "Gruplama" }))).toEqual({ left: 950 - 300, top: 44 });
    await user.click(screen.getByRole("button", { name: "Görünüm işlemleri" }));
    expect(px(screen.getByRole("menu", { name: "Görünüm işlemleri" }))).toEqual({ left: 1024 - 8 - 300, top: 34 });
  });
});

describe("tablo ayrıntıları (docs/12)", () => {
  const two = [group(["Hammadde"], 2, { children: [group(["Hammadde", "Çubuk"], 2)] })];
  const twoLevels = savedView(3, "G", { columns: [{ field: "Code" }, { field: "SafetyStock" }], group_by: ["MaterialLevel", "MaterialGroup"] });

  it("gruplu görünümde veri satırının ilk hücresi en alt grubun adıyla aynı hizada", async () => {
    await openTable({ groups: two, views: { views: [twoLevels], default_view_id: 3 } });
    const cell = (await screen.findByText("Hammadde/Çubuk-0")).closest("td")!;
    expect(cell.style.paddingLeft).toBe("calc(var(--space-2) + 2.5385rem)");  // 1 düzey girinti + ok
    const [, sub] = screen.getAllByRole("row", { expanded: true });
    expect((sub.querySelector(".sc-tgroup-head") as HTMLElement).style.paddingLeft).toBe("1.2308rem");
    expect(within(dataRows()[2] as HTMLElement).getAllByRole("cell")[1].style.paddingLeft).toBe("");  // yalnız ilk hücre
  });

  it("başlık ikonları ayrı kapta; aktif filtre işaretli; düğmeler klavyeyle ulaşılır", async () => {
    const user = userEvent.setup();
    await openTable();
    const tools = header("Malzeme adı").querySelector(".sc-table-head-tools")!;
    expect(within(tools as HTMLElement).getAllByRole("button")).toHaveLength(2);
    expect(tools).not.toHaveClass("has-filter");
    await user.click(screen.getByRole("button", { name: "Malzeme adı filtresi" }));
    await user.type(within(screen.getByRole("dialog", { name: "Malzeme adı filtresi" })).getByLabelText("Değer"), "mil{Enter}");
    expect(tools).toHaveClass("has-filter");
    expect(screen.getByRole("button", { name: "Malzeme adı filtresi" })).toHaveClass("is-active");
    sortButton("Malzeme adı").focus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Malzeme adı filtresi" })).toHaveFocus();
  });

  it("ara toplamın önünde tür kısaltması", async () => {
    const user = userEvent.setup();
    const tree = [group(["Hammadde"], 4, { aggregates: { SafetyStock: 7 }, unit_decimals: { SafetyStock: 0 } })];
    const view = savedView(4, "S", { columns: [{ field: "Code" }, { field: "SafetyStock" }], group_by: ["MaterialLevel"] });
    await openTable({ groups: tree, views: { views: [view], default_view_id: 4 } });
    const fnOf = async () => (await screen.findAllByRole("row", { expanded: true }))[0].querySelector(".sc-agg-fn")?.textContent;
    expect(await fnOf()).toBe("Σ");
    for (const [name, short] of [["Ortalama (boşlar hariç)", "ort."], ["Ortalama (sıfırlar hariç)", "ort."], ["En küçük", "en az"],
                                 ["En büyük", "en çok"], ["Sayı (dolu satır)", "n"]] as const) {
      await user.click(screen.getByRole("button", { name: "Güvenlik stoğu kolon işlemleri" }));
      await user.click(screen.getByRole("menuitem", { name: /Ara toplam/ }));
      await user.click(within(screen.getByRole("group", { name: "Ara toplam" })).getByRole("menuitemradio", { name }));
      await waitFor(async () => expect(await fnOf()).toBe(short));
    }
  });

  it("toplu daralt / aç: Grupla'nın yanında ikonlu düğme grubu, adları ipucunda", async () => {
    await openTable({ groups: two, views: { views: [twoLevels], default_view_id: 3 } });
    const toggles = await screen.findByRole("group", { name: "Grupları daralt ve aç" });
    expect(within(toggles).getAllByRole("button").map((b) => b.getAttribute("title")))
      .toEqual(["Tümünü daralt", "Tümünü aç", "1. düzeye kadar aç"]);
    expect(toggles.previousElementSibling).toHaveTextContent("Grupla (2)");
  });

  it("kaydedilmemiş değişiklikte • ve soluk 'Kaydedilmedi'", async () => {
    const user = userEvent.setup();
    await openTable();
    expect(screen.queryByText("Kaydedilmedi")).toBeNull();
    await user.click(sortButton("Malzeme adı"));
    expect(screen.getByText("Kaydedilmedi")).toHaveClass("sc-muted");
    expect(screen.getByRole("img", { name: "Kaydedilmemiş değişiklik" })).toBeInTheDocument();
  });
});

describe("araç çubuğu düzeni (U-22, docs/12)", () => {
  const root = () => document.querySelector(".sc-table")!;
  const status = () => document.querySelector(".sc-table-status");
  const toolbarEl = () => root().querySelector(":scope > .sc-table-toolbar")!;

  it("araç çubuğu (görünüm, sayaç | Grupla, Alanlar) tablonun hemen üstünde, çerçevenin dışında; filtre ya da gruplama yoksa ikinci satır yok", async () => {
    await openTable();
    const toolbar = toolbarEl();
    expect(toolbar.nextElementSibling).toHaveAttribute("data-testid", "table-scroll");
    const main = toolbar.querySelector(".sc-table-toolbar-main")!;
    expect(within(main as HTMLElement).getByRole("combobox", { name: "Görünüm" })).toBeInTheDocument();
    expect(within(main as HTMLElement).getByLabelText("Kayıt sayısı (gösterilen / toplam)")).toHaveTextContent("1.234 / 50.000");
    const tools = toolbar.querySelector(".sc-table-tools")!;
    expect(within(tools as HTMLElement).getAllByRole("button").map((b) => b.textContent)).toEqual(["Grupla", "Alanlar (7/9)"]);
    expect(status()).toBeNull();
  });

  it("filtre ya da gruplama varken araç çubuğunun altında tek satır; kalkınca satır da kalkar", async () => {
    const user = userEvent.setup();
    await openTable({ groups: [group(["Hammadde"], 2)] });
    await user.click(screen.getByRole("button", { name: "Malzeme adı filtresi" }));
    await user.type(within(screen.getByRole("dialog", { name: "Malzeme adı filtresi" })).getByLabelText("Değer"), "mil{Enter}");
    expect(status()).toBe(toolbarEl().nextElementSibling);
    expect(status()!.nextElementSibling).toHaveAttribute("data-testid", "table-scroll");
    expect(within(status() as HTMLElement).getByRole("list", { name: "Aktif filtreler" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Filtreleri temizle" }));
    await waitFor(() => expect(status()).toBeNull());
    await user.click(screen.getByRole("button", { name: "Grupla" }));
    await user.selectOptions(screen.getByLabelText("Alan ekle"), "MaterialLevel");
    expect(await within(root() as HTMLElement).findByText("Malzeme seviyesi ile gruplu")).toBeInTheDocument();
    expect(status()).not.toBeNull();
  });

  it("sıralama varken 'Sıralamayı temizle' araç çubuğunda ikon", async () => {
    const user = userEvent.setup();
    await openTable();
    await user.click(sortButton("Malzeme kodu"));
    const clear = screen.getByRole("button", { name: "Sıralamayı temizle" });
    expect(clear.closest(".sc-table-toolbar-main")).not.toBeNull();
    expect(clear).toHaveAttribute("title", "Sıralamayı temizle");
    expect(status()).toBeNull();
  });
});

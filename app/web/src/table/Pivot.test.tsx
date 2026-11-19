// Pivot (K-183, docs/12 "Pivot standardı"): ⚙ › Pivot görünümü, ayar paneli (satır, sütun, değer, değerlerin yeri, toplamlar, sıralama),
// katlı başlık ve satır başlıkları, boş ve karışık birim hücresi, başlıktan süzme, ilişkili alanın panelden seçilmesi, görünümle saklama,
// sınır ve hata durumları, parça parça yükleme.
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { meAs, mockApi, renderApp, type Reply } from "../test/helpers";
import { ApiError } from "../api/client";
import { groupStarts, headerCells, reasonOf } from "./PivotGrid";
import {
  defaultFn, dropOrphans, emptyPivot, fitPivot, pivotExportRequest, fnLabel, fnsFor, formatPivotCell, normalizePivot, type PivotColumn, type PivotConfig, type PivotData, pivotReady, pivotRequest, type PivotRequest,
  type PivotValueInfo, valueDisplay, valueLabel, valueName,
} from "./pivotModel";
import { col, useTableTestSetup } from "./testBackend";
import type { ListColumn } from "./types";

useTableTestSetup();

const LIST = "/api/transaction-sales-order";
const COLUMNS = [
  col("OrderNo", "Sipariş no", "text", "text"), col("CustomerCode", "Müşteri", "text", "list", { values_from_server: true }), col("MaterialCode", "Malzeme", "text", "list"),
  col("RequestedDate", "İstek tarihi", "date", "date"), col("OpenQuantity", "Açık miktar", "number", "number", { decimals_from_unit: true }),
  col("OrderedQuantity", "Sipariş miktarı", "number", "number", { decimals_from_unit: true }), col("Price", "Fiyat", "number", "number", { decimals: 2, aggregate: "wavg", aggregate_weight: "OpenQuantity" }),
  col("ManualState", "Manuel değer", "text", "list", { pivot: false }), col("UpdatedAt", "Son değişiklik zamanı", "datetime", "date", { pivot: false }),
];
const GROUP: ListColumn = col("MaterialId/MaterialGroup", "Malzeme · Malzeme grubu", "text", "list", { default_visible: false, related: true });
const byField = new Map([...COLUMNS, GROUP].map((c) => [c.field, c]));
const info = (id: string, fn: PivotValueInfo["fn"], field: string | null, extra: Partial<PivotValueInfo> = {}): PivotValueInfo =>
  ({ id, fn, field, weight: null, decimals: 2, percent: false, from_unit: false, ...extra });

/** Sahte sunucu: iki müşteri × iki ay; istenen toplamlara göre satır ve sütunlar. */
function data(req: PivotRequest): PivotData {
  const months = req.columns.length ? ["2026-11-01", "2026-12-01"] : [];
  const columns: PivotColumn[] = req.columns.length
    ? [...months.map((m) => ({ key: [m], level: 1, total: false })), ...(req.totals.columns ? [{ key: [], level: 0, total: true }] : [])]
    : [{ key: [], level: 0, total: false }];
  const cells = (base: number) => req.values.map((_, k) => columns.map((c, s) => (c.total ? base * 2 + k : s === 1 && base === 10 ? null : base + s + k)));
  const all = [
    { key: ["MUS-A", "MAM-001"], level: 2, total: false, cells: cells(10) },
    { key: ["MUS-A", "MAM-002"], level: 2, total: false, cells: req.values.map(() => columns.map(() => ({ mixed: true as const }))) },
    ...(req.totals.subtotals ? [{ key: ["MUS-A"], level: 1, total: true, cells: cells(30) }] : []),
    { key: ["MUS-B", "MAM-001"], level: 2, total: false, cells: req.values.map(() => columns.map(() => ({ v: 1.5, d: 3 }))) },
    ...(req.totals.subtotals ? [{ key: ["MUS-B"], level: 1, total: true, cells: cells(40) }] : []),
    ...(req.totals.rows ? [{ key: [], level: 0, total: true, cells: cells(70) }] : []),
  ].map((r) => (req.rows.length === 1 ? { ...r, key: r.key.slice(0, 1), level: Math.min(r.level, 1) } : r))
    // kuralı olan değerde: ilk satırın ilk sütunu kuralı tutar; toplam satırları yalnız "Toplamlara da uygula" açıksa
    .map((r, i) => {
      const formats = Object.fromEntries(req.values.flatMap((v, k) => (v.rules?.length && (i === 0 || (r.total && v.rules_on_totals)) ? [[String(k), columns.map((_, s) => (s === 0 ? 0 : null))]] : [])));
      return Object.keys(formats).length ? { ...r, formats } : r;
    });
  return {
    row_fields: req.rows.map((a) => ({ field: a.field, type: "text", bucket: null })),
    column_fields: req.columns.map((a) => ({ field: a.field, type: "date", bucket: a.bucket ?? null })),
    columns, values: req.values.map((v) => info(v.id, v.kind === "calc" ? "calc" : v.fn ?? "sum", v.field ?? null, { decimals: v.fn === "count" || v.fn === "distinct" ? 0 : 2, weight: v.weight ?? null })),
    rows: all.slice(req.offset, req.offset + req.limit), offset: req.offset, row_count: all.length, week_start: "Pazartesi",
  };
}

const PIVOT: PivotConfig = {
  ...emptyPivot(), rows: [{ field: "CustomerCode" }, { field: "MaterialCode" }], columns: [{ field: "RequestedDate", bucket: "month" }],
  values: [{ id: "d1", field: "OpenQuantity", fn: "sum" }, { id: "d2", field: "OrderNo", fn: "distinct" }],
};
const viewWith = (pivot: PivotConfig | null, extra: object = {}) => ({
  views: [{ id: 5, name: "Pivot", owner_user_id: 1, owner_name: "x", is_shared: false, is_owner: true, updated_at: "2026-11-19T10:00:00+00:00", warnings: [],
            definition: { v: 1, columns: [{ field: "OrderNo" }, { field: "CustomerCode" }], pinned: 0, sort: [], filters: [], group_by: [], ...(pivot ? { pivot } : {}) } }],
  default_view_id: 5, ...extra,
});

function backend(views: object = { views: [], default_view_id: null }, reply?: (req: PivotRequest) => Reply) {
  const pivots: PivotRequest[] = [];
  const saved: { definition: { pivot?: PivotConfig } }[] = [];
  const exports: Record<string, unknown>[] = [];
  mockApi({
    "/api/transaction-data/counts": { body: { data_version: 35, tabs: [] } },
    [`${LIST}/columns`]: { body: { chunk_size: 100, columns: COLUMNS, relations: [{ path: "MaterialId", label: "Malzeme" }],
                                   export: { title: "Satış siparişi", file_slug: "satis-siparisi", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    [`${LIST}/related`]: { body: { path: "MaterialId", label: "Malzeme", fields: [GROUP], relations: [] } },
    [`${LIST}/views`]: (_url, init) => {
      if (init?.method === "POST" || init?.method === "PUT") {
        const body = JSON.parse(String(init.body));
        saved.push(body);
        return { status: init.method === "POST" ? 201 : 200, body: { ...(views as { views: object[] }).views?.[0], id: 9, name: body.name ?? "Pivot", definition: body.definition, warnings: [] } };
      }
      return { body: views };
    },
    [`${LIST}/values`]: { body: [{ value: "MUS-A", count: 2 }, { value: "MUS-B", count: 1 }] },
    [`${LIST}/query`]: { body: { rows: [{ Id: 1, OrderNo: "SO-1", CustomerCode: "MUS-A" }], filtered: 1, total: 1 } },
    [`${LIST}/pivot/export`]: (_url, init) => {
      exports.push(JSON.parse(String(init?.body)));
      return { body: "xlsx", headers: { "Content-Disposition": "attachment; filename*=UTF-8''satis-siparisi_pivot.xlsx" } };
    },
    [`${LIST}/pivot`]: (_url, init) => {
      const req = JSON.parse(String(init?.body)) as PivotRequest;
      pivots.push(req);
      return reply ? reply(req) : { body: data(req) };
    },
  });
  return { pivots, saved, exports, last: () => pivots[pivots.length - 1] };
}

async function open(views?: object, reply?: (req: PivotRequest) => Reply) {
  const user = userEvent.setup();
  const calls = backend(views, reply);
  renderApp("/veri/islem-verisi?sekme=talep&tablo=satis-siparisi", meAs("Key user"));
  await screen.findByRole("button", { name: /^Tablo ayarları/ }, { timeout: 5000 });
  return { user, ...calls };
}

const grid = () => screen.getByRole("table", { name: "Pivot" });
const panel = () => screen.getByRole("complementary", { name: "Pivot ayarları" });
const menuItem = async (user: ReturnType<typeof userEvent.setup>, name: string) => {
  await user.click(screen.getByRole("button", { name: /^Tablo ayarları/ }));
  await user.click(within(screen.getByRole("menu")).getByText(name));
};
/** Kurulmuş pivotta panel bölümleri kapalı gelir; testin dokunacağı bölümler açılır (Sıralama'yı testler kendisi açar). */
const openSections = async (user: ReturnType<typeof userEvent.setup>, names = ["Satırlar", "Sütunlar", "Değerler", "Değerlerin yeri", "Toplamlar"]) => {
  for (const name of names) {
    const head = within(panel()).getByRole("button", { name: new RegExp(`^${name}\\d*$`) });
    if (head.getAttribute("aria-expanded") === "false") await user.click(head);
  }
};
const bodyRows = () => within(grid()).getAllByRole("row").filter((r) => r.hasAttribute("aria-rowindex"))
  .map((r) => [...r.querySelectorAll("th, td")].map((c) => c.textContent ?? ""));

describe("pivot modeli", () => {
  it("etiket, hazır olma, istek ve uyarlama", () => {
    expect(valueLabel({ field: "OpenQuantity", fn: "sum" }, byField)).toBe("Açık miktar · Toplam");
    expect(valueLabel({ field: "Price", fn: "wavg", weight: "OpenQuantity" }, byField)).toBe("Fiyat · Ağırlıklı ortalama (Açık miktar)");
    expect(valueLabel({ field: null, fn: "count" }, byField)).toBe("Say");
    expect(pivotReady(emptyPivot())).toBe(false);
    expect(pivotReady({ ...PIVOT, values: [{ id: "d1", field: "Price", fn: "wavg" }] })).toBe(false);   // ağırlık seçilmeden çizilmez
    expect(pivotReady(PIVOT)).toBe(true);
    const req = pivotRequest({ ...PIVOT, values_on: "rows", values: [{ id: "d1", field: "OpenQuantity", fn: "sum", decimals: 1 }, { id: "d2", fn: "count", field: "x" }] }, [], null, 3, 0, 100);
    expect(req.values).toEqual([{ id: "d1", fn: "sum", field: "OpenQuantity" }, { id: "d2", fn: "count" }]);   // gösterim ayarı isteğe girmez
    expect("values_on" in req || "scenario_id" in req).toBe(false);
    expect(pivotRequest({ ...PIVOT, columns: [{ field: "RequestedDate", bucket: "week" }] }, [], null, 3, 0, 100).scenario_id).toBe(3);
    const fitted = fitPivot({ ...PIVOT, rows: [{ field: "CustomerCode" }, { field: "Gone" }], sort: { by: "d2", dir: "desc" },
                              values: [{ id: "d1", field: "OpenQuantity", fn: "sum" }, { id: "d2", field: "Gone", fn: "distinct" }] }, COLUMNS)!;
    expect([fitted.rows.length, fitted.values.map((v) => v.id), fitted.sort]).toEqual([1, ["d1"], { by: "name", dir: "asc" }]);
    expect(normalizePivot({ rows: [{ field: "A" }] })).toMatchObject({ open: true, values_on: "columns", totals: { rows: false, columns: false, subtotals: false } });
    expect(normalizePivot(null)).toBeNull();
  });

  it("hücre biçimi: boş boş kalır, 0 yazılır, karışık birim çizgi, ortalamada bir ondalık fazla, yüzde", () => {
    expect(formatPivotCell(null, info("a", "sum", "x"), null)).toBe("");
    expect(formatPivotCell(0, info("a", "sum", "x", { decimals: 0 }), null)).toBe("0");
    expect(formatPivotCell({ mixed: true }, info("a", "sum", "x"), null)).toBe("—");
    expect(formatPivotCell({ v: 12, d: 0 }, info("a", "sum", "x", { from_unit: true }), null)).toBe("12");
    expect(formatPivotCell({ v: 12.25, d: 0 }, info("a", "avg", "x", { from_unit: true }), null)).toBe("12,3");
    expect(formatPivotCell(0.6, info("a", "wavg", "x", { percent: true }), null)).toBe("%60,000");
    expect(formatPivotCell(1234.5, info("a", "sum", "x"), 1)).toBe("1.234,5");
  });

  it("tarih alanında En erken · En geç; metinde yalnız Say ve Benzersiz say; hücre tarih biçiminde", () => {
    const date = byField.get("RequestedDate")!;
    expect(fnsFor(date).map((fn) => fnLabel(fn, date))).toEqual(["En erken", "En geç", "Say", "Benzersiz say"]);
    expect(fnsFor(byField.get("OrderNo")).map((fn) => fnLabel(fn, byField.get("OrderNo")))).toEqual(["Say", "Benzersiz say"]);
    expect(fnsFor(byField.get("Price")).map((fn) => fnLabel(fn, byField.get("Price"))))
      .toEqual(["Toplam", "Ortalama", "En düşük", "En yüksek", "Say", "Benzersiz say", "Ağırlıklı ortalama"]);
    expect([defaultFn(date), defaultFn(byField.get("OrderNo")!), defaultFn(byField.get("Price")!)]).toEqual(["min", "distinct", "wavg"]);
    expect(valueLabel({ field: "RequestedDate", fn: "min" }, byField)).toBe("İstek tarihi · En erken");
    expect(valueLabel({ field: "RequestedDate", fn: "max" }, byField)).toBe("İstek tarihi · En geç");
    expect(formatPivotCell("2026-11-17", info("a", "min", "RequestedDate", { type: "date" }), null)).toBe("17.11.2026");
  });

  it("katlı başlık: aynı üst değer birleşir; ara toplam kendi katında başlar, alta uzanır", () => {
    const cols: PivotColumn[] = [
      { key: ["2026-10-01", "A"], level: 2, total: false }, { key: ["2026-10-01", "B"], level: 2, total: false }, { key: ["2026-10-01"], level: 1, total: true },
      { key: ["2027-01-01", null], level: 2, total: false, empty: true }, { key: [], level: 0, total: true },
    ];
    const fields = [{ field: "RequestedDate", type: "date" as const, bucket: "quarter" as const }, { field: "Type", type: "text" as const, bucket: null }];
    expect(headerCells(cols, 0, 2, 2, fields).map((h) => [h.label, h.colSpan, h.rowSpan])).toEqual([["Ç4 2026", 6, 1], ["Ç1 2027", 2, 1], ["Toplam", 2, 2]]);
    expect(headerCells(cols, 1, 2, 2, fields).map((h) => [h.label, h.colSpan, h.rowSpan])).toEqual([["A", 2, 1], ["B", 2, 1], ["Toplam", 2, 1], ["", 2, 1]]);
    // dikey ayraç: en dıştaki grubun ilk sütununda ve sağdaki Toplam grubunda; grubun kendi ara toplamında yok
    expect(groupStarts(cols)).toEqual([false, false, false, true, true]);
    expect(headerCells(cols, 0, 2, 2, fields).map((h) => h.start)).toEqual([false, true, true]);
  });

  it("değerin gösterimi: iki satır; özel ad verilince o ad; sunucunun reddinde neden yazılır", () => {
    expect(valueDisplay({ field: "OpenQuantity", fn: "sum" }, byField)).toEqual({ top: "Açık miktar", bottom: "Toplam", full: "Açık miktar · Toplam" });
    expect(valueDisplay({ field: null, fn: "count" }, byField)).toEqual({ top: "Say", bottom: null, full: "Say" });
    expect(valueDisplay({ field: "OrderNo", fn: "distinct", name: " Sipariş sayısı " }, byField))
      .toEqual({ top: "Sipariş sayısı", bottom: null, full: "Sipariş no · Benzersiz say" });
    expect([valueName({ field: "OrderNo", fn: "distinct", name: "Sipariş sayısı" }, byField), valueName({ field: "OrderNo", fn: "distinct" }, byField)])
      .toEqual(["Sipariş sayısı", "Sipariş no · Benzersiz say"]);
    expect(normalizePivot({ values: [{ id: "d1", fn: "count", name: "  " }] })!.values[0].name).toBeNull();
    const rejected = new ApiError(422, "validation", "Girilen bilgiler geçersiz.", [{ field: "values.2.fn", problem: "Bu hesaplama yalnız sayı alanında: İstek tarihi" }]);
    expect(reasonOf(rejected)).toBe("Bu hesaplama yalnız sayı alanında: İstek tarihi");
    expect(reasonOf(new ApiError(422, "pivot_too_large", "Sütun sayısı çok fazla"))).toBe("Sütun sayısı çok fazla");
  });
});

describe("pivot görünümü (K-183)", () => {
  it("⚙ menüsünden açılır; panel açık gelir; Grupla ve Alanlar kapalıdır; alan ve değer eklenince pivot çizilir", async () => {
    const { user, pivots, last } = await open();
    await menuItem(user, "Pivot görünümü");
    expect(panel()).toBeInTheDocument();
    expect(screen.getByText("Satır alanı ve değer seçin")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Grupla/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^Alanlar \(/ })).toBeDisabled();
    expect(pivots).toHaveLength(0);                                             // satır alanı ve değer seçilmeden istek yok
    const rows = within(panel()).getByRole("button", { name: /^Satırlar/ }).closest("section")!;
    await user.click(within(rows).getByRole("button", { name: "Alan ekle" }));
    expect(within(rows).queryByRole("button", { name: "Açık miktar" })).toBeNull();   // ondalıklı sayı satır olamaz
    await user.click(within(rows).getByRole("button", { name: "Müşteri" }));
    const values = within(panel()).getByRole("button", { name: /^Değerler\s*\d*$/ }).closest("section")!;
    await user.click(within(values).getByRole("button", { name: "Değer ekle" }));
    await user.click(within(values).getByRole("button", { name: "Açık miktar" }));
    await waitFor(() => expect(last()).toMatchObject({ rows: [{ field: "CustomerCode" }], columns: [], values: [{ id: "d1", field: "OpenQuantity", fn: "sum" }], offset: 0, limit: 100 }));
    await within(grid()).findByText("MUS-A");
    expect(within(grid()).getByRole("columnheader", { name: "Açık miktar · Toplam" })).toBeInTheDocument();
    // sütuna tarih alanı: dönem tipi seçilir (varsayılan Ay)
    const columns = within(panel()).getByRole("button", { name: /^Sütunlar/ }).closest("section")!;
    await user.click(within(columns).getByRole("button", { name: "Alan ekle" }));
    await user.click(within(columns).getByRole("button", { name: "İstek tarihi" }));
    await waitFor(() => expect(last().columns).toEqual([{ field: "RequestedDate", bucket: "month" }]));
    await user.selectOptions(within(columns).getByRole("combobox", { name: "İstek tarihi: dönem tipi" }), "Çeyrek");
    await waitFor(() => expect(last().columns).toEqual([{ field: "RequestedDate", bucket: "quarter" }]));
    // pivot kapanınca tablo geri gelir
    await menuItem(user, "Pivot görünümü");
    expect(screen.queryByRole("table", { name: "Pivot" })).toBeNull();
    expect(screen.getByRole("button", { name: /^Grupla/ })).toBeEnabled();
  });

  it("seçicide tablonun kendi alanları listelenir; değer çipinde alan ve hesaplama iki satırdır; tarihte En erken", async () => {
    const { user, last } = await open();
    await menuItem(user, "Pivot görünümü");
    const rows = within(panel()).getByRole("button", { name: /^Satırlar/ }).closest("section")!;
    await user.click(within(rows).getByRole("button", { name: "Alan ekle" }));
    const picker = within(rows).getByRole("group", { name: "Alan ekle" });
    expect(within(picker).getAllByRole("button").map((b) => b.textContent).slice(0, 4)).toEqual(["Sipariş no", "Müşteri", "Malzeme", "İstek tarihi"]);
    expect(within(picker).getAllByRole("button").slice(0, 4).every((b) => b.classList.contains("sc-table-pick"))).toBe(true);
    for (const name of ["Manuel değer", "Son değişiklik zamanı"]) expect(within(picker).queryByRole("button", { name })).toBeNull();   // hiçbir seçicide
    await user.click(within(picker).getByRole("button", { name: "Müşteri" }));
    const values = within(panel()).getByRole("button", { name: /^Değerler\s*\d*$/ }).closest("section")!;
    await user.click(within(values).getByRole("button", { name: "Değer ekle" }));
    const valueNames = within(within(values).getByRole("group", { name: "Değer ekle" })).getAllByRole("button").map((b) => b.textContent);
    expect(valueNames).toEqual(expect.arrayContaining(["Sipariş no", "İstek tarihi", "Açık miktar", "Fiyat"]));
    expect(valueNames).not.toEqual(expect.arrayContaining(["Manuel değer"]));
    expect(valueNames).not.toEqual(expect.arrayContaining(["Son değişiklik zamanı"]));
    await user.click(within(values).getByRole("button", { name: "İstek tarihi" }));
    await waitFor(() => expect(last().values).toEqual([{ id: "d1", fn: "min", field: "RequestedDate" }]));
    const chip = within(values).getByRole("button", { name: "İstek tarihi · En erken" });
    expect([...chip.querySelectorAll("span")].map((x) => x.textContent)).toEqual(["İstek tarihi", "En erken"]);   // hesaplama kendi satırında
    await user.click(chip);
    expect(within(within(values).getByRole("combobox", { name: "Hesaplama" })).getAllByRole("option").map((o) => o.textContent))
      .toEqual(["En erken", "En geç", "Say", "Benzersiz say"]);
    // aynı alan sütunda da kullanılır (değerde kullanılmış olması engel değil)
    const columns = within(panel()).getByRole("button", { name: /^Sütunlar/ }).closest("section")!;
    await user.click(within(columns).getByRole("button", { name: "Alan ekle" }));
    await user.click(within(columns).getByRole("button", { name: "İstek tarihi" }));
    await waitFor(() => expect(last()).toMatchObject({ columns: [{ field: "RequestedDate", bucket: "month" }], values: [{ id: "d1", fn: "min", field: "RequestedDate" }] }));
    // değere özel ad: başlıkta, çipte ve sıralama listesinde
    await user.type(within(values).getByRole("textbox", { name: "Ad" }), "İlk sipariş");
    expect(await within(values).findByRole("button", { name: "İlk sipariş" })).toHaveAttribute("title", "İstek tarihi · En erken");
    expect((await within(grid()).findAllByRole("columnheader", { name: "İlk sipariş" })).length).toBeGreaterThan(0);
    await user.click(within(panel()).getByRole("button", { name: /^Sıralama/ }));
    expect(within(within(panel()).getByRole("combobox", { name: "Sırala" })).getAllByRole("option").map((o) => o.textContent)).toEqual(["Ada göre", "İlk sipariş"]);
  });

  it("alanlar ve değerler sürüklenerek sıralanır", async () => {
    const { user, last } = await open(viewWith(PIVOT));
    await within(await screen.findByRole("table", { name: "Pivot" }, { timeout: 5000 })).findByText("MUS-A");
    await menuItem(user, "Pivot ayarları"); await openSections(user);
    const rows = within(panel()).getByRole("button", { name: /^Satırlar/ }).closest("section")!;
    const [first, second] = within(rows).getAllByRole("listitem");
    fireEvent.dragStart(second);
    fireEvent.dragOver(first);
    fireEvent.drop(first);
    await waitFor(() => expect(last().rows.map((a) => a.field)).toEqual(["MaterialCode", "CustomerCode"]));
    const values = within(panel()).getByRole("button", { name: /^Değerler\s*\d*$/ }).closest("section")!;
    const items = within(values).getAllByRole("listitem");
    fireEvent.dragStart(items[1]);
    fireEvent.dragOver(items[0]);
    fireEvent.drop(items[0]);
    await waitFor(() => expect(last().values.map((v) => v.id)).toEqual(["d2", "d1"]));
    fireEvent.dragStart(within(rows).getAllByRole("listitem")[0]);     // başka bölüme bırakılamaz
    fireEvent.drop(within(values).getAllByRole("listitem")[0]);
    expect(last().rows.map((a) => a.field)).toEqual(["MaterialCode", "CustomerCode"]);
  });

  it("katlı başlık, satır başlıkları, toplam adları, boş ve karışık birim hücresi, birimin ondalığı", async () => {
    await open(viewWith({ ...PIVOT, totals: { rows: true, columns: true, subtotals: true } }));
    await within(await screen.findByRole("table", { name: "Pivot" }, { timeout: 5000 })).findByText("MUS-A toplamı");
    expect(screen.queryByRole("complementary", { name: "Pivot ayarları" })).toBeNull();   // görünümden açılınca panel kapalı
    const heads = within(grid()).getAllByRole("columnheader").map((h) => h.getAttribute("aria-label") ?? h.textContent);
    expect(heads).toEqual(expect.arrayContaining(["Kas 2026", "Ara 2026", "Toplam", "Açık miktar · Toplam", "Sipariş no · Benzersiz say"]));
    // değer başlığı iki satır: üstte alan, altta hesaplama; aylar arasında dikey ayraç
    const value = within(grid()).getAllByRole("columnheader", { name: "Açık miktar · Toplam" });
    expect([...value[0].querySelectorAll("span")].map((x) => x.textContent)).toEqual(["Açık miktar", "Toplam"]);
    expect(value.map((h) => h.classList.contains("is-group-start"))).toEqual([false, true, true]);
    expect(within(grid()).getByRole("columnheader", { name: "Ara 2026" })).toHaveClass("is-group-start");
    expect(within(grid()).getByRole("columnheader", { name: "Kas 2026" })).not.toHaveClass("is-group-start");
    expect(within(grid()).getByRole("columnheader", { name: "Kas 2026" })).toHaveAttribute("colspan", "2");
    const rows = bodyRows();
    expect(rows.map((r) => r.slice(0, 2))).toEqual([["MUS-A", "MAM-001"], ["", "MAM-002"], ["MUS-A toplamı", ""], ["MUS-B", "MAM-001"], ["MUS-B toplamı", ""], ["Genel toplam", ""]]);
    expect(rows[0].slice(2)).toEqual(["10,00", "11", "", "", "20,00", "21"]);     // kaydı olmayan hücre boş
    expect(rows[1].slice(2)).toEqual(["—", "—", "—", "—", "—", "—"]);
    expect(within(grid()).getAllByTitle("Birimler farklı; toplam yok").length).toBe(6);
    expect(rows[3][2]).toBe("1,500");                                            // birimin ondalığı (3)
  });

  it("değerlerin yeri, toplamlar ve sıralama panelden; değer ayarında hesaplama ve ağırlık alanı", async () => {
    const { user, last } = await open(viewWith(PIVOT));
    await within(await screen.findByRole("table", { name: "Pivot" }, { timeout: 5000 })).findByText("MUS-A");
    await menuItem(user, "Pivot ayarları"); await openSections(user);
    await user.click(within(panel()).getByRole("radio", { name: "Satırlarda" }));
    await waitFor(() => expect(within(grid()).getByRole("columnheader", { name: "Değer" })).toBeInTheDocument());
    expect(bodyRows().slice(0, 2).map((r) => r.slice(0, 3))).toEqual([["MUS-A", "MAM-001", "Açık miktar · Toplam"], ["", "", "Sipariş no · Benzersiz say"]]);
    for (const name of ["Satır toplamı", "Sütun toplamı", "Ara toplamlar"]) await user.click(within(panel()).getByRole("switch", { name }));
    await waitFor(() => expect(last().totals).toEqual({ rows: true, columns: true, subtotals: true }));
    await user.click(within(panel()).getByRole("button", { name: /^Sıralama/ }));
    await user.selectOptions(within(panel()).getByRole("combobox", { name: "Sırala" }), "Açık miktar · Toplam");
    await waitFor(() => expect(last().sort).toEqual({ by: "d1", dir: "desc" }));
    await user.click(within(panel()).getByRole("button", { name: "Açık miktar · Toplam" }));
    const calc = within(panel()).getByRole("combobox", { name: "Hesaplama" });
    expect(within(calc).getAllByRole("option").map((o) => o.textContent)).toEqual(["Toplam", "Ortalama", "En düşük", "En yüksek", "Say", "Benzersiz say", "Ağırlıklı ortalama"]);
    await user.selectOptions(calc, "Ağırlıklı ortalama");
    await user.selectOptions(within(panel()).getByRole("combobox", { name: "Ağırlık alanı" }), "Sipariş miktarı");
    await waitFor(() => expect(last().values[0]).toEqual({ id: "d1", fn: "wavg", field: "OpenQuantity", weight: "OrderedQuantity" }));
    expect(await within(panel()).findByRole("button", { name: "Açık miktar · Ağırlıklı ortalama (Sipariş miktarı)" })).toBeInTheDocument();
    await user.click(within(panel()).getAllByRole("button", { name: /: çıkar$/ })[0]);
    await waitFor(() => expect(last().rows).toEqual([{ field: "MaterialCode" }]));
  });

  it("başlıktaki huni tablonun filtresini açar; filtre pivot isteğine ve çipe girer", async () => {
    const { user, last } = await open(viewWith(PIVOT));
    await within(await screen.findByRole("table", { name: "Pivot" }, { timeout: 5000 })).findByText("MUS-A");
    await user.click(within(grid()).getByRole("button", { name: "Müşteri filtresi" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(await within(dialog).findByRole("checkbox", { name: /MUS-B/ }));
    await user.click(within(dialog).getByRole("button", { name: "Uygula" }));
    await waitFor(() => expect(last().filters).toEqual([{ field: "CustomerCode", op: "in", values: ["MUS-B"] }]));
    expect(document.body.textContent).toMatch(/Müşteri:\s*MUS-B/);  // filtre çipi
  });

  it("ilişkili alan panelden doğrudan seçilir; tabloya kolon eklenmez; görünümle saklanır", async () => {
    const { user, last, saved } = await open(viewWith(PIVOT));
    await within(await screen.findByRole("table", { name: "Pivot" }, { timeout: 5000 })).findByText("MUS-A");
    await menuItem(user, "Pivot ayarları"); await openSections(user);
    const rows = within(panel()).getByRole("button", { name: /^Satırlar/ }).closest("section")!;
    await user.click(within(rows).getByRole("button", { name: "Alan ekle" }));
    await user.click(within(rows).getByRole("button", { name: "Malzeme", expanded: false }));
    await user.click(await within(rows).findByRole("button", { name: "Malzeme grubu" }));
    await waitFor(() => expect(last().rows.map((a) => a.field)).toEqual(["CustomerCode", "MaterialCode", "MaterialId/MaterialGroup"]));
    expect(await within(grid()).findByRole("columnheader", { name: /Malzeme · Malzeme grubu/ })).toBeInTheDocument();
    await menuItem(user, "Kaydet");
    await waitFor(() => expect(saved).toHaveLength(1));
    expect(saved[0].definition.pivot).toMatchObject({ open: true, rows: [{ field: "CustomerCode" }, { field: "MaterialCode" }, { field: "MaterialId/MaterialGroup" }] });
    expect((saved[0].definition as unknown as { columns: { field: string }[] }).columns.map((c) => c.field)).toEqual(["OrderNo", "CustomerCode"]);
  });

  it("sınır ve hata: pivot çizilmez, neden yazar; \"Yeniden dene\"", async () => {
    let fail = true;
    const { user, pivots } = await open(viewWith(PIVOT), (req) => (fail
      ? { status: 422, body: { error: { code: "pivot_too_large", message: "Sütun sayısı çok fazla (200'den çok). Daha büyük bir dönem seçin, alan çıkarın ya da süzün." } } }
      : { body: data(req) }));
    expect(await screen.findByText(/Sütun sayısı çok fazla/, {}, { timeout: 5000 })).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Pivot" })).toBeNull();
    fail = false;
    const before = pivots.length;
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    await within(await screen.findByRole("table", { name: "Pivot" })).findByText("MUS-A");
    expect(pivots.length).toBe(before + 1);
  });

  it("boş sonuç ve parça parça yükleme", async () => {
    const big = (req: PivotRequest): Reply => {
      const d = data({ ...req, totals: { rows: false, columns: false, subtotals: false } });
      const row = (i: number) => ({ key: [`M-${String(i).padStart(4, "0")}`, "X"], level: 2, total: false, cells: d.rows[0]?.cells ?? d.values.map(() => d.columns.map(() => 1)) });
      return { body: { ...d, rows: Array.from({ length: Math.min(req.limit, 250 - req.offset) }, (_, i) => row(req.offset + i)), row_count: 250 } };
    };
    const { pivots } = await open(viewWith(PIVOT), big);
    await within(await screen.findByRole("table", { name: "Pivot" }, { timeout: 5000 })).findByText("M-0000");
    expect(grid()).toHaveAttribute("aria-rowcount", "250");                      // satır sınırı yok: sayaç sunucudan
    expect(pivots.every((p) => p.limit === 100)).toBe(true);
    expect(pivots.map((p) => p.offset)).toContain(0);
  });

  it("filtrede kayıt yoksa ızgaranın yerinde yazar", async () => {
    await open(viewWith(PIVOT), (req) => ({ body: { ...data(req), rows: [], row_count: 0 } }));
    expect(await screen.findByText("Bu filtrede kayıt yok", {}, { timeout: 5000 })).toBeInTheDocument();
  });
});

describe("hesaplanan değer, değerin kuralı, Excel ve varsayılan hesaplama (7.7b, K-183)", () => {
  const RULE = { id: "k1", enabled: true, condition: { op: "lt" as const, value: 0.5 }, format: { fill: "#f7dcd5" } };
  const SUMS: PivotConfig = { ...PIVOT, values: [{ id: "d1", field: "OpenQuantity", fn: "sum" }, { id: "d2", field: "OrderedQuantity", fn: "sum" }] };
  const CALC: PivotConfig = { ...SUMS, values: [...SUMS.values, { id: "d3", kind: "calc", field: null, fn: "sum", name: "Açık oranı", a: "d1", op: "div", b: "d2", percent: true, rules: [RULE] }] };

  it("model: etiket yolu söyler; istek, hazır olma, uyarlama, işleneni giden hesaplanan değer, varsayılan hesaplama, Excel isteği", () => {
    const calc = CALC.values[2];
    expect(valueLabel(calc, byField)).toBe("Açık oranı · Toplamlardan");
    expect(valueDisplay(calc, byField)).toEqual({ top: "Açık oranı", bottom: "Toplamlardan", full: "Açık oranı · Toplamlardan" });   // özel adda da yol görünür
    expect(valueName({ ...calc, name: null }, byField)).toBe("Hesaplanan değer · Toplamlardan");
    expect(pivotReady(CALC)).toBe(true);
    expect(pivotReady({ ...CALC, values: [...SUMS.values, { ...calc, b: null }] })).toBe(false);
    const req = pivotRequest({ ...CALC, values: [{ ...SUMS.values[0], rules: [{ ...RULE, enabled: false }] }, SUMS.values[1], { ...calc, rules_on_totals: true }] }, [], null, 1, 0, 100);
    expect(req.values).toEqual([{ id: "d1", fn: "sum", field: "OpenQuantity" }, { id: "d2", fn: "sum", field: "OrderedQuantity" },
                                { id: "d3", kind: "calc", a: "d1", op: "div", b: "d2", percent: true, rules: [RULE], rules_on_totals: true }]);   // kapalı kural isteğe girmez
    expect(fitPivot({ ...CALC, sort: { by: "d3", dir: "desc" } }, COLUMNS.filter((c) => c.field !== "OrderedQuantity"))).toMatchObject({ values: [{ id: "d1" }], sort: { by: "name" } });
    expect(dropOrphans({ ...CALC, values: CALC.values.filter((v) => v.id !== "d1") }, byField).values.map((v) => v.id)).toEqual(["d2"]);
    const dated: PivotConfig = { ...CALC, values: [{ id: "d1", field: "RequestedDate", fn: "min" }, CALC.values[1], CALC.values[2]] };
    expect(dropOrphans(dated, byField).values.map((v) => v.id)).toEqual(["d1", "d2"]);   // tarih sonucu işlenen olamaz
    expect(normalizePivot(JSON.parse(JSON.stringify(CALC)))!.values[2]).toMatchObject({ kind: "calc", a: "d1", op: "div", b: "d2", percent: true, rules: [RULE] });
    const price: ListColumn = { ...byField.get("Price")!, aggregate: null, aggregate_weight: null };
    expect([defaultFn(price), defaultFn({ ...price, aggregate: "avg" }), defaultFn({ ...price, aggregate: "wavg", aggregate_weight: "OpenQuantity" }),
            defaultFn({ ...price, aggregate: "wavg" }), defaultFn({ ...price, aggregate: "avg_nonzero" })]).toEqual(["sum", "avg", "wavg", "sum", "avg"]);
    const exp = pivotExportRequest({ ...CALC, values_on: "rows", values: [{ ...SUMS.values[0], decimals: 1, name: "Açık" }, SUMS.values[1], calc] }, [], null, 1, byField);
    expect("offset" in exp || "limit" in exp).toBe(false);
    expect(exp).toMatchObject({ values_on: "rows", names: { d1: "Açık", d2: "Sipariş miktarı · Toplam", d3: "Açık oranı · Toplamlardan" } });
    expect(exp.values[0]).toEqual({ id: "d1", fn: "sum", field: "OpenQuantity", decimals: 1, name: "Açık" });
  });

  it("kayıtlı görünümden: başlıkta ad ve altında \"Toplamlardan\"; kuralı tutan hücre boyanır; istek hesaplanan değeri taşır", async () => {
    const { last } = await open(viewWith(CALC));
    const table = await screen.findByRole("table", { name: "Pivot" }, { timeout: 5000 });
    await within(table).findByText("MUS-A");
    expect(within(table).getAllByText("Açık oranı").length).toBeGreaterThan(0);
    expect(within(table).getAllByText("Toplamlardan").length).toBeGreaterThan(0);
    expect(last().values[2]).toEqual({ id: "d3", kind: "calc", a: "d1", op: "div", b: "d2", percent: true, rules: [RULE] });
    const ruled = [...table.querySelectorAll("td.is-ruled")];
    expect(ruled).toHaveLength(1);                                    // sahte sunucu ilk satırın ilk sütununu işaretler; toplamlar işaretsiz
    expect(ruled[0]).toHaveStyle({ backgroundColor: "#f7dcd5" });
  });

  it("panelden: hesaplanan değer formu; kural penceresinde ikon ve alan karşılaştırması yok; yüzde eşik oran olarak; Toplamlara da uygula; işlenen çıkınca düşer", async () => {
    const { user, last } = await open(viewWith(SUMS));
    await within(await screen.findByRole("table", { name: "Pivot" }, { timeout: 5000 })).findByText("MUS-A");
    await menuItem(user, "Pivot ayarları"); await openSections(user);
    await user.click(within(panel()).getByRole("button", { name: "Hesaplanan değer ekle" }));
    await waitFor(() => expect(last().values[2]).toEqual({ id: "d3", kind: "calc", a: "d1", op: "div", b: "d2", percent: false }));
    expect(within(panel()).getByRole("button", { name: "Hesaplanan değer · Toplamlardan" })).toHaveAttribute("aria-expanded", "true");
    await user.type(within(panel()).getByRole("textbox", { name: "Ad" }), "Oran");
    expect(await within(panel()).findByRole("button", { name: "Oran · Toplamlardan" })).toBeInTheDocument();
    expect(within(within(panel()).getByRole("combobox", { name: "A" })).getAllByRole("option").map((o) => o.textContent)).toEqual(["Açık miktar · Toplam", "Sipariş miktarı · Toplam"]);
    await user.click(within(panel()).getByRole("radio", { name: "×" }));
    await user.click(within(panel()).getByRole("radio", { name: "Yüzde" }));
    await waitFor(() => expect(last().values[2]).toMatchObject({ op: "mul", percent: true }));

    await user.click(within(panel()).getByRole("button", { name: "Kural ekle" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni biçim kuralı" });
    expect(within(dialog).queryByText("İkon")).toBeNull();
    expect(within(dialog).queryByText("Karşılaştır")).toBeNull();
    expect(within(within(dialog).getByRole("combobox", { name: "Koşul" })).getAllByRole("option")).toHaveLength(6);   // yalnız sayı koşulları
    await user.type(within(dialog).getByLabelText("Değer (%)"), "50");
    await user.tab();
    await user.click(within(dialog).getByRole("button", { name: /^Zemin:/ }));
    await user.click(within(await screen.findByRole("dialog", { name: "Zemin" })).getByRole("button", { name: "Açık kiremit #f7dcd5" }));
    await user.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(last().values[2].rules).toEqual([{ id: "k1", enabled: true, condition: { op: "gt", value: 0.5 }, format: { fill: "#f7dcd5" } }]));
    expect(last().values[2].rules_on_totals).toBeUndefined();
    expect(within(panel()).getByRole("button", { name: /^Kuralı düzenle: / })).toBeInTheDocument();
    await user.click(within(panel()).getByRole("switch", { name: "Toplamlara da uygula" }));
    await waitFor(() => expect(last().values[2].rules_on_totals).toBe(true));
    await user.click(within(panel()).getByRole("button", { name: /^Kuralı kaldır: / }));
    await waitFor(() => expect(last().values[2].rules).toBeUndefined());

    await user.click(within(panel()).getByRole("button", { name: "Açık miktar · Toplam: çıkar" }));
    await waitFor(() => expect(last().values.map((v) => v.id)).toEqual(["d2"]));   // işleneni giden hesaplanan değer de gider
  });

  it("Excel düğmesi pivot açıkken pivotu aktarır: pencere açılmaz, dosya iner; istekte değerlerin yeri ve ekrandaki adlar", async () => {
    const downloads: string[] = [];
    Object.assign(URL, { createObjectURL: vi.fn(() => "blob:x"), revokeObjectURL: vi.fn() });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { downloads.push(this.download); });
    const { user, exports } = await open(viewWith({ ...CALC, values_on: "rows" }));
    await within(await screen.findByRole("table", { name: "Pivot" }, { timeout: 5000 })).findByText("MUS-A");
    await user.click(screen.getByRole("button", { name: "Excel'e aktar" }));
    await waitFor(() => expect(downloads).toEqual(["satis-siparisi_pivot.xlsx"]));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(exports).toHaveLength(1);
    expect(exports[0]).toMatchObject({ values_on: "rows", title: "Satış siparişi", rows: CALC.rows, totals: CALC.totals,
                                       names: { d1: "Açık miktar · Toplam", d3: "Açık oranı · Toplamlardan" } });
    expect("offset" in exports[0] || "limit" in exports[0]).toBe(false);
  });

  it("eklenen değer alanın liste tanımındaki varsayılan hesaplamasıyla gelir (ağırlıklı ortalamada ağırlık alanıyla)", async () => {
    const { user, last } = await open(viewWith({ ...PIVOT, values: [{ id: "d1", field: "OpenQuantity", fn: "sum" }] }));
    await within(await screen.findByRole("table", { name: "Pivot" }, { timeout: 5000 })).findByText("MUS-A");
    await menuItem(user, "Pivot ayarları"); await openSections(user);
    await user.click(within(panel()).getByRole("button", { name: "Değer ekle" }));
    await user.click(await within(panel()).findByRole("button", { name: "Fiyat" }));
    await waitFor(() => expect(last().values[1]).toEqual({ id: "d2", fn: "wavg", field: "Price", weight: "OpenQuantity" }));
  });
});

describe("ayar panelinin bölümleri (K-183, 7.7b demo kararı)", () => {
  const sections = () => Object.fromEntries(within(panel()).getAllByRole("heading", { level: 3 }).map((h) => {
    const b = within(h).getByRole("button");
    return [b.textContent, b.getAttribute("aria-expanded")];
  }));

  it("kurulmuş pivotta bölümler kapalı gelir, başlıkta öğe sayısı görünür; açılan bölüm panel kapanana kadar açık kalır", async () => {
    const { user, last } = await open(viewWith(PIVOT));
    await within(await screen.findByRole("table", { name: "Pivot" }, { timeout: 5000 })).findByText("MUS-A");
    await menuItem(user, "Pivot ayarları");
    expect(sections()).toEqual({ "Satırlar2": "false", "Sütunlar1": "false", "Değerler2": "false", "Değerlerin yeri": "false", "Toplamlar": "false", "Sıralama": "false" });
    expect(within(panel()).queryByRole("button", { name: "Alan ekle" })).toBeNull();
    await user.click(within(panel()).getByRole("button", { name: /^Değerler\d*$/ }));
    await user.click(within(panel()).getByRole("button", { name: "Değer ekle" }));
    await user.click(await within(panel()).findByRole("button", { name: "Fiyat" }));
    await waitFor(() => expect(last().values).toHaveLength(3));
    expect(sections()).toMatchObject({ "Değerler3": "true", "Satırlar2": "false" });        // öğe eklenince bölüm açık kalır; ötekiler kapalı
    await user.click(within(panel()).getByRole("button", { name: "Paneli kapat" }));
    await menuItem(user, "Pivot ayarları");
    expect(sections()).toMatchObject({ "Değerler3": "false", "Satırlar2": "false" });       // yeniden açılınca kural: hepsi kapalı
  });

  it("pivot henüz kurulmamışsa Satırlar, Sütunlar ve Değerler açık gelir; ilk alandan sonra yeniden açılınca kapalı", async () => {
    const { user } = await open();
    await menuItem(user, "Pivot görünümü");
    expect(sections()).toEqual({ "Satırlar": "true", "Sütunlar": "true", "Değerler": "true", "Değerlerin yeri": "false", "Toplamlar": "false", "Sıralama": "false" });
    await user.click(within(panel()).getAllByRole("button", { name: "Alan ekle" })[0]);
    await user.click(await within(panel()).findByRole("button", { name: "Müşteri" }));
    expect(sections()).toMatchObject({ "Satırlar1": "true", "Sütunlar": "true", "Değerler": "true" });   // panel kapanana kadar açık
    await user.click(within(panel()).getByRole("button", { name: "Paneli kapat" }));
    await menuItem(user, "Pivot ayarları");
    expect(sections()).toMatchObject({ "Satırlar1": "false", "Sütunlar": "false", "Değerler": "false" });
  });
});

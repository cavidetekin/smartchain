// Tablo bileşeni (1.3, docs/12): sözleşmeye giden istekler (K-87), U-6/U-7/U-8/U-12, sanal gövde ve U-23.
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { mockApi, mockSocket, renderApp, type Reply } from "../test/helpers";
import { OVERSCAN, ROW_REM } from "./DataTable";
import type { ListColumn, QueryRequest } from "./types";

const col = (field: string, label: string, type: ListColumn["type"], filter: ListColumn["filter"],
             extra: Partial<ListColumn> = {}): ListColumn => ({
  field, label, type, filter, values: null, values_from_server: false, decimals: null, default_visible: true, ...extra,
});

const COLUMNS: ListColumn[] = [
  col("Code", "Malzeme kodu", "text", "text"),
  col("Name", "Malzeme adı", "text", "text"),
  col("MaterialLevel", "Malzeme seviyesi", "text", "list", { values: ["Hammadde", "Yarı mamul", "Nihai ürün"] }),
  col("MaterialGroup", "Malzeme grubu", "text", "list", { values_from_server: true }),
  col("IsSellable", "Satılabilir", "bool", "list", { values: [true, false] }),
  col("SafetyStock", "Güvenlik stoğu", "number", "number", { decimals: 2 }),
  col("UpdatedAt", "Son değişiklik zamanı", "datetime", "date"),
  col("AdditionalText1", "Malzeme sınıfı", "text", "text", { default_visible: false }),
];

const VIEW_PX = 560;
let queries: QueryRequest[] = [];
let valueRequests: unknown[] = [];

function backend({ filtered = 1234, total = 50000, status = 200 } = {}) {
  queries = [];
  valueRequests = [];
  return mockApi({
    "/api/materials/columns": { body: COLUMNS },
    "/api/materials/query": (_url, init): Reply => {
      const body = JSON.parse(String(init?.body)) as QueryRequest;
      queries.push(body);
      if (status !== 200) return { status, body: { error: { code: "database_unavailable", message: "Veritabanına bağlanılamıyor.", trace_id: "x" } } };
      const n = Math.max(0, Math.min(body.limit, filtered - body.offset));
      const rows = Array.from({ length: n }, (_, k) => {
        const i = body.offset + k;
        return { Id: i + 1, Code: `M-${i}`, Name: `Malzeme ${i}`, MaterialLevel: "Hammadde", MaterialGroup: "Çubuk",
                 IsSellable: i % 2 === 0, SafetyStock: 1234.5, UpdatedAt: "2026-10-27T09:20:00+00:00", AdditionalText1: "A" };
      });
      return { body: { rows, offset: body.offset, filtered, total } };
    },
    "/api/materials/values": (_url, init): Reply => {
      valueRequests.push(JSON.parse(String(init?.body)));
      return { body: [{ value: "Çubuk", count: 20 }, { value: "Levha", count: 20 }] };
    },
  });
}

const last = () => queries[queries.length - 1];

// jsdom ölçü vermez: sanal kaydırıcı kap boyunu offsetHeight'tan okur (test yardımcısı).
const sizes = Object.getOwnPropertyDescriptors(HTMLElement.prototype);
beforeEach(() => {
  mockSocket();
  Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
    configurable: true, get() { return (this as HTMLElement).dataset.testid === "table-scroll" ? VIEW_PX : 0; },
  });
  Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
    configurable: true, get() { return (this as HTMLElement).dataset.testid === "table-scroll" ? 1000 : 0; },
  });
});
afterEach(() => {
  Object.defineProperty(HTMLElement.prototype, "offsetHeight", sizes.offsetHeight);
  Object.defineProperty(HTMLElement.prototype, "offsetWidth", sizes.offsetWidth);
});

async function open(opts?: Parameters<typeof backend>[0]) {
  backend(opts);
  renderApp("/tablo");
  await screen.findByRole("columnheader", { name: /Malzeme kodu/ });
  await waitFor(() => expect(queries.length).toBeGreaterThan(0));
}

const dataRows = () => [...document.querySelectorAll("tbody tr[aria-rowindex]")];
const sortButton = (label: string) => within(screen.getByRole("columnheader", { name: new RegExp(label) }))
  .getAllByRole("button")[0];

describe("sayaç ve sözleşme", () => {
  it("varsayılan alanlarla ilk parçayı ister; sayaç Türkçe '1.234 / 50.000'", async () => {
    await open();
    expect(queries[0]).toEqual({
      fields: ["Code", "Name", "MaterialLevel", "MaterialGroup", "IsSellable", "SafetyStock", "UpdatedAt"],
      sort: [], filters: [], offset: 0, limit: 100,
    });
    expect(await screen.findByLabelText("Kayıt sayısı (gösterilen / toplam)")).toHaveTextContent("1.234 / 50.000");
    expect(await screen.findByText("M-0")).toBeInTheDocument();
    const first = dataRows()[0];
    expect(within(first as HTMLElement).getByText("1.234,50")).toHaveClass("is-num");
    expect(within(first as HTMLElement).getByText("Evet")).toBeInTheDocument();
    expect(within(first as HTMLElement).getByText("27.10.2026 12:20")).toBeInTheDocument();
  });

  it("sayfa menüde yoktur", async () => {
    await open();
    expect(screen.queryByRole("link", { name: /Tablo bileşeni/ })).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Tablo bileşeni");
  });
});

describe("sıralama (U-7)", () => {
  it("tıklama artan → azalan → kapalı", async () => {
    const user = userEvent.setup();
    await open();
    await user.click(sortButton("Malzeme kodu"));
    await waitFor(() => expect(last().sort).toEqual([{ field: "Code", dir: "asc" }]));
    expect(screen.getByRole("columnheader", { name: /Malzeme kodu/ })).toHaveAttribute("aria-sort", "ascending");
    await user.click(sortButton("Malzeme kodu"));
    await waitFor(() => expect(last().sort).toEqual([{ field: "Code", dir: "desc" }]));
    await user.click(sortButton("Malzeme kodu"));
    await waitFor(() => expect(last().sort).toEqual([]));
  });

  it("Shift+tıklama ek sıralama ekler; öncelik başlıkta görünür", async () => {
    const user = userEvent.setup();
    await open();
    await user.click(sortButton("Malzeme seviyesi"));
    await user.keyboard("{Shift>}");
    await user.click(sortButton("Malzeme kodu"));
    await user.click(sortButton("Malzeme kodu"));
    await user.keyboard("{/Shift}");
    await waitFor(() => expect(last().sort).toEqual([{ field: "MaterialLevel", dir: "asc" }, { field: "Code", dir: "desc" }]));
    expect(screen.getByLabelText("Sıralama önceliği 1")).toHaveTextContent("1");
    expect(within(screen.getByRole("columnheader", { name: /Malzeme kodu/ })).getByLabelText("Sıralama önceliği 2"))
      .toHaveTextContent("2");
    await user.click(sortButton("Malzeme adı"));  // Shift'siz: tek sıralamaya döner
    await waitFor(() => expect(last().sort).toEqual([{ field: "Name", dir: "asc" }]));
    expect(screen.queryByLabelText("Sıralama önceliği 1")).toBeNull();
  });
});

describe("filtreler (U-8)", () => {
  const openFilter = async (user: ReturnType<typeof userEvent.setup>, label: string) => {
    await user.click(screen.getByRole("button", { name: `${label} filtresi` }));
    return screen.getByRole("dialog", { name: `${label} filtresi` });
  };

  it("metin: koşul ve değer", async () => {
    const user = userEvent.setup();
    await open();
    const menu = await openFilter(user, "Malzeme adı");
    await user.selectOptions(within(menu).getByLabelText("Koşul"), "starts_with");
    await user.type(within(menu).getByLabelText("Değer"), "mil{Enter}");
    await waitFor(() => expect(last().filters).toEqual([{ field: "Name", op: "starts_with", value: "mil" }]));
    expect(screen.getByRole("button", { name: "Malzeme adı filtresi" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("dialog", { name: "Malzeme adı filtresi" })).toBeNull();
  });

  it("liste: sabit değerlerde arama ve çoklu seçim; evet/hayır", async () => {
    const user = userEvent.setup();
    await open();
    let menu = await openFilter(user, "Malzeme seviyesi");
    await user.type(within(menu).getByRole("searchbox"), "mamul");
    expect(within(menu).queryByRole("checkbox", { name: "Hammadde" })).toBeNull();
    await user.click(within(menu).getByRole("checkbox", { name: "Yarı mamul" }));
    await user.click(within(menu).getByRole("button", { name: "Uygula" }));
    menu = await openFilter(user, "Satılabilir");
    await user.click(within(menu).getByRole("checkbox", { name: "Evet" }));
    await user.click(within(menu).getByRole("button", { name: "Uygula" }));
    await waitFor(() => expect(last().filters).toEqual([
      { field: "MaterialLevel", op: "in", values: ["Yarı mamul"] }, { field: "IsSellable", op: "in", values: [true] },
    ]));
  });

  it("liste: değerler sunucudan, sayılarıyla ve diğer filtrelerle", async () => {
    const user = userEvent.setup();
    await open();
    let menu = await openFilter(user, "Malzeme seviyesi");
    await user.click(within(menu).getByRole("checkbox", { name: "Hammadde" }));
    await user.click(within(menu).getByRole("button", { name: "Uygula" }));
    menu = await openFilter(user, "Malzeme grubu");
    await user.click(await within(menu).findByRole("checkbox", { name: "Çubuk" }));
    expect(within(menu).getAllByText("20")).toHaveLength(2);
    expect(valueRequests[0]).toEqual({ field: "MaterialGroup", search: "",
                                       filters: [{ field: "MaterialLevel", op: "in", values: ["Hammadde"] }] });
    await user.click(within(menu).getByRole("button", { name: "Uygula" }));
    await waitFor(() => expect(last().filters[1]).toEqual({ field: "MaterialGroup", op: "in", values: ["Çubuk"] }));
  });

  it("sayı: Türkçe giriş, aralık ve büyük", async () => {
    const user = userEvent.setup();
    await open();
    let menu = await openFilter(user, "Güvenlik stoğu");
    await user.type(within(menu).getByLabelText("En az"), "1.234,5{Enter}");
    await waitFor(() => expect(last().filters).toEqual([{ field: "SafetyStock", op: "between", min: 1234.5 }]));
    menu = await openFilter(user, "Güvenlik stoğu");
    await user.click(within(menu).getByRole("radio", { name: "Büyük" }));
    await user.type(within(menu).getByLabelText("Değer"), "10");
    await user.click(within(menu).getByRole("button", { name: "Uygula" }));
    await waitFor(() => expect(last().filters).toEqual([{ field: "SafetyStock", op: "gt", value: 10 }]));
  });

  it("tarih: aralık gg.aa.yyyy → ISO; göreli seçim", async () => {
    const user = userEvent.setup();
    await open();
    let menu = await openFilter(user, "Son değişiklik zamanı");
    await user.type(within(menu).getByLabelText("Başlangıç"), "27.10.2026{Enter}");
    await waitFor(() => expect(last().filters).toEqual([{ field: "UpdatedAt", op: "between", from: "2026-10-27" }]));
    menu = await openFilter(user, "Son değişiklik zamanı");
    await user.click(within(menu).getByRole("radio", { name: "Göreli" }));
    await user.click(within(menu).getByRole("radio", { name: "Sonraki 4 hafta" }));
    await user.click(within(menu).getByRole("button", { name: "Uygula" }));
    await waitFor(() => expect(last().filters).toEqual([{ field: "UpdatedAt", op: "relative", value: "next_4_weeks" }]));
  });

  it("temizle filtreyi kaldırır; eşleşme yoksa 'Filtreleri temizle'", async () => {
    const user = userEvent.setup();
    await open({ filtered: 0, total: 200 });
    const menu = await openFilter(user, "Malzeme adı");
    await user.type(within(menu).getByLabelText("Değer"), "yok{Enter}");
    expect(await screen.findByText(/Eşleşen kayıt yok/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Filtreleri temizle" }));
    await waitFor(() => expect(last().filters).toEqual([]));
  });
});

describe("alan paneli (U-6)", () => {
  it("aramalı liste; açılan alan istenir ve başlıkta görünür, kapatılan çıkar", async () => {
    const user = userEvent.setup();
    await open();
    await user.click(screen.getByRole("button", { name: "Alanlar (7/8)" }));
    const panel = screen.getByRole("dialog", { name: "Alanlar (7/8)" });
    await user.type(within(panel).getByRole("searchbox"), "SINIF");
    expect(within(panel).getAllByRole("checkbox")).toHaveLength(1);
    await user.click(within(panel).getByRole("checkbox", { name: "Malzeme sınıfı" }));
    await waitFor(() => expect(last().fields).toContain("AdditionalText1"));
    expect(screen.getByRole("columnheader", { name: /Malzeme sınıfı/ })).toBeInTheDocument();
    await user.clear(within(screen.getByRole("dialog")).getByRole("searchbox"));
    await user.click(within(screen.getByRole("dialog")).getByRole("checkbox", { name: "Malzeme kodu" }));
    await waitFor(() => expect(last().fields).not.toContain("Code"));
    expect(screen.queryByRole("columnheader", { name: /Malzeme kodu/ })).toBeNull();
  });

  it("son açık alan kapatılamaz; varsayılana dön", async () => {
    const user = userEvent.setup();
    await open();
    await user.click(screen.getByRole("button", { name: /Alanlar/ }));
    const boxes = () => within(screen.getByRole("dialog")).getAllByRole("checkbox") as HTMLInputElement[];
    for (const label of ["Malzeme adı", "Malzeme seviyesi", "Malzeme grubu", "Satılabilir", "Güvenlik stoğu",
                         "Son değişiklik zamanı"]) {
      await user.click(within(screen.getByRole("dialog")).getByRole("checkbox", { name: label }));
    }
    expect(boxes().find((b) => b.checked)).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Varsayılana dön" }));
    await waitFor(() => expect(last().fields).toHaveLength(7));
  });
});

describe("sanal gövde (docs/12 performans hedefi, U-23)", () => {
  it("100.000 satırda DOM'da yalnız görünen satırlar ve tampon; kaydırınca eksik parça bir kez istenir", async () => {
    await open({ filtered: 100_000, total: 100_000 });
    await screen.findByText("M-0");
    const visibleRows = Math.ceil(VIEW_PX / Math.round(13 * ROW_REM));
    expect(dataRows().length).toBeLessThanOrEqual(visibleRows + 2 * OVERSCAN);
    expect(queries.map((q) => q.offset)).toEqual([0]);

    const scroller = screen.getByTestId("table-scroll");
    const scrollTo = async (row: number) => {
      await act(async () => {
        scroller.scrollTop = row * Math.round(13 * ROW_REM);
        fireEvent.scroll(scroller);
      });
    };
    await scrollTo(5_000);
    await screen.findByText("M-5000");
    expect(dataRows().length).toBeLessThanOrEqual(visibleRows + 2 * OVERSCAN);
    await scrollTo(0);
    await scrollTo(5_000);
    expect(queries.map((q) => q.offset).sort((a, b) => a - b)).toEqual([0, 4900, 5000]);
  });

  it("satır yüksekliği yazı boyutuyla ölçeklenir", async () => {
    const user = userEvent.setup();
    await open({ filtered: 100_000, total: 100_000 });
    await screen.findByText("M-0");
    const rowPx = () => {
      const spacer = [...document.querySelectorAll<HTMLElement>("tr.sc-table-spacer")].pop()!;
      const lastIndex = Math.max(...dataRows().map((r) => Number(r.getAttribute("aria-rowindex")) - 2));
      return parseFloat(spacer.style.height) / (100_000 - lastIndex - 1);
    };
    expect(rowPx()).toBe(28);
    await user.click(screen.getByRole("button", { name: "Kullanıcı #3" }));
    await user.click(screen.getByRole("radio", { name: /Büyük/ }));
    await waitFor(() => expect(rowPx()).toBe(34));
  });
});

describe("hata", () => {
  it("liste okunamazsa mesaj ve yeniden dene", async () => {
    const user = userEvent.setup();
    await open({ status: 503 });
    expect(await screen.findByText(/Veritabanına bağlanılamıyor/)).toBeInTheDocument();
    const before = queries.length;
    await user.click(screen.getByRole("button", { name: "Yeniden dene" }));
    await waitFor(() => expect(queries.length).toBe(before + 1));
  });
});

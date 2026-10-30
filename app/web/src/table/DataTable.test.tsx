// Tablo bileşeni (1.3, docs/12): sözleşmeye giden istekler (K-87), U-6/U-7/U-8/U-12, sanal gövde ve U-23.
import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { OVERSCAN, ROW_REM } from "./DataTable";
import { calls, dataRows, lastQuery as last, openTable as open, useTableTestSetup, VIEW_PX } from "./testBackend";

useTableTestSetup();
const queries = calls.queries;

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
    expect(within(first as HTMLElement).getByText("1.234")).toHaveClass("is-num");          // ADET: 0 ondalık
    expect(within(dataRows()[1] as HTMLElement).getByText("12,250")).toHaveClass("is-num");  // KG: 3 ondalık (K-88)
    expect(within(first as HTMLElement).getByText("Evet")).toBeInTheDocument();
    expect(within(first as HTMLElement).getByText("27.10.2026 12:20")).toBeInTheDocument();
  });

  it("sayfa menüde yoktur", async () => {
    await open();
    expect(screen.queryByRole("link", { name: /Tablo bileşeni/ })).toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Tablo bileşeni");
  });
});

describe("parça büyüklüğü (ListChunkSize)", () => {
  it("tablo kolonlar cevabındaki parça büyüklüğünden fazlasını istemez", async () => {
    await open({ filtered: 100_000, total: 100_000, chunk: 30 });
    await screen.findByText("M-0");
    const scroller = screen.getByTestId("table-scroll");
    await act(async () => {
      scroller.scrollTop = 1_000 * Math.round(13 * ROW_REM);
      fireEvent.scroll(scroller);
    });
    await screen.findByText("M-1000");
    expect(queries.every((q) => q.limit === 30 && q.offset % 30 === 0)).toBe(true);
    expect(queries.length).toBeGreaterThan(1);
  });
});

describe("araç çubuğu", () => {
  it("'Filtreleri temizle' filtre varken etiketlerin yanında; 'Sıralamayı temizle' ikonu sıralama varken açık", async () => {
    const user = userEvent.setup();
    await open();
    const sortClear = () => screen.getByRole("button", { name: "Sıralamayı temizle" });
    expect(screen.queryByRole("button", { name: "Filtreleri temizle" })).toBeNull();
    expect(sortClear()).toBeDisabled();
    await user.click(sortButton("Malzeme kodu"));
    await user.click(screen.getByRole("button", { name: "Malzeme adı filtresi" }));
    await user.type(within(screen.getByRole("dialog", { name: "Malzeme adı filtresi" })).getByLabelText("Değer"), "mil{Enter}");
    await waitFor(() => expect(last().filters).toHaveLength(1));
    const clear = screen.getByRole("button", { name: "Filtreleri temizle" });
    expect(clear.closest(".sc-table-status")).not.toBeNull();  // filtre etiketlerinin yanında
    await user.click(clear);
    await waitFor(() => expect(last().filters).toEqual([]));
    expect(screen.queryByRole("button", { name: "Filtreleri temizle" })).toBeNull();
    expect(last().sort).toEqual([{ field: "Code", dir: "asc" }]);
    expect(sortClear()).toBeEnabled();
    await user.click(sortClear());
    await waitFor(() => expect(last().sort).toEqual([]));
    expect(sortClear()).toBeDisabled();
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
    expect(calls.values[0]).toEqual({ field: "MaterialGroup", search: "",
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

  it("tarih: takvimden seçim; Esc yalnız takvimi kapatır", async () => {
    const user = userEvent.setup();
    await open();
    const menu = await openFilter(user, "Son değişiklik zamanı");
    await user.click(within(menu).getByRole("button", { name: "Başlangıç: Takvimden seç" }));
    await user.keyboard("{Escape}");
    expect(screen.getByRole("dialog", { name: "Son değişiklik zamanı filtresi" })).toBeInTheDocument();
    await user.click(within(menu).getByRole("button", { name: "Başlangıç: Takvimden seç" }));
    await user.click(screen.getByRole("button", { name: "Bugün" }));
    const today = new Date();
    const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
    await user.click(within(menu).getByRole("button", { name: "Uygula" }));
    await waitFor(() => expect(last().filters).toEqual([{ field: "UpdatedAt", op: "between", from: iso }]));
  });

  it("temizle filtreyi kaldırır; eşleşme yoksa 'Filtreleri temizle'", async () => {
    const user = userEvent.setup();
    await open({ filtered: 0, total: 200 });
    const menu = await openFilter(user, "Malzeme adı");
    await user.type(within(menu).getByLabelText("Değer"), "yok{Enter}");
    expect(await screen.findByText(/Eşleşen kayıt yok/)).toBeInTheDocument();
    await user.click(within(screen.getByRole("row", { name: /Eşleşen kayıt yok/ })).getByRole("button", { name: "Filtreleri temizle" }));
    await waitFor(() => expect(last().filters).toEqual([]));
  });
});

describe("alan paneli (U-6)", () => {
  it("aramalı liste; açılan alan istenir ve başlıkta görünür, kapatılan çıkar", async () => {
    const user = userEvent.setup();
    await open();
    await user.click(screen.getByRole("button", { name: "Alanlar (7/10)" }));
    const panel = screen.getByRole("dialog", { name: "Alanlar (7/10)" });
    await user.type(within(panel).getByRole("searchbox"), "SINIF");
    expect(within(panel).getAllByRole("checkbox")).toHaveLength(1);
    expect(within(panel).getByRole("checkbox").closest("[title]")).toHaveAttribute("title", "Malzeme sınıfı");
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

// Manuel değer (K-170, K-172): hücre düzenleme standardı (düz metin, ✎, çift tıklama / Enter / yazmaya başlama, ok tuşları, Esc), düzenleme
// çubuğu, köşe işareti ve kaynak ipucu (yalnız manuel ve kural), hücre menüsünden, Delete ile ve seçili kayıtlarda toplu kaldırma, Excel'den
// yapıştırma özeti, kaydetme hata mesajı, fareyle kaydırma ve klavye birlikte; manuel alanı olmayan tabloda imleç ve seçim yok; End user düzenleyemez.
import { act, createEvent, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { col, useTableTestSetup } from "../table/testBackend";
import { cellOf, openEditor, setCell } from "../table/testEditing";
import { ROW_REM } from "../table/DataTable";
import { meAs, mockApi, renderApp, type Reply } from "../test/helpers";

useTableTestSetup();

const COLUMNS = [
  col("ManualState", "Manuel değer", "text", "list", { values: ["Var", "Var / ERP Güncellendi", "Var / Kural Güncellendi"] }),
  col("Code", "Müşteri kodu", "text", "text"), col("Name", "Müşteri adı", "text", "text", { manual: true }),
  col("Priority", "Müşteri önceliği", "integer", "number", { manual: true }), col("CustomerGroup", "Müşteri grubu", "text", "text"),
  col("Segment", "Segment", "text", "list", { manual: true, values: ["A", "B"] }),
];
const ROWS = [
  { Id: 1, ManualState: "Var / Kural Güncellendi", Code: "MUS-A", Name: "Manuel ad", Priority: 1, CustomerGroup: "Yurt içi", Segment: "A",
    _sources: { Name: { source: "Manuel", by: "Ayşe Planlama", at: "2026-11-12T11:20:00+00:00", changed: true, base: "Akdeniz", underlying: "Akdeniz Pompa",
                        underlying_source: "Kural", rule_id: 3, rule_name: "Müşteri adı düzeltme" },
                CustomerGroup: { source: "Kural", rule_id: 5, rule_name: "Müşteri grubu" } } },
  { Id: 2, ManualState: null, Code: "MUS-B", Name: "Batı", Priority: 2, CustomerGroup: null, Segment: "B", _sources: {} },
  { Id: 3, ManualState: "Var / ERP Güncellendi", Code: "MUS-C", Name: "Ceyhan", Priority: 3, CustomerGroup: null, Segment: null,
    _sources: { Priority: { source: "Manuel", by: "Ayşe Planlama", at: "2026-11-12T11:20:00+00:00", changed: true, base: 8, underlying: 9, underlying_source: "ERP" } } },
];

function backend(save: Reply = { body: { saved: 1 } }, columns = COLUMNS, rows: object[] = ROWS) {
  const sent: { url: string; body: unknown }[] = [];
  mockApi({
    "/api/master-data/counts": { body: { data_version: 35, tabs: [] } },
    "/api/master-customer/columns": { body: { chunk_size: 100, columns, export: { title: "Müşteri", file_slug: "musteri", sync_max_rows: 10000, max_rows: 500000, file_hours: 24 } } },
    "/api/master-customer/views": { body: { views: [], default_view_id: null } },
    "/api/master-customer/query": (_url, init) => {
      const q = JSON.parse(String(init?.body)) as { offset?: number; limit?: number };
      const from = q.offset ?? 0;
      return { body: { rows: rows.slice(from, from + (q.limit ?? 100)), filtered: rows.length, total: rows.length } };
    },
    "/api/manual-values/remove": (url, init) => { sent.push({ url, body: JSON.parse(String(init?.body)) }); return { body: { removed: 1 } }; },
    "/api/manual-values": (url, init) => { sent.push({ url, body: JSON.parse(String(init?.body)) }); return save; },
  });
  return sent;
}

async function open(role = "Key user", save?: Reply, columns = COLUMNS, rows: object[] = ROWS) {
  const user = userEvent.setup();
  const sent = backend(save, columns, rows);
  renderApp("/veri/ana-veri?sekme=tedarikci-ve-musteri&tablo=musteri", meAs(role));
  await screen.findByText(String((rows[1] as { Code: string }).Code), {}, { timeout: 5000 });
  return { user, sent };
}

const toolbar = () => screen.getByTestId("table-scroll").parentElement!;
const paste = (target: HTMLElement, text: string) => {
  const event = createEvent.paste(target, { clipboardData: { getData: () => text } });
  fireEvent(target, event);
};

describe("hücre düzenleme standardı", () => {
  it("düz metin, başlıkta ✎; çift tıklama düzenleyiciyi açar, Enter taslağa alır ve alttaki hücreye geçer; Kaydet toplu gönderir", async () => {
    const { user, sent } = await open();
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.getByRole("columnheader", { name: /Müşteri adı/ })).toHaveTextContent("✎");
    expect(screen.getByRole("columnheader", { name: /Müşteri grubu/ })).not.toHaveTextContent("✎");
    const editor = await openEditor(user, cellOf("MUS-B", "Müşteri adı"));
    expect(editor).toHaveValue("Batı");
    await user.clear(editor);
    await user.type(editor, "Batı Pompa{Enter}");
    expect(cellOf("MUS-B", "Müşteri adı")).toHaveTextContent("Batı Pompa");
    expect(cellOf("MUS-B", "Müşteri adı")).toHaveClass("is-draft");
    await waitFor(() => expect(cellOf("MUS-C", "Müşteri adı")).toHaveClass("is-cursor"));
    await user.click(within(toolbar()).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(sent).toEqual([{ url: "/api/manual-values", body: { list: "master-customer", changes: [{ id: "2", field: "Name", value: "Batı Pompa" }] } }]));
  });

  it("tıklamak seçer; ok tuşlarıyla gezilir; yazmaya başlamak açar, Esc vazgeçer; seçenekli alanda liste", async () => {
    const { user } = await open();
    await user.click(cellOf("MUS-A", "Müşteri adı"));
    expect(cellOf("MUS-A", "Müşteri adı")).toHaveClass("is-cursor");
    await user.keyboard("{ArrowDown}{ArrowRight}");
    expect(cellOf("MUS-B", "Müşteri önceliği")).toHaveClass("is-cursor");
    await user.keyboard("7");
    const box = cellOf("MUS-B", "Müşteri önceliği").querySelector("input")!;
    expect(box).toHaveValue("7");
    await user.keyboard("{Escape}");
    expect(cellOf("MUS-B", "Müşteri önceliği")).toHaveTextContent("2");
    expect(cellOf("MUS-B", "Müşteri önceliği")).not.toHaveClass("is-draft");
    const select = await openEditor(user, cellOf("MUS-B", "Segment"));
    expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual(["", "A", "B"]);
  });

  it("köşe işareti; kaynak ipucu yalnız manuel değer ve kural sonucunda (ERP'den olduğu gibi gelen değerde yok); hücrede düğme yok", async () => {
    const { user } = await open();
    expect(cellOf("MUS-A", "Müşteri adı")).toHaveClass("sc-cell-manual", "is-changed");
    expect(cellOf("MUS-B", "Müşteri adı")).not.toHaveClass("sc-cell-manual");
    expect(within(cellOf("MUS-A", "Müşteri adı")).queryByRole("button")).toBeNull();   // köşe işareti metnin dışında, düğme yok
    expect(cellOf("MUS-B", "Müşteri adı").querySelector(".sc-cell-source")).toBeNull();   // ERP: ipucu yok
    await user.hover(cellOf("MUS-A", "Müşteri adı").querySelector(".sc-cell-source")!);
    const tip = await screen.findByRole("tooltip");
    expect([...tip.querySelectorAll("div")].map((d) => d.textContent)).toEqual([
      "Manuel değer: Manuel ad · Ayşe Planlama · 12.11.2026 14:20", "Kural sonucu güncellendi (Müşteri adı düzeltme): Akdeniz → Akdeniz Pompa"]);
    await user.unhover(cellOf("MUS-A", "Müşteri adı").querySelector(".sc-cell-source")!);
    await user.hover(cellOf("MUS-C", "Müşteri önceliği").querySelector(".sc-cell-source")!);
    expect(await screen.findByRole("tooltip")).toHaveTextContent("ERP'den gelen değer güncellendi: 8 → 9");
    await user.unhover(cellOf("MUS-C", "Müşteri önceliği").querySelector(".sc-cell-source")!);
    await user.hover(cellOf("MUS-A", "Müşteri grubu").querySelector(".sc-cell-source")!);   // manuel olmayan kolonda da kural
    expect(await screen.findByRole("tooltip")).toHaveTextContent(/^Kural: Müşteri grubu$/);
  });

  it("kaydetme ya hep ya hiç: tek hata özeti ve hücre ipucu", async () => {
    const { user } = await open("Key user", { status: 422, body: { error: { code: "validation", message: "Kaydedilmedi.", trace_id: "x",
      details: [{ id: "2", field: "Priority", problem: "Tam sayı girilmeli.", record: "MUS-B" }] } } });
    await setCell(user, "MUS-B", "Müşteri önceliği", "1,5");
    await user.click(within(toolbar()).getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Kaydedilmedi. MUS-B · Müşteri önceliği: tam sayı girilmeli.")).toBeInTheDocument();
    const cell = cellOf("MUS-B", "Müşteri önceliği");
    expect(cell).toHaveClass("is-invalid");
    await user.hover(cell.querySelector(".sc-cell-source")!);
    expect(await screen.findByRole("tooltip")).toHaveTextContent(/^Tam sayı girilmeli\.$/);
  });

  it("birden çok hata: hücre sayısıyla", async () => {
    const { user } = await open("Key user", { status: 422, body: { error: { code: "validation", message: "Kaydedilmedi.", trace_id: "x",
      details: [{ id: "2", field: "Priority", problem: "Tam sayı girilmeli.", record: "MUS-B" }, { id: "3", field: "Priority", problem: "Tam sayı girilmeli.", record: "MUS-C" }] } } });
    await setCell(user, "MUS-B", "Müşteri önceliği", "1,5");
    await user.click(within(toolbar()).getByRole("button", { name: "Kaydet" }));
    expect(await screen.findByText("Kaydedilmedi. 2 hücrede geçersiz değer var.")).toBeInTheDocument();
  });
});

describe("kaldırma", () => {
  it("sağ tıkta satır menüsü, hücre seçenekleri başta (hücrenin boş kısmında da: Kopyala · Manuel değeri kaldır · Detay; K-171); kaldırma taslaktır; Kaydet kaldırır", async () => {
    const { user, sent } = await open();
    const cell = cellOf("MUS-A", "Müşteri adı");
    const empty = createEvent.contextMenu(cell);   // metnin dışı: hücrenin kendisi
    fireEvent(cell, empty);
    expect(empty.defaultPrevented).toBe(true);   // tarayıcının menüsü çıkmaz
    expect(within(screen.getByRole("menu", { name: "MUS-A işlemleri" })).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Kopyala", "Manuel değeri kaldır", "Detay"]);
    expect(cell).toHaveClass("is-cursor");   // sağ tık hücreyi seçer
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    await user.hover(cell.querySelector(".sc-cell-source")!);
    expect(await screen.findByRole("tooltip")).toBeInTheDocument();
    fireEvent.contextMenu(cell.querySelector(".sc-cell-source")!);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();   // ipucu menüyü örtmez
    await user.click(within(screen.getByRole("menu", { name: "MUS-A işlemleri" })).getByRole("menuitem", { name: "Manuel değeri kaldır" }));
    expect(cellOf("MUS-A", "Müşteri adı")).toHaveTextContent("Akdeniz Pompa");   // alttaki değer görünür
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    await user.click(within(toolbar()).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(sent).toEqual([{ url: "/api/manual-values/remove", body: { list: "master-customer", items: [{ id: "1", field: "Name" }] } }]));
  });

  it("seçili hücrede Delete kaldırma taslağı; manuel değeri olmayan hücrede bir şey yapmaz", async () => {
    const { user } = await open();
    await user.click(cellOf("MUS-B", "Müşteri adı"));
    await user.keyboard("{Delete}");
    expect(cellOf("MUS-B", "Müşteri adı")).not.toHaveClass("is-draft");
    await user.click(cellOf("MUS-C", "Müşteri önceliği"));
    await user.keyboard("{Delete}");
    expect(cellOf("MUS-C", "Müşteri önceliği")).toHaveClass("is-draft");
    expect(cellOf("MUS-C", "Müşteri önceliği").querySelector(".sc-cell-removed")).toHaveTextContent("9");
    expect(cellOf("MUS-C", "Müşteri önceliği").querySelector(".sc-cell-editor")).toBeNull();
  });

  it("manuel değeri olmayan hücrede menü Kopyala · Detay; Kopyala ve Ctrl+C hücreyi ekrandaki biçimiyle kopyalar", async () => {
    const { user } = await open();
    const event = createEvent.contextMenu(cellOf("MUS-B", "Müşteri adı"));
    fireEvent(cellOf("MUS-B", "Müşteri adı"), event);
    expect(event.defaultPrevented).toBe(true);
    const menu = screen.getByRole("menu", { name: "MUS-B işlemleri" });
    expect(within(menu).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Kopyala", "Detay"]);
    await user.click(within(menu).getByRole("menuitem", { name: "Kopyala" }));
    await waitFor(async () => expect(await navigator.clipboard.readText()).toBe("Batı"));
    expect(screen.queryByText(/kopyalandı/i)).toBeNull();   // kopyalamada bildirim yok (K-171)
    await user.click(cellOf("MUS-C", "Müşteri önceliği"));
    fireEvent.keyDown(cellOf("MUS-C", "Müşteri önceliği"), { key: "c", ctrlKey: true });
    await waitFor(async () => expect(await navigator.clipboard.readText()).toBe("3"));
  });

  it("çoklu seçimde toplu (K-171): seçili satıra sağ tıkta \"Seçili n satır · Manuel değerleri kaldır\"; şeritte düğme yok; Kaydet kaldırır", async () => {
    const { user, sent } = await open();
    expect(screen.queryByRole("button", { name: /Manuel değerleri kaldır/ })).not.toBeInTheDocument();   // şeritte düğme yok
    const row = (code: string) => cellOf(code, "Müşteri adı").closest("tr") as HTMLElement;
    await user.keyboard("{Control>}");
    await user.click(row("MUS-B"));
    await user.keyboard("{/Control}");
    fireEvent.contextMenu(cellOf("MUS-B", "Müşteri adı"));
    let menu = screen.getByRole("menu", { name: "MUS-B işlemleri" });
    expect(within(menu).getByText("Seçili 1 satır")).toBeInTheDocument();
    await user.click(within(menu).getByRole("menuitem", { name: "Manuel değerleri kaldır" }));
    expect(await screen.findByText("Seçili kayıtlarda manuel değer yok.")).toBeInTheDocument();
    await user.keyboard("{Control>}");
    await user.click(row("MUS-B"));
    await user.click(row("MUS-A"));
    await user.click(row("MUS-C"));
    await user.keyboard("{/Control}");
    fireEvent.contextMenu(cellOf("MUS-C", "Müşteri adı"));
    menu = screen.getByRole("menu", { name: "MUS-C işlemleri" });
    expect(within(menu).getByText("Seçili 2 satır")).toBeInTheDocument();
    expect(within(menu).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Manuel değerleri kaldır", "Kopyala", "Detay"]);
    await user.click(within(menu).getByRole("menuitem", { name: "Manuel değerleri kaldır" }));
    await waitFor(() => expect(cellOf("MUS-A", "Müşteri adı")).toHaveClass("is-draft"));
    expect(cellOf("MUS-C", "Müşteri önceliği")).toHaveTextContent("9");
    await user.click(within(toolbar()).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(sent).toEqual([{ url: "/api/manual-values/remove", body: { list: "master-customer", items: [{ id: "1", field: "Name" }, { id: "3", field: "Priority" }] } }]));
  });
});

describe("Excel'den yapıştırma", () => {
  it("geçerli hücreler lila taslağa; alınmayanlar neden ve alan bazında sayıyla özetlenir (hücreler tek tek değil)", async () => {
    const { user } = await open();
    await user.click(cellOf("MUS-A", "Müşteri adı"));
    paste(cellOf("MUS-A", "Müşteri adı"), "Ada\t5\tYurt dışı\nBora\tçok\tİç\nCan\t7\n");
    expect(cellOf("MUS-A", "Müşteri adı")).toHaveTextContent("Ada");
    expect(cellOf("MUS-A", "Müşteri önceliği")).toHaveClass("is-draft");
    expect(cellOf("MUS-B", "Müşteri adı")).toHaveTextContent("Bora");
    expect(cellOf("MUS-B", "Müşteri önceliği")).toHaveTextContent("2");   // geçersiz: alınmadı
    const report = screen.getByText("5 hücre taslağa alındı, 3 hücre alınmadı.").closest(".sc-alert")!;
    expect(report).toHaveTextContent("Manuel değer girilemeyen alanlar: Müşteri grubu (2 hücre). Tam sayı olmayan değer: Müşteri önceliği (1 hücre).");
    expect(report).not.toHaveTextContent("MUS-A");
    expect(within(toolbar()).getByRole("button", { name: "Kaydet" })).toBeInTheDocument();
  });

  it("tablonun dışına taşan hücreler sayıyla", async () => {
    const { user } = await open();
    await user.click(cellOf("MUS-C", "Müşteri adı"));
    paste(cellOf("MUS-C", "Müşteri adı"), "Cem\nDuru\nEce");
    const report = screen.getByText("1 hücre taslağa alındı, 2 hücre alınmadı.").closest(".sc-alert")!;
    expect(report).toHaveTextContent("Tablonun dışında: 2 hücre.");
    expect(report).not.toHaveTextContent("Duru");
  });
});

describe("kaydırma ve klavye (K-172)", () => {
  const MANY = Array.from({ length: 300 }, (_, i) => ({ Id: i + 1, ManualState: null, Code: `M-${i}`, Name: `Ad ${i}`, Priority: i, CustomerGroup: null, Segment: null, _sources: {} }));
  const rowPx = Math.round(13 * ROW_REM);

  it("hücre seçiliyken fareyle kaydırma geri çekilmez; ok tuşu imleci sürdürür ve görünür alana getirir", async () => {
    const { user } = await open("Key user", undefined, COLUMNS, MANY);
    await user.click(cellOf("M-1", "Müşteri adı"));
    expect(cellOf("M-1", "Müşteri adı")).toHaveClass("is-cursor");
    const scroller = screen.getByTestId("table-scroll");
    for (const row of [40, 120, 200]) {   // imleç hücresi çizimden çıkar; kaydırma takılmaz
      await act(async () => {
        scroller.scrollTop = row * rowPx;
        fireEvent.scroll(scroller);
      });
      await screen.findByText(`M-${row}`);
      expect(scroller.scrollTop).toBe(row * rowPx);
    }
    expect(document.activeElement).toBe(scroller);   // odak tablo kutusunda: klavye çalışır
    scroller.scrollTo = ((opts: ScrollToOptions) => {   // jsdom'da yok: sanal kaydırmanın görünür alana getirmesi
      scroller.scrollTop = opts.top ?? scroller.scrollTop;
      fireEvent.scroll(scroller);
    }) as typeof scroller.scrollTo;
    await act(async () => {
      fireEvent.keyDown(scroller, { key: "ArrowDown" });
    });
    await waitFor(() => expect(cellOf("M-2", "Müşteri adı")).toHaveClass("is-cursor"));
    expect(scroller.scrollTop).toBeLessThan(200 * rowPx);
    await act(async () => {
      scroller.scrollTop = 150 * rowPx;   // yine fareyle: imleç yerinde, kaydırma serbest
      fireEvent.scroll(scroller);
    });
    await screen.findByText("M-150");
    expect(scroller.scrollTop).toBe(150 * rowPx);
  });
});

describe("manuel alanı olmayan tablo (K-172)", () => {
  const PLAIN = COLUMNS.map((c) => ({ ...c, manual: false }));
  it("hücre imleci, ✎ ve seçim kutusu yok; yalnız satır vurgusu", async () => {
    const { user } = await open("Key user", undefined, PLAIN);
    expect(screen.getByRole("columnheader", { name: /Müşteri adı/ })).not.toHaveTextContent("✎");
    expect(screen.queryByRole("checkbox", { name: /Seç:/ })).not.toBeInTheDocument();
    await user.click(cellOf("MUS-B", "Müşteri adı"));
    expect(cellOf("MUS-B", "Müşteri adı")).not.toHaveClass("is-cursor");
    expect(cellOf("MUS-B", "Müşteri adı").closest("tr")).toHaveClass("is-selected");
  });
});

describe("yetki", () => {
  it("End user düzenleyemez ve kaldıramaz; işaret ve ipucu görünür", async () => {
    const { user } = await open("End user");
    expect(screen.getByRole("columnheader", { name: /Müşteri adı/ })).not.toHaveTextContent("✎");
    await user.dblClick(cellOf("MUS-B", "Müşteri adı"));
    expect(cellOf("MUS-B", "Müşteri adı").querySelector(".sc-cell-editor")).toBeNull();
    expect(screen.queryByRole("button", { name: /Manuel değeri kaldır/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /Seç:/ })).not.toBeInTheDocument();
    expect(cellOf("MUS-A", "Müşteri adı")).toHaveClass("sc-cell-manual");
  });
});

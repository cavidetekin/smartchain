// Koşullu biçimlendirme (1.6, U-24, K-95, K-96): kuralların tek girişi kolon menüsü ("Koşullu biçim ekle…",
// "Biçimi yönet…"), alan karşılaştırması ve "Boşları 0 say", kendiliğinden okunur yazı rengi, ikon rengi ve yeri,
// tarih ve tarih-saat alanlarında bütün koşullar, sıra ve öncelik, aç/kapa, sil, etki, görünümle kayıt, Excel,
// kural değişince eski satırların ekranda kalması.
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { calls, dataRows, lastQuery, openTable, ruleGate, savedView, STANDARD_FIELDS, useTableTestSetup } from "./testBackend";
import type { FormatRule } from "./types";

useTableTestSetup();

const STOCK = 5;  // görünen kolonlarda Güvenlik stoğu (Code, Name, MaterialLevel, MaterialGroup, IsSellable, SafetyStock, UpdatedAt)
const NAME = 1;
const cell = (row: number, col = STOCK) => dataRows()[row].querySelectorAll("td")[col] as HTMLElement;

const columnMenu = async (label: string) => {
  await userEvent.click(screen.getByRole("button", { name: `${label} kolon işlemleri` }));
  return screen.findByRole("menu", { name: `${label} kolon işlemleri` });
};
const openPanel = async (label = "Malzeme kodu") => {
  const menu = await columnMenu(label);
  await userEvent.click(within(menu).getByRole("menuitem", { name: "Biçimi yönet…" }));
  return screen.findByRole("dialog", { name: "Koşullu biçim kuralları" });
};
const newRuleFrom = async (label: string) => {
  const menu = await columnMenu(label);
  await userEvent.click(within(menu).getByRole("menuitem", { name: "Koşullu biçim ekle…" }));
  return screen.findByRole("dialog", { name: "Yeni biçim kuralı" });
};
const pickColor = async (label: string, swatch: string) => {
  await userEvent.click(screen.getByRole("button", { name: new RegExp(`^${label}:`) }));
  const pop = await screen.findByRole("dialog", { name: label });
  await userEvent.click(within(pop).getByRole("button", { name: swatch }));
};

const rule = (id: string, condition: FormatRule["condition"], format: FormatRule["format"], extra: Partial<FormatRule> = {}): FormatRule =>
  ({ id, field: "SafetyStock", enabled: true, condition, format, ...extra });

const openWithRules = (rules: FormatRule[]) =>
  openTable({ views: { views: [savedView(5, "Kurallı", { columns: STANDARD_FIELDS.map((field) => ({ field })), rules })],
                       default_view_id: 5 } });

describe("kuralların girişi: kolon menüsü", () => {
  it("araç çubuğunda biçim düğmesi yok; menüde 'Koşullu biçim ekle…' ve 'Biçimi yönet…' var, 'Bu alanın kuralları' yok", async () => {
    await openTable();
    await screen.findByText("M-0");
    expect(screen.queryByRole("button", { name: /^Biçim/ })).toBeNull();
    const menu = await columnMenu("Güvenlik stoğu");
    const items = within(menu).getAllByRole("menuitem").map((m) => m.textContent);
    expect(items).toContain("Koşullu biçim ekle…");
    expect(items).toContain("Biçimi yönet…");
    expect(items.some((t) => t?.startsWith("Bu alanın kuralları"))).toBe(false);
  });

  it("'Koşullu biçim ekle…': bu kolonla yeni kural; zemin ve kalın; istekte kural, hücrede biçim ve ipucu", async () => {
    await openTable();
    await screen.findByText("M-0");
    const dialog = await newRuleFrom("Güvenlik stoğu");
    expect(within(dialog).getByRole("combobox", { name: "Alan" })).toHaveValue("SafetyStock");
    expect(within(dialog).getByRole("combobox", { name: "Koşul" })).toHaveValue("gt");
    expect(within(dialog).getByRole("button", { name: "Kaydet" })).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText("Değer"), "100");
    await userEvent.tab();
    await pickColor("Zemin", "Açık kiremit #f7dcd5");
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "Kalın" }));
    expect(within(dialog).getByTestId("rule-preview")).toHaveStyle({ backgroundColor: "#f7dcd5" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Kaydet" }));

    await waitFor(() => expect(lastQuery().rules).toEqual([{ field: "SafetyStock", condition: { op: "gt", value: 100 } }]));
    await waitFor(() => expect(cell(0)).toHaveStyle({ backgroundColor: "#f7dcd5" }));
    expect(cell(0).style.fontWeight).toBe("var(--fw-semibold)");
    expect(cell(0)).toHaveAttribute("title", "Koşullu biçim: Güvenlik stoğu > 100");
    expect(cell(1).style.backgroundColor).toBe("");                 // 12,25 tutmaz
    expect(screen.queryByRole("dialog")).toBeNull();                 // menüden açıldı: liste açılmaz
    expect(screen.getByRole("img", { name: "Kaydedilmemiş değişiklik" })).toBeInTheDocument();  // görünüm değişti (K-89)
    const panel = await openPanel("Güvenlik stoğu");
    expect(panel).toHaveTextContent("Güvenlik stoğu > 100");
  });

  it("'Biçimi yönet…' → Kural ekle: liste hangi kolondan açıldıysa o kolonla başlar; kaydedince liste geri açılır", async () => {
    await openTable();
    await screen.findByText("M-0");
    const panel = await openPanel("Malzeme adı");
    expect(panel).toHaveTextContent("Kural yok");
    await userEvent.click(within(panel).getByRole("button", { name: "Kural ekle" }));
    const dialog = await screen.findByRole("dialog", { name: "Yeni biçim kuralı" });
    expect(within(dialog).getByRole("combobox", { name: "Alan" })).toHaveValue("Name");
    await userEvent.type(within(dialog).getByLabelText("Değer"), "1");
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "Kalın" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    const back = await screen.findByRole("dialog", { name: "Koşullu biçim kuralları" });
    expect(back).toHaveTextContent("Malzeme adı eşittir '1'");
  });
});

describe("alan karşılaştırması", () => {
  it("yalnız aynı tipteki alanlar; 'Boşları 0 say' varsayılan açık; kapatılınca gövdede false", async () => {
    await openTable();
    await screen.findByText("M-0");
    let dialog = await newRuleFrom("Güvenlik stoğu");
    await userEvent.click(within(dialog).getByRole("radio", { name: "Alan" }));
    const ref = within(dialog).getByRole("combobox", { name: "Karşılaştırılan alan" });
    expect([...ref.querySelectorAll("option")].map((o) => o.textContent)).toEqual(["—", "Üretim süresi (gün)"]);  // gizli de
    await userEvent.selectOptions(ref, "ProductionLeadTimeDays");
    expect(within(dialog).getByRole("checkbox", { name: "Boşları 0 say" })).toBeChecked();
    await userEvent.click(within(dialog).getByRole("radio", { name: "Yukarı ok" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(lastQuery().rules).toEqual(
      [{ field: "SafetyStock", condition: { op: "gt", field_ref: "ProductionLeadTimeDays" } }]));
    await waitFor(() => expect(cell(3).querySelector(".sc-rule-icon")).not.toBeNull());  // 12,25 > boş (0)
    expect(cell(1).querySelector(".sc-rule-icon")).not.toBeNull();                         // 12,25 > 3

    const panel = await openPanel("Güvenlik stoğu");
    expect(panel).toHaveTextContent("Güvenlik stoğu > Üretim süresi (gün)");
    await userEvent.click(within(panel).getByRole("button", { name: "Güvenlik stoğu > Üretim süresi (gün) kuralını düzenle" }));
    dialog = await screen.findByRole("dialog", { name: "Biçim kuralını düzenle" });
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "Boşları 0 say" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(lastQuery().rules?.[0].condition).toEqual(
      { op: "gt", field_ref: "ProductionLeadTimeDays", empty_as_zero: false }));
    await waitFor(() => expect(cell(3).querySelector(".sc-rule-icon")).toBeNull());       // boş artık tutmaz
  });
});

describe("tarih ve tarih-saat alanları: bütün koşullarla kural kaydedilir", () => {
  const cases: [string, (d: HTMLElement) => Promise<void>, object][] = [
    ["Sonra", async (d) => { await userEvent.type(within(d).getByLabelText("Değer"), "28.10.2026"); }, { op: "gt", value: "2026-10-28" }],
    ["Önce", async (d) => { await userEvent.type(within(d).getByLabelText("Değer"), "01.11.2026"); }, { op: "lt", value: "2026-11-01" }],
    ["Aynı gün", async (d) => { await userEvent.type(within(d).getByLabelText("Değer"), "27.10.2026"); }, { op: "eq", value: "2026-10-27" }],
    ["Arası", async (d) => {
      await userEvent.type(within(d).getByLabelText("Başlangıç"), "01.10.2026");
      await userEvent.type(within(d).getByLabelText("Bitiş"), "31.10.2026");
    }, { op: "between", from: "2026-10-01", to: "2026-10-31" }],
    ["Göreli", async (d) => { await userEvent.click(within(d).getByRole("radio", { name: "Sonraki 4 hafta" })); },
     { op: "relative", value: "next_4_weeks" }],
    ["Boş", async () => {}, { op: "empty" }],
    ["Sonra (alan)", async (d) => {
      await userEvent.click(within(d).getByRole("radio", { name: "Alan" }));
      const ref = within(d).getByRole("combobox", { name: "Karşılaştırılan alan" });
      expect([...ref.querySelectorAll("option")].map((o) => o.textContent)).toEqual(["—", "Son giriş tarihi"]);
      expect(within(d).queryByRole("checkbox", { name: "Boşları 0 say" })).toBeNull();  // tarihte boşsa tutmaz
      await userEvent.selectOptions(ref, "LastReceiptDate");
    }, { op: "gt", field_ref: "LastReceiptDate" }],
  ];

  it.each(cases)("Son değişiklik zamanı (tarih-saat): %s", async (opLabel, fill, condition) => {
    await openTable();
    await screen.findByText("M-0");
    const dialog = await newRuleFrom("Son değişiklik zamanı");
    await userEvent.selectOptions(within(dialog).getByRole("combobox", { name: "Koşul" }),
                                  opLabel.replace(" (alan)", ""));
    await fill(dialog);
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "Kalın" }));
    // tarih alanından çıkmadan (odak alanda) Kaydet açık: tarih yazılırken işlenir
    const save = within(dialog).getByRole("button", { name: "Kaydet" });
    expect(save).toBeEnabled();
    await userEvent.click(save);
    await waitFor(() => expect(lastQuery().rules).toEqual([{ field: "UpdatedAt", condition }]));
  });

  it("Sonra: tarih yazıp doğrudan Kaydet'e (alandan çıkmadan, Enter'sız) basılabilir", async () => {
    await openTable();
    await screen.findByText("M-0");
    const dialog = await newRuleFrom("Son değişiklik zamanı");
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "Kalın" }));
    const input = within(dialog).getByLabelText("Değer");
    await userEvent.type(input, "28.10.2026");
    expect(input).toHaveFocus();
    expect(within(dialog).getByRole("button", { name: "Kaydet" })).toBeEnabled();
  });
});

describe("Her zaman (koşulsuz kolon biçimi)", () => {
  it("her tipin koşul listesinde en sonda; seçilince değer alanı gizlenir; gövdede op always", async () => {
    await openTable();
    await screen.findByText("M-0");
    for (const label of ["Güvenlik stoğu", "Malzeme adı", "Son değişiklik zamanı", "Satılabilir"]) {
      const dialog = await newRuleFrom(label);
      const ops = [...within(dialog).getByRole("combobox", { name: "Koşul" }).querySelectorAll("option")];
      expect(ops.at(-1)?.textContent).toBe("Her zaman");
      await userEvent.click(within(dialog).getByRole("button", { name: "Vazgeç" }));
    }
    const dialog = await newRuleFrom("Güvenlik stoğu");
    await userEvent.selectOptions(within(dialog).getByRole("combobox", { name: "Koşul" }), "Her zaman");
    expect(within(dialog).queryByLabelText("Değer")).toBeNull();
    expect(within(dialog).queryByRole("radio", { name: "Alan" })).toBeNull();
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "Kalın" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(lastQuery().rules).toEqual([{ field: "SafetyStock", condition: { op: "always" } }]));
    await waitFor(() => expect(dataRows().every((tr) => (tr.querySelectorAll("td")[STOCK] as HTMLElement).style.fontWeight)).toBe(true));
  });

  it("boş hücreler dahil kolonun bütün hücreleri; listede 'Kolon biçimi'; üstteki kural önce", async () => {
    const columns = [...STANDARD_FIELDS, "LastReceiptDate"].map((field) => ({ field }));
    const rules: FormatRule[] = [
      rule("a", { op: "always" }, { fill: "#eef0fb" }, { field: "LastReceiptDate" }),
      rule("b", { op: "empty" }, { fill: "#f7dcd5", bold: true }, { field: "LastReceiptDate" }),
    ];
    await openTable({ views: { views: [savedView(5, "Kolon", { columns, rules })], default_view_id: 5 } });
    const DATE = 7;
    await waitFor(() => expect(cell(0, DATE)).toHaveStyle({ backgroundColor: "#eef0fb" }));
    expect(cell(0, DATE)).toHaveTextContent("");                       // boş hücre (i % 3 === 0) de boyalı
    expect(cell(0, DATE).style.fontWeight).toBe("var(--fw-semibold)");  // kalın alttaki "boş" kuralından
    expect(cell(1, DATE)).toHaveStyle({ backgroundColor: "#eef0fb" });   // dolu hücre de
    const panel = await openPanel();
    expect(within(panel).getAllByRole("listitem")[0]).toHaveTextContent("Son giriş tarihi Kolon biçimi");
    within(panel).getAllByRole("listitem")[0].focus();
    await userEvent.keyboard("{Alt>}{ArrowDown}{/Alt}");                // "boş" kuralı üste: zemin onun
    expect(cell(0, DATE)).toHaveStyle({ backgroundColor: "#f7dcd5" });
    expect(cell(1, DATE)).toHaveStyle({ backgroundColor: "#eef0fb" });
  });
});

describe("biçim: otomatik yazı rengi, ikon rengi ve yeri", () => {
  it("ikonlar: uyarı ünlemsiz üçgen; nokta, uyarı, bayrak, yıldız içi dolu; oklar, onay, çarpı çizgi", async () => {
    await openTable();
    await screen.findByText("M-0");
    const dialog = await newRuleFrom("Güvenlik stoğu");
    const icon = (name: string) => within(dialog).getByRole("radio", { name }).querySelector("svg")!;
    expect(icon("Uyarı")).toHaveClass("lucide-triangle");
    for (const name of ["Nokta", "Uyarı", "Bayrak", "Yıldız"]) expect(icon(name)).toHaveClass("is-filled");
    for (const name of ["Yukarı ok", "Aşağı ok", "Onay", "Çarpı"]) expect(icon(name)).not.toHaveClass("is-filled");
  });

  it("yazı rengi 'Renksiz' ise koyu zeminde okunur renk kendiliğinden; uyarı yok; seçilen yazı rengine dokunulmaz", async () => {
    await openTable();
    await screen.findByText("M-0");
    const dialog = await newRuleFrom("Güvenlik stoğu");
    await pickColor("Zemin", "#002060");
    expect(within(dialog).getByTestId("rule-preview")).toHaveStyle({ color: "#ffffff" });
    expect(within(dialog).queryByText(/Okunması zor/)).toBeNull();
    expect(within(dialog).getByRole("button", { name: "Yazı rengi: Renksiz" })).toBeInTheDocument();
    await pickColor("Yazı rengi", "Hardal #d9a521");
    expect(within(dialog).getByTestId("rule-preview")).toHaveStyle({ color: "#d9a521" });
  });

  it("ikon varsayılan renginde; ikon rengi seçilebilir; sayıda değerin başında, metinde sonunda", async () => {
    await openWithRules([
      rule("a", { op: "gt", value: 100 }, { icon: "warning" }),
      rule("b", { op: "contains", value: "malzeme" }, { icon: "flag", icon_color: "#c00000" }, { field: "Name" }),
    ]);
    await waitFor(() => expect(cell(0).querySelector(".sc-rule-icon")).not.toBeNull());
    const stock = cell(0).querySelector(".sc-ruled")!;
    expect(stock).toHaveClass("is-start");
    expect(stock.firstElementChild).toHaveClass("sc-rule-icon");            // sayı: ikon başta
    expect(stock.firstElementChild).toHaveStyle({ color: "#d9a521" });      // uyarı: hardal
    const name = cell(0, NAME).querySelector(".sc-ruled")!;
    expect(name).toHaveClass("is-end");
    expect(name.lastElementChild).toHaveClass("sc-rule-icon");              // metin: ikon sonda
    expect(name.lastElementChild).toHaveStyle({ color: "#c00000" });        // seçilen ikon rengi
    expect(cell(0, NAME).querySelector(".sc-ruled-value")).toHaveTextContent("Malzeme 0");

    const panel = await openPanel();
    await userEvent.click(within(panel).getByRole("button", { name: /Güvenlik stoğu > 100 kuralını düzenle/ }));
    const dialog = await screen.findByRole("dialog", { name: "Biçim kuralını düzenle" });
    expect(within(dialog).getByRole("button", { name: "İkon rengi: Varsayılan" })).toBeInTheDocument();
    await pickColor("İkon rengi", "Petrol #2e7d7a");
    await userEvent.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await waitFor(() => expect(cell(0).querySelector(".sc-rule-icon")).toHaveStyle({ color: "#2e7d7a" }));
  });
});

describe("sıra, öncelik, aç/kapa, sil, etki", () => {
  const RULES = [
    rule("a", { op: "gt", value: 100 }, { fill: "#f7dcd5" }),
    rule("b", { op: "gt", value: 0 }, { fill: "#dce0f7", bold: true }),
  ];

  it("aynı özellikte üstteki kazanır; sıra değişince hemen geçerli; açıklama satırı ve satır sayısı yok", async () => {
    await openWithRules(RULES);
    await waitFor(() => expect(cell(0)).toHaveStyle({ backgroundColor: "#f7dcd5" }));
    expect(cell(0).style.fontWeight).toBe("var(--fw-semibold)");   // kalın alttaki kuraldan
    expect(cell(1)).toHaveStyle({ backgroundColor: "#dce0f7" });    // yalnız alttaki tutuyor

    const panel = await openPanel();
    expect(panel).not.toHaveTextContent(/\d+ satır/);           // kural başına satır sayısı gösterilmez
    expect(panel).not.toHaveTextContent("Üstteki kural");
    expect(panel).not.toHaveTextContent("Aynı biçim özelliğinde");

    const first = within(panel).getAllByRole("listitem")[0];
    first.focus();
    await userEvent.keyboard("{Alt>}{ArrowDown}{/Alt}");
    expect(within(panel).getAllByRole("listitem")[0]).toHaveAccessibleName(/^1\. kural: Güvenlik stoğu > 0/);
    expect(cell(0)).toHaveStyle({ backgroundColor: "#dce0f7" });   // b artık üstte
  });

  it("pasif kural istekte yok ve uygulanmaz; silinen kural hemen düşer", async () => {
    await openWithRules(RULES);
    await waitFor(() => expect(cell(0)).toHaveStyle({ backgroundColor: "#f7dcd5" }));
    const panel = await openPanel();
    await userEvent.click(within(panel).getByRole("checkbox", { name: "Güvenlik stoğu > 100 kuralı aktif" }));
    await waitFor(() => expect(lastQuery().rules).toEqual([{ field: "SafetyStock", condition: { op: "gt", value: 0 } }]));
    await waitFor(() => expect(cell(0)).toHaveStyle({ backgroundColor: "#dce0f7" }));
    await userEvent.click(within(panel).getByRole("button", { name: "Güvenlik stoğu > 0 kuralını sil" }));
    expect(cell(0).style.backgroundColor).toBe("");
    expect(within(panel).getAllByRole("listitem")).toHaveLength(1);
  });

  it("kural değişince eski satırlar yeni cevap gelene kadar ekranda kalır (yer tutucu yok)", async () => {
    await openWithRules(RULES);
    await waitFor(() => expect(cell(0)).toHaveStyle({ backgroundColor: "#f7dcd5" }));
    ruleGate.hold = true;
    const panel = await openPanel();
    await userEvent.click(within(panel).getByRole("checkbox", { name: "Güvenlik stoğu > 0 kuralı aktif" }));
    expect(document.querySelector("tr.is-placeholder")).toBeNull();
    expect(dataRows()[0]).toHaveTextContent("M-0");
    await act(async () => ruleGate.release());
    await waitFor(() => expect(lastQuery().rules).toHaveLength(1));
  });

  it("seçili satır: boyalı hücreye ayrı çerçeve sınıfı verilmez (satırın tamamında aynı işaret)", async () => {
    await openWithRules(RULES);
    await waitFor(() => expect(cell(0)).toHaveStyle({ backgroundColor: "#f7dcd5" }));
    await userEvent.click(dataRows()[0]);
    expect(dataRows()[0]).toHaveClass("is-selected");
    expect(dataRows()[0].querySelector("td.has-rule")).toBeNull();
    expect(cell(0)).toHaveStyle({ backgroundColor: "#f7dcd5" });   // zemin korunur
  });
});

describe("görünüm ve Excel", () => {
  it("gizli alanın kuralı listede 'alan gizli', istekte yok; görünümle kaydedilir; Excel'e aktif ve görünenler gider", async () => {
    const hidden = rule("h", { op: "gt", value: 1 }, { bold: true }, { field: "ProductionLeadTimeDays" });
    const visible = rule("v", { op: "gt", value: 100 }, { fill: "#f7dcd5", icon: "flag" });
    await openWithRules([visible, hidden]);
    await waitFor(() => expect(lastQuery().rules).toEqual([{ field: "SafetyStock", condition: { op: "gt", value: 100 } }]));
    const panel = await openPanel();
    expect(within(panel).getAllByRole("listitem")[1]).toHaveTextContent("alan gizli");

    await userEvent.click(within(panel).getByRole("button", { name: "Güvenlik stoğu > 100 kuralını düzenle" }));
    const dialog = await screen.findByRole("dialog", { name: "Biçim kuralını düzenle" });
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "Kalın" }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Kaydet" }));
    await screen.findByRole("dialog", { name: "Koşullu biçim kuralları" });  // listeden açıldı: liste geri açılır
    await userEvent.keyboard("{Escape}");

    await userEvent.click(screen.getByRole("button", { name: "Görünüm işlemleri" }));
    await userEvent.click(screen.getByRole("menuitem", { name: "Kaydet" }));
    await waitFor(() => expect(calls.views.some((c) => c.method === "PUT")).toBe(true));
    const saved = calls.views.find((c) => c.method === "PUT")!.body as { definition: { rules: FormatRule[] } };
    expect(saved.definition.rules.map((r) => [r.id, r.format])).toEqual([
      ["v", { fill: "#f7dcd5", icon: "flag", bold: true }], ["h", { bold: true }]]);

    await userEvent.click(screen.getByRole("button", { name: "Excel'e aktar" }));
    await userEvent.click(within(await screen.findByRole("dialog", { name: /Excel'e aktar/ })).getByRole("button", { name: "İndir" }));
    await waitFor(() => expect(calls.exports).toHaveLength(1));
    expect(calls.exports[0].body.rules.map((r) => r.id)).toEqual(["v"]);
  });
});

describe("renk seçici", () => {
  it("ok tuşlarıyla gezinilir; Diğer renk #rrggbb doğrulanır", async () => {
    await openTable();
    await screen.findByText("M-0");
    await newRuleFrom("Güvenlik stoğu");
    await userEvent.click(screen.getByRole("button", { name: "Yazı rengi: Renksiz" }));
    const pop = await screen.findByRole("dialog", { name: "Yazı rengi" });
    expect(within(pop).getByRole("button", { name: "İndigo #4f5bd5" })).toHaveFocus();
    await userEvent.keyboard("{ArrowRight}");
    expect(within(pop).getByRole("button", { name: "Açık indigo #dce0f7" })).toHaveFocus();
    const other = within(pop).getByRole("textbox");
    await userEvent.type(other, "zzz{Enter}");
    expect(within(pop).getByRole("alert")).toHaveTextContent("#rrggbb");
    await userEvent.clear(other);
    await userEvent.type(other, "#1E2257{Enter}");
    expect(screen.getByRole("button", { name: "Yazı rengi: #1e2257" })).toBeInTheDocument();
  });
});

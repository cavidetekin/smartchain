// Koşullu biçim (K-95, K-96) birim testleri: kontrast, palet, hücre biçiminin birleşmesi, çakışma, sıra, görünüm.
import { describe, expect, it } from "vitest";

import { contrast, isHex, READABLE, suggestText } from "../ui/contrast";
import { DEFAULT_TEXT, PRODUCT_COLORS, STANDARD_COLORS, THEME_GRID } from "../ui/palette";
import {
  activeRules, canUseFieldRef, cellFormat, dropRule, formatStyle, iconColor, moveRule, newRuleId, refCandidates, textColor,
} from "./rules";
import { COLUMNS } from "./testBackend";
import type { FormatRule, Row } from "./types";
import { fromDefinition, isDirty, toDefinition } from "./viewState";

const r = (id: string, field: string, format: FormatRule["format"], enabled = true): FormatRule =>
  ({ id, field, enabled, condition: { op: "empty" }, format });

describe("kontrast (WCAG)", () => {
  it("bilinen oranlar", () => {
    expect(contrast("#000000", "#ffffff")).toBeCloseTo(21, 1);
    expect(contrast("#ffffff", "#ffffff")).toBeCloseTo(1, 5);
    expect(contrast("#767676", "#ffffff")).toBeCloseTo(4.54, 1);
  });

  it.each(["#002060", "#ffc000", "#4472c4", "#f7dcd5", "#a5a5a5", "#808080", "#ffffff"])(
    "%s zeminde önerilen yazı okunur", (fill) => {
      expect(contrast(suggestText(fill, DEFAULT_TEXT), fill)).toBeGreaterThanOrEqual(READABLE);
    });

  it("açık zeminde varsayılan yazı rengi kalır, koyu zeminde beyaz", () => {
    expect(suggestText("#f7dcd5", DEFAULT_TEXT)).toBe(DEFAULT_TEXT);
    expect(suggestText("#002060", DEFAULT_TEXT)).toBe("#ffffff");
  });

  // Excel aynı hesabı yapar: tests/test_export_unit.py SUGGEST ile aynı örnekler (ekran ve Excel aynı renk)
  it.each([["#002060", "#ffffff"], ["#ffc000", "#1f2430"], ["#4472c4", "#ffffff"], ["#f7dcd5", "#1f2430"],
           ["#a5a5a5", "#1f2430"], ["#808080", "#131313"], ["#ffffff", "#1f2430"], ["#7f7f7f", "#131313"], ["#ff0000", "#330000"]])(
    "%s zeminde %s (Excel ile aynı)", (fill, expected) => expect(suggestText(fill, DEFAULT_TEXT)).toBe(expected));

  it("hex doğrulaması", () => {
    expect([isHex("#1e2257"), isHex("#1E2257"), isHex("1e2257"), isHex("#12345"), isHex("#gggggg")])
      .toEqual([true, true, false, false, false]);
  });
});

describe("palet (K-96)", () => {
  it("tema 6 × 10, ilk satır temel renkler; standart 10; ürün renkleri tokens'tan", () => {
    expect(THEME_GRID).toHaveLength(6);
    THEME_GRID.forEach((row) => expect(row).toHaveLength(10));
    expect(THEME_GRID[0][4]).toBe("#4472c4");
    expect(THEME_GRID.flat().every(isHex)).toBe(true);
    expect(new Set(THEME_GRID.map((row) => row[4])).size).toBe(6);  // tonlar birbirinden farklı
    expect(STANDARD_COLORS).toHaveLength(10);
    expect(PRODUCT_COLORS.find((p) => p.token === "indigo-500")?.hex).toBe("#4f5bd5");
    expect(PRODUCT_COLORS.find((p) => p.token === "status-over-bg")?.hex).toBe("#f7dcd5");
  });
});

describe("hücre biçimi ve liste", () => {
  const rules = [r("a", "SafetyStock", { fill: "#111111", icon: "flag" }), r("b", "SafetyStock", { fill: "#222222", bold: true }),
                 r("c", "Name", { color: "#333333" })];
  const row = (ids: string[]) => ({ Id: 1, _ruleIds: ids }) as Row;

  it("özellik bazında üstteki kazanır; yalnız o alanın kuralları", () => {
    expect(cellFormat(rules, row(["a", "b", "c"]), "SafetyStock")?.format).toEqual({ fill: "#111111", icon: "flag", bold: true });
    expect(cellFormat(rules, row(["b"]), "SafetyStock")?.format).toEqual({ fill: "#222222", bold: true });
    expect(cellFormat(rules, row(["c"]), "SafetyStock")).toBeNull();
    expect(cellFormat(rules, row([]), "Name")).toBeNull();
    expect(cellFormat(moveRule(rules, "b", -1), row(["a", "b"]), "SafetyStock")?.format.fill).toBe("#222222");  // sıra
    expect(cellFormat(rules.filter((x) => x.id !== "a"), row(["a", "b"]), "SafetyStock")?.format.fill).toBe("#222222");  // silinen düşer
  });

  it("yazı rengi seçilmemişse zemine göre okunur renk; seçilmişse dokunulmaz (K-96)", () => {
    expect(textColor({ fill: "#002060" })).toBe("#ffffff");
    expect(textColor({ fill: "#f7dcd5" })).toBe(DEFAULT_TEXT);
    expect(textColor({ fill: "#002060", color: "#1e2257" })).toBe("#1e2257");  // kullanıcının seçimi
    expect(textColor({ bold: true })).toBeUndefined();
    expect(formatStyle({ fill: "#4472c4" })).toEqual({ backgroundColor: "#4472c4", color: "#ffffff" });
  });

  it("ikon rengi: seçilmişse o, değilse ikonun varsayılanı", () => {
    expect(iconColor({ icon: "warning" })).toBe("#d9a521");   // hardal
    expect(iconColor({ icon: "cross" })).toBe("#c8452f");     // kiremit
    expect(iconColor({ icon: "check" })).toBe("#2f8f5b");     // yeşil
    expect([iconColor({ icon: "arrow_up" }), iconColor({ icon: "arrow_down" }), iconColor({ icon: "dot" })])
      .toEqual(["#4f5bd5", "#4f5bd5", "#4f5bd5"]);            // indigo
    expect([iconColor({ icon: "flag" }), iconColor({ icon: "star" })]).toEqual(["#2e7d7a", "#2e7d7a"]);  // petrol
    expect(iconColor({ icon: "star", icon_color: "#c00000" })).toBe("#c00000");
    expect(iconColor({ bold: true })).toBeUndefined();
  });

  it("aktif kurallar: pasif, gizli alan ve bilinmeyen karşılaştırma alanı hariç", () => {
    const known = new Set(COLUMNS.map((c) => c.field));
    const withRef = { ...r("d", "SafetyStock", { bold: true }), condition: { op: "gt" as const, field_ref: "Gone" } };
    const list = [rules[0], { ...rules[1], enabled: false }, r("e", "ProductionLeadTimeDays", { bold: true }), withRef];
    expect(activeRules(list, ["Code", "SafetyStock"], known).map((x) => x.id)).toEqual(["a"]);
  });

  it("alan karşılaştırması yalnız sayı ve tarihte gt/lt/eq; adaylar aynı tipte", () => {
    const stock = COLUMNS.find((c) => c.field === "SafetyStock")!;
    const name = COLUMNS.find((c) => c.field === "Name")!;
    expect([canUseFieldRef(stock, "gt"), canUseFieldRef(stock, "between"), canUseFieldRef(name, "equals")]).toEqual([true, false, false]);
    expect(refCandidates(stock, COLUMNS).map((c) => c.field)).toEqual(["ProductionLeadTimeDays"]);
  });

  it("sürükle-bırak ve kimlik", () => {
    expect(dropRule(rules, "c", "a", "before").map((x) => x.id)).toEqual(["c", "a", "b"]);
    expect(dropRule(rules, "a", "c", "after").map((x) => x.id)).toEqual(["b", "c", "a"]);
    expect(newRuleId([r("k3", "Name", {}), r("x", "Name", {})])).toBe("k4");
  });
});

describe("görünüm (K-89)", () => {
  it("kurallar içerikte; bilinmeyen alanın kuralı açılışta atılır; değişiklik 'Kaydedilmedi' sayılır", () => {
    const def = {
      v: 1 as const, columns: [{ field: "Code" }], pinned: 0, sort: [], filters: [], group_by: [],
      rules: [r("a", "SafetyStock", { bold: true }), r("b", "Gone", { bold: true }),
              { ...r("c", "SafetyStock", { bold: true }), condition: { op: "lt" as const, field_ref: "Gone" } }],
    };
    const state = fromDefinition(def, COLUMNS);
    expect(state.rules.map((x) => x.id)).toEqual(["a"]);
    expect(toDefinition(state).rules?.map((x) => x.id)).toEqual(["a"]);
    const base = toDefinition(state);
    expect(isDirty(state, base)).toBe(false);
    expect(isDirty({ ...state, rules: [{ ...state.rules[0], enabled: false }] }, base)).toBe(true);
    expect(isDirty({ ...state, rules: [{ ...state.rules[0], format: { fill: "#ffffff" } }] }, base)).toBe(true);
  });
});

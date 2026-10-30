// Stil sistemi (K-85, docs/12): değerler, kontrastlar, U-2 durum renklerinin yeri, U-5 seri sırası, rem (U-23).
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { ROW_REM } from "../table/DataTable";
import { contrast as contrastOf, luminance } from "../ui/contrast";

const read = (name: string) => readFileSync(new URL(name, import.meta.url), "utf-8");
const tokens = read("./tokens.css");
const sheets = { "app.css": read("./app.css"), "components.css": read("./components.css") };

function token(name: string): string {
  const m = tokens.match(new RegExp(`--${name}:[ \\t]*([^;]+);`));
  if (!m) throw new Error(`--${name} yok`);
  const v = m[1].trim();
  const ref = v.match(/^var\(--([\w-]+)\)$/);
  return ref ? token(ref[1]) : v.toLowerCase();
}

/** Belirteç adlarıyla kontrast (ui/contrast ile aynı hesap). */
function contrast(a: string, b: string): number {
  return contrastOf(token(a), token(b));
}

/** CSS kurallarını (seçici, gövde) olarak ayırır; yorumlar atılır. */
function rules(css: string): { selector: string; body: string }[] {
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, "");
  return [...clean.matchAll(/([^{}]+)\{([^}]*)\}/g)].map((m) => ({ selector: m[1].trim(), body: m[2] }));
}

describe("K-85 değerleri (mockup'lardan)", () => {
  it.each([
    ["status-risk", "#d9a521"], ["status-risk-bg", "#f7ebc4"], ["status-risk-text", "#6b5200"],
    ["status-over", "#c8452f"], ["status-over-bg", "#f7dcd5"], ["status-over-bg-soft", "#fbede8"],
    ["status-over-text", "#9a2e1a"], ["status-over-text-strong", "#8a3612"], ["status-over-border", "#ebcab8"],
    ["status-ok", "#2f8f5b"], ["status-ok-bg", "#ddf0e4"], ["status-ok-text", "#254d3b"],
    ["info-bg", "#eef0fb"], ["info-text", "#1e2257"], ["info-border", "#dce0f7"],
    ["occ-low-bg", "#f4f5f7"], ["occ-normal-bg", "#eef0fb"], ["occ-high-bg", "#c5cbf2"], ["occ-risk-bg", "#f2d98e"],
    ["occ-over-bg", "#f4cfc4"], ["occ-over-text", "#8a3612"], ["field-border", "#b4b9c2"], ["field-border-focus", "#4f5bd5"], ["focus-ring", "#dfe1f7"],
    ["cell-frozen-bg", "#e6e8ec"],
  ])("--%s = %s", (name, value) => {
    expect(token(name)).toBe(value);
  });
});

describe("kontrast (WCAG AA)", () => {
  it.each([
    ["occ-low-text", "occ-low-bg"], ["occ-normal-text", "occ-normal-bg"], ["occ-high-text", "occ-high-bg"],
    ["occ-risk-text", "occ-risk-bg"], ["occ-over-text", "occ-over-bg"],
    ["status-ok-text", "status-ok-bg"], ["status-risk-text", "status-risk-bg"], ["status-over-text", "status-over-bg"],
    ["info-text", "info-bg"], ["neutral-text", "neutral-bg"],
    ["status-ok-text", "status-ok-bg-soft"], ["status-risk-text", "status-risk-bg-soft"],
    ["status-over-text-strong", "status-over-bg-soft"],
    ["sidebar-active-text", "indigo-500"], ["status-over-on", "status-over"], ["text", "surface"],
    ["status-over-text-strong", "surface"], ["status-over-text", "surface"], ["cell-frozen-text", "cell-frozen-bg"],
    ["text-muted", "surface"], ["text-muted", "bg"],
  ])("%s / %s ≥ 4,5:1", (fg, bg) => {
    expect(contrast(fg, bg)).toBeGreaterThanOrEqual(4.5);
  });

  it.each(["table-group-1-bg", "table-group-2-bg", "table-row-selected-bg", "table-row-hover-bg", "surface"])(
    "tablo zemini %s: yazı ve soluk yazı ≥ 4,5:1", (bg) => {
      expect(contrast("text", bg)).toBeGreaterThanOrEqual(4.5);
      expect(contrast("text-muted", bg)).toBeGreaterThanOrEqual(4.5);
    });

  it("tablo başlığı: #1E2257 yazı ve soluk ikon zeminde ≥ 4,5:1", () => {
    expect(contrast("table-head-text", "table-head-bg")).toBeGreaterThanOrEqual(4.5);
    expect(contrast("text-muted", "table-head-bg")).toBeGreaterThanOrEqual(4.5);
  });

  it("KPI'daki kiremit değer beyaz kartta ≥ 4,5:1", () => {
    expect(contrast("status-over", "surface")).toBeGreaterThanOrEqual(4.5);
  });
});

describe("U-2: durum renkleri yalnız durum bileşenlerinde", () => {
  // İzin verilen seçiciler: rozet, uyarı, doluluk, hücre işaretleri, form hatası, KPI durumu,
  // geri alınamaz işlem butonu (K-85 istisnası), bağlantı noktası.
  const ALLOWED = /\.sc-tag--(ok|risk|critical)|\.sc-alert--(ok|risk|error)|\.sc-occ--|\.sc-cell--shortage|\.sc-field(\.is-invalid|-error)|\.sc-kpi--(ok|risk|over)|\.sc-btn--danger|\.sc-dot/;

  it.each(Object.entries(sheets))("%s", (_, css) => {
    const misuse = rules(css)
      .filter((r) => /var\(--(status-|occ-)/.test(r.body))
      .filter((r) => !ALLOWED.test(r.selector))
      .map((r) => r.selector);
    expect(misuse).toEqual([]);
  });
});

describe("tablo renkleri (K-85, docs/12; bütün tablolar ortak)", () => {
  it.each([
    ["table-head-bg", "#dce0f7"], ["table-head-text", "#1e2257"], ["table-head-border", "#c5cbf2"], ["table-border", "#c5cbf2"],
    ["table-group-1-bg", "#eceef7"], ["table-group-1-border", "#e1e4ee"], ["table-group-2-bg", "#f7f8fc"],
    ["table-row-selected-bg", "#eef0fb"], ["table-row-hover-bg", "#f4f5fb"],
  ])("--%s = %s", (name, value) => expect(token(name)).toBe(value));

  it("başlık, grup, seçili, üzerine gelinen ve normal satır birbirinden ayrı; gruplar başlıktan açık", () => {
    const names = ["table-head-bg", "table-group-1-bg", "table-group-2-bg", "table-row-selected-bg", "table-row-hover-bg", "surface"];
    expect(new Set(names.map(token)).size).toBe(names.length);
    const lum = (n: string) => luminance(token(n));
    expect(lum("table-group-1-bg")).toBeGreaterThan(lum("table-head-bg"));
    expect(lum("table-group-2-bg")).toBeGreaterThan(lum("table-group-1-bg"));
    expect(lum("surface")).toBeGreaterThan(lum("table-group-2-bg"));
  });

  it("tablo stilleri değerleri değişkenlerden alır; grup satırı üzerine gelince değişmez", () => {
    const css = rules(sheets["components.css"]);
    const body = (sel: string) => css.find((r) => r.selector === sel)?.body ?? "";
    expect(body(".sc-table-grid thead th")).toMatch(/var\(--table-head-bg\)/);
    expect(body(".sc-table-grid thead th")).toMatch(/var\(--table-head-text\)/);
    expect(body(".sc-table-scroll")).toMatch(/var\(--table-border\)/);  // çerçeve başlık satırından başlar
    expect(body(".sc-table-toolbar")).not.toMatch(/background|border/);    // araç çubuğu sayfa zemininde
    expect(body(".sc-table-status")).not.toMatch(/background|border/);
    expect(body(".sc-table")).toMatch(/gap:\s*var\(--table-toolbar-gap\)/);
    expect(token("table-toolbar-gap")).toBe("0.5rem");
    expect(body(".sc-table-grid tr.sc-table-row:hover td")).toMatch(/var\(--table-row-hover-bg\)/);
    expect(body(".sc-table-grid tr.sc-table-row.is-selected td")).toMatch(/var\(--table-row-selected-bg\)/);
    expect(css.filter((r) => r.selector.includes("sc-table-group") && r.selector.includes(":hover"))).toEqual([]);
  });

  it("grup adı 1. düzey 600, alt düzey 500; başlık ikonları üzerine gelince ya da odakta, aktif filtre her zaman", () => {
    const css = rules(sheets["components.css"]);
    const body = (sel: string) => css.find((r) => r.selector === sel)?.body ?? "";
    expect(body(".sc-table-group--1 .sc-tgroup-value")).toMatch(/var\(--fw-semibold\)/);
    expect(body(".sc-table-group--2 .sc-tgroup-value")).toMatch(/var\(--fw-medium\)/);
    expect(token("fw-semibold")).toBe("600");
    expect(token("fw-medium")).toBe("500");
    expect(body(".sc-table-head-tools .sc-table-filter-btn")).toMatch(/opacity:\s*0/);
    const shown = css.find((r) => r.selector.includes("th:hover") && r.selector.includes("th:focus-within")
                                  && r.selector.includes(".is-active"));
    expect(shown?.body).toMatch(/opacity:\s*1/);
  });
});

describe("U-5: grafik serileri", () => {
  const series = [1, 2, 3, 4, 5, 6].map((i) => `chart-${i}`);

  it("sıra indigo, petrol, hardal, kurşun, erik, kahve", () => {
    expect(series.map(token)).toEqual(["#4f5bd5", "#2e7d7a", "#b8860b", "#5a606b", "#8e4585", "#8a6440"]);
  });

  it.each(series)("%s beyaz zeminde ≥ 3:1", (name) => {
    expect(contrast(name, "surface")).toBeGreaterThanOrEqual(3);
  });

  it("kiremit ve kırmızı seri değil (durum rengi)", () => {
    const over = ["status-over", "status-over-text", "status-over-text-strong", "occ-over-bg"].map(token);
    for (const name of series) {
      expect(over).not.toContain(token(name));
      const [r, g, b] = [1, 3, 5].map((i) => parseInt(token(name).slice(i, i + 2), 16));
      expect(r > 1.5 * g && r > 1.5 * b).toBe(false); // baskın kırmızı ton yok
    }
  });
});

describe("K-86: yazı tipleri", () => {
  it("sayı fontu Inter; JetBrains Mono ve --font-mono yok", () => {
    expect(tokens).toMatch(/--font-num:\s*"Inter"/);
    expect(tokens).toMatch(/--font-sans:\s*"Instrument Sans"/);
    for (const css of [tokens, ...Object.values(sheets)]) expect(css).not.toMatch(/font-mono|JetBrains/);
  });

  it.each(Object.entries(sheets))("%s: --font-num her yerde eşit genişlikte rakamla", (_, css) => {
    const loose = rules(css)
      .filter((r) => r.body.includes("var(--font-num)") && !r.body.includes("tabular-nums"))
      .map((r) => r.selector);
    expect(loose).toEqual([]);
  });
});

describe("tek kaynak ve ölçek (K-85, U-23)", () => {
  it.each(Object.entries(sheets))("%s renk sabiti içermez", (_, css) => {
    expect(css.match(/#[0-9a-f]{3,8}\b|rgba?\(/gi)).toBeNull();
  });

  it("app.css (kabuk) ile components.css aynı sınıfı tanımlamaz", () => {
    // Tanımlanan sınıf, seçicinin ilk sınıfıdır (".sc-popover .sc-segment" sc-popover'ı tanımlar, segmenti yalnız ayarlar).
    const defined = (css: string) => new Set(rules(css).flatMap((r) => r.selector.split(","))
      .map((sel) => sel.trim().match(/^\.(sc-[\w-]+)/)?.[1]).filter((c): c is string => Boolean(c)));
    const shell = defined(sheets["app.css"]);
    expect([...defined(sheets["components.css"])].filter((c) => shell.has(c))).toEqual([]);
  });

  it("components.css ölçüleri rem; px yalnız 1–2 px çizgi", () => {
    const px = [...sheets["components.css"].matchAll(/(\d*\.?\d+)px/g)].map((m) => m[1]);
    expect(px.filter((v) => v !== "1" && v !== "2")).toEqual([]);
  });

  it("yazı ölçeği standart 13 px'te 11…28 px", () => {
    const px = (name: string) => Math.round(parseFloat(token(name)) * 13);
    expect(["xs", "sm", "base", "md", "lg", "xl", "2xl", "kpi"].map((s) => px(`fs-${s}`)))
      .toEqual([11, 12, 13, 14, 16, 18, 24, 28]);
    expect([1, 2, 3, 4, 5, 6, 8].map((i) => px(`space-${i}`))).toEqual([4, 8, 12, 16, 20, 24, 32]);
  });

  it("tarih kutusu gg.aa.yyyy'yi her yazı boyutunda tam gösterir: en az 10 ch + iç boşluk, eşit genişlikte rakam", () => {
    const min = tokens.match(/--date-input-min:\s*calc\((\d+(?:\.\d+)?)ch \+ 2 \* var\(--space-3\) \+ 2px\)/);
    expect(min).not.toBeNull();
    expect(Number(min![1])).toBeGreaterThanOrEqual(10);  // ch yazı boyutuyla ölçeklenir (U-23); px sabit yok
    const css = rules(sheets["components.css"]);
    const input = css.find((r) => r.selector === ".sc-date .sc-input")!;
    expect(input.body).toMatch(/min-width:\s*var\(--date-input-min\)/);
    expect(input.body).not.toMatch(/min-width:\s*0/);
    const date = css.find((r) => r.selector === ".sc-input--date")!;
    expect(date.body).toMatch(/var\(--font-num\)/);
    expect(date.body).toMatch(/tabular-nums/);
  });

  it("filtre menüsü içeriğe göre genişler; iki alan sığmazsa alt alta", () => {
    const css = rules(sheets["components.css"]);
    expect(css.find((r) => r.selector === ".sc-table-pop")!.body).toMatch(/width:\s*max-content/);
    const pair = css.find((r) => r.selector === ".sc-table-pop-pair")!.body;
    expect(pair).toMatch(/display:\s*flex/);
    expect(pair).toMatch(/flex-wrap:\s*wrap/);
  });

  it("tablo satırı 13 px'te 28 px; DataTable aynı değeri kullanır (U-23)", () => {
    expect(token("row-height")).toBe(`${ROW_REM}rem`);
    expect(Math.round(ROW_REM * 13)).toBe(28);
  });
});

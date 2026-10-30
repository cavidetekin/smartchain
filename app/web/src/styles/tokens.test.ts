// Kenar menü renkleri tokens.css'ten gelir ve koyu zeminde okunur (WCAG AA: en az 4,5:1).
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { contrast } from "../ui/contrast";

const read = (name: string) => readFileSync(new URL(name, import.meta.url), "utf-8");
const tokens = read("./tokens.css");
const app = read("./app.css");

function token(name: string): string {
  const m = tokens.match(new RegExp(`--${name}:[ \\t]*([^;]+);`));
  if (!m) throw new Error(`--${name} yok`);
  const v = m[1].trim();
  const ref = v.match(/^var\(--([\w-]+)\)$/);
  return ref ? token(ref[1]) : v;
}

describe("kenar menü (K-84, açık indigo)", () => {
  const bg = token("sidebar-bg");
  const hex = (name: string) => token(name).toLowerCase();

  it("K-84'teki değerler", () => {
    expect([hex("sidebar-bg"), hex("sidebar-border"), hex("sidebar-brand")]).toEqual(["#eef0fb", "#dce0f7", "#1e2257"]);
    expect([hex("sidebar-group"), hex("sidebar-text"), hex("sidebar-icon")]).toEqual(["#4a5180", "#1f2329", "#5a6290"]);
    expect([hex("sidebar-sub-text"), hex("sidebar-sub-icon")]).toEqual(["#3f444d", "#6e76a8"]);
    expect([hex("sidebar-active-bg"), hex("sidebar-active-text"), hex("sidebar-hover")]).toEqual(["#4f5bd5", "#ffffff", "#dce0f7"]);
    expect([hex("sidebar-disabled"), hex("sidebar-field"), hex("sidebar-field-border")]).toEqual(["#5a6290", "#ffffff", "#dce0f7"]);
    expect([hex("bg"), hex("surface")]).toEqual(["#f7f8fa", "#ffffff"]);
    expect([token("sidebar-group-weight"), token("sidebar-active-weight"), token("sidebar-group-tracking")])
      .toEqual(["600", "600", "0.08em"]);
  });

  it("ölçüler standart yazı boyutunda (13 px): menü 256 px, grup başlığı 11 px", () => {
    const px = (name: string) => parseFloat(token(name)) * 13;
    expect(px("sidebar-width")).toBeCloseTo(256, 0);
    expect(px("sidebar-group-size")).toBeCloseTo(11, 0);
  });

  it("iç boşluk standart boyutta 10 px + 8 px; logo, arama, grup başlığı ve ekranlar aynı sol hizada", () => {
    const px = (name: string) => parseFloat(token(name)) * 13;
    expect(px("sidebar-pad-x")).toBeCloseTo(10, 0);
    expect(px("sidebar-item-pad-x")).toBeCloseTo(8, 0);
    const rule = (selector: string) => {
      const start = app.indexOf(`${selector} {`);
      expect(start, selector).toBeGreaterThanOrEqual(0);
      return app.slice(start, app.indexOf("}", start));
    };
    // Kapsayıcılar kenardan pad-x içeride (seçili zemin kenara değmez), içerik ayrıca item-pad-x içeride.
    expect(rule(".sc-menu")).toContain("padding: 0 var(--sidebar-pad-x)");
    expect(rule(".sc-search")).toContain("margin: 0 var(--sidebar-pad-x)");
    expect(rule(".sc-search")).toContain("calc(var(--sidebar-item-pad-x) - 1px)");
    expect(rule(".sc-brand")).toContain("calc(var(--sidebar-pad-x) + var(--sidebar-item-pad-x))");
    expect(rule(".sc-group-head")).toContain("padding: 0.35rem var(--sidebar-item-pad-x)");
    expect(rule(".sc-item")).toContain("padding: 0.45rem var(--sidebar-item-pad-x)");
  });

  it.each(["sidebar-text", "sidebar-group", "sidebar-sub-text", "sidebar-disabled", "sidebar-muted"])(
    "%s menü zemininde ≥ 4,5:1", (name) => {
      expect(contrast(token(name), bg)).toBeGreaterThanOrEqual(4.5);
    });

  it("ikonlar ≥ 3:1; seçili ekran ve üzerine gelince yazı ≥ 4,5:1; arama kutusu okunur", () => {
    expect(contrast(token("sidebar-icon"), bg)).toBeGreaterThanOrEqual(3);
    expect(contrast(token("sidebar-sub-icon"), bg)).toBeGreaterThanOrEqual(3);
    expect(contrast(token("sidebar-active-text"), token("sidebar-active-bg"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(token("sidebar-text"), token("sidebar-hover"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(token("sidebar-sub-text"), token("sidebar-hover"))).toBeGreaterThanOrEqual(4.5);
    expect(contrast(token("sidebar-text"), token("sidebar-field"))).toBeGreaterThanOrEqual(4.5);
  });

  it("app.css renkleri koda sabit yazmaz, tokens.css'ten alır", () => {
    expect(app.match(/#[0-9a-f]{3,8}\b|rgba?\(/gi)).toBeNull();
  });
});

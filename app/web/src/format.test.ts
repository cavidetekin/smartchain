// Türkçe biçim (U-19).
import { describe, expect, it } from "vitest";

import { fold, formatDate, formatDateTime, formatNumber, parseTrDate, parseTrNumber, weekLabel } from "./format";

describe("Türkçe biçim", () => {
  it("sayılar 1.234,5", () => {
    expect(formatNumber(1234.5, 1)).toBe("1.234,5");
    expect(formatNumber(1234567)).toBe("1.234.567");
  });

  it("tarih gg.aa.yyyy, saat yerel", () => {
    expect(formatDate(new Date(2026, 9, 3))).toBe("03.10.2026");
    expect(formatDateTime(new Date("2026-10-27T09:20:00+00:00"))).toBe("27.10.2026 12:20"); // TZ Europe/Istanbul
  });

  it("hafta H44", () => {
    expect(weekLabel(new Date(2026, 9, 27))).toBe("H44");
  });

  it("Türkçe büyük/küçük harf", () => {
    expect(fold("SİSTEM IŞIK")).toBe("sistem ışık");
  });
});

describe("Türkçe giriş ayrıştırma", () => {
  it.each([
    ["1.234,5", 1234.5], ["1234,5", 1234.5], ["-12", -12], ["1.234.567", 1234567], [" 42 ", 42], ["0,25", 0.25],
  ])("%s → %s", (text, n) => expect(parseTrNumber(text)).toBe(n));

  it.each(["", "1,234.5", "12.34", "abc", "1.2345", "1,,2"])("'%s' geçersiz", (text) => {
    expect(parseTrNumber(text)).toBeNull();
  });

  it("tarih gg.aa.yyyy", () => {
    expect(parseTrDate("27.10.2026")).toEqual(new Date(2026, 9, 27));
    expect(parseTrDate("1.2.2026")).toEqual(new Date(2026, 1, 1));
    expect(parseTrDate("31.02.2026")).toBeNull();
    expect(parseTrDate("2026-10-27")).toBeNull();
  });
});

// Türkçe biçim (U-19).
import { describe, expect, it } from "vitest";

import { fold, formatDate, formatDateTime, formatNumber, weekLabel } from "./format";

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

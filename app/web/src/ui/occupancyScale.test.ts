// Doluluk eşikleri (K-85): parametre; varsayılanlar bugünkü değerler, müşteriye göre değişir (7.5).
import { describe, expect, it } from "vitest";

import { DEFAULT_THRESHOLDS, legendLabels, occupancyLevel, type OccupancyThresholds } from "./occupancyScale";

describe("varsayılan eşikler (40 / 70 / 90 / 100)", () => {
  it.each([
    [0, "low"], [39, "low"], [39.4, "low"], [39.5, "normal"], [40, "normal"], [69, "normal"], [70, "high"],
    [89, "high"], [90, "risk"], [100, "risk"], [100.4, "risk"], [100.6, "over"], [112, "over"],
  ])("%s → %s", (value, level) => {
    expect(occupancyLevel(value as number)).toBe(level);
  });

  it("lejant metinleri eşiklerden", () => {
    expect(DEFAULT_THRESHOLDS).toEqual({ low: 40, normal: 70, risk: 90, over: 100 });
    expect(legendLabels()).toEqual({
      low: "< %40", normal: "%40–69", high: "%70–89", risk: "Risk %90–100", over: "Aşırı yük > %100",
    });
  });
});

describe("farklı eşik seti (30 / 60 / 85 / 95)", () => {
  const t: OccupancyThresholds = { low: 30, normal: 60, risk: 85, over: 95 };

  it.each([
    [29, "low"], [30, "normal"], [59, "normal"], [60, "high"], [84, "high"], [85, "risk"], [95, "risk"],
    [95.4, "risk"], [95.6, "over"], [100, "over"],
  ])("%s → %s", (value, level) => {
    expect(occupancyLevel(value as number, t)).toBe(level);
  });

  it("lejant yeni eşikleri yazar", () => {
    expect(legendLabels(t)).toEqual({
      low: "< %30", normal: "%30–59", high: "%60–84", risk: "Risk %85–95", over: "Aşırı yük > %95",
    });
  });
});

it("sırasız eşik hata verir", () => {
  expect(() => occupancyLevel(50, { low: 70, normal: 40, risk: 90, over: 100 })).toThrow(/sırasız/);
});

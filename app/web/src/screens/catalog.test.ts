// Ekran kataloğu: menünün tek tanımı (K-82, docs/12).
import { describe, expect, it } from "vitest";

import { childrenOf, GROUPS, SCREENS } from "./catalog";

describe("ekran kataloğu", () => {
  it("25 ekranı birer kez içerir", () => {
    const nos = SCREENS.map((s) => s.no).sort();
    expect(nos).toEqual(Array.from({ length: 25 }, (_, i) => String(i + 1).padStart(2, "0")));
    expect(new Set(SCREENS.map((s) => s.path)).size).toBe(25);
  });

  it("grup sırası K-82'deki gibi", () => {
    expect(GROUPS.map((g) => g.id)).toEqual(["planlama", "takip", "veri", "parametre", "yonetim"]);
    expect(SCREENS[0]).toMatchObject({ no: "01", name: "Ana sayfa", group: null });
  });

  it("çalışmanın ekranları (10–19) Çalışma'nın altında ve çalışma gerektirir", () => {
    const kids = childrenOf("09");
    expect(kids.map((s) => s.no)).toEqual(["10", "11", "12", "13", "14", "15", "16", "17", "18", "19"]);
    expect(kids.every((s) => s.requiresWorkspace && s.group === "planlama")).toBe(true);
  });

  it("en çok iki seviye: alt ekranın altında ekran yok", () => {
    for (const s of SCREENS.filter((x) => x.parent)) {
      expect(childrenOf(s.no)).toEqual([]);
      expect(SCREENS.find((p) => p.no === s.parent)?.parent).toBeUndefined();
    }
  });

  it("her ekranın geleceği adım ve tanımı var", () => {
    for (const s of SCREENS) {
      expect(s.step).toMatch(/^\d+\.\d+$/);
      expect(s.description.length).toBeGreaterThan(10);
    }
    expect(SCREENS.find((s) => s.no === "22")?.step).toBe("2.3");
    expect(SCREENS.find((s) => s.no === "18")?.step).toBe("10.12");
  });
});

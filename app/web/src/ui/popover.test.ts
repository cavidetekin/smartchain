// Açılır pencere yerleşimi (docs/12): görünür alana sığar.
import { describe, expect, it } from "vitest";

import { placePopover, placeSubmenu } from "./popover";

const VIEW = { width: 1366, height: 768 };
const size = { width: 280, height: 320 };

describe("placePopover", () => {
  it("yer varsa altta, açan öğenin solundan açılır", () => {
    expect(placePopover({ left: 100, top: 100, right: 130, bottom: 128 }, size, VIEW)).toEqual({ left: 100, top: 132 });
  });

  it("sağ kenara yakınsa sola açılır (sağ kenarı açan öğeyle hizalı)", () => {
    expect(placePopover({ left: 1300, top: 100, right: 1330, bottom: 128 }, size, VIEW)).toEqual({ left: 1050, top: 132 });
  });

  it("altta yer yoksa yukarı açılır", () => {
    expect(placePopover({ left: 100, top: 600, right: 130, bottom: 628 }, size, VIEW)).toEqual({ left: 100, top: 276 });
  });

  it("ne altta ne üstte yer varsa altta kalır; soldan taşmaz", () => {
    expect(placePopover({ left: 2, top: 200, right: 30, bottom: 228 }, { width: 280, height: 700 }, VIEW))
      .toEqual({ left: 8, top: 232 });
  });
});

describe("placeSubmenu", () => {
  const sub = { width: 220, height: 300 };
  it("ana menünün sağında, üst kenarı öğeyle hizalı", () => {
    expect(placeSubmenu({ left: 100, top: 200, right: 300, bottom: 228 }, sub, VIEW)).toEqual({ left: 300, top: 200 });
  });
  it("sağda yer yoksa ana menünün solunda", () => {
    expect(placeSubmenu({ left: 1100, top: 200, right: 1300, bottom: 228 }, sub, VIEW)).toEqual({ left: 880, top: 200 });
  });
  it("alttan taşacaksa yukarı kayar", () => {
    expect(placeSubmenu({ left: 100, top: 600, right: 300, bottom: 628 }, sub, VIEW)).toEqual({ left: 300, top: 768 - 8 - 300 });
  });
});

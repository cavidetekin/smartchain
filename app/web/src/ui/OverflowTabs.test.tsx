// Tablo şeridinin sekmeleri (K-173): sığmayanlar "Diğer ▾" menüsüne girer; seçili sekme oradaysa menünün adında görünür.
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { OverflowTabs } from "./OverflowTabs";

const OPTIONS = ["Malzeme", "Ürün ağacı ve rota", "Kaynak", "Tedarikçi ve müşteri", "Lokasyon ve birim"].map((label, i) => ({ value: `t${i}`, label }));
const sizes = Object.getOwnPropertyDescriptors(HTMLElement.prototype);

function Harness({ width }: { width: number }) {
  const [value, setValue] = useState("t0");
  return (
    <div data-testid="lead" data-width={width}>
      <OverflowTabs<string> label="Bölümler" value={value} onChange={setValue} options={OPTIONS} />
    </div>
  );
}

beforeEach(() => {
  // sekme 100 px, "Diğer" 60 px; şeridin solu data-width kadar
  Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
    configurable: true,
    get() { const el = this as HTMLElement; return el.hasAttribute("data-tab") ? 100 : el.hasAttribute("data-more") ? 60 : 0; },
  });
  Object.defineProperty(HTMLElement.prototype, "clientWidth", {
    configurable: true,
    get() { const el = this as HTMLElement; return Number(el.dataset.width ?? 0); },
  });
});
afterEach(() => {
  Object.defineProperty(HTMLElement.prototype, "offsetWidth", sizes.offsetWidth);
  delete (HTMLElement.prototype as { clientWidth?: number }).clientWidth;   // asıl tanım Element'te
});

describe("OverflowTabs", () => {
  it("sığan sekmeler görünür, kalanlar Diğer menüsünde; seçilen gizli sekme Diğer'in adında", async () => {
    const user = userEvent.setup();
    render(<Harness width={350} />);
    const group = screen.getByRole("radiogroup", { name: "Bölümler" });
    expect(within(group).getAllByRole("radio").map((r) => r.textContent)).toEqual(["Malzeme", "Ürün ağacı ve rota"]);
    const more = within(group).getByRole("button", { name: "Diğer" });
    await user.click(more);
    const menu = screen.getByRole("menu", { name: "Diğer" });
    expect(within(menu).getAllByRole("menuitem").map((m) => m.textContent)).toEqual(["Kaynak", "Tedarikçi ve müşteri", "Lokasyon ve birim"]);
    await user.click(within(menu).getByRole("menuitem", { name: "Tedarikçi ve müşteri" }));
    expect(within(group).getByRole("button", { name: "Tedarikçi ve müşteri" })).toHaveClass("is-current");
    expect(within(group).getByRole("radio", { name: "Malzeme" })).toHaveAttribute("aria-checked", "false");
  });

  it("hepsi sığıyorsa Diğer yok; genişlik ölçülemiyorsa da hepsi görünür", () => {
    const { unmount } = render(<Harness width={1000} />);
    expect(screen.getAllByRole("radio")).toHaveLength(5);
    expect(screen.queryByRole("button", { name: "Diğer" })).toBeNull();
    unmount();
    render(<Harness width={0} />);
    expect(screen.getAllByRole("radio")).toHaveLength(5);
  });
});

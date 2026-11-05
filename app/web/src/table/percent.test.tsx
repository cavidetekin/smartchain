// Yüzde gösterim (K-113): veride oran, ekranda %5,00; filtre ve kural değeri yüzde girilir, oran saklanır.
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { formatPercent, percentInput, percentValue } from "../format";
import { formatCell } from "./DataTable";
import { describeFilter, FilterMenu } from "./filters";
import { RuleDialog } from "./RuleDialog";
import { col } from "./testBackend";
import type { FormatRule } from "./types";

const scrap = col("ScrapRatio", "Fire oranı", "number", "number", { decimals: 2, percent: true });

describe("yüzde gösterim", () => {
  it("hücre oranı yüzde yazar; boş boş kalır", () => {
    expect(formatPercent(0.05)).toBe("%5,00");
    expect(formatCell(scrap, 0.05)).toBe("%5,00");
    expect(formatCell(scrap, "0.0225")).toBe("%2,25");
    expect(formatCell(scrap, 0)).toBe("%0,00");
    expect(formatCell(scrap, null)).toBe("");
  });

  it("giriş ve saklanan değer arasında kayan nokta artığı kalmaz", () => {
    expect(percentValue(7)).toBe(0.07);
    expect(percentInput(0.07)).toBe(7);
    expect(percentInput(percentValue(2.25))).toBe(2.25);
  });

  it("filtre etiketi yüzde yazar", () => {
    expect(describeFilter({ field: "ScrapRatio", op: "gt", value: 0.05 }, scrap)).toBe("> %5,00");
    expect(describeFilter({ field: "ScrapRatio", op: "between", min: 0.01, max: 0.1 }, scrap)).toBe("%1,00–%10,00");
  });

  it("filtre yüzde gösterir, oran uygular", async () => {
    const onApply = vi.fn();
    render(<FilterMenu list="materials" column={scrap} filter={{ field: "ScrapRatio", op: "gt", value: 0.05 }} others={[]} onApply={onApply} />);
    const input = screen.getByLabelText("Değer (%)");
    expect(input).toHaveValue("5,00");
    await userEvent.clear(input);
    await userEvent.type(input, "10");
    await userEvent.click(screen.getByRole("button", { name: "Uygula" }));
    expect(onApply).toHaveBeenCalledWith({ field: "ScrapRatio", op: "gt", value: 0.1 });
  });

  it("koşullu biçim yüzde gösterir, oran kaydeder", async () => {
    const onSave = vi.fn();
    const rule: FormatRule = { id: "r", enabled: true, field: "ScrapRatio", condition: { op: "gt", value: 0.05 }, format: { bold: true } };
    render(<RuleDialog rule={rule} isNew={false} columns={[scrap]} onClose={() => {}} onSave={onSave} />);
    const input = screen.getByLabelText("Değer (%)");
    expect(input).toHaveValue("5,00");
    await userEvent.clear(input);
    await userEvent.type(input, "10");
    await userEvent.click(screen.getByRole("button", { name: "Kaydet" }));
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave.mock.calls[0][0].condition).toMatchObject({ op: "gt", value: 0.1 });
  });
});

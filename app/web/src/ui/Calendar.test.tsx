// Takvim (docs/12 · Form alanları): Türkçe adlar, Pazartesi başlangıcı, ISO hafta, Bugün, klavye, Esc; elle giriş aynen.
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { DateField } from ".";
import { monthWeeks } from "./Calendar";

function Field({ initial, onChange = () => {} }: { initial: Date | null; onChange?(d: Date | null): void }) {
  const [v, setV] = useState<Date | null>(initial);
  return (
    <>
      <DateField label="Teslim" value={v} onChange={(d) => { setV(d); onChange(d); }} />
      <button type="button">dışarı</button>
    </>
  );
}

const openCalendar = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole("button", { name: "Teslim: Takvimden seç" }));
  return screen.getByRole("dialog", { name: /2026|2027/ });
};

describe("takvim", () => {
  it("Türkçe ay ve gün adları, Pazartesi başlar, satırda ISO hafta; seçili gün odakta", async () => {
    const user = userEvent.setup();
    render(<Field initial={new Date(2026, 9, 27)} />);
    const cal = await openCalendar(user);
    expect(within(cal).getByText("Ekim 2026")).toBeInTheDocument();
    const heads = within(cal).getAllByRole("columnheader").map((h) => h.textContent);
    expect(heads).toEqual(["H", "Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]);
    expect(within(cal).getByRole("rowheader", { name: "H44" })).toBeInTheDocument();
    const day = within(cal).getByRole("button", { name: "27 Ekim 2026 Salı" });
    expect(day).toHaveFocus();
    expect(day.closest("td")).toHaveAttribute("aria-selected", "true");
    const firstRow = within(cal).getAllByRole("row")[1];
    expect(within(firstRow).getAllByRole("button")[0]).toHaveAccessibleName("28 Eylül 2026 Pazartesi");
  });

  it("yıl dönümünde hafta numarası ISO: 28.12.2026 haftası H53", () => {
    const weeks = monthWeeks(new Date(2027, 0, 5));
    expect(weeks[0][0]).toEqual(new Date(2026, 11, 28));
    render(<Field initial={new Date(2027, 0, 5)} />);
    fireEvent.click(screen.getByRole("button", { name: "Teslim: Takvimden seç" }));
    expect(screen.getByRole("rowheader", { name: "H53" })).toBeInTheDocument();
    expect(screen.getByRole("rowheader", { name: "H1" })).toBeInTheDocument();
  });

  it("tıklayınca seçer, alanı gg.aa.yyyy yazar, kapanır ve odak düğmeye döner", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Field initial={new Date(2026, 9, 27)} onChange={onChange} />);
    const cal = await openCalendar(user);
    await user.click(within(cal).getByRole("button", { name: "29 Ekim 2026 Perşembe" }));
    expect(onChange).toHaveBeenLastCalledWith(new Date(2026, 9, 29));
    expect(screen.getByLabelText("Teslim")).toHaveValue("29.10.2026");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("button", { name: "Teslim: Takvimden seç" })).toHaveFocus();
  });

  it("klavye: oklar gün ve hafta, Page Up/Down ay, Home/End hafta başı ve sonu, Enter seçer", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Field initial={new Date(2026, 9, 27)} onChange={onChange} />);
    const cal = await openCalendar(user);
    await user.keyboard("{ArrowRight}");
    expect(within(cal).getByRole("button", { name: "28 Ekim 2026 Çarşamba" })).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(within(cal).getByText("Kasım 2026")).toBeInTheDocument();
    expect(within(cal).getByRole("button", { name: "4 Kasım 2026 Çarşamba" })).toHaveFocus();
    await user.keyboard("{PageUp}{PageUp}");
    expect(within(cal).getByRole("button", { name: "4 Eylül 2026 Cuma" })).toHaveFocus();
    await user.keyboard("{Home}");
    expect(within(cal).getByRole("button", { name: "31 Ağustos 2026 Pazartesi" })).toHaveFocus();
    await user.keyboard("{End}");
    expect(within(cal).getByRole("button", { name: "6 Eylül 2026 Pazar" })).toHaveFocus();
    await user.keyboard("{ArrowUp}{ArrowLeft}{PageDown}");
    expect(within(cal).getByRole("button", { name: "29 Eylül 2026 Salı" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onChange).toHaveBeenLastCalledWith(new Date(2026, 8, 29));
    expect(screen.getByLabelText("Teslim")).toHaveValue("29.09.2026");
  });

  it("Esc ve dışarı tıklama kapatır, değer değişmez", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Field initial={new Date(2026, 9, 27)} onChange={onChange} />);
    await openCalendar(user);
    await user.keyboard("{ArrowRight}{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("button", { name: "Teslim: Takvimden seç" })).toHaveFocus();
    await openCalendar(user);
    await user.click(screen.getByRole("button", { name: "dışarı" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("boş alanda bugünün ayı açılır, bugün işaretli; 'Bugün' gece yarısını seçer", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 9, 27, 15, 40));
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Field initial={null} onChange={onChange} />);
    const cal = await openCalendar(user);
    expect(within(cal).getByRole("button", { name: "27 Ekim 2026 Salı" })).toHaveAttribute("aria-current", "date");
    await user.keyboard("{PageDown}");
    await user.click(within(cal).getByRole("button", { name: "Bugün" }));
    expect(onChange).toHaveBeenLastCalledWith(new Date(2026, 9, 27));
    expect(screen.getByLabelText("Teslim")).toHaveValue("27.10.2026");
  });

  it("elle yazılan tarih takvimde açılır", async () => {
    const user = userEvent.setup();
    render(<Field initial={null} />);
    await user.type(screen.getByLabelText("Teslim"), "3.2.2027");
    const cal = await openCalendar(user);
    expect(within(cal).getByText("Şubat 2027")).toBeInTheDocument();
    expect(within(cal).getByRole("button", { name: "3 Şubat 2027 Çarşamba" })).toHaveFocus();
  });

  it("pasif alanda takvim açılmaz", () => {
    render(<DateField label="Teslim" value={null} onChange={() => {}} disabled />);
    expect(screen.getByRole("button", { name: "Teslim: Takvimden seç" })).toBeDisabled();
  });
});

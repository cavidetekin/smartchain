// Ortak bileşenler (K-85): U-3 (yazısız durum yok), erişilebilirlik, Türkçe giriş, klavye.
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  Alert, Badge, Button, Checkbox, DateField, KpiCard, NumberField, OccupancyCell, OccupancyLegend, RadioGroup, SearchField,
  Segment,
} from ".";

describe("rozet ve uyarı (U-3)", () => {
  it("rozet yazısız oluşturulamaz", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Badge tone="critical">{"  "}</Badge>)).toThrow(/yazısız/);
    render(<Badge tone="ok">tamam</Badge>);
    expect(screen.getByText("tamam")).toHaveClass("sc-tag", "sc-tag--ok");
  });

  it("her uyarı tonunun ikonu var; hata role=alert, diğerleri status", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Alert tone="info">{""}</Alert>)).toThrow(/metinsiz/);
    for (const [tone, name] of [["info", "Bilgi"], ["ok", "Tamam"], ["risk", "Risk"], ["error", "Hata"]] as const) {
      const { unmount } = render(<Alert tone={tone}>metin</Alert>);
      expect(screen.getByRole("img", { name })).toBeInTheDocument();
      expect(screen.getByRole(tone === "error" ? "alert" : "status")).toHaveTextContent("metin");
      unmount();
    }
  });

  it("kapatılabilir uyarı", async () => {
    const onClose = vi.fn();
    render(<Alert tone="error" onClose={onClose}>dolu</Alert>);
    await userEvent.click(screen.getByRole("button", { name: "Kapat" }));
    expect(onClose).toHaveBeenCalled();
  });
});

describe("buton", () => {
  it("pasif ve meşgul buton tıklanmaz", async () => {
    const onClick = vi.fn();
    render(<><Button disabled onClick={onClick}>A</Button><Button busy onClick={onClick}>B</Button></>);
    for (const b of screen.getAllByRole("button")) await userEvent.click(b);
    expect(onClick).not.toHaveBeenCalled();
    expect(screen.getByText("Çalışıyor…").closest("button")).toHaveAttribute("aria-busy", "true");
  });

  it("geri alınamaz işlem kiremit sınıfında", () => {
    render(<Button variant="danger">İptal et</Button>);
    expect(screen.getByRole("button", { name: "İptal et" })).toHaveClass("sc-btn--danger");
  });
});

function Num() {
  const [v, setV] = useState<number | null>(1234.5);
  return (
    <>
      <NumberField label="Miktar" value={v} onChange={setV} decimals={1} />
      <output data-testid="value">{String(v)}</output>
    </>
  );
}

describe("form alanları (U-19)", () => {
  it("sayı Türkçe görünür ve girilir; geçersizde hata, değer değişmez", async () => {
    const user = userEvent.setup();
    render(<Num />);
    const box = screen.getByLabelText("Miktar");
    expect(box).toHaveValue("1.234,5");
    await user.clear(box);
    await user.type(box, "2.500,25{Enter}");
    expect(screen.getByTestId("value")).toHaveTextContent("2500.25");
    expect(box).toHaveValue("2.500,3");
    await user.clear(box);
    await user.type(box, "12.34");
    fireEvent.blur(box);
    expect(box).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText(/Sayı geçersiz/)).toBeInTheDocument();
    expect(screen.getByTestId("value")).toHaveTextContent("2500.25");
  });

  it("tarih gg.aa.yyyy", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<DateField label="Teslim" value={new Date(2026, 9, 27)} onChange={onChange} />);
    const box = screen.getByLabelText("Teslim");
    expect(box).toHaveValue("27.10.2026");
    await user.clear(box);
    await user.type(box, "31.02.2026");
    fireEvent.blur(box);
    expect(screen.getByText(/Tarih geçersiz/)).toBeInTheDocument();
    await user.clear(box);
    await user.type(box, "1.12.2026{Enter}");
    expect(onChange).toHaveBeenLastCalledWith(new Date(2026, 11, 1));
    expect(box).toHaveValue("01.12.2026");
  });

  it("segment ok tuşlarıyla, onay kutusu boşlukla çalışır", async () => {
    const user = userEvent.setup();
    function S() {
      const [v, setV] = useState("hafta");
      const [c, setC] = useState(false);
      return (
        <>
          <Segment<string> label="Dönem" value={v} onChange={setV}
                           options={[{ value: "gun", label: "Günlük" }, { value: "hafta", label: "Haftalık" },
                                     { value: "ay", label: "Aylık" }]} />
          <Checkbox label="Fazla mesai" checked={c} onChange={setC} />
        </>
      );
    }
    render(<S />);
    screen.getByRole("radio", { name: "Haftalık" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("radio", { name: "Aylık" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Aylık" })).toHaveFocus();
    screen.getByRole("checkbox", { name: "Fazla mesai" }).focus();
    await user.keyboard(" ");
    expect(screen.getByRole("checkbox", { name: "Fazla mesai" })).toBeChecked();
  });

  it("segment ve seçenek grubunun etiketi üstte görünür; hideLabel yalnız erişilebilir ad bırakır", () => {
    const opts = [{ value: "a", label: "A" }, { value: "b", label: "B" }];
    render(
      <>
        <Segment<string> label="Dönem" value="a" onChange={() => {}} options={opts} />
        <Segment<string> label="Yazı boyutu" hideLabel value="a" onChange={() => {}} options={opts} />
        <RadioGroup label="Kaynak kısıtı" value="a" onChange={() => {}} options={opts} />
      </>,
    );
    const seg = screen.getByRole("radiogroup", { name: "Dönem" });
    expect(seg.previousElementSibling).toHaveTextContent("Dönem");
    expect(seg.previousElementSibling).toHaveClass("sc-field-label");
    expect(screen.getByRole("radiogroup", { name: "Yazı boyutu" }).closest(".sc-segment-field")).toBeNull();
    expect(screen.queryByText("Yazı boyutu")).toBeNull();
    const group = screen.getByRole("group", { name: "Kaynak kısıtı" });
    expect(group.firstElementChild?.tagName).toBe("LEGEND");
    expect(group.firstElementChild).toHaveClass("sc-field-label");
    expect(group.querySelector(".sc-radio-options")?.querySelectorAll("input[type=radio]")).toHaveLength(2);
  });

  it("arama kutusu tek satır, aranabilir", async () => {
    const onChange = vi.fn();
    render(<SearchField label="Malzeme ara" value="" onChange={onChange} />);
    const box = screen.getByRole("searchbox", { name: "Malzeme ara" });
    expect(box.closest("label")).toHaveClass("sc-search-field");
    await userEvent.type(box, "x");
    expect(onChange).toHaveBeenCalledWith("x");
  });
});

describe("doluluk ve KPI", () => {
  it("hücre değeri yazar, eşik prop'tan gelir", () => {
    render(
      <>
        <OccupancyCell value={92} delta={6} />
        <OccupancyCell value={92} thresholds={{ low: 30, normal: 60, risk: 95, over: 100 }} />
      </>,
    );
    const [a, b] = screen.getAllByText("%92").map((e) => e.closest(".sc-occ")!);
    expect(a).toHaveAttribute("data-level", "risk");
    expect(b).toHaveAttribute("data-level", "high");
    expect(screen.getByText("+6 pt")).toBeInTheDocument();
  });

  it("lejant eşiklerden üretilir", () => {
    render(<OccupancyLegend thresholds={{ low: 30, normal: 60, risk: 85, over: 95 }} />);
    expect(screen.getByText("Risk %85–95")).toBeInTheDocument();
  });

  it("KPI değeri durum varsa durum sınıfında", () => {
    render(<KpiCard label="Aşırı yük" value="5" tone="over" note="Doluluk %100 üstü" />);
    expect(screen.getByText("5")).toHaveClass("sc-kpi-value", "sc-kpi--over");
  });
});

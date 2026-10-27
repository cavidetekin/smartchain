// Stil örnekleri sayfası (/stil): bütün bölümler ve yazı boyutu (U-23).
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it } from "vitest";

import { tr } from "../i18n/tr";
import { mockApi, mockSocket, renderApp } from "../test/helpers";

beforeEach(() => {
  mockApi();
  mockSocket();
});

it("bütün bölümler var; menüde yer almaz", () => {
  renderApp("/stil");
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Stil örnekleri");
  for (const title of Object.values(tr.style.sections)) {
    expect(screen.getByRole("heading", { level: 2, name: title })).toBeInTheDocument();
  }
  expect(screen.queryByRole("link", { name: /Stil örnekleri/ })).toBeNull();
});

it("farklı eşiklerle aynı değerler farklı seviyede", () => {
  renderApp("/stil");
  const alt = screen.getByTestId("occ-alt");
  const levels = [...alt.querySelectorAll(".sc-occ")].map((e) => e.getAttribute("data-level"));
  expect(levels).toEqual(["normal", "normal", "high", "risk", "risk", "over", "over", "over"]);
});

it("yazı boyutu seçince bütün arayüz ölçeklenir", async () => {
  renderApp("/stil");
  expect(document.documentElement.style.fontSize).toBe("13px");
  const typeSegment = screen.getAllByRole("radiogroup", { name: "Yazı boyutu" })[0];
  await userEvent.click(typeSegment.querySelector('[data-value="16"]')!);
  expect(document.documentElement.style.fontSize).toBe("16px");
});

it("tarih alanında takvim düğmesi var", async () => {
  renderApp("/stil");
  await userEvent.click(screen.getByRole("button", { name: "Teslim tarihi: Takvimden seç" }));
  expect(screen.getByRole("dialog", { name: "Ekim 2026" })).toBeInTheDocument();
});

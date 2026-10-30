// Koşullu biçim paleti (U-24, K-96): Excel benzeri. Değerler tokens.css'ten üretilen design-tokens.json'dan (K-92).
// Tema renklerinin tonları Excel'in oranlarıyla üretilir: açık renkte koyulaştırma, koyu renkte açma, diğerlerinde
// %80, %60, %40 açma ve %25, %50 koyulaştırma.
import tokens from "../../../shared/design-tokens.json";
import { mix } from "./contrast";

const colors: Record<string, string> = tokens.colors;
export const tokenColor = (name: string) => color(name);
function color(name: string) {
  const v = colors[name];
  if (!v) throw new Error(`design-tokens.json'da renk yok: ${name}`);
  return v;
}

/** Ürün renkleri (öneri): indigo, hardal, kiremit, yeşil, petrol, kurşun tonları; adları arayüzde. */
export const PRODUCT_COLORS: { token: string; hex: string }[] = [
  "indigo-500", "indigo-100", "status-risk", "status-risk-bg", "status-over", "status-over-bg", "status-ok", "status-ok-bg",
  "chart-2", "lead-100", "lead-600", "lead-900",
].map((token) => ({ token, hex: color(token) }));

const THEME = Array.from({ length: 10 }, (_, i) => color(`cf-theme-${i + 1}`));
export const STANDARD_COLORS: string[] = Array.from({ length: 10 }, (_, i) => color(`cf-std-${i + 1}`));

function shades(base: string): string[] {
  if (base === "#ffffff") return [base, ...[-0.05, -0.15, -0.25, -0.35, -0.5].map((a) => mix(base, a))];
  if (base === "#000000") return [base, ...[0.5, 0.35, 0.25, 0.15, 0.05].map((a) => mix(base, a))];
  return [base, ...[0.8, 0.6, 0.4, -0.25, -0.5].map((a) => mix(base, a))];
}

/** Tema renkleri: 6 satır × 10 kolon (ilk satır temel renkler). */
export const THEME_GRID: string[][] = (() => {
  const cols = THEME.map(shades);
  return Array.from({ length: 6 }, (_, r) => cols.map((c) => c[r]));
})();

/** Varsayılan yazı rengi (okunurluk hesabında yazı rengi seçilmemişse). */
export const DEFAULT_TEXT = color("text");

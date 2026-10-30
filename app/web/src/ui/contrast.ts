// Okunurluk (WCAG 2.1; U-24, K-96): renk kontrastı ve okunur yazı rengi önerisi. Stil sistemi testleri de bunu kullanır.

export const READABLE = 4.5;

export function isHex(s: string): boolean {
  return /^#[0-9a-f]{6}$/i.test(s);
}

function channels(hex: string): [number, number, number] {
  return [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16)) as [number, number, number];
}

const toHex = (c: number[]) => `#${c.map((x) => Math.round(Math.min(255, Math.max(0, x))).toString(16).padStart(2, "0")).join("")}`;

export function luminance(hex: string): number {
  const c = channels(hex).map((x) => x / 255).map((x) => (x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}

export function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** Rengi beyaza (amount > 0) ya da siyaha (amount < 0) doğru karıştırır; Excel'in ton/gölge mantığı. */
export function mix(hex: string, amount: number): string {
  const c = channels(hex);
  return toHex(c.map((x) => (amount >= 0 ? x + (255 - x) * amount : x * (1 + amount))));
}

/**
 * Zemine okunur yazı rengi: önce varsayılan yazı rengi ve beyaz; ikisi de 4,5:1'i tutmuyorsa zeminin tonundan
 * koyulaştırılmış ya da açılmış ilk okunur renk. En yüksek kontrastlı aday döner.
 */
export function suggestText(fill: string, defaultText: string): string {
  const candidates = [defaultText, "#ffffff"];
  const ok = candidates.filter((c) => contrast(c, fill) >= READABLE);
  if (ok.length) return ok.sort((a, b) => contrast(b, fill) - contrast(a, fill))[0];
  const dark = luminance(fill) > 0.18;
  for (let i = 10; i < 20; i++) {  // %50 … %95, %5 adım (export/formats.py ile aynı)
    const c = mix(fill, dark ? -i / 20 : i / 20);
    if (contrast(c, fill) >= READABLE) return c;
  }
  return dark ? "#000000" : "#ffffff";
}

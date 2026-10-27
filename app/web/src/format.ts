// Türkçe sayı ve tarih biçimi (U-19): 1.234,5 · gg.aa.yyyy · H44.

const LOCALE = "tr-TR";

export function formatNumber(value: number, fractionDigits = 0): string {
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value);
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** gg.aa.yyyy (yerel saat). */
export function formatDate(d: Date): string {
  return `${pad(d.getDate())}.${pad(d.getMonth() + 1)}.${d.getFullYear()}`;
}

/** gg.aa.yyyy ss:dd (yerel saat). */
export function formatDateTime(d: Date): string {
  return `${formatDate(d)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** ISO hafta numarası: H44. */
export function weekLabel(d: Date): string {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const day = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - day);
  const yearStart = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  return `H${Math.ceil(((t.getTime() - yearStart.getTime()) / 86400000 + 1) / 7)}`;
}

/** Türkçe büyük/küçük harf duyarsız karşılaştırma için (İ/ı doğru). */
export function fold(text: string): string {
  return text.toLocaleLowerCase(LOCALE);
}

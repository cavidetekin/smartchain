// Türkçe sayı ve tarih biçimi (U-19): 1.234,5 · gg.aa.yyyy · H44.

const LOCALE = "tr-TR";

const numberFormats = new Map<number, Intl.NumberFormat>();

/** Biçimlendirici ondalık sayısına göre bir kez kurulur (her hücrede yeniden kurmak tabloyu yavaşlatıyordu). */
export function formatNumber(value: number, fractionDigits = 0): string {
  let f = numberFormats.get(fractionDigits);
  if (!f) {
    f = new Intl.NumberFormat(LOCALE, { minimumFractionDigits: fractionDigits, maximumFractionDigits: fractionDigits });
    numberFormats.set(fractionDigits, f);
  }
  return f.format(value);
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

/** Türkçe sayı girişi: "1.234,5", "1234,5", "-12" → sayı; geçersizse null (U-19). */
export function parseTrNumber(text: string): number | null {
  const t = text.trim().replace(/\s/g, "");
  if (!t) return null;
  if (!/^-?(\d{1,3}(\.\d{3})+|\d+)(,\d+)?$/.test(t)) return null;
  return Number(t.replace(/\./g, "").replace(",", "."));
}

/** gg.aa.yyyy → Date (yerel); geçersiz ya da takvimde olmayan tarih null. */
export function parseTrDate(text: string): Date | null {
  const m = text.trim().match(/^(\d{1,2})\.(\d{1,2})\.(\d{4})$/);
  if (!m) return null;
  const [d, mo, y] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const date = new Date(y, mo - 1, d);
  return date.getFullYear() === y && date.getMonth() === mo - 1 && date.getDate() === d ? date : null;
}

/** Sözleşmedeki tarih (docs/08): yerel gün, ISO "yyyy-aa-gg". */
export function toIsoDate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

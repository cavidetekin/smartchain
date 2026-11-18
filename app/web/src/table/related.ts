// İlişkili alanlar (K-182): satırın bağlı olduğu tek kaydın alanı kolon olarak eklenir. Alan adı yol + alan ("ResourceGroupId/IsCritical",
// "WorkOrderId/MaterialId/Name"); sınır sunucuyla aynı: bir tabloda en çok 20 ilişkili alan ve 8 ilişki (birleştirme).
import type { ListColumn } from "./types";

export const RELATED_SEP = "/";
export const MAX_RELATED_FIELDS = 20;
export const MAX_RELATED_JOINS = 8;

export const isRelatedField = (field: string) => field.includes(RELATED_SEP);

/** Alanın ilişki yolu: "WorkOrderId/MaterialId/Name" → "WorkOrderId/MaterialId". */
export const relatedPath = (field: string) => field.slice(0, field.lastIndexOf(RELATED_SEP));

/** Alanların gerektirdiği birleştirmeler: her yol ve üst yolu bir ilişkidir. */
export function joinPaths(fields: Iterable<string>): Set<string> {
  const out = new Set<string>();
  for (const f of fields) {
    if (!isRelatedField(f)) continue;
    const parts = relatedPath(f).split(RELATED_SEP);
    parts.forEach((_, i) => out.add(parts.slice(0, i + 1).join(RELATED_SEP)));
  }
  return out;
}

/** Açık alanlara bu ilişkili alan eklenebilir mi? Eklenemiyorsa neden: "fields" (alan sınırı) ya da "joins" (ilişki sınırı). */
export function relatedLimit(order: string[], field: string): "fields" | "joins" | null {
  const related = order.filter(isRelatedField);
  if (related.length >= MAX_RELATED_FIELDS) return "fields";
  return joinPaths([...related, field]).size > MAX_RELATED_JOINS ? "joins" : null;
}

/** Bilinen kolonlar: tablonun kendi kolonları ve tanınan ilişkili kolonlar (tekrarsız, ilk gelen kalır). */
export function mergeColumns(base: ListColumn[], ...more: ListColumn[][]): ListColumn[] {
  const seen = new Set(base.map((c) => c.field));
  const out = [...base];
  for (const list of more) for (const c of list) if (!seen.has(c.field)) { seen.add(c.field); out.push(c); }
  return out;
}

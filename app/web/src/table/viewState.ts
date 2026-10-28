// Tablo durumu ve kayıtlı görünüm içeriği (K-89, docs/08 "Görünümler"). Saf işlevler: dönüşüm, karşılaştırma, taşıma.
import type { AggSpec, ColumnType, ListColumn, ListFilter, SortItem, ViewDefinition } from "./types";

export interface TableState {
  /** Görünen alanlar, görünen sırada. */
  order: string[];
  /** Kullanıcının verdiği genişlikler (rem); yoksa tipin varsayılanı. */
  widths: Record<string, number>;
  /** Soldan sabit kolon sayısı (U-10). */
  pinned: number;
  sort: SortItem[];
  /** Alan başına en çok bir filtre. */
  filters: ListFilter[];
  groupBy: string[];
  /** Varsayılandan farklı seçilen ara toplam türleri (K-90). */
  aggregates: Record<string, AggSpec>;
}

/** Tipin varsayılan genişliği (rem; 13 px'te 180 / 120 / 140 / 100 px). */
export const DEFAULT_WIDTH_REM: Record<ColumnType, number> = {
  text: 13.8462, number: 9.2308, integer: 9.2308, date: 9.2308, datetime: 10.7692, bool: 7.6923,
};
export const MIN_WIDTH_REM = 4;
export const MAX_WIDTH_REM = 60;
export const MAX_GROUP_FIELDS = 4;

export const clampWidth = (rem: number) => Math.min(MAX_WIDTH_REM, Math.max(MIN_WIDTH_REM, Math.round(rem * 100) / 100));

/** "Standart" görünüm: liste tanımındaki varsayılan alanlar ve sunucunun varsayılan sıralaması (K-89). */
export function standardState(columns: ListColumn[]): TableState {
  return { order: columns.filter((c) => c.default_visible).map((c) => c.field), widths: {}, pinned: 0, sort: [],
           filters: [], groupBy: [], aggregates: {} };
}

export function fromDefinition(def: ViewDefinition, columns: ListColumn[]): TableState {
  const known = new Set(columns.map((c) => c.field));
  const cols = def.columns.filter((c) => known.has(c.field));
  if (!cols.length) return standardState(columns);
  return {
    order: cols.map((c) => c.field),
    widths: Object.fromEntries(cols.filter((c) => typeof c.width === "number").map((c) => [c.field, c.width as number])),
    pinned: Math.min(def.pinned, cols.length),
    sort: def.sort.filter((s) => known.has(s.field)),
    filters: def.filters.filter((f) => known.has(f.field)),
    groupBy: def.group_by.filter((g) => known.has(g)),
    aggregates: Object.fromEntries(Object.entries(def.aggregates ?? {}).filter(([f]) => known.has(f))),
  };
}

export function toDefinition(s: TableState): ViewDefinition {
  return {
    v: 1,
    columns: s.order.map((field) => ({ field, width: s.widths[field] ?? null })),
    pinned: Math.min(s.pinned, s.order.length),
    sort: s.sort,
    filters: s.filters,
    group_by: s.groupBy,
    aggregates: s.aggregates,
  };
}

/** Karşılaştırma için kararlı biçim: boş anahtarlar atılır, filtreler alana göre sıralanır. */
function normalize(def: ViewDefinition): string {
  const clean = (f: ListFilter) => Object.fromEntries(
    Object.entries(f).filter(([, v]) => v !== undefined && v !== null && v !== false).sort(([a], [b]) => a.localeCompare(b)));
  return JSON.stringify({
    columns: def.columns.map((c) => [c.field, c.width ?? null]),
    pinned: def.pinned,
    sort: def.sort.map((s) => [s.field, s.dir]),
    filters: [...def.filters].sort((a, b) => a.field.localeCompare(b.field)).map(clean),
    group_by: def.group_by,
    aggregates: Object.entries(def.aggregates ?? {}).sort(([a], [b]) => a.localeCompare(b))
      .map(([f, a]) => [f, a.fn, a.weight ?? null]),
  });
}

/** Kaydedilmemiş değişiklik var mı (U-9): o anki durum görünümün içeriğinden farklıysa. */
export function isDirty(state: TableState, baseline: ViewDefinition): boolean {
  return normalize(toDefinition(state)) !== normalize(baseline);
}

/** Alanı sola (-1) ya da sağa (+1) taşır; sınırda değişmez. */
export function moveField(order: string[], field: string, delta: number): string[] {
  const i = order.indexOf(field);
  const j = i + delta;
  if (i < 0 || j < 0 || j >= order.length) return order;
  const next = [...order];
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}

/** Sürükle-bırak: alanı hedefin önüne ya da arkasına koyar. */
export function dropField(order: string[], field: string, target: string, side: "before" | "after"): string[] {
  if (field === target) return order;
  const rest = order.filter((f) => f !== field);
  const at = rest.indexOf(target) + (side === "after" ? 1 : 0);
  return [...rest.slice(0, at), field, ...rest.slice(at)];
}

const isNumber = (c: ListColumn) => c.type === "number" || c.type === "integer";

/** Kolonun geçerli ara toplamı: kullanıcının seçimi, yoksa liste tanımının varsayılanı (K-90). */
export function aggregateOf(col: ListColumn, s: TableState): AggSpec {
  if (!isNumber(col)) return { fn: "none" };
  return s.aggregates[col.field] ?? { fn: col.aggregate ?? "none" };
}

/** Seçimi yazar; varsayılanla aynıysa kaydı siler (görünüm temiz kalsın). */
export function withAggregate(s: TableState, col: ListColumn, spec: AggSpec): TableState {
  const aggregates = { ...s.aggregates };
  if (spec.fn === (col.aggregate ?? "none") && spec.fn !== "wavg") delete aggregates[col.field];
  else aggregates[col.field] = spec.fn === "wavg" ? { fn: "wavg", weight: spec.weight } : { fn: spec.fn };
  return { ...s, aggregates };
}

/** Gruplama isteğinin ara toplamları: görünen sayı kolonlarında "yok" olmayanlar. */
export function requestAggregates(columns: ListColumn[], s: TableState): Record<string, AggSpec> {
  return Object.fromEntries(columns.filter((c) => s.order.includes(c.field)).map((c) => [c.field, aggregateOf(c, s)])
    .filter(([, a]) => (a as AggSpec).fn !== "none"));
}

export function withFilter(filters: ListFilter[], field: string, f: ListFilter | null): ListFilter[] {
  const rest = filters.filter((x) => x.field !== field);
  return f ? [...rest, f] : rest;
}

/** Alan gizlenince sabitleme sayısı görünen kolonları aşmaz. */
export function withOrder(s: TableState, order: string[]): TableState {
  return { ...s, order, pinned: Math.min(s.pinned, order.length) };
}

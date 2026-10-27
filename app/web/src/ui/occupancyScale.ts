// Doluluk skalası (K-85, docs/12). Eşikler koda sabit değil: parametre; müşteriye göre değişir
// ve 7.5'te uyarı eşikleri ekranından gelir. Eşik, ekranda yazan yuvarlanmış değere uygulanır.

export type OccupancyLevel = "low" | "normal" | "high" | "risk" | "over";

/** low: normal'in başladığı değer · normal: yüksek'in başladığı · risk: risk'in başladığı · over: üstü aşırı yük. */
export interface OccupancyThresholds {
  low: number;
  normal: number;
  risk: number;
  over: number;
}

export const DEFAULT_THRESHOLDS: OccupancyThresholds = { low: 40, normal: 70, risk: 90, over: 100 };

export function validateThresholds(t: OccupancyThresholds): void {
  if (!(t.low < t.normal && t.normal < t.risk && t.risk <= t.over)) {
    throw new Error(`Doluluk eşikleri sırasız: ${t.low} / ${t.normal} / ${t.risk} / ${t.over}`);
  }
}

export function occupancyLevel(value: number, t: OccupancyThresholds = DEFAULT_THRESHOLDS): OccupancyLevel {
  validateThresholds(t);
  const shown = Math.round(value);
  if (shown < t.low) return "low";
  if (shown < t.normal) return "normal";
  if (shown < t.risk) return "high";
  if (shown <= t.over) return "risk";
  return "over";
}

export const LEVELS: OccupancyLevel[] = ["low", "normal", "high", "risk", "over"];

/** Lejant metinleri eşiklerden üretilir (mockup m23-0291: "< %40", "%40–69", "%70–89", "Risk %90–100", "Aşırı yük > %100"). */
export function legendLabels(t: OccupancyThresholds = DEFAULT_THRESHOLDS): Record<OccupancyLevel, string> {
  validateThresholds(t);
  return {
    low: `< %${t.low}`,
    normal: `%${t.low}–${t.normal - 1}`,
    high: `%${t.normal}–${t.risk - 1}`,
    risk: `Risk %${t.risk}–${t.over}`,
    over: `Aşırı yük > %${t.over}`,
  };
}

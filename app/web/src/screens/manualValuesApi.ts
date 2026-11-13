// Manuel değer uçları (fonksiyon 12 girme, 13 kaldırma; K-170). Satırların hücre kaynağı ortak liste cevabında (_sources).
import { sendJson } from "../api/client";

/** Hücrenin kaynağı: manuel değer ya da kural; ERP olan hücre cevapta yoktur. */
export interface CellSource {
  source: "Manuel" | "Kural";
  rule_id?: number | null;
  rule_name?: string | null;
  /** Manuel: giren, zaman (UTC), alttaki değer girildiğinden beri değişti mi; girildiğindeki ve son aktarımdaki alttaki değer. */
  by?: string | null;
  at?: string;
  changed?: boolean;
  base?: unknown;
  underlying?: unknown;
  underlying_source?: "ERP" | "Kural";
}

export type CellSources = Record<string, CellSource>;

export interface ManualChange { id: number | string; field: string; value: unknown }
export interface ManualItem { id: number | string; field?: string }

export const manualValuesApi = {
  save: (list: string, changes: ManualChange[]) => sendJson<{ saved: number }>("POST", "/api/manual-values", { list, changes }),
  remove: (list: string, items: ManualItem[]) => sendJson<{ removed: number }>("POST", "/api/manual-values/remove", { list, items }),
};

// Veri kuralları (docs/08; K-140…K-142). Liste ortak liste sözleşmesiyle: `data-rules`.
import { getJson, postJson, sendJson } from "../api/client";
import type { Condition, FieldInfo } from "./validationApi";

export const KIND_VALUE = "Değer";
export const KIND_FIELD = "Alan";
export const KIND_FORMULA = "Formül";
export const KIND_CLEAR = "Boşalt";
export const RESULT_KINDS = [KIND_VALUE, KIND_FIELD, KIND_FORMULA, KIND_CLEAR] as const;
export const MODE_ONLY_EMPTY = "Yalnız boşsa";
export const MODE_ALWAYS = "Her zaman";
export const NUMBER_OPERATORS = ["+", "−", "×", "÷"] as const;
export const DATE_OPERATORS = ["+", "−"] as const;  // gün
export const STATUS_FAILED = "Çalışmadı";
export const STATUS_RAN = "Çalıştı";

export interface RuleResult {
  kind: string;
  value: string | null;
  source_field: string | null;
  operator: string | null;
  operand_value: string | null;
  operand_field: string | null;
}

export interface DataRuleDetail {
  id: number;
  entity: string;
  name: string;
  target: string;
  result: RuleResult;
  mode: string;
  active: boolean;
  seq: number;
  groups: Condition[][];
  condition: string;
  result_text: string;
}

export interface DataRuleField extends FieldInfo {
  /** Hedef olabilir mi (anahtar alan olamaz, K-141). */
  target: boolean;
  reason: string | null;
}

export interface DataRuleChange {
  id?: number;
  entity?: string;
  name?: string;
  target?: string;
  result?: RuleResult;
  mode?: string;
  active?: boolean;
  groups?: Condition[][];
  delete?: boolean;
}

export const emptyResult = (): RuleResult => ({ kind: KIND_VALUE, value: null, source_field: null, operator: null, operand_value: null, operand_field: null });

/** Sonuç tamam mı (sunucu da denetler). */
export function resultComplete(r: RuleResult): boolean {
  if (r.kind === KIND_CLEAR) return true;
  if (r.kind === KIND_VALUE) return Boolean(r.value && r.value.trim());
  if (r.kind === KIND_FIELD) return Boolean(r.source_field);
  return Boolean(r.source_field && r.operator && (r.operand_field || (r.operand_value && r.operand_value.trim())));
}

/** Kayıtlar listesinin `RuleEffects` alanı (K-140): alan → (sıra, kural, ham değer). */
export function parseEffects(raw: unknown): Map<string, { seq: string; rule: string; raw: string }> {
  const out = new Map<string, { seq: string; rule: string; raw: string }>();
  if (typeof raw !== "string" || !raw) return out;
  for (const part of raw.split("\u001e")) {
    const [field, seq, rule, value] = part.split("\u001f");
    if (field) out.set(field, { seq: seq ?? "", rule: rule ?? "", raw: value ?? "" });
  }
  return out;
}

export const dataRulesApi = {
  rule: (id: number, signal?: AbortSignal) => getJson<DataRuleDetail>(`/api/data-rules/${id}`, signal),
  fields: (entity: string, signal?: AbortSignal) => getJson<DataRuleField[]>(`/api/data-rules/fields/${encodeURIComponent(entity)}`, signal),
  save: (changes: DataRuleChange[], orders: { entity: string; ids: number[] }[]) =>
    sendJson<{ saved: number; changed_entities: string[] }>("PUT", "/api/data-rules", { changes, orders }),
  apply: (entity: string | null) => postJson<{ job_ids: number[] }>("/api/data-rules/apply", { entity }),
};

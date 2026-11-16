// Parametreler (ekran 06; fonksiyon 22, 23; K-175; docs/08 "Parametreler").
import { getJson, postJson, sendJson } from "../api/client";

export interface ParamDef {
  key: string;
  label: string;
  kind: "bool" | "choice" | "int" | "number";
  options?: string[];
  min?: number;
  max?: number;
  nullable?: boolean;
  enabled_when?: { key: string; value: string };
  hint?: string;
  /** Değerin birimini taşıyan parametre: ekranda aynı satırda. */
  unit_key?: string;
}
export interface SubDef { key: string; title: string; table: "buckets" | "report" | null; params: ParamDef[] }
export interface SectionDef { key: string; title: string; table: "objectives" | null; subs: SubDef[] }
export type ParamValues = Record<string, string | null>;
export interface ParametersData {
  scenario: { id: number; name: string }; sections: SectionDef[]; values: ParamValues;
  /** Kayıtlı değerlerden hesaplananlar: fix periyodun son günü (yoksa null). */
  computed: { fix_period_end: string | null };
}

export interface ObjectiveRow {
  id: number; code: string; label: string; seq: number | null; seconds: number | null; tolerance: number | null; active: boolean;
}
export interface ObjectivesData { rows: ObjectiveRow[]; total_seconds: number }

export interface BucketRow { bucket_type: string; count: number | null; span_unit: string }
export interface BucketPart extends BucketRow { start: string; end: string; buckets: number; days: number }
export interface Period { no: number; start: string; end: string; bucket_type: string; days: number }
export interface BucketPreview { rows: BucketPart[]; start: string | null; end: string | null; buckets: number; periods: Period[] }
export interface BucketsData extends BucketPreview { bucket_types: string[]; span_units: string[] }
export type Axis = "plan" | "rapor";

export const parametersApi = {
  read: (signal?: AbortSignal) => getJson<ParametersData>("/api/parameters", signal),
  save: (changes: Record<string, string | boolean | number | null>) => sendJson<ParametersData>("PUT", "/api/parameters", { changes }),
  objectives: (signal?: AbortSignal) => getJson<ObjectivesData>("/api/parameters/objectives", signal),
  saveObjectives: (rows: { id: number; active: boolean; seconds: number | string | null; tolerance: number | string | null }[]) =>
    sendJson<ObjectivesData>("PUT", "/api/parameters/objectives", { rows }),
  buckets: (axis: Axis, signal?: AbortSignal) => getJson<BucketsData>(`/api/parameters/time-buckets/${axis}`, signal),
  preview: (axis: Axis, rows: BucketRow[], signal?: AbortSignal) => postJson<BucketPreview>(`/api/parameters/time-buckets/${axis}/preview`, { rows }, signal),
  saveBuckets: (axis: Axis, rows: BucketRow[]) => sendJson<BucketsData>("PUT", `/api/parameters/time-buckets/${axis}`, { rows }),
  currentScenario: (signal?: AbortSignal) => getJson<{ id: number; name: string }>("/api/scenarios/current", signal),
};

// Validasyon ve validasyon kuralları (docs/08; K-134, K-136, K-139). Listeler ortak liste sözleşmesiyle:
// `validation-records-<tablo>` (Kayıtlar; kurala göre süzme `RuleIds`), `validation-rules`.
import { getJson, postJson, saveBlob, sendJson } from "../api/client";
import { listApi, type ExportResult, type ListFilter } from "../table/types";

export const STATE_QUEUED = "Sırada";
export const STATE_RULES = "Kurallar çalışıyor";
export const STATE_VALIDATING = "Valide ediliyor";
export const STATE_DONE = "Bitti";
export const STATE_FAILED = "Valide edilemedi";
export const RUNNING_STATES = [STATE_QUEUED, STATE_RULES, STATE_VALIDATING];
export const SEVERITIES = ["Hata", "Uyarı", "Bilgi"] as const;
export const KIND_STRUCTURAL = "Yapısal";
export const KIND_BUILTIN = "Hazır";
export const KIND_USER = "Kullanıcı";

export interface RuleCount {
  id: number;
  name: string;
  severity: string;
  rows: number;
  /** Yalnız tablo düzeyi bulguda (ör. "Karşılaştırılacak veri yok"). */
  message: string | null;
}

export interface ValidationSummary {
  entity: string;
  name: string;
  state: string | null;
  outcome: string | null;
  batch: { id: number; received_at: string; method: string; mode: string; uploaded_by_name: string | null } | null;
  current_rows: number;
  error_rows: number;
  warning_rows: number;
  info_rows: number;
  error_rate: number | null;
  threshold: number | null;
  /** Bulgular görünümü: kural bazında (K-139). */
  rules: RuleCount[];
}

export interface Condition {
  field: string;
  operator: string;
  value: string | null;
  compare_field: string | null;
}

export interface RuleDetail {
  id: number;
  entity: string;
  code: string;
  name: string;
  kind: string;
  check_type: string;
  severity: string;
  message: string;
  active: boolean;
  locked: boolean;
  /** Pencerede düzenlenir: kullanıcı kuralı ya da koşulu editörle ifade edilen hazır kural (K-139). */
  editable: boolean;
  /** Hazır kural düzenlendi; "İlk hâline döndür" sıfırlar. */
  customized: boolean;
  groups: Condition[][];
  condition: string;
}

export interface FieldInfo {
  name: string;
  label: string;
  kind: "text" | "number" | "integer" | "date" | "bool";
  values: string[];
}

export interface RuleChange {
  id?: number;
  entity?: string;
  name?: string;
  severity?: string;
  message?: string;
  active?: boolean;
  groups?: Condition[][];
  delete?: boolean;
  /** İlk hâline döndür (hazır kural, K-139). */
  reset?: boolean;
}

export const recordsList = (entity: string) => `validation-records-${entity}`;
/** Kuralla değişenler ve Tüm satırlar: aynı satırlar, Sorun ve Sınıf en sonda (K-143). */
export const dataList = (entity: string) => `validation-data-${entity}`;
/** Kayıtlar görünümünün üç seçeneği (K-143): işlenmiş katmanın bulgulu satırları, kuralla değişenleri ya da tamamı. */
export type RecordScope = "findings" | "effects" | "all";
export const scopeFilter = (scope: RecordScope): ListFilter[] =>
  scope === "findings" ? [{ field: "HasFindings", op: "in", values: [true] }] : scope === "effects" ? [{ field: "HasEffects", op: "in", values: [true] }] : [];

/** Kayıtlar'ı bir kurala takılan satırlarla süzer (Bulgular'da kurala tıklayınca, K-139). */
export const ruleFilter = (ruleId: number): ListFilter => ({ field: "RuleIds", op: "contains", value: `,${ruleId},` });

export const validationApi = {
  summary: (entity: string, signal?: AbortSignal) => getJson<ValidationSummary>(`/api/validation/${encodeURIComponent(entity)}`, signal),
  revalidate: (entity: string) => postJson<{ job_id: number }>(`/api/validation/${encodeURIComponent(entity)}/revalidate`, {}),
  rule: (id: number, signal?: AbortSignal) => getJson<RuleDetail>(`/api/validation-rules/${id}`, signal),
  fields: (entity: string, signal?: AbortSignal) => getJson<FieldInfo[]>(`/api/validation-rules/fields/${encodeURIComponent(entity)}`, signal),
  save: (changes: RuleChange[], thresholds: { entity: string; value: string | null }[]) =>
    sendJson<{ saved: number; changed_entities: string[] }>("PUT", "/api/validation-rules", { changes, thresholds }),
  /** Hatalı kayıtları indir: Kayıtlar görünümünün Excel'i, görünen kolonlar ve Sınıf (K-134). */
  downloadRecords: async (entity: string): Promise<ExportResult> => {
    const api = listApi(recordsList(entity));
    const { columns } = await api.columns();
    const result = await api.export({
      fields: columns.map((c) => c.field), widths: {}, sort: [], filters: scopeFilter("findings"), group_by: [], aggregates: {}, rules: [],
      scope: { rows: "all", columns: "all" },
    });
    if (result.kind === "file") saveBlob(result.blob, result.fileName);
    return result;
  },
};

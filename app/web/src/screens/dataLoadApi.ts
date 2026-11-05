// Excel şablonu ve yükleme uç noktaları (docs/08; K-110, K-129). Listeler ortak liste sözleşmesiyle (`data-entities`, `import-findings`).
import { downloadFile, getJson, postJson, uploadFile } from "../api/client";

export interface TemplateInfo {
  entity: string;
  name: string;
  version: number;
  file_name: string;
  field_count: number;
  required: string[];
}

export const MODE_CHANGED = "Değişen";
export const MODE_FULL = "Tam";

export interface ImportSummary {
  batch_id: number;
  entity: string;
  name: string;
  file_name: string;
  mode: string;
  status: string;
  checked: boolean;
  template_version: number | null;
  current_version: number;
  read: number | null;
  valid: number | null;
  errors: number | null;
  notes: number | null;
  file_findings: { severity: string; message: string }[];
  job: { id: number; status: string; progress: string | null } | null;
}

const imports = "/api/imports";

export const dataLoadApi = {
  upload: (entity: string, mode: string, file: File) =>
    uploadFile<ImportSummary | { batch_id: number; job_id: number }>(`${imports}/${encodeURIComponent(entity)}?mode=${encodeURIComponent(mode)}`, file),
  pending: (entity: string, signal?: AbortSignal) => getJson<ImportSummary | null>(`${imports}/pending/${encodeURIComponent(entity)}`, signal),
  summary: (batchId: number, signal?: AbortSignal) => getJson<ImportSummary>(`${imports}/${batchId}`, signal),
  continueBatch: (batchId: number) => postJson<ImportSummary>(`${imports}/${batchId}/continue`, {}),
  cancel: (batchId: number) => postJson<ImportSummary>(`${imports}/${batchId}/cancel`, {}),
  errorReport: (batchId: number) => downloadFile(`${imports}/${batchId}/error-report`, `hata-raporu_${batchId}.xlsx`),
  info: (entity: string, signal?: AbortSignal) => getJson<TemplateInfo>(`/api/templates/${encodeURIComponent(entity)}/info`, signal),
  download: (entity: string, fallback: string) => downloadFile(`/api/templates/${encodeURIComponent(entity)}`, fallback),
};

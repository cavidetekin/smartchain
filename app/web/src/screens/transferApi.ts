// Tam ve kısmi aktarım (docs/08; K-149…K-153, K-155): onay penceresi, başlatma, sonuç.
import { downloadFile, getJson, postJson } from "../api/client";

export const STATUS_READY = "Aktarılır";

export interface TransferPlanRow {
  entity: string;
  name: string;
  current_rows: number;
  error_rows: number;
  status: string;
  note: string | null;
  /** Çalışmayan veri kuralı sayısı (K-163): pencere uyarır, kullanıcı bilerek devam eder. */
  failed_rules?: number;
}

export interface TransferPlan {
  tables: TransferPlanRow[];
  blocked: { reason: string; tables: string[] } | null;
}

export interface PartialGroup {
  name: string;
  tables: TransferPlanRow[];
}

export interface PartialPlan {
  groups: PartialGroup[];
  busy: string | null;
  pending: string[];
}

export interface TransferTable {
  entity: string;
  name: string;
  new: number | null;
  changed: number | null;
  closed: number | null;
  not_transferred: number | null;
  note: string | null;
}

export interface TransferResult {
  job_id: number;
  status: string;
  progress: string | null;
  error: string | null;
  data_version: number | null;
  tables: TransferTable[];
  /** Veri aktarım raporu üst bilgisi (K-156). */
  transfer_type?: string;
  groups?: string[] | null;
  requested_by_name?: string | null;
  started_at?: string | null;
  duration_seconds?: number | null;
}

/** Ham veri temizliği (fonksiyon 09, K-156). */
export interface CleanupSummary {
  retention_days: number;
  batches: number;
  abandoned: number;
  rows: number;
  files: number;
  size: number;
  tables: { entity: string; name: string; rows: number }[];
}

export interface CleanupState {
  retention_days: number | null;
  last: { job_id: number; status: string; requested_at: string; ended_at: string | null; error: string | null; requested_by_name: string | null;
          result: (CleanupSummary & { note?: string }) | { note: string } | null } | null;
}

export interface CleanupPlan {
  retention_days: number | null;
  preview: CleanupSummary | null;
  blocked: string | null;
}

export const transferApi = {
  plan: (signal?: AbortSignal) => getJson<TransferPlan>("/api/transfers/plan", signal),
  start: () => postJson<{ job_id: number }>("/api/transfers", {}),
  partialPlan: (signal?: AbortSignal) => getJson<PartialPlan>("/api/transfers/partial/plan", signal),
  startPartial: (groups: string[]) => postJson<{ job_id: number }>("/api/transfers/partial", { groups }),
  result: (jobId: number, signal?: AbortSignal) => getJson<TransferResult>(`/api/transfers/${jobId}`, signal),
  excel: (jobId: number) => downloadFile(`/api/transfers/${jobId}/excel`, `smartchain_veri-aktarim-raporu_is-${jobId}.xlsx`),
};

export const cleanupApi = {
  state: (signal?: AbortSignal) => getJson<CleanupState>("/api/cleanup", signal),
  plan: (signal?: AbortSignal) => getJson<CleanupPlan>("/api/cleanup/plan", signal),
  start: () => postJson<{ job_id: number }>("/api/cleanup", {}),
};

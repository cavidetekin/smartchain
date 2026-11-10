// Tam aktarım (docs/08; K-149…K-153): onay penceresi, başlatma, sonuç.
import { getJson, postJson } from "../api/client";

export const STATUS_READY = "Aktarılır";

export interface TransferPlanRow {
  entity: string;
  name: string;
  current_rows: number;
  error_rows: number;
  status: string;
  note: string | null;
}

export interface TransferPlan {
  tables: TransferPlanRow[];
  blocked: { reason: string; tables: string[] } | null;
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
}

export const transferApi = {
  plan: (signal?: AbortSignal) => getJson<TransferPlan>("/api/transfers/plan", signal),
  start: () => postJson<{ job_id: number }>("/api/transfers", {}),
  result: (jobId: number, signal?: AbortSignal) => getJson<TransferResult>(`/api/transfers/${jobId}`, signal),
};

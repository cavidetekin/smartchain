// Zamanlanmış işler (ekran 25 · Zamanlanmış işler sekmesi, fonksiyon 92; K-163, K-164): tanım, bekleme süreleri, şimdi çalıştır, durum çipi.
import { getJson, postJson, sendJson } from "../api/client";

export const SCOPE_ALL = "Tümü";
export const SCOPE_SELECTED = "Seçilen";
export const MODE_FULL = "Tam";
export const MODE_PARTIAL = "Kısmi";
export const FLOW_STOPPED = "Durdu";
export const FLOW_NOT_STARTED = "Başlamadı";
export const FLOW_DONE = "Bitti";

export interface FlowRun {
  id: number;
  flow_id: number;
  flow_name: string;
  trigger: string;
  state: string;
  step: string;
  reason: string | null;
  scheduled_at: string;
  started_at: string | null;
  ended_at: string | null;
  data_version_id: number | null;
  transfer_job_id: number | null;
}

export interface Flow {
  id: number;
  name: string;
  is_active: boolean;
  run_time: string;
  days: number[];
  days_text: string;
  pull_scope: string;
  pull_tables: string[];
  transfer_mode: string;
  transfer_groups: string[];
  cleanup: boolean;
  updated_at: string;
  updated_by_name: string;
  next_at: string | null;
  last: FlowRun | null;
}

export interface FlowTable {
  entity: string;
  name: string;
  method: string;
}

export interface FlowOptions {
  tables: FlowTable[];
  sql_tables: string[];
  /** Aktarım grupları (Kısmi veri aktarımı kartları). */
  groups: { name: string; tables: FlowTable[]; sql_tables: string[] }[];
  /** Veri çekimi kümeleri: Ana veri ve aktarım grupları (K-164). */
  pull_sets: { name: string; tables: FlowTable[] }[];
}

export type FlowSettings = { FlowWaitMinutes: number; FlowRefreshWaitMinutes: number };

export interface FlowsResponse {
  flows: Flow[];
  options: FlowOptions;
  running: FlowRun | null;
  can_edit: boolean;
  settings: FlowSettings;
  limits: Record<keyof FlowSettings, { min: number; max: number }>;
}

export interface FlowBody {
  name: string;
  is_active: boolean;
  run_time: string;
  days: number[];
  pull_scope: string;
  pull_tables: string[];
  transfer_mode: string;
  transfer_groups: string[];
  cleanup: boolean;
}

export interface FlowAlert extends FlowRun {
  at: string;
}

export interface FlowStatus {
  running: (FlowRun & { message: string }) | null;
  alerts: FlowAlert[];
  can_view_history: boolean;
}

export const flowsApi = {
  list: (signal?: AbortSignal) => getJson<FlowsResponse>("/api/flows", signal),
  create: (body: FlowBody) => postJson<FlowsResponse & { id: number }>("/api/flows", body),
  update: (id: number, body: FlowBody) => sendJson<FlowsResponse & { id: number }>("PUT", `/api/flows/${id}`, body),
  saveSettings: (changes: Partial<FlowSettings>) => sendJson<FlowsResponse>("PUT", "/api/flows/settings", changes),
  runNow: (id: number) => postJson<{ run_id: number }>(`/api/flows/${id}/run`, {}),
  status: (signal?: AbortSignal) => getJson<FlowStatus>("/api/flows/status", signal),
  dismiss: (runId: number) => sendJson<void>("POST", `/api/flows/runs/${runId}/dismiss`),
};

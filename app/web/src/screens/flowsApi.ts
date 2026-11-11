// Zamanlanmış akışlar (ekran 23, fonksiyon 92; K-163): tanım, şimdi çalıştır, durum çipi.
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

export interface FlowOptions {
  tables: { entity: string; name: string; method: string }[];
  sql_tables: string[];
  groups: { name: string; tables: { entity: string; name: string }[]; sql_tables: string[] }[];
}

export interface FlowsResponse {
  flows: Flow[];
  options: FlowOptions;
  running: FlowRun | null;
  can_edit: boolean;
  settings: { FlowWaitMinutes: number; FlowRefreshWaitMinutes: number };
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
  runNow: (id: number) => postJson<{ run_id: number }>(`/api/flows/${id}/run`, {}),
  status: (signal?: AbortSignal) => getJson<FlowStatus>("/api/flows/status", signal),
  dismiss: (runId: number) => sendJson<void>("POST", `/api/flows/runs/${runId}/dismiss`),
};

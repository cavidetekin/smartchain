// Sistem sağlığı uç noktaları (ekran 24, docs/08; K-106). Listeler ortak sözleşmeyle gelir.
import { getJson, sendJson } from "../api/client";
import type { Job } from "../api/client";

export type ServiceKey = "app" | "engine" | "database" | "notifications";

export interface ServiceInfo {
  key: ServiceKey;
  status: string;
  heartbeat_at?: string | null;
  started_at?: string;
  version?: string | null;
  busy?: number;
  ms?: number;
  pool_in_use?: number;
  pool_size?: number;
  connections?: number;
}

export interface HealthSummary {
  server_time: string;
  cards: {
    queue: { queued: number; oldest_wait_minutes: number | null; threshold: number; warn: boolean };
    interactive: { running: number; limit: number };
    errors: { last_7_days: number; resolved: number };
    disk: { percent: number; free_bytes: number; threshold: number; warn: boolean; database_bytes: number; data_versions: number };
  };
  services: ServiceInfo[];
}

export interface EventDetail {
  id: number;
  occurred_at: string;
  component: string;
  message: string;
  resolution: string | null;
  is_resolved: boolean;
  job_id: number | null;
  trace_id: string | null;
  detail: string | null;
}

export const systemHealthApi = {
  summary: (signal?: AbortSignal) => getJson<HealthSummary>("/api/system-health", signal),
  event: (id: number, signal?: AbortSignal) => getJson<EventDetail>(`/api/system-events/${id}`, signal),
  prioritize: (jobId: number) => sendJson<Job>("POST", `/api/jobs/${jobId}/prioritize`, {}),
};

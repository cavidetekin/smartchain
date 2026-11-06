// Entegrasyon tanımı ve veri çekme uç noktaları (docs/08, K-130). Listeler ortak liste sözleşmesiyle (`data-entities`, `integration-entities`).
import { getJson, postJson, sendJson } from "../api/client";

export const METHODS = ["Excel", "SQL"] as const;  // API 11.5'te
export const METHOD_SQL = "SQL";

export type PullState = "Okunacak" | "Yeni veri yok" | "Veri güncellemesi devam ediyor" | "Atlandı" | "Hata" | "Alındı" | "Hatalı" | "Tamamlanmadı";

/** Tablo içi düzenlemenin toplu kaydı (K-132). */
export interface EntityChange {
  entity: string;
  method?: string;
  view?: string;
  pull_enabled?: boolean;
  reason?: string;
}

export interface PullPlanRow {
  entity: string;
  name: string;
  method: string;
  source: string | null;
  state: PullState;
  reason: string | null;
}

export interface PullPlan {
  database: string | null;
  tables: PullPlanRow[];
  last: { at: string; by: string } | null;
}

export interface PullAttempt {
  attempt: number;
  at: string;
  message: string;
}

export interface PullTable {
  entity: string;
  name: string;
  method: string;
  source: string | null;
  status: PullState;
  reason: string | null;
  read: number | null;
  valid: number | null;
  errors: number | null;
  batch_id: number | null;
  attempts: PullAttempt[];
}

export interface PullResult {
  job_id: number;
  status: string;
  progress: string | null;
  error: string | null;
  requested_at: string;
  tables: PullTable[];
}

export interface Connection {
  database: string | null;
  account: string;
  last_read: string | null;
  last_upload: string | null;
  sql_tables: number;
  excel_tables: number;
}

export interface TestStep {
  key: string;
  label: string;
  ok: boolean;
  detail: string;
  ms: number;
}

export interface TestTable {
  entity: string;
  name: string;
  view: string;
  status: string;
  matched: number;
  expected: number;
  errors: string[];
  warnings: string[];
  notes: string[];
}

export interface TestResult {
  database: string;
  ok: boolean;
  steps: TestStep[];
  tables: TestTable[];
}

export interface Preview {
  entity: string;
  name: string;
  view: string;
  status: string;
  errors: string[];
  warnings: string[];
  columns: { field: string; label: string }[];
  rows: { values: Record<string, string | number | boolean | null>; findings: { severity: string; field: string | null; message: string }[] }[];
}

export interface ViewVersion {
  version: number;
  view: string;
  seen_at: string;
  app_version: string;
  definition: string | null;
}

const entityPath = (entity: string) => `/api/integration/entities/${encodeURIComponent(entity)}`;

export const integrationApi = {
  saveEntities: (changes: EntityChange[]) => sendJson<{ saved: number }>("PUT", "/api/integration/entities", { changes }),
  connection: (signal?: AbortSignal) => getJson<Connection>("/api/integration/connection", signal),
  saveConnection: (database: string) => sendJson<Connection>("PUT", "/api/integration/connection", { database }),
  test: () => postJson<TestResult>("/api/integration/test", {}),
  preview: (entity: string) => postJson<Preview>(`${entityPath(entity)}/preview`, {}),
  viewVersions: (entity: string, signal?: AbortSignal) => getJson<ViewVersion[]>(`${entityPath(entity)}/view-versions`, signal),
  pullPlan: (signal?: AbortSignal) => getJson<PullPlan>("/api/pulls/plan", signal),
  startPull: (entities: string[], readAnyway: string[]) => postJson<{ job_id: number }>("/api/pulls", { entities, read_anyway: readAnyway }),
  pullResult: (jobId: number, signal?: AbortSignal) => getJson<PullResult>(`/api/pulls/${jobId}`, signal),
};

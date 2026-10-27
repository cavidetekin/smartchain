// API istemcisi. Adresler göreli: geliştirmede Vite, kurulumda IIS /api'yi API'ye yönlendirir (K-74, K-83).

export interface ApiErrorDetail {
  field: string;
  problem: string;
}

export interface ApiErrorBody {
  error: { code: string; message: string; trace_id: string; details?: ApiErrorDetail[] };
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: ApiErrorDetail[] = []) {
    super(message);
  }
}

async function readJson<T>(r: Response): Promise<T> {
  if (!r.ok) {
    let code = `http_${r.status}`;
    let message = r.statusText;
    let details: ApiErrorDetail[] = [];
    try {
      const body = (await r.json()) as ApiErrorBody;
      code = body.error.code;
      message = body.error.message;
      details = body.error.details ?? [];
    } catch {
      // gövde JSON değil
    }
    throw new ApiError(r.status, code, message, details);
  }
  return (await r.json()) as T;
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return readJson<T>(await fetch(path, { headers: { Accept: "application/json" }, signal }));
}

export async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return readJson<T>(await fetch(path, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  }));
}

export interface DataVersion {
  id: number;
  location_code: string;
  created_at: string;
  load_type: string;
  is_synthetic: boolean;
}

export interface Job {
  id: number;
  job_type: string;
  channel: string;
  status: string;
  progress: string | null;
  queue_position: number | null;
  updated_at: string;
}

export interface JobList {
  jobs: Job[];
  counters: Record<string, { running: number; queued: number; limit: number }>;
}

export const api = {
  currentDataVersion: () => getJson<DataVersion>("/api/data-versions/current"),
  jobs: (userId: number) => getJson<JobList>(`/api/jobs?user_id=${userId}`),
};

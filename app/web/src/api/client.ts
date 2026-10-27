// API istemcisi. Adresler göreli: geliştirmede Vite, kurulumda IIS /api'yi API'ye yönlendirir (K-74, K-83).

export interface ApiErrorBody {
  error: { code: string; message: string; trace_id: string };
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

export async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(path, { headers: { Accept: "application/json" } });
  if (!r.ok) {
    let code = `http_${r.status}`;
    let message = r.statusText;
    try {
      const body = (await r.json()) as ApiErrorBody;
      code = body.error.code;
      message = body.error.message;
    } catch {
      // gövde JSON değil
    }
    throw new ApiError(r.status, code, message);
  }
  return (await r.json()) as T;
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

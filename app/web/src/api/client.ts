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

/** Oturum olayı (K-97): herhangi bir istek oturumun bittiğini (401) söylerse ya da WebSocket oturum bitti diye
 *  kapanırsa yayılır; oturum sağlayıcısı (auth/AuthContext) giriş sayfasına döner. */
export const AUTH_EVENT = "smartchain:auth";
export type AuthEventDetail = { kind: "expired"; code: string; message: string } | { kind: "check" };
const SESSION_CODES = new Set(["not_authenticated", "session_expired"]);

export function emitAuth(detail: AuthEventDetail): void {
  window.dispatchEvent(new CustomEvent<AuthEventDetail>(AUTH_EVENT, { detail }));
}

/** Yetki reddi (K-100): sunucu 403 forbidden ya da sahiplik reddi (…_not_owner) dönerse kabuk tek yerde bildirir.
 *  Giriş akışının 403'leri (kilit, kapalı hesap, şifre değişikliği, köken) bu olayı yaymaz. */
export const FORBIDDEN_EVENT = "smartchain:forbidden";
const isForbidden = (code: string) => code === "forbidden" || code.endsWith("_not_owner");

/** Oturumdaki rol (AuthContext koyar). Sunucunun X-Smartchain-Role başlığı farklıysa rol değişmiştir: me yenilenir. */
let knownRole: string | null = null;
export function setKnownRole(role: string | null): void {
  knownRole = role;
}

/** Hata cevabını (docs/08) ApiError'a çevirir; başarılıysa cevabı olduğu gibi döndürür. */
export async function ensureOk(r: Response): Promise<Response> {
  const role = r.headers?.get("X-Smartchain-Role");
  if (role && knownRole && role !== knownRole) {
    knownRole = role;
    emitAuth({ kind: "check" });
  }
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
    if (r.status === 401 && SESSION_CODES.has(code)) emitAuth({ kind: "expired", code, message });
    if (r.status === 403 && isForbidden(code)) {
      window.dispatchEvent(new CustomEvent<string>(FORBIDDEN_EVENT, { detail: message }));
    }
    throw new ApiError(r.status, code, message, details);
  }
  return r;
}

async function readJson<T>(r: Response): Promise<T> {
  await ensureOk(r);
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return readJson<T>(await fetch(path, { headers: { Accept: "application/json" }, signal }));
}

export async function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return sendJson<T>("POST", path, body, signal);
}

export async function sendJson<T>(method: "POST" | "PUT" | "DELETE", path: string, body?: unknown,
                                  signal?: AbortSignal): Promise<T> {
  return readJson<T>(await fetch(path, {
    method,
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  }));
}

/** Content-Disposition'daki dosya adı (filename*=UTF-8''… önce). */
export function fileNameFrom(disposition: string | null, fallback: string): string {
  const utf = /filename\*=UTF-8''([^;]+)/i.exec(disposition ?? "");
  if (utf) return decodeURIComponent(utf[1]);
  const plain = /filename="?([^";]+)"?/i.exec(disposition ?? "");
  return plain ? plain[1] : fallback;
}

/** Dosyayı tarayıcının indirmesine verir (internetsiz; bağlantı bellekteki dosyaya). */
export function saveBlob(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/** Sunucudaki dosyayı indirir; hata (ör. 410 süresi geçti) ApiError olarak döner. */
export async function downloadFile(path: string, fallback: string): Promise<void> {
  const r = await ensureOk(await fetch(path));
  saveBlob(await r.blob(), fileNameFrom(r.headers.get("Content-Disposition"), fallback));
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
  requested_by?: number | null;
  requested_by_name?: string | null;
  progress: string | null;
  error_text?: string | null;
  queue_position: number | null;
  updated_at: string;
}

export interface JobList {
  jobs: Job[];
  counters: Record<string, { running: number; queued: number; limit: number }>;
}

export const api = {
  currentDataVersion: () => getJson<DataVersion>("/api/data-versions/current"),
  /** Oturumdaki kullanıcının işleri (K-97); "all": herkesin işleri (93, Admin ve System owner; K-100). */
  jobs: (scope: "own" | "all" = "own") => getJson<JobList>(scope === "all" ? "/api/jobs?scope=all" : "/api/jobs"),
  /** Sıradaki işi iptal eder (kendi işi 48; başkasının işi 93). */
  cancelJob: (jobId: number) => postJson<Job>(`/api/jobs/${jobId}/cancel`, {}),
  /** Arka planda hazırlanan Excel dosyası (K-91). */
  downloadExport: (jobId: number, fallback: string) => downloadFile(`/api/exports/${jobId}/file`, fallback),
};

/** İş türü ve durumları (app/jobs/constants.py). */
export const JOB_EXPORT = "Dışa aktarım";
export const JOB_DONE = "Bitti";
export const JOB_FAILED = "Hata";

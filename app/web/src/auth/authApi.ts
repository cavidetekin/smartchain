// Giriş ve oturum uç noktaları (docs/08 "Oturum ve kimlik"; K-97, K-98).
import { getJson, postJson } from "../api/client";

export interface PasswordPolicy {
  min_length: number;
  require_letter_and_digit: boolean;
  history_count: number;
  lock_after: number;
  lock_minutes: number;
}

export interface Me {
  id: number;
  user_name: string;
  full_name: string | null;
  role: string;
  /** Rolün her fonksiyondaki yetki düzeyi (K-100): "10" → "read" … */
  permissions: Record<string, string>;
  must_change_password: boolean;
  /** "İlk giriş" | "Sıfırlama" | "Süre doldu" */
  password_change_reason: string | null;
  idle_seconds_left: number;
  session: { idle_minutes: number; warning_minutes: number };
  policy: PasswordPolicy;
}

export const authApi = {
  me: () => getJson<Me>("/api/auth/me"),
  login: (user_name: string, password: string) => postJson<Me>("/api/auth/login", { user_name, password }),
  logout: () => postJson<void>("/api/auth/logout", {}),
  /** Kullanıcı etkinliği: hareketsizlik sayacı sıfırlanır (yalnız kullanıcı girdisi olunca, en çok dakikada bir). */
  activity: () => postJson<{ idle_seconds_left: number }>("/api/auth/activity", {}),
  changePassword: (current_password: string, new_password: string) =>
    postJson<void>("/api/auth/password", { current_password, new_password }),
};

/** Sürüm (giriş sayfasının alt satırı); /api/health oturumsuz açıktır. Ulaşılamazsa null. */
export async function appVersion(): Promise<string | null> {
  try {
    const r = await fetch("/api/health", { headers: { Accept: "application/json" } });
    return ((await r.json()) as { app_version?: string }).app_version ?? null;
  } catch {
    return null;
  }
}

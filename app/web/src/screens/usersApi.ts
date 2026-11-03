// Kullanıcı yönetimi uç noktaları (docs/08 "Kullanıcılar"; K-101). Liste ortak liste sözleşmesiyle gelir (listApi("users")).
import { getJson, postJson, sendJson } from "../api/client";

export type UserAction = "role" | "name" | "reset" | "unlock" | "close" | "reopen";

export interface UserRecord {
  id: number;
  user_name: string;
  full_name: string | null;
  role: string;
  status: string;
  is_active: boolean;
  last_login_at: string | null;
  open_sessions: number;
}

export interface ActionState {
  allowed: boolean;
  reason: string | null;
  required_role: string | null;
}

export interface UserDetail {
  user: UserRecord;
  actions: Record<UserAction, ActionState>;
  assignable_roles: string[];
}

/** Geçici şifre yalnız bu cevapta gelir (Cache-Control: no-store); arayüz pencere kapanınca unutur. */
export interface TemporaryPassword {
  user: UserRecord;
  temporary_password: string;
}

export const usersApi = {
  detail: (id: number, signal?: AbortSignal) => getJson<UserDetail>(`/api/users/${id}`, signal),
  create: (body: { full_name: string; user_name: string; role: string }) => postJson<TemporaryPassword>("/api/users", body),
  changeRole: (id: number, role: string) => sendJson<{ user: UserRecord }>("PUT", `/api/users/${id}/role`, { role }),
  changeName: (id: number, full_name: string) => sendJson<{ user: UserRecord }>("PUT", `/api/users/${id}/name`, { full_name }),
  resetPassword: (id: number) => postJson<TemporaryPassword>(`/api/users/${id}/reset-password`, {}),
  unlock: (id: number) => postJson<{ user: UserRecord }>(`/api/users/${id}/unlock`, {}),
  close: (id: number) => postJson<{ user: UserRecord }>(`/api/users/${id}/close`, {}),
  reopen: (id: number) => postJson<{ user: UserRecord }>(`/api/users/${id}/reopen`, {}),
};

/** K-101: küçük harf, Türkçe karaktersiz, rakam ve . _ -; harfle başlar, 2–60 karakter. Sunucuyla aynı. */
export const USER_NAME_PATTERN = /^[a-z][a-z0-9._-]{1,59}$/;

/** Kopyala (K-101): navigator.clipboard yalnız HTTPS'te ya da localhost'ta var; yoksa seçili alandan kopyalanır. */
export async function copyText(text: string, input: HTMLInputElement | null): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // izin yoksa aşağıdaki yol denenir
  }
  if (!input) return false;
  input.focus();
  input.select();
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  }
}

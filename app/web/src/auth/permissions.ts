// Yetki (fonksiyon 90; K-99, K-100). Kullanıcının yetkisi her zaman sunucudan, GET /api/auth/me'nin permissions
// alanından gelir; arayüz yalnız görünürlüğü ayarlar, güvenlik sunucudadır. Gereken rolü (ipucu metni) bulmak için
// matrisin üretilmiş kopyası okunur: app/shared/permissions.json (python -m app.api.permissions; tek kaynak kod).
import matrix from "../../../shared/permissions.json";
import { tr } from "../i18n/tr";
import type { Me } from "./authApi";

export type Level = "full" | "owner" | "self" | "read" | "none";
export type Access = "read" | "write";

export const ROLES = matrix.roles as readonly string[];
export const SYSTEM_OWNER = "System owner";

/** own: kullanıcının kendi nesnesi ya da kaydı mı (sahibi ve kendi düzeyleri için). */
export function allows(level: Level, access: Access, own = true): boolean {
  switch (level) {
    case "full": return true;
    case "owner": return access === "read" || own;
    case "self": return own;
    case "read": return access === "read";
    default: return false;
  }
}

export function can(me: Me, fn: number, access: Access = "read", own = true): boolean {
  return allows((me.permissions[String(fn)] ?? "none") as Level, access, own);
}

/** O erişime (başkasının nesnesi dahil) izin veren en dar rol. */
export function requiredRole(fn: number, access: Access): string {
  const levels = matrix.functions[fn - 1]?.levels as Record<string, Level> | undefined;
  for (const role of [...ROLES].reverse()) {
    if (levels && allows(levels[role], access, false)) return role;
  }
  return SYSTEM_OWNER;
}

/** Pasif düğmenin ve yetkisiz ekranın açıklaması: "Bu işlem için Admin yetkisi gerekir. Yetki için yöneticinize…". */
export function forbiddenReason(fn: number, access: Access): string {
  const role = requiredRole(fn, access);
  return tr.authz.required(role, role === SYSTEM_OWNER);
}

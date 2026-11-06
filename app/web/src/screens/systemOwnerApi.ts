// Sistem ayarları ve yetki matrisi uç noktaları (docs/08; K-100, K-104, K-105). Liste ortak sözleşmeyle gelir.
import { downloadFile, getJson, sendJson } from "../api/client";

export interface FieldDetail {
  table: string;
  field: string;
  label: string | null;
  standard_label: string;
  description: string | null;
  is_additional: boolean;
  field_class: string;
  value_priority: string | null;
  manual_overrides: boolean | null;
  editable_in_workspace: boolean;
  is_required: boolean | null;
  if_empty: string | null;
  options: { field_class: string[]; value_priority: string[] };
  used_in_views: number;
  used_in_rules: number;
}

export type PolicyKey =
  | "PasswordMinLength" | "PasswordRequireLetterAndDigit" | "PasswordHistoryCount" | "PasswordMaxAgeDays"
  | "LoginMaxFailedAttempts" | "LoginLockMinutes" | "SessionIdleMinutes" | "SessionWarningMinutes";

export type PolicyValues = Record<PolicyKey, number | boolean>;

export interface LoginPolicy {
  values: PolicyValues;
  defaults: PolicyValues;
  limits: Partial<Record<PolicyKey, { min: number; max: number }>>;
}

export interface HealthSettings {
  values: Record<string, number>;
  defaults: Record<string, number>;
  limits: Partial<Record<string, { min: number; max: number }>>;
}

export type Level = "full" | "owner" | "self" | "read" | "none";

export interface PermissionMatrix {
  roles: string[];
  groups: { key: string; name: string; levels: Record<string, Level> }[];
}

const path = (table: string, field: string) => `/api/field-definitions/${encodeURIComponent(table)}/${encodeURIComponent(field)}`;

export const systemOwnerApi = {
  field: (table: string, field: string, signal?: AbortSignal) => getJson<FieldDetail>(path(table, field), signal),
  setLabel: (table: string, field: string, label: string) => sendJson<FieldDetail>("PUT", `${path(table, field)}/label`, { label }),
  policy: (signal?: AbortSignal) => getJson<LoginPolicy>("/api/settings/login-policy", signal),
  setPolicy: (changes: Partial<PolicyValues>) => sendJson<LoginPolicy>("PUT", "/api/settings/login-policy", changes),
  healthSettings: (signal?: AbortSignal) => getJson<HealthSettings>("/api/settings/health", signal),
  setHealthSettings: (changes: Record<string, number | boolean | null>) => sendJson<HealthSettings>("PUT", "/api/settings/health", changes),
  matrix: (signal?: AbortSignal) => getJson<PermissionMatrix>("/api/permissions/matrix", signal),
  exportMatrix: () => downloadFile("/api/permissions/matrix/export", "smartchain_yetki-matrisi.xlsx"),
};

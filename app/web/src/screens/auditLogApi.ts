// Denetim izi uç noktaları (ekran 26, docs/08; K-108). Liste ortak sözleşmeyle gelir.
import { getJson } from "../api/client";

export interface AuditChange {
  field: string;
  old: string;
  new: string;
}

export interface AuditDetail {
  id: number;
  at: string;
  actor: string;
  action: string;
  object_type: string | null;
  object: string | null;
  has_object: boolean;
  changes: AuditChange[];
  /** "Kayda git" (K-173): nesnesi veri kaydı olan satırda hedef ya da bulunamama nedeni. */
  target?: { list: string; id: string } | null;
  target_reason?: string;
}

export interface AuditHistory {
  rows: { id: number; at: string; actor: string; action: string }[];
  truncated: boolean;
}

export const auditLogApi = {
  detail: (id: number, signal?: AbortSignal) => getJson<AuditDetail>(`/api/audit-log/${id}`, signal),
  history: (id: number, signal?: AbortSignal) => getJson<AuditHistory>(`/api/audit-log/${id}/history`, signal),
};

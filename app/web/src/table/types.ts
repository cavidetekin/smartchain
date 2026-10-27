// Liste sorgu sözleşmesi (K-87, docs/08 "Liste sorgusu"): sunucuyla birebir.
import { getJson, postJson, sendJson } from "../api/client";

export type ColumnType = "text" | "integer" | "number" | "bool" | "date" | "datetime";
export type FilterType = "text" | "list" | "number" | "date";
export type ListValue = string | boolean;

export interface ListColumn {
  field: string;
  label: string;
  type: ColumnType;
  filter: FilterType;
  values: ListValue[] | null;
  values_from_server: boolean;
  decimals: number | null;
  /** Miktar kolonu: ondalık her satırda birimden (satırdaki _unit_decimals; K-88). */
  decimals_from_unit: boolean;
  /** Gruplamada ara toplam (K-90). */
  aggregate: "sum" | "avg" | null;
  default_visible: boolean;
}

export interface ColumnsResponse {
  /** Parça büyüklüğü: SystemSetting ListChunkSize; tablo bir istekte bundan fazlasını istemez. */
  chunk_size: number;
  columns: ListColumn[];
}

export type TextOp = "contains" | "not_contains" | "equals" | "starts_with";
export type NumberOp = "between" | "eq" | "gt" | "lt";
export type RelativeDate = "this_week" | "next_4_weeks";

export interface ListFilter {
  field: string;
  op: TextOp | NumberOp | "in" | "relative" | "empty";
  value?: string | number;
  values?: ListValue[];
  min?: number;
  max?: number;
  from?: string;
  to?: string;
  /** Liste filtresinde: değerler ya da boş (U-13). */
  empty?: boolean;
}

export interface SortItem {
  field: string;
  dir: "asc" | "desc";
}

export interface GroupKey {
  field: string;
  value: ListValue | null;
}

export interface QueryRequest {
  fields: string[];
  sort: SortItem[];
  filters: ListFilter[];
  offset: number;
  limit: number;
  group_key?: GroupKey[];
}

/** Grup ağacı düğümü (K-90): key kökten bu gruba kadar değerler; null boş grup. */
export interface GroupNode {
  key: (ListValue | null)[];
  count: number;
  aggregates: Record<string, number | null>;
  mixed_units: string[];
  unit_decimals: Record<string, number>;
  children?: GroupNode[];
}

export interface GroupsResponse {
  groups: GroupNode[];
  aggregates: Record<string, number | null>;
  leaf_groups: number;
  filtered: number;
  total: number;
}

/** Kayıtlı görünüm içeriği, sürüm 1 (K-89, docs/08). Genişlik rem. */
export interface ViewDefinition {
  v: 1;
  columns: { field: string; width?: number | null }[];
  pinned: number;
  sort: SortItem[];
  filters: ListFilter[];
  group_by: string[];
}

export interface SavedView {
  id: number;
  name: string;
  owner_user_id: number;
  owner_name: string;
  is_shared: boolean;
  is_owner: boolean;
  updated_at: string;
  definition: ViewDefinition;
  warnings: string[];
}

export interface ViewsResponse {
  views: SavedView[];
  default_view_id: number | null;
}

export type Row = { Id: number } & Record<string, unknown>;

export interface QueryResponse {
  rows: Row[];
  offset: number;
  filtered: number;
  total: number;
}

export interface ValueCount {
  /** null: boş değerlerin sayısı (U-13). */
  value: ListValue | null;
  count: number;
}

export function listApi(list: string) {
  const base = `/api/${list}`;
  return {
    columns: (signal?: AbortSignal) => getJson<ColumnsResponse>(`${base}/columns`, signal),
    query: (body: QueryRequest, signal?: AbortSignal) => postJson<QueryResponse>(`${base}/query`, body, signal),
    values: (body: { field: string; search: string; filters: ListFilter[] }, signal?: AbortSignal) =>
      postJson<ValueCount[]>(`${base}/values`, body, signal),
    groups: (body: { group_by: string[]; fields: string[]; filters: ListFilter[]; sort: SortItem[] }, signal?: AbortSignal) =>
      postJson<GroupsResponse>(`${base}/groups`, body, signal),
    views: (userId: number, signal?: AbortSignal) => getJson<ViewsResponse>(`${base}/views?user_id=${userId}`, signal),
    createView: (userId: number, body: { name: string; is_shared: boolean; definition: ViewDefinition }) =>
      sendJson<SavedView>("POST", `${base}/views?user_id=${userId}`, body),
    updateView: (userId: number, id: number, body: { name?: string; is_shared?: boolean; definition?: ViewDefinition }) =>
      sendJson<SavedView>("PUT", `${base}/views/${id}?user_id=${userId}`, body),
    deleteView: (userId: number, id: number) => sendJson<void>("DELETE", `${base}/views/${id}?user_id=${userId}`),
    setDefaultView: (userId: number, viewId: number | null) =>
      sendJson<{ default_view_id: number | null }>("PUT", `${base}/views/default?user_id=${userId}`, { view_id: viewId }),
  };
}

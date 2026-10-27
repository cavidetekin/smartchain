// Liste sorgu sözleşmesi (K-87, docs/08 "Liste sorgusu"): sunucuyla birebir.
import { getJson, postJson } from "../api/client";

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
  op: TextOp | NumberOp | "in" | "relative";
  value?: string | number;
  values?: ListValue[];
  min?: number;
  max?: number;
  from?: string;
  to?: string;
}

export interface SortItem {
  field: string;
  dir: "asc" | "desc";
}

export interface QueryRequest {
  fields: string[];
  sort: SortItem[];
  filters: ListFilter[];
  offset: number;
  limit: number;
}

export type Row = { Id: number } & Record<string, unknown>;

export interface QueryResponse {
  rows: Row[];
  offset: number;
  filtered: number;
  total: number;
}

export interface ValueCount {
  value: ListValue;
  count: number;
}

export function listApi(list: string) {
  const base = `/api/${list}`;
  return {
    columns: (signal?: AbortSignal) => getJson<ColumnsResponse>(`${base}/columns`, signal),
    query: (body: QueryRequest, signal?: AbortSignal) => postJson<QueryResponse>(`${base}/query`, body, signal),
    values: (body: { field: string; search: string; filters: ListFilter[] }, signal?: AbortSignal) =>
      postJson<ValueCount[]>(`${base}/values`, body, signal),
  };
}

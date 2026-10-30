// Liste sorgu sözleşmesi (K-87, docs/08 "Liste sorgusu"): sunucuyla birebir.
import { ensureOk, fileNameFrom, getJson, postJson, sendJson } from "../api/client";

export type ColumnType = "text" | "integer" | "number" | "bool" | "date" | "datetime";
export type FilterType = "text" | "list" | "number" | "date";
export type ListValue = string | boolean;

/** Ara toplam türü (K-90, docs/08). */
export type AggFn = "sum" | "avg" | "avg_nonzero" | "wavg" | "min" | "max" | "count" | "none";
export interface AggSpec {
  fn: AggFn;
  /** Yalnız wavg: ağırlık alanı (sayı). */
  weight?: string;
}

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
  /** Gruplamada varsayılan ara toplam (K-90). */
  aggregate: AggFn | null;
  default_visible: boolean;
}

/** Dışa aktarım bilgisi (K-91): listenin adı, dosya adındaki kısa ad, anlık eşik ve üst sınır. */
export interface ExportInfo {
  title: string;
  file_slug: string;
  sync_max_rows: number;
  max_rows: number;
  /** Arka planda hazırlanan dosyanın indirilebileceği süre (saat). */
  file_hours: number;
}

export interface ColumnsResponse {
  /** Parça büyüklüğü: SystemSetting ListChunkSize; tablo bir istekte bundan fazlasını istemez. */
  chunk_size: number;
  columns: ListColumn[];
  export: ExportInfo;
}

/** Excel'e aktarım kapsamı (K-91, docs/08 "Dışa aktarım"). */
export interface ExportScope {
  rows: "filtered" | "all";
  columns: "visible" | "all";
}

export interface ExportRequest {
  fields: string[];
  widths: Record<string, number>;
  sort: SortItem[];
  filters: ListFilter[];
  group_by: string[];
  aggregates: Record<string, AggSpec>;
  /** Aktif ve görünen kolonların kuralları; Excel hücresine uygulanır (K-95). */
  rules: FormatRule[];
  scope: ExportScope;
}

/** Anlık: dosya gövdede (200). Arka plan: iş (202), bitince bildirim. */
export type ExportResult =
  | { kind: "file"; blob: Blob; fileName: string }
  | { kind: "job"; job_id: number; file_name: string; rows: number };

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

/** Koşullu biçim kuralı (U-24, K-95, docs/08 "Koşullu biçim kuralları"). */
export type RuleOp = "gt" | "lt" | "between" | "eq" | "empty" | "relative" | "equals" | "contains" | "starts_with" | "in"
  | "always";  // "Her zaman": koşulsuz kolon biçimi
export type RuleIcon = "arrow_up" | "arrow_down" | "dot" | "warning" | "check" | "cross" | "flag" | "star";
export const RULE_ICONS: RuleIcon[] = ["arrow_up", "arrow_down", "dot", "warning", "check", "cross", "flag", "star"];
export const MAX_RULES = 20;

export interface RuleCondition {
  op: RuleOp;
  value?: string | number;
  values?: ListValue[];
  min?: number;
  max?: number;
  from?: string;
  to?: string;
  /** Sayı ve tarihte gt/lt/eq için sabit değer yerine başka alan (aynı tipte). */
  field_ref?: string;
  /** Sayı alanı karşılaştırmasında boşları 0 say (yoksa: evet). */
  empty_as_zero?: boolean;
}

export interface RuleFormat {
  fill?: string;
  color?: string;
  bold?: boolean;
  icon?: RuleIcon;
  /** İkonun rengi (yoksa ikonun varsayılan rengi; Excel'de ikon hücrenin yazı rengiyle). */
  icon_color?: string;
}

export interface RuleSpec {
  field: string;
  condition: RuleCondition;
}

export interface FormatRule extends RuleSpec {
  id: string;
  enabled: boolean;
  format: RuleFormat;
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
  /** Koşullu biçim (K-95): satırlar _rules ile döner (tutan kuralların bu listedeki sırası). */
  rules?: RuleSpec[];
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
  /** Varsayılandan farklı seçilen ara toplam türleri (K-90). */
  aggregates?: Record<string, AggSpec>;
  /** Koşullu biçim kuralları, sıralı: üstteki kazanır (K-95). */
  rules?: FormatRule[];
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
    groups: (body: { group_by: string[]; fields: string[]; aggregates: Record<string, AggSpec>; filters: ListFilter[];
                     sort: SortItem[] }, signal?: AbortSignal) =>
      postJson<GroupsResponse>(`${base}/groups`, body, signal),
    views: (userId: number, signal?: AbortSignal) => getJson<ViewsResponse>(`${base}/views?user_id=${userId}`, signal),
    createView: (userId: number, body: { name: string; is_shared: boolean; definition: ViewDefinition }) =>
      sendJson<SavedView>("POST", `${base}/views?user_id=${userId}`, body),
    updateView: (userId: number, id: number, body: { name?: string; is_shared?: boolean; definition?: ViewDefinition }) =>
      sendJson<SavedView>("PUT", `${base}/views/${id}?user_id=${userId}`, body),
    deleteView: (userId: number, id: number) => sendJson<void>("DELETE", `${base}/views/${id}?user_id=${userId}`),
    export: async (userId: number, body: ExportRequest): Promise<ExportResult> => {
      const r = await ensureOk(await fetch(`${base}/export?user_id=${userId}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      }));
      if (r.status === 202) return { kind: "job", ...(await r.json() as { job_id: number; file_name: string; rows: number }) };
      return { kind: "file", blob: await r.blob(), fileName: fileNameFrom(r.headers.get("Content-Disposition"), "smartchain.xlsx") };
    },
    setDefaultView: (userId: number, viewId: number | null) =>
      sendJson<{ default_view_id: number | null }>("PUT", `${base}/views/default?user_id=${userId}`, { view_id: viewId }),
  };
}

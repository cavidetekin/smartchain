// Tablo testleri için sahte liste sunucusu (K-87, K-89, K-90): kolonlar, parça satırlar, değerler, gruplar, görünümler.
// İstekler `calls`'a kaydedilir; testler sözleşmeye gidenleri doğrular.
import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect } from "vitest";

import { mockApi, mockSocket, renderApp, type Reply } from "../test/helpers";
import type {
  ExportInfo, ExportRequest, GroupNode, GroupsResponse, ListColumn, QueryRequest, RuleSpec, SavedView, ViewDefinition,
  ViewsResponse,
} from "./types";

export const col = (field: string, label: string, type: ListColumn["type"], filter: ListColumn["filter"],
                    extra: Partial<ListColumn> = {}): ListColumn => ({
  field, label, type, filter, values: null, values_from_server: false, decimals: null, decimals_from_unit: false,
  aggregate: null, default_visible: true, ...extra,
});

export const COLUMNS: ListColumn[] = [
  col("Code", "Malzeme kodu", "text", "text"),
  col("Name", "Malzeme adı", "text", "text"),
  col("MaterialLevel", "Malzeme seviyesi", "text", "list", { values: ["Hammadde", "Yarı mamul", "Nihai ürün"] }),
  col("MaterialGroup", "Malzeme grubu", "text", "list", { values_from_server: true }),
  col("IsSellable", "Satılabilir", "bool", "list", { values: [true, false] }),
  col("SafetyStock", "Güvenlik stoğu", "number", "number", { decimals_from_unit: true, aggregate: "sum" }),
  col("UpdatedAt", "Son değişiklik zamanı", "datetime", "date"),
  col("AdditionalText1", "Malzeme sınıfı", "text", "text", { default_visible: false }),
  col("ProductionLeadTimeDays", "Üretim süresi (gün)", "number", "number", { decimals: 0, aggregate: "avg", default_visible: false }),
  col("LastReceiptDate", "Son giriş tarihi", "date", "date", { default_visible: false }),
];
export const STANDARD_FIELDS = ["Code", "Name", "MaterialLevel", "MaterialGroup", "IsSellable", "SafetyStock", "UpdatedAt"];

export const VIEW_PX = 560;

export interface Calls {
  queries: QueryRequest[];
  values: unknown[];
  groups: { group_by: string[]; fields: string[]; aggregates: Record<string, { fn: string; weight?: string }>; filters: unknown[]; sort: unknown[] }[];
  views: { method: string; url: string; body: unknown }[];
  exports: { url: string; body: ExportRequest }[];
  downloads: string[];
}
export const calls: Calls = { queries: [], values: [], groups: [], views: [], exports: [], downloads: [] };

/** Kural sorgularını bekleten kapı: açık değilse kurallı sorgu cevabı kapı açılana kadar gelmez. */
export const ruleGate = { hold: false, release: () => {} };

/** Sahte sunucunun kural değerlendirmesi (testlerde yeterli alt küme): sayı ve alan karşılaştırması, metin. */
export function evalRule(row: Record<string, unknown>, r: RuleSpec): boolean {
  const v = row[r.field];
  const c = r.condition;
  if (c.op === "always") return true;
  if (c.op === "empty") return v === null || v === undefined || v === "";
  const num = (x: unknown) => x === null || x === undefined || typeof x === "number";
  if (c.field_ref !== undefined && c.empty_as_zero !== false && num(v) && num(row[c.field_ref])) {  // boşları 0 say
    const [a, b] = [(v as number | null) ?? 0, (row[c.field_ref] as number | null) ?? 0];
    return c.op === "gt" ? a > b : c.op === "lt" ? a < b : a === b;
  }
  if (v === null || v === undefined) return false;
  const other = c.field_ref !== undefined ? row[c.field_ref] : c.value;
  if (other === null || other === undefined) return false;
  const [a, b] = [v as number, other as number];
  switch (c.op) {
    case "gt": return a > b;
    case "lt": return a < b;
    case "eq": return a === b;
    case "between": return (c.min === undefined || a >= c.min) && (c.max === undefined || a <= c.max);
    case "contains": return String(v).toLocaleLowerCase("tr").includes(String(c.value).toLocaleLowerCase("tr"));
    case "equals": return String(v).toLocaleLowerCase("tr") === String(c.value).toLocaleLowerCase("tr");
    case "in": return (c.values ?? []).includes(v as never);
    default: return false;
  }
}

export const EXPORT_INFO: ExportInfo = { title: "Malzeme listesi", file_slug: "malzeme", sync_max_rows: 10_000,
                                         max_rows: 500_000, file_hours: 24 };
export const EXPORT_FILE = "smartchain_malzeme_veri-v35_2026-10-28_1706.xlsx";
export const lastQuery = () => calls.queries[calls.queries.length - 1];

export function savedView(id: number, name: string, definition: Partial<ViewDefinition>, extra: Partial<SavedView> = {}): SavedView {
  return {
    id, name, owner_user_id: 3, owner_name: "Demo kullanıcı", is_shared: false, is_owner: true,
    updated_at: "2026-10-27T09:20:00+00:00", warnings: [],
    definition: { v: 1, columns: [{ field: "Code" }, { field: "Name" }], pinned: 0, sort: [], filters: [], group_by: [], ...definition },
    ...extra,
  };
}

export const group = (key: (string | null)[], count: number, extra: Partial<GroupNode> = {}): GroupNode => ({
  key, count, aggregates: {}, mixed_units: [], unit_decimals: {}, ...extra,
});

export interface BackendOptions {
  filtered?: number;
  total?: number;
  status?: number;
  chunk?: number;
  views?: ViewsResponse;
  groups?: GroupNode[];
  /** Excel'e aktarım cevabı (varsayılan: anlık dosya, 200). */
  exportReply?: Reply;
}

export function backend({ filtered = 1234, total = 50000, status = 200, chunk = 100, views, groups = [], exportReply }:
                        BackendOptions = {}) {
  for (const list of Object.values(calls)) list.length = 0;  // yerinde: testler diziyi önceden tutabilir
  ruleGate.hold = false;
  let saved = views ?? { views: [], default_view_id: null };
  let nextId = 100;
  const leafCount = (keys: { value: unknown }[]) => {
    let nodes = groups;
    let node: GroupNode | undefined;
    for (const k of keys) {
      node = nodes.find((n) => n.key[n.key.length - 1] === k.value);
      nodes = node?.children ?? [];
    }
    return node?.count ?? 0;
  };
  return mockApi({
    "/api/materials/columns": { body: { chunk_size: chunk, columns: COLUMNS, export: EXPORT_INFO } },
    "/api/materials/export": (url, init): Reply => {
      calls.exports.push({ url, body: JSON.parse(String(init?.body)) });
      return exportReply ?? { body: "xlsx", headers: { "Content-Disposition": `attachment; filename*=UTF-8''${EXPORT_FILE}` } };
    },
    "/api/exports/": (url): Reply => {
      calls.downloads.push(url);
      return { body: "xlsx", headers: { "Content-Disposition": `attachment; filename="${EXPORT_FILE}"` } };
    },
    "/api/materials/query": async (_url, init): Promise<Reply> => {
      const body = JSON.parse(String(init?.body)) as QueryRequest;
      calls.queries.push(body);
      if (status !== 200) return { status, body: { error: { code: "database_unavailable", message: "Veritabanına bağlanılamıyor.", trace_id: "x" } } };
      const inGroup = body.group_key?.length ? leafCount(body.group_key) : null;
      const n = Math.max(0, Math.min(body.limit, (inGroup ?? filtered) - body.offset));
      const prefix = body.group_key?.map((k) => String(k.value)).join("/");
      const rows = Array.from({ length: n }, (_, k) => {
        const i = body.offset + k;
        return { Id: i + 1, Code: prefix ? `${prefix}-${i}` : `M-${i}`, Name: `Malzeme ${i}`, MaterialLevel: "Hammadde",
                 MaterialGroup: "Çubuk", IsSellable: i % 2 === 0, SafetyStock: i % 2 === 0 ? 1234 : 12.25,
                 _unit_decimals: i % 2 === 0 ? 0 : 3, UpdatedAt: "2026-10-27T09:20:00+00:00", AdditionalText1: "A",
                 ProductionLeadTimeDays: i % 4 === 3 ? null : 3, LastReceiptDate: i % 3 === 0 ? null : "2026-10-20" };
      });
      if (body.rules?.length) {
        if (ruleGate.hold) await new Promise<void>((resolve) => { ruleGate.release = resolve; });
        rows.forEach((row) => Object.assign(row, { _rules: body.rules!.map((r, i) => (evalRule(row, r) ? i : -1)).filter((i) => i >= 0) }));
      }
      return { body: { rows, offset: body.offset, filtered: inGroup ?? filtered, total } };
    },
    "/api/materials/values": (_url, init): Reply => {
      calls.values.push(JSON.parse(String(init?.body)));
      return { body: [{ value: null, count: 4 }, { value: "Çubuk", count: 20 }, { value: "Levha", count: 20 }] };
    },
    "/api/materials/groups": (_url, init): Reply => {
      calls.groups.push(JSON.parse(String(init?.body)));
      const sum = groups.reduce((a, g) => a + g.count, 0);
      const body: GroupsResponse = { groups, aggregates: {}, leaf_groups: groups.length, filtered: sum, total };
      return { body };
    },
    "/api/materials/views": (url, init): Reply => {
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      calls.views.push({ method, url, body });
      if (method === "GET") return { body: saved };
      if (url.includes("/views/default")) {
        saved = { ...saved, default_view_id: body.view_id };
        return { body: { default_view_id: body.view_id } };
      }
      const id = Number(url.match(/\/views\/(\d+)/)?.[1]);
      if (method === "DELETE") {
        saved = { ...saved, views: saved.views.filter((v) => v.id !== id) };
        return { status: 204, body: null };
      }
      if (method === "POST") {
        if (saved.views.some((v) => v.name === body.name && v.is_owner)) {
          return { status: 409, body: { error: { code: "view_name_taken", message: "Bu adda bir görünümünüz zaten var.", trace_id: "x" } } };
        }
        const v = savedView(nextId++, body.name, body.definition, { is_shared: body.is_shared });
        saved = { ...saved, views: [...saved.views, v] };
        return { status: 201, body: v };
      }
      const v = { ...saved.views.find((x) => x.id === id)!, ...body };
      saved = { ...saved, views: saved.views.map((x) => (x.id === id ? v : x)) };
      return { body: v };
    },
  });
}

/** jsdom ölçü vermez: sanal kaydırıcı kap boyunu offsetHeight'tan okur. */
export function useTableTestSetup() {
  const sizes = Object.getOwnPropertyDescriptors(HTMLElement.prototype);
  beforeEach(() => {
    mockSocket();
    Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
      configurable: true, get() { return (this as HTMLElement).dataset.testid === "table-scroll" ? VIEW_PX : 0; },
    });
    Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
      configurable: true, get() { return (this as HTMLElement).dataset.testid === "table-scroll" ? 1000 : 0; },
    });
  });
  afterEach(() => {
    Object.defineProperty(HTMLElement.prototype, "offsetHeight", sizes.offsetHeight);
    Object.defineProperty(HTMLElement.prototype, "offsetWidth", sizes.offsetWidth);
  });
}

export async function openTable(opts?: BackendOptions) {
  backend(opts);
  renderApp("/tablo");
  await screen.findAllByRole("columnheader");
  await waitFor(() => expect(calls.queries.length + calls.groups.length).toBeGreaterThan(0));
}

export const dataRows = () => [...document.querySelectorAll("tbody tr[aria-rowindex]")];

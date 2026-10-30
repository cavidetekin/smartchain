// Gruplu okuma (K-90): grup ağacı sunucudan; satırlar yaprak grup başına grup anahtarıyla, parça parça (ListChunkSize)
// ve önbellekli okunur. Açık/kapalı gruplardan düz bir gösterim listesi kurulur (sanal kaydırma için).
// Yalnız koşullu biçim kuralları değişince (K-95) ağaç yeniden istenmez; istenmiş satır parçaları yeni kurallarla
// yeniden istenir, eski satırlar gelene kadar ekranda kalır.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { type AggSpec, listApi, type GroupKey, type GroupNode, type GroupsResponse, type Row } from "./types";
import { dataKeyOf, type ListRequest, queryBody, withRuleIds } from "./useListQuery";

export type DisplayItem =
  | { kind: "group"; node: GroupNode; depth: number; id: string }
  | { kind: "row"; leaf: string; keys: GroupKey[]; index: number };

export const groupId = (node: GroupNode) => JSON.stringify(node.key);

/** Açık gruplardan gösterim listesi: grup başlığı, altında alt gruplar ya da satır yerleri. */
export function flatten(groups: GroupNode[], groupBy: string[], collapsed: Set<string>): DisplayItem[] {
  const out: DisplayItem[] = [];
  const walk = (nodes: GroupNode[], depth: number) => {
    for (const node of nodes) {
      const id = groupId(node);
      out.push({ kind: "group", node, depth, id });
      if (collapsed.has(id)) continue;
      if (node.children?.length) {
        walk(node.children, depth + 1);
      } else {
        const keys = node.key.map((value, i) => ({ field: groupBy[i], value }));
        for (let index = 0; index < node.count; index++) out.push({ kind: "row", leaf: id, keys, index });
      }
    }
  };
  walk(groups, 0);
  return out;
}

export interface GroupedState {
  status: "idle" | "loading" | "ready" | "error";
  error: ApiError | null;
  tree: GroupsResponse | null;
  row(leaf: string, index: number): Row | undefined;
  /** Yaprak grubun [first, last] aralığını kapsayan eksik parçaları ister. */
  ensure(leaf: string, keys: GroupKey[], first: number, last: number): void;
  retry(): void;
}

export function useGroupedQuery(list: string, request: ListRequest | null, groupBy: string[],
                                chunkSize: number, aggregates: Record<string, AggSpec>): GroupedState {
  const api = useMemo(() => listApi(list), [list]);
  const active = Boolean(request && groupBy.length && chunkSize);
  const key = active ? JSON.stringify([dataKeyOf(request), groupBy, aggregates]) : "";
  const rulesKey = JSON.stringify(request?.rules ?? []);
  const chunks = useRef(new Map<string, Row[]>());
  const inflight = useRef(new Set<string>());
  /** İstenmiş parçalar ve grup anahtarları: kurallar değişince yeniden istenir. */
  const wanted = useRef(new Map<string, { keys: GroupKey[]; chunk: number }>());
  const generation = useRef(0);
  const rowsGeneration = useRef(0);
  const lastRulesKey = useRef(rulesKey);
  const [, setTick] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{ status: GroupedState["status"]; error: ApiError | null; tree: GroupsResponse | null }>(
    { status: "idle", error: null, tree: null },
  );

  useEffect(() => {
    generation.current += 1;
    rowsGeneration.current += 1;
    chunks.current.clear();
    inflight.current.clear();
    wanted.current.clear();
    lastRulesKey.current = rulesKey;
    if (!active || !request) {
      setState({ status: "idle", error: null, tree: null });
      return;
    }
    const gen = generation.current;
    const ctrl = new AbortController();
    setState((s) => ({ ...s, status: "loading", error: null }));
    api.groups({ group_by: groupBy, fields: request.fields, aggregates, filters: request.filters, sort: request.sort },
               ctrl.signal)
      .then((tree) => gen === generation.current && setState({ status: "ready", error: null, tree }))
      .catch((e: unknown) => {
        if (gen !== generation.current || ctrl.signal.aborted) return;
        setState({ status: "error", error: e instanceof ApiError ? e : new ApiError(0, "network", String(e)), tree: null });
      });
    return () => ctrl.abort();
    // key request ve groupBy'ı içerir
  }, [api, key, attempt]);

  const fetchChunk = useCallback((id: string, keys: GroupKey[], c: number) => {
    if (!request) return;
    const [gen, rowsGen] = [generation.current, rowsGeneration.current];
    wanted.current.set(id, { keys, chunk: c });
    inflight.current.add(id);
    api.query({ ...queryBody(request), group_key: keys, offset: c * chunkSize, limit: chunkSize })
      .then((r) => {
        if (gen !== generation.current || rowsGen !== rowsGeneration.current) return;
        chunks.current.set(id, withRuleIds(r.rows, request.rules));
        setTick((t) => t + 1);
      })
      .catch((e: unknown) => {
        if (gen !== generation.current || rowsGen !== rowsGeneration.current) return;
        setState((s) => ({ ...s, status: "error", error: e instanceof ApiError ? e : new ApiError(0, "network", String(e)) }));
      })
      .finally(() => inflight.current.delete(id));
  }, [api, request, chunkSize]);

  const ensure = useCallback((leaf: string, keys: GroupKey[], first: number, last: number) => {
    for (let c = Math.floor(first / chunkSize); c <= Math.floor(last / chunkSize); c++) {
      const id = `${leaf}|${c}`;
      if (!chunks.current.has(id) && !inflight.current.has(id)) fetchChunk(id, keys, c);
    }
  }, [fetchChunk, chunkSize]);

  // Yalnız kurallar değişti (ağaç aynı): istenmiş parçalar yeniden istenir, eskiler gelene kadar kalır.
  useEffect(() => {
    if (lastRulesKey.current === rulesKey) return;
    lastRulesKey.current = rulesKey;
    rowsGeneration.current += 1;
    inflight.current.clear();
    wanted.current.forEach(({ keys, chunk }, id) => fetchChunk(id, keys, chunk));
  }, [rulesKey, fetchChunk]);

  const row = useCallback((leaf: string, index: number) =>
    chunks.current.get(`${leaf}|${Math.floor(index / chunkSize)}`)?.[index % chunkSize], [chunkSize]);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  return { ...state, row, ensure, retry };
}

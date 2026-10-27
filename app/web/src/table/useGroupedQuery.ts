// Gruplu okuma (K-90): grup ağacı sunucudan; satırlar yaprak grup başına grup anahtarıyla, parça parça (ListChunkSize)
// ve önbellekli okunur. Açık/kapalı gruplardan düz bir gösterim listesi kurulur (sanal kaydırma için).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { listApi, type GroupKey, type GroupNode, type GroupsResponse, type Row } from "./types";
import type { ListRequest } from "./useListQuery";

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
                                chunkSize: number): GroupedState {
  const api = useMemo(() => listApi(list), [list]);
  const active = Boolean(request && groupBy.length && chunkSize);
  const key = active ? JSON.stringify([request, groupBy]) : "";
  const chunks = useRef(new Map<string, Row[]>());
  const inflight = useRef(new Set<string>());
  const generation = useRef(0);
  const [, setTick] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<{ status: GroupedState["status"]; error: ApiError | null; tree: GroupsResponse | null }>(
    { status: "idle", error: null, tree: null },
  );

  useEffect(() => {
    generation.current += 1;
    chunks.current.clear();
    inflight.current.clear();
    if (!active || !request) {
      setState({ status: "idle", error: null, tree: null });
      return;
    }
    const gen = generation.current;
    const ctrl = new AbortController();
    setState((s) => ({ ...s, status: "loading", error: null }));
    api.groups({ group_by: groupBy, fields: request.fields, filters: request.filters, sort: request.sort }, ctrl.signal)
      .then((tree) => gen === generation.current && setState({ status: "ready", error: null, tree }))
      .catch((e: unknown) => {
        if (gen !== generation.current || ctrl.signal.aborted) return;
        setState({ status: "error", error: e instanceof ApiError ? e : new ApiError(0, "network", String(e)), tree: null });
      });
    return () => ctrl.abort();
    // key request ve groupBy'ı içerir
  }, [api, key, attempt]);

  const ensure = useCallback((leaf: string, keys: GroupKey[], first: number, last: number) => {
    if (!request) return;
    const gen = generation.current;
    for (let c = Math.floor(first / chunkSize); c <= Math.floor(last / chunkSize); c++) {
      const id = `${leaf}|${c}`;
      if (chunks.current.has(id) || inflight.current.has(id)) continue;
      inflight.current.add(id);
      api.query({ ...request, group_key: keys, offset: c * chunkSize, limit: chunkSize })
        .then((r) => {
          if (gen !== generation.current) return;
          chunks.current.set(id, r.rows);
          setTick((t) => t + 1);
        })
        .catch((e: unknown) => {
          if (gen !== generation.current) return;
          setState((s) => ({ ...s, status: "error", error: e instanceof ApiError ? e : new ApiError(0, "network", String(e)) }));
        })
        .finally(() => inflight.current.delete(id));
    }
  }, [api, request, chunkSize]);

  const row = useCallback((leaf: string, index: number) =>
    chunks.current.get(`${leaf}|${Math.floor(index / chunkSize)}`)?.[index % chunkSize], [chunkSize]);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  return { ...state, row, ensure, retry };
}

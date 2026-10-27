// Parça parça yükleme (K-87): 100 satırlık parçalar önbellekte; aynı parça iki kez istenmez.
// Alan, sıralama ya da filtre değişince önbellek sıfırlanır ve eski istekler iptal edilir.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { listApi, type ListFilter, type Row, type SortItem } from "./types";

export const CHUNK = 100;

export interface ListRequest {
  fields: string[];
  sort: SortItem[];
  filters: ListFilter[];
}

export interface ListState {
  status: "loading" | "ready" | "error";
  error: ApiError | null;
  filtered: number;
  total: number;
  /** Yüklendiyse satır; değilse undefined (yer tutucu). */
  row(index: number): Row | undefined;
  /** Görünen aralığı kapsayan eksik parçaları ister. */
  ensure(first: number, last: number): void;
  retry(): void;
}

export function useListQuery(list: string, request: ListRequest | null): ListState {
  const api = useMemo(() => listApi(list), [list]);
  const key = request ? JSON.stringify(request) : "";
  const chunks = useRef(new Map<number, Row[]>());
  const inflight = useRef(new Map<number, AbortController>());
  const generation = useRef(0);
  const [, setTick] = useState(0);
  const [state, setState] = useState<{ status: ListState["status"]; error: ApiError | null; filtered: number; total: number }>(
    { status: "loading", error: null, filtered: 0, total: 0 },
  );

  const load = useCallback((chunk: number) => {
    if (!request || chunks.current.has(chunk) || inflight.current.has(chunk)) return;
    const gen = generation.current;
    const ctrl = new AbortController();
    inflight.current.set(chunk, ctrl);
    api.query({ ...request, offset: chunk * CHUNK, limit: CHUNK }, ctrl.signal)
      .then((r) => {
        if (gen !== generation.current) return;
        chunks.current.set(chunk, r.rows);
        setState({ status: "ready", error: null, filtered: r.filtered, total: r.total });
        setTick((t) => t + 1);
      })
      .catch((e: unknown) => {
        if (gen !== generation.current || ctrl.signal.aborted) return;
        const err = e instanceof ApiError ? e : new ApiError(0, "network", String(e));
        setState((s) => ({ ...s, status: "error", error: err }));
      })
      .finally(() => {
        if (inflight.current.get(chunk) === ctrl) inflight.current.delete(chunk);
      });
  }, [api, key]);

  const reset = useCallback(() => {
    generation.current += 1;
    inflight.current.forEach((c) => c.abort());
    inflight.current.clear();
    chunks.current.clear();
    setState((s) => ({ ...s, status: "loading", error: null }));
  }, []);

  useEffect(() => {
    if (!request) return;
    reset();
    load(0);
    return () => {
      generation.current += 1;
      inflight.current.forEach((c) => c.abort());
      inflight.current.clear();
    };
  }, [key, load, reset]);

  const ensure = useCallback((first: number, last: number) => {
    for (let c = Math.floor(first / CHUNK); c <= Math.floor(last / CHUNK); c++) load(c);
  }, [load]);

  const retry = useCallback(() => {
    reset();
    load(0);
  }, [reset, load]);

  const row = useCallback((index: number) => chunks.current.get(Math.floor(index / CHUNK))?.[index % CHUNK], []);

  return { ...state, row, ensure, retry };
}

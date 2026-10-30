// Parça parça yükleme (K-87): parçalar (ListChunkSize satır) önbellekte; aynı parça iki kez istenmez.
// Alan, sıralama ya da filtre değişince önbellek sıfırlanır ve eski istekler iptal edilir. Yalnız koşullu biçim
// kuralları değişince (K-95) önbellek korunur: eski satırlar ekranda kalır, yüklü parçalar yeni kurallarla yeniden
// istenir ve geldikçe yerine konur (yer tutucu görünmez).
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { listApi, type ListFilter, type Row, type RuleSpec, type SortItem } from "./types";

/** Ekrana uygulanan kural: kimlik + alan + koşul (sunucuya yalnız alan ve koşul gider). */
export type RequestRule = RuleSpec & { id: string };

export interface ListRequest {
  fields: string[];
  sort: SortItem[];
  filters: ListFilter[];
  /** Ekrana uygulanan kurallar (aktif, alanı görünen); satırlar _rules (sıra) ile döner, _ruleIds'e çevrilir. */
  rules?: RequestRule[];
}

/** Sorgu gövdesi: kurallar yalnız alan ve koşulla. */
export function queryBody(r: ListRequest) {
  const { rules, ...rest } = r;
  return rules?.length ? { ...rest, rules: rules.map(({ field, condition }) => ({ field, condition })) } : rest;
}

/** Satırın _rules sıralarını isteğin kural kimliklerine çevirir: kurallar değişse de eski satır doğru kurala bağlı. */
export function withRuleIds(rows: Row[], rules: RequestRule[] | undefined): Row[] {
  if (!rules?.length) return rows;
  return rows.map((row) => {
    const { _rules, ...rest } = row as Row & { _rules?: number[] };
    return { ...rest, _ruleIds: (_rules ?? []).map((i) => rules[i]?.id).filter(Boolean) } as Row;
  });
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

/** Veri anahtarı: kurallar hariç (kural değişince satırlar sıfırlanmaz). */
export const dataKeyOf = (r: ListRequest | null) =>
  r ? JSON.stringify({ fields: r.fields, sort: r.sort, filters: r.filters }) : "";

export function useListQuery(list: string, request: ListRequest | null, chunkSize: number): ListState {
  const api = useMemo(() => listApi(list), [list]);
  const dataKey = dataKeyOf(request);
  const rulesKey = JSON.stringify(request?.rules ?? []);
  const chunks = useRef(new Map<number, Row[]>());
  const inflight = useRef(new Map<number, AbortController>());
  /** İstenmiş parçalar (yüklü ya da yolda): kurallar değişince hepsi yeniden istenir. */
  const wanted = useRef(new Set<number>());
  const generation = useRef(0);
  const lastDataKey = useRef<string | null>(null);
  const [, setTick] = useState(0);
  const [state, setState] = useState<{ status: ListState["status"]; error: ApiError | null; filtered: number; total: number }>(
    { status: "loading", error: null, filtered: 0, total: 0 },
  );

  const load = useCallback((chunk: number, force = false) => {
    if (!request || (!force && chunks.current.has(chunk)) || inflight.current.has(chunk)) return;
    wanted.current.add(chunk);
    const gen = generation.current;
    const ctrl = new AbortController();
    inflight.current.set(chunk, ctrl);
    api.query({ ...queryBody(request), offset: chunk * chunkSize, limit: chunkSize }, ctrl.signal)
      .then((r) => {
        if (gen !== generation.current) return;
        chunks.current.set(chunk, withRuleIds(r.rows, request.rules));
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
  }, [api, dataKey, rulesKey, chunkSize]);

  const cancel = useCallback(() => {
    generation.current += 1;
    inflight.current.forEach((c) => c.abort());
    inflight.current.clear();
  }, []);

  const reset = useCallback(() => {
    cancel();
    chunks.current.clear();
    wanted.current.clear();
    setState((s) => ({ ...s, status: "loading", error: null }));
  }, [cancel]);

  useEffect(() => {
    if (!request) return;
    if (lastDataKey.current === dataKey && wanted.current.size) {
      // yalnız kurallar değişti: önbellek kalır, istenmiş parçalar yeni kurallarla yeniden istenir
      cancel();
      [...wanted.current].forEach((c) => load(c, true));
    } else {
      lastDataKey.current = dataKey;
      reset();
      load(0);
    }
    return cancel;
  }, [dataKey, rulesKey, load, reset, cancel]);

  const ensure = useCallback((first: number, last: number) => {
    for (let c = Math.floor(first / chunkSize); c <= Math.floor(last / chunkSize); c++) load(c);
  }, [load, chunkSize]);

  const retry = useCallback(() => {
    reset();
    load(0);
  }, [reset, load]);

  const row = useCallback((index: number) => chunks.current.get(Math.floor(index / chunkSize))?.[index % chunkSize],
    [chunkSize]);

  return { ...state, row, ensure, retry };
}

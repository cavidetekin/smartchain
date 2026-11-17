// Tablonun grafik bölmesi (K-178, docs/12 "Grafik standardı"): başlık düğmeleri (☰ ayar paneli, ⤢ tam ekran, ✕ kapat), grafik ve sağında ayar paneli.
// Veri sunucudan toplanmış gelir (`POST /api/<liste>/chart`): tablonun filtresi aynen gider; yalnız veriyi değiştiren ayar yeniden sorar (kısa
// bekleyerek), görünüş ayarı sormaz. Hâller: ilk yükleme, yenilenirken eski grafik soluk, boş, hata, karışık birim uyarısı.
import { Maximize2, Minimize2, SlidersHorizontal, X } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { Alert, Button } from "../ui";
import { type ChartConfig, type ChartData, chartRequest, newSeries } from "../ui/chart/chartModel";
import { buildOption, isEmptyData } from "../ui/chart/chartOption";
import { ChartPanel } from "../ui/chart/ChartPanel";
import { listApi, type ListColumn, type ListFilter } from "./types";

const T = tr.chart;
const Chart = lazy(() => import("../ui/chart/Chart"));  // çizim kütüphanesi ilk açılışta ayrı parça olarak yerelden yüklenir
/** Veriyi değiştiren ayardan sonra bekleme (ms): yazarken her tuşta istek atılmaz. */
export const CHART_DEBOUNCE_MS = 250;
/** Grafik alanı bundan darsa ayar paneli grafiğin üstüne açılır (px). */
const NARROW_PX = 880;

export function ChartPane({ list, columns, filters, chart, reloadKey, onChange, onClose, style, fresh, onSettled }: {
  list: string; columns: ListColumn[];
  /** Tablonun o anki filtresi (ekranın sabit filtresi dahil). */
  filters: ListFilter[];
  chart: ChartConfig;
  /** Tablo yenilenince artar: grafik de yeniden sorar. */
  reloadKey: number | string;
  onChange(next: ChartConfig): void;
  onClose(): void;
  style?: React.CSSProperties;
  /** İlk açılışın varsayılan grafiği (K-178): birimler karışık olduğu için çizilemiyorsa seri Adet'e çevrilir, grafik boş gelmez. */
  fresh?: boolean;
  onSettled?(): void;
}) {
  const { scenario, fontSize } = useShell();
  const [panel, setPanel] = useState(false);  // grafik her açılışta panel kapalı gelir; açık ya da kapalı olması hiçbir yerde saklanmaz (K-178)
  const [data, setData] = useState<ChartData | null>(null);
  const [shownKey, setShownKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [narrow, setNarrow] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const first = useRef(true);

  const request = useMemo(() => chartRequest(chart, filters, scenario?.id), [chart, filters, scenario?.id]);
  const key = JSON.stringify(request);
  useEffect(() => {
    const ctrl = new AbortController();
    const run = () => {
      listApi(list).chart(JSON.parse(key), ctrl.signal)
        .then((d) => { setData(d); setShownKey(key); setError(null); })
        .catch((e: unknown) => { if (!ctrl.signal.aborted) { setError(e instanceof ApiError ? e.message : T.failed); setShownKey(key); } });
    };
    const timer = window.setTimeout(run, first.current ? 0 : CHART_DEBOUNCE_MS);
    first.current = false;
    return () => { window.clearTimeout(timer); ctrl.abort(); };
  }, [list, key, reloadKey, attempt]);

  useEffect(() => {
    const el = root.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(() => setNarrow(el.clientWidth < NARROW_PX));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!fresh || !data || shownKey !== key) return;
    onSettled?.();
    if (data.series.length > 0 && data.series.every((s) => s.mixed_units)) onChange({ ...chart, series: [newSeries("s1", null, "count")] });
  }, [fresh, data, shownKey, key]);  // eslint-disable-line react-hooks/exhaustive-deps

  const built = useMemo(() => (data && !error ? buildOption(chart, data, columns, { narrow, fontSize }) : null), [chart, data, columns, narrow, fontSize, error]);
  const stale = shownKey !== key;
  const empty = Boolean(data && isEmptyData(data));
  const togglePanel = () => setPanel((open) => !open);
  const full = chart.layout === "full";

  return (
    <div className={`sc-chart-pane${narrow ? " is-narrow" : ""}`} ref={root} style={style} data-testid="chart-pane">
      <div className="sc-chart-main">
        <div className="sc-chart-head">
          <button type="button" className="sc-tool-btn" aria-label={T.settings} title={T.settings} aria-pressed={panel} onClick={togglePanel}><SlidersHorizontal aria-hidden="true" /></button>
          <button type="button" className="sc-tool-btn" aria-label={full ? T.splitView : T.fullScreen} title={full ? T.splitView : T.fullScreen} aria-pressed={full}
                  onClick={() => onChange({ ...chart, layout: full ? "split" : "full" })}>{full ? <Minimize2 aria-hidden="true" /> : <Maximize2 aria-hidden="true" />}</button>
          <button type="button" className="sc-tool-btn" aria-label={T.close} title={T.close} onClick={onClose}><X aria-hidden="true" /></button>
        </div>
        <div className={`sc-chart-body${stale && data ? " is-stale" : ""}`} aria-busy={stale}>
          {error ? (
            <Alert tone="error" title={T.loadError}>{error} <Button size="sm" onClick={() => setAttempt((n) => n + 1)}>{tr.table.retry}</Button></Alert>
          ) : !data ? (
            <p className="sc-chart-state">{T.loading}</p>
          ) : empty ? (
            <p className="sc-chart-state">{T.noData}</p>
          ) : built ? (
            <Suspense fallback={<p className="sc-chart-state">{T.loading}</p>}>
              <Chart option={built.option} label={chart.title || T.chart} />
            </Suspense>
          ) : null}
        </div>
        {built && built.mixed.length > 0 && <Alert tone="risk">{T.mixedUnits(built.mixed.join(", "))}</Alert>}
      </div>
      {panel && <ChartPanel chart={chart} columns={columns} onChange={onChange} />}
    </div>
  );
}

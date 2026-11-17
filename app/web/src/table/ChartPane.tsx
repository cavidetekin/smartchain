// Tablonun grafik bölmesi (K-178, K-179; docs/12 "Grafik standardı"): başlık düğmeleri (☰ ayar paneli, ⤢ tam ekran, ✕ kapat), grafik ve sağında ayar
// paneli. Veri sunucudan toplanmış gelir (`POST /api/<liste>/chart`): tablonun filtresi aynen gider; yalnız veriyi değiştiren ayar yeniden sorar (kısa
// bekleyerek), görünüş ayarı sormaz. Hâller: ilk yükleme, yenilenirken eski grafik soluk, boş, hata, karışık birim uyarısı.
// Seçim ve iniş (K-179): parçaya tık seçer ya da seçimi kaldırır; sağ tık menüsü ve dönem seçiliyken başlıktaki düğme alt döneme iner (çoklu dönemde de); sol üstte
// iniş izi. İkisi de geçicidir (görünüme kaydedilmez); durumları tabloda tutulur, çünkü tablo da aynı seçime süzülür.
import { ChevronDown, Maximize2, Minimize2, SlidersHorizontal, X } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, emitNotice } from "../api/client";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { Alert, Button } from "../ui";
import {
  type ChartBucket, type ChartConfig, type ChartData, type ChartPick, chartRequest, effectiveBucket, finerBuckets, isDateField, MAX_SELECTION, newSeries,
  NO_PICK, type PickItem, samePick,
} from "../ui/chart/chartModel";
import { bucketLabel, buildOption, isEmptyData } from "../ui/chart/chartOption";
import { ChartPanel } from "../ui/chart/ChartPanel";
import { MenuItem, RowPopMenu } from "../ui/PopMenu";
import { listApi, type ListColumn, type ListFilter } from "./types";

const T = tr.chart;
const Chart = lazy(() => import("../ui/chart/Chart"));  // çizim kütüphanesi ilk açılışta ayrı parça olarak yerelden yüklenir
/** Veriyi değiştiren ayardan sonra bekleme (ms): yazarken her tuşta istek atılmaz. */
export const CHART_DEBOUNCE_MS = 250;
/** Grafik alanı bundan darsa ayar paneli grafiğin üstüne açılır (px). */
const NARROW_PX = 880;
const ALLOWED = { allowed: true };

export function ChartPane({ list, columns, filters, chart, reloadKey, onChange, onClose, style, fresh, onSettled, pick, onPick }: {
  list: string; columns: ListColumn[];
  /** Tablonun o anki filtresi (ekranın sabit filtresi dahil). */
  filters: ListFilter[];
  chart: ChartConfig;
  /** Tablo yenilenince artar: grafik de yeniden sorar. */
  reloadKey: number | string;
  onChange(next: ChartConfig): void;
  onClose(): void;
  style?: React.CSSProperties;
  /** İlk açılışın varsayılan grafiği (K-178): birimler karışık olduğu için çizilemiyorsa seri Say'a çevrilir, grafik boş gelmez. */
  fresh?: boolean;
  onSettled?(): void;
  /** Seçim ve iniş (K-179): geçici; tablo da buna süzülür. */
  pick: ChartPick;
  onPick(next: ChartPick): void;
}) {
  const { scenario, fontSize } = useShell();
  const [panel, setPanel] = useState(false);  // grafik her açılışta panel kapalı gelir; açık ya da kapalı olması hiçbir yerde saklanmaz (K-178)
  const [data, setData] = useState<ChartData | null>(null);
  const [shownKey, setShownKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [narrow, setNarrow] = useState(false);
  const [menu, setMenu] = useState<{ x: number; y: number; item: PickItem | "other" } | null>(null);
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const [drillMenu, setDrillMenu] = useState<HTMLElement | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const first = useRef(true);

  // İnişle geçerli dönem: görünümün kayıtlı dönemi değişmez
  const bucket = effectiveBucket(chart, pick);
  const shown = useMemo(() => ({ ...chart, x: { ...chart.x, bucket } }), [chart, bucket]);
  const drillKey = JSON.stringify(pick.drill);
  const request = useMemo(() => chartRequest(chart, filters, scenario?.id, JSON.parse(drillKey)), [chart, filters, scenario?.id, drillKey]);
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

  const stale = shownKey !== key;
  const built = useMemo(() => (data && !error ? buildOption(shown, data, columns, { narrow, fontSize, selected: pick.items }) : null),
                        [shown, data, columns, narrow, fontSize, error, pick.items]);
  const empty = Boolean(data && isEmptyData(data));
  const togglePanel = () => setPanel((open) => !open);
  const full = chart.layout === "full";

  // Seçim: tek tık seçer, yeniden tık kaldırır; "Diğer" seçilemez
  const toggle = (item: PickItem | "other" | null) => {
    if (item === null || stale) return;
    if (item === "other") { emitNotice(T.otherNotSelectable); return; }
    const has = pick.items.some((i) => samePick(i, item));
    if (!has && pick.items.length >= MAX_SELECTION) { emitNotice(T.selectionMax(MAX_SELECTION)); return; }
    onPick({ ...pick, items: has ? pick.items.filter((i) => !samePick(i, item)) : [...pick.items, item] });
  };
  // İniş: dönemin içine, daha ince bir dönemle; önceki seçim temizlenir
  const dateAxis = isDateField(columns.find((c) => c.field === chart.x.field));
  const finer = dateAxis ? finerBuckets(bucket) : [];
  const drillTo = (keys: string[], to: ChartBucket) => {
    if (bucket && keys.length) onPick({ items: [], drill: [...pick.drill, { bucket, keys: [...keys].sort(), to }] });
  };
  // Seçili dönemler (kırılımda parçanın dönemi; "(Boş)" dönemine inilmez): bir ya da daha fazlası seçiliyken başlıkta "Alt döneme in"
  const periods = finer.length > 0 ? [...new Set(pick.items.map((i) => i.x))].filter((x): x is string => typeof x === "string") : [];
  /** Sağ tıkla iniş: seçili dönemlerden birine tıklandıysa seçimin tamamına, değilse yalnız tıklanana. */
  const drillKeys = (x: string) => (periods.includes(x) ? periods : [x]);
  const menuItem = menu && menu.item !== "other" ? menu.item : null;
  const closeMenu = () => { setMenu(null); setMenuAnchor(null); };

  return (
    <div className={`sc-chart-pane${narrow ? " is-narrow" : ""}`} ref={root} style={style} data-testid="chart-pane">
      <div className="sc-chart-main">
        {(pick.drill.length > 0 || periods.length > 0) && (
          <div className="sc-chart-trail">
            {pick.drill.length > 0 && (
              <nav aria-label={T.trail}>
                <ol>
                  <li><button type="button" onClick={() => onPick(NO_PICK)}>{T.trailAll}</button></li>
                  {pick.drill.map((step, i) => {
                    const names = step.keys.map((k) => bucketLabel(k, step.bucket));
                    const label = names.length === 1 ? names[0] : T.periods(names.length);
                    const tip = names.length > 1 ? names.join(", ") : undefined;
                    return (
                      <li key={`${step.bucket}:${step.keys.join(",")}`}>
                        {i === pick.drill.length - 1
                          ? <span aria-current="true" title={tip}>{label}</span>
                          : <button type="button" title={tip} onClick={() => onPick({ items: [], drill: pick.drill.slice(0, i + 1) })}>{label}</button>}
                      </li>
                    );
                  })}
                </ol>
              </nav>
            )}
            {periods.length > 0 && (
              <Button size="sm" onClick={(e) => (finer.length === 1 ? drillTo(periods, finer[0]) : setDrillMenu(drillMenu ? null : e.currentTarget))}
                      aria-haspopup={finer.length > 1 ? "menu" : undefined} aria-expanded={finer.length > 1 ? Boolean(drillMenu) : undefined}>
                {T.drillDown}{finer.length > 1 && <ChevronDown aria-hidden="true" />}
              </Button>
            )}
          </div>
        )}
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
              <Chart option={built.option} label={chart.title || T.chart}
                     onPick={(si, di) => toggle(built.hit(si, di))}
                     onMenu={(si, di, x, y) => { const item = built.hit(si, di); if (item !== null && !stale) setMenu({ x, y, item }); }} />
            </Suspense>
          ) : null}
        </div>
        {built && built.mixed.length > 0 && <Alert tone="risk">{T.mixedUnits(built.mixed.join(", "))}</Alert>}
      </div>
      {panel && <ChartPanel chart={chart} columns={columns} onChange={onChange} />}

      {/* Sağ tık menüsü (K-179): alt döneme in ve seç / seçimi kaldır */}
      {menu && <span className="sc-chart-menu-anchor" style={{ left: menu.x, top: menu.y }} ref={setMenuAnchor} />}
      {menu && menuAnchor && (
        <RowPopMenu label={T.partMenu} anchor={menuAnchor} onClose={closeMenu}>
          {menuItem && typeof menuItem.x === "string" && finer.length > 0 && (
            <>
              <div role="presentation" className="sc-popmenu-heading">{T.drillDown}</div>
              {finer.map((to) => (
                <MenuItem key={to} label={T.buckets[to]} state={ALLOWED} onClick={() => { closeMenu(); drillTo(drillKeys(menuItem.x as string), to); }} />
              ))}
              <div role="separator" className="sc-popmenu-sep" />
            </>
          )}
          <MenuItem label={menuItem && pick.items.some((i) => samePick(i, menuItem)) ? T.unselect : T.select}
                    state={menuItem ? ALLOWED : { allowed: false, reason: T.otherNotSelectable }}
                    onClick={() => { closeMenu(); toggle(menuItem); }} />
        </RowPopMenu>
      )}
      {drillMenu && periods.length > 0 && (
        <RowPopMenu label={T.drillDown} anchor={drillMenu} onClose={() => setDrillMenu(null)}>
          {finer.map((to) => (
            <MenuItem key={to} label={T.buckets[to]} state={ALLOWED} onClick={() => { setDrillMenu(null); drillTo(periods, to); }} />
          ))}
        </RowPopMenu>
      )}
    </div>
  );
}

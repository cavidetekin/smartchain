// Tablonun grafik bölmesi (K-178, K-179; docs/12 "Grafik standardı"): başlık düğmeleri (⭳ dışa aktar, ☰ ayar paneli, ⤢ tam ekran, ✕ kapat), grafik ve
// sağında ayar paneli. Veri sunucudan gelir: çubuk, çizgi, pasta ve halkada toplanmış (`POST /api/<liste>/chart`), dağılımda noktalar
// (`POST /api/<liste>/chart/points`); tablonun filtresi aynen gider; yalnız veriyi değiştiren ayar yeniden sorar (kısa bekleyerek), görünüş ayarı
// sormaz. Hâller: ilk yükleme, yenilenirken eski grafik soluk, boş, hata, uyarılar (karışık birim, negatif dilim, örnekleme).
// Seçim ve iniş (K-179): parçaya tık seçer ya da seçimi kaldırır; sağ tık menüsü ve dönem seçiliyken başlıktaki düğme alt döneme iner (çoklu dönemde de); sol üstte
// iniş izi. İkisi de geçicidir (görünüme kaydedilmez); durumları tabloda tutulur, çünkü tablo da aynı seçime süzülür.
// Dışa aktarma (K-179): Görsel (PNG; tarayıcıda, ekrandaki ayarla, seçim soluklaştırması olmadan) ve Veri (Excel); ikisi de denetim izine düşer.
import { ChevronDown, Download, Maximize2, Minimize2, SlidersHorizontal, X } from "lucide-react";
import { lazy, type MutableRefObject, Suspense, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, emitNotice, saveBlob } from "../api/client";
import { tr } from "../i18n/tr";
import { useShell } from "../shell/ShellContext";
import { Alert, Button } from "../ui";
import {
  type ChartBucket, type ChartConfig, type ChartData, type ChartPick, type ChartRequest, chartRequest, effectiveBucket, finerBuckets, isDateField, MAX_SELECTION, newSeries,
  NO_PICK, type PickItem, type PointsData, type PointsRequest, pointsRequest, samePick,
} from "../ui/chart/chartModel";
import { bucketLabel, buildOption, buildScatter, isEmptyData, SURFACE } from "../ui/chart/chartOption";
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
/** Görselin en küçük ölçüsü (px): dar bölmede de okunur çıktı. */
const IMAGE_MIN = { width: 720, height: 360 };

/** data: adresini dosyaya çevirir (PNG). */
async function dataUrlBlob(url: string): Promise<Blob> {
  const [head, body] = url.split(",");
  const bytes = atob(body);
  const out = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) out[i] = bytes.charCodeAt(i);
  return new Blob([out], { type: /data:([^;]+)/.exec(head)?.[1] ?? "image/png" });
}

export function ChartPane({ list, columns, filters, chart, reloadKey, onChange, onClose, style, fresh, onSettled, pick, onPick, canExport, imageRef }: {
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
  /** Dışa aktarma yetkisi (fonksiyon 86): yoksa dışa aktar düğmesi çıkmaz. */
  canExport?: boolean;
  /** Tablonun Excel'ine "Grafiği ekle" (K-179): çizilmiş grafiğin görselini (PNG, data: adresi) üretir; çizilecek grafik yoksa null. */
  imageRef?: MutableRefObject<(() => Promise<string | null>) | null>;
}) {
  const { scenario, fontSize } = useShell();
  const [panel, setPanel] = useState(false);  // grafik her açılışta panel kapalı gelir; açık ya da kapalı olması hiçbir yerde saklanmaz (K-178)
  const [data, setData] = useState<ChartData | null>(null);
  const [points, setPoints] = useState<PointsData | null>(null);
  const [shownKey, setShownKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [narrow, setNarrow] = useState(false);
  const [box, setBox] = useState({ width: 0, height: 0 });
  const [menu, setMenu] = useState<{ x: number; y: number; item: PickItem | "other" } | null>(null);
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const [drillMenu, setDrillMenu] = useState<HTMLElement | null>(null);
  const [exportMenu, setExportMenu] = useState<HTMLElement | null>(null);
  const [exporting, setExporting] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const first = useRef(true);

  const scatter = chart.kind === "scatter" && chart.scatter !== null;
  // İnişle geçerli dönem: görünümün kayıtlı dönemi değişmez
  const bucket = effectiveBucket(chart, pick);
  const shown = useMemo(() => ({ ...chart, x: { ...chart.x, bucket } }), [chart, bucket]);
  const drillKey = JSON.stringify(pick.drill);
  const request = useMemo(() => (scatter ? pointsRequest(chart, filters) : chartRequest(chart, filters, scenario?.id, JSON.parse(drillKey))),
                          [scatter, chart, filters, scenario?.id, drillKey]);
  const key = JSON.stringify([scatter ? "points" : "chart", request]);
  useEffect(() => {
    const ctrl = new AbortController();
    const run = () => {
      const [what, req] = JSON.parse(key);
      const done = () => { setShownKey(key); setError(null); };
      (what === "points" ? listApi(list).points(req, ctrl.signal).then((d) => { setPoints(d); done(); })
        : listApi(list).chart(req, ctrl.signal).then((d) => { setData(d); done(); }))
        .catch((e: unknown) => { if (!ctrl.signal.aborted) { setError(e instanceof ApiError ? e.message : T.failed); setShownKey(key); } });
    };
    const timer = window.setTimeout(run, first.current ? 0 : CHART_DEBOUNCE_MS);
    first.current = false;
    return () => { window.clearTimeout(timer); ctrl.abort(); };
  }, [list, key, reloadKey, attempt]);

  useEffect(() => {
    const el = root.current;
    if (!el || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(() => {
      setNarrow(el.clientWidth < NARROW_PX);
      const b = body.current;
      if (!b) return;
      const cs = getComputedStyle(b);  // çizim alanı: bölmenin iç kutusu (dolgu hariç)
      const width = Math.round(b.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight));
      const height = Math.round(b.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom));
      setBox((old) => (old.width === width && old.height === height ? old : { width, height }));
    });
    observer.observe(el);
    if (body.current) observer.observe(body.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!fresh || !data || shownKey !== key) return;
    onSettled?.();
    if (data.series.length > 0 && data.series.every((s) => s.mixed_units)) onChange({ ...chart, series: [newSeries("s1", null, "count")] });
  }, [fresh, data, shownKey, key]);  // eslint-disable-line react-hooks/exhaustive-deps

  const stale = shownKey !== key;
  const loaded = scatter ? points : data;
  const build = (selected: PickItem[], size: { width: number; height: number }) => {
    const opts = { narrow, fontSize, selected, width: size.width, height: size.height };
    if (scatter) return points ? buildScatter(chart, points, columns, opts) : null;
    return data ? buildOption(shown, data, columns, opts) : null;
  };
  const built = useMemo(() => (error ? null : build(pick.items, box)),
                        [shown, data, points, scatter, columns, narrow, fontSize, error, pick.items, box]);  // eslint-disable-line react-hooks/exhaustive-deps
  const empty = Boolean(scatter ? points && points.rows === 0 : data && isEmptyData(data));
  const drawable = Boolean(built) && !empty && !stale && !error;
  const togglePanel = () => setPanel((open) => !open);
  const full = chart.layout === "full";

  // Görsel (PNG): ekrandaki ayarla; seçim soluklaştırması ve üstüne gelme bandı girmez. Çizim ekran dışındaki bir tuvalde yapılır (yazı tipleri doğru çıkar).
  const image = async (): Promise<string | null> => {
    const size = { width: Math.max(IMAGE_MIN.width, box.width), height: Math.max(IMAGE_MIN.height, box.height, built?.minHeight ?? 0) };
    const plain = build([], size);
    if (!plain) return null;
    const { renderPng } = await import("../ui/chart/echarts");
    return renderPng(plain.option, size.width, size.height, SURFACE);
  };
  const imageFn = useRef(image);
  imageFn.current = image;
  useEffect(() => {
    if (!imageRef) return undefined;
    imageRef.current = drawable ? () => imageFn.current() : null;
    return () => { imageRef.current = null; };
  }, [imageRef, drawable]);

  const exportAs = async (format: "png" | "xlsx") => {
    setExportMenu(null);
    if (!drawable || exporting) return;
    setExporting(true);
    try {
      const url = await image();
      if (!url) throw new Error(T.exportFailed);
      const api = listApi(list);
      if (format === "png") {
        const { file_name } = await api.chartExportLog({ kind: chart.kind });  // iz yazılamazsa dosya inmez
        saveBlob(await dataUrlBlob(url), file_name);
      } else {
        const file = await api.chartExport({ kind: chart.kind, ...(scatter ? { points: request as PointsRequest } : { chart: request as ChartRequest }), image: url.split(",")[1], title: chart.title });
        saveBlob(file.blob, file.fileName);
      }
    } catch (e) {
      emitNotice(e instanceof ApiError ? e.message : T.exportFailed);
    } finally {
      setExporting(false);
    }
  };

  // Seçim: tek tık seçer, yeniden tık kaldırır; "Diğer" seçilemez
  const toggle = (item: PickItem | "other" | null) => {
    if (item === null || stale) return;
    if (item === "other") { emitNotice(T.otherNotSelectable); return; }
    const has = pick.items.some((i) => samePick(i, item));
    if (!has && pick.items.length >= MAX_SELECTION) { emitNotice(T.selectionMax(MAX_SELECTION)); return; }
    onPick({ ...pick, items: has ? pick.items.filter((i) => !samePick(i, item)) : [...pick.items, item] });
  };
  // İniş: dönemin içine, daha ince bir dönemle; önceki seçim temizlenir. Yalnız çubuk ve çizgi grafiğinde, tarih ekseninde
  const dateAxis = chart.kind === "xy" && isDateField(columns.find((c) => c.field === chart.x.field));
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
  const notes = built ? [...(built.mixed.length ? [T.mixedUnits(built.mixed.join(", "))] : []), ...built.notes] : [];

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
          {canExport && (
            <button type="button" className="sc-tool-btn" aria-label={T.exportChart} title={T.exportChart} aria-haspopup="menu" aria-expanded={Boolean(exportMenu)}
                    disabled={!drawable || exporting} onClick={(e) => setExportMenu(exportMenu ? null : e.currentTarget)}><Download aria-hidden="true" /></button>
          )}
          <button type="button" className="sc-tool-btn" aria-label={T.settings} title={T.settings} aria-pressed={panel} onClick={togglePanel}><SlidersHorizontal aria-hidden="true" /></button>
          <button type="button" className="sc-tool-btn" aria-label={full ? T.splitView : T.fullScreen} title={full ? T.splitView : T.fullScreen} aria-pressed={full}
                  onClick={() => onChange({ ...chart, layout: full ? "split" : "full" })}>{full ? <Minimize2 aria-hidden="true" /> : <Maximize2 aria-hidden="true" />}</button>
          <button type="button" className="sc-tool-btn" aria-label={T.close} title={T.close} onClick={onClose}><X aria-hidden="true" /></button>
        </div>
        <div className={`sc-chart-body${stale && loaded ? " is-stale" : ""}`} aria-busy={stale} ref={body}>
          {error ? (
            <Alert tone="error" title={T.loadError}>{error} <Button size="sm" onClick={() => setAttempt((n) => n + 1)}>{tr.table.retry}</Button></Alert>
          ) : !loaded ? (
            <p className="sc-chart-state">{T.loading}</p>
          ) : empty ? (
            <p className="sc-chart-state">{T.noData}</p>
          ) : built ? (
            <Suspense fallback={<p className="sc-chart-state">{T.loading}</p>}>
              <Chart option={built.option} label={chart.title || T.chart} minHeight={built.minHeight}
                     onPick={(si, di) => toggle(built.hit(si, di))}
                     onMenu={(si, di, x, y) => { const item = built.hit(si, di); if (item !== null && !stale) setMenu({ x, y, item }); }} />
            </Suspense>
          ) : null}
        </div>
        {notes.map((note) => <Alert key={note} tone="risk">{note}</Alert>)}
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
      {exportMenu && (
        <RowPopMenu label={T.exportChart} anchor={exportMenu} onClose={() => setExportMenu(null)}>
          <MenuItem label={T.exportPng} state={ALLOWED} onClick={() => void exportAs("png")} />
          <MenuItem label={T.exportXlsx} state={ALLOWED} onClick={() => void exportAs("xlsx")} />
        </RowPopMenu>
      )}
    </div>
  );
}

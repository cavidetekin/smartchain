// Ana–detay düzeni (K-161, docs/12): üstte ana tablo, satır seçilince altta detay kartı. Kapatma (×, Esc, seçili satıra yeniden tıklama), sürüklenebilir ayraç
// (çift tıklayınca ilk oran), büyütme, kayıt olan ilk sekme. Ekranlar seçimi `useMasterDetail` ile tutar, yerleşimi `MasterDetail` çizer.
import { Maximize2, Minimize2, X } from "lucide-react";
import { type KeyboardEvent, type MouseEvent, type ReactNode, useCallback, useEffect, useRef, useState } from "react";

import { tr } from "../i18n/tr";
import { loadPaneRatio, savePaneRatio } from "../prefs";
import { Segment } from "./fields";
import { OverflowTabs } from "./OverflowTabs";

const MIN_RATIO = 0.15;
const MAX_RATIO = 0.85;
const DEFAULT_RATIO = 0.5;
const KEY_STEP = 0.05;
/** Açıkken Esc'i kendisi kapatan katmanlar: önce onlar kapanır. */
const OVERLAYS = ".sc-floating, .sc-table-pop, [role='dialog']";

export interface DetailTab<K extends string> {
  value: K;
  label: string;
  count: number;
  /** Pasif sekme (ör. boş ilişki, K-173). */
  disabled?: boolean;
}

const clamp = (ratio: number) => Math.min(MAX_RATIO, Math.max(MIN_RATIO, ratio));

/** Kayıt olan ilk sekme; hepsi boşsa ilk sekme (K-161). */
export function firstFilledTab<K extends string>(tabs: readonly { value: K; count: number }[]): K {
  return (tabs.find((t) => t.count > 0) ?? tabs[0]).value;
}

/** Seçili kayıt ve sekme. tabsOf ve keyOf bileşen dışında sabit olmalı. */
export function useMasterDetail<T, K extends string>(tabsOf: (item: T) => readonly DetailTab<K>[], keyOf: (item: T) => string | number) {
  const [state, setState] = useState<{ item: T; tab: K } | null>(null);
  const toggle = useCallback((item: T) => {
    setState((cur) => (cur && keyOf(cur.item) === keyOf(item) ? null : { item, tab: firstFilledTab(tabsOf(item)) }));
  }, [keyOf, tabsOf]);
  const close = useCallback(() => setState(null), []);
  const setTab = useCallback((tab: K) => setState((cur) => (cur ? { ...cur, tab } : cur)), []);
  return { selected: state?.item ?? null, tab: state?.tab ?? null, toggle, close, setTab };
}

export function MasterDetail<K extends string>({ id, master, detail, onClose, hideTitle = false }: {
  /** Ayraç oranının hatırlandığı ekran adı. */
  id: string;
  master: ReactNode;
  detail: { title: string; tabsLabel: string; tabs: readonly DetailTab<K>[]; tab: K; onTab(tab: K): void; body?: ReactNode;
            /** Şerit kipi (K-173): başlık satırı yok; sekmeler ve Büyüt / ✕ kart tablosunun şeridine verilir (solda sekmeler, sağda düğmeler). */
            renderBody?: (parts: { tabs: ReactNode; controls: ReactNode }) => ReactNode } | null;
  onClose(): void;
  /** Başlık kartta yazmaz (ör. kaydın kodu ve adı kartın araç çubuğunda, K-171); erişilebilir ad ve büyütme şeridi yine başlıktan. */
  hideTitle?: boolean;
}) {
  const [ratio, setRatio] = useState(() => clamp(loadPaneRatio(id) ?? DEFAULT_RATIO));
  const root = useRef<HTMLDivElement>(null);
  const ratioRef = useRef(ratio);
  ratioRef.current = ratio;
  const open = detail !== null;
  const opener = useRef<HTMLElement | null>(null);
  const [expanded, setExpanded] = useState(false);  // ana tablo tek satırlık şeritte; DataTable durumu korunsun diye bağlı kalır

  useEffect(() => {
    if (!open) {
      setExpanded(false);
      return undefined;
    }
    opener.current = document.activeElement as HTMLElement | null;
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape" && !e.defaultPrevented && !document.querySelector(OVERLAYS)) onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      if (opener.current?.isConnected) opener.current.focus();
    };
  }, [open, onClose]);

  const apply = (next: number, persist: boolean) => {
    const value = clamp(next);
    setRatio(value);
    if (persist) savePaneRatio(id, value);
  };

  const onMouseDown = (e: MouseEvent) => {
    e.preventDefault();
    const move = (ev: globalThis.MouseEvent) => {
      const box = root.current?.getBoundingClientRect();
      if (box && box.height > 0) apply((ev.clientY - box.top) / box.height, false);
    };
    const up = () => {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", up);
      savePaneRatio(id, ratioRef.current);
    };
    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", up);
  };

  const onKeyDown = (e: KeyboardEvent) => {
    if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
    e.preventDefault();
    apply(ratio + (e.key === "ArrowDown" ? KEY_STEP : -KEY_STEP), true);
  };

  const controls = (
    <>
      <button type="button" className="sc-tool-btn" aria-label={expanded ? tr.ui.collapsePane : tr.ui.expandPane} title={expanded ? tr.ui.collapsePane : tr.ui.expandPane}
              aria-pressed={expanded} onClick={() => setExpanded((v) => !v)}>
        {expanded ? <Minimize2 aria-hidden /> : <Maximize2 aria-hidden />}
      </button>
      <button type="button" className="sc-tool-btn" aria-label={tr.ui.close} title={tr.ui.close} onClick={onClose}><X aria-hidden /></button>
    </>
  );

  return (
    <div className="sc-md" ref={root}>
      {expanded && detail && <div className="sc-md-collapsed">{detail.title}</div>}
      <div className="sc-md-pane" style={expanded ? { display: "none" } : { flexGrow: open ? ratio : 1 }}>{master}</div>
      {detail && (
        <>
          {!expanded && (
            <div role="separator" aria-orientation="horizontal" aria-label={tr.ui.resizePanes} tabIndex={0} className="sc-md-splitter"
                 aria-valuenow={Math.round(ratio * 100)} aria-valuemin={MIN_RATIO * 100} aria-valuemax={MAX_RATIO * 100}
                 onMouseDown={onMouseDown} onKeyDown={onKeyDown} onDoubleClick={() => apply(DEFAULT_RATIO, true)} />
          )}
          <section className={`sc-md-pane sc-md-detail${detail.renderBody ? " sc-md-detail--strip" : ""}`} style={{ flexGrow: expanded ? 1 : 1 - ratio }} aria-label={detail.title}>
            {detail.renderBody ? (
              <>
                {hideTitle && <h2 className="sc-visually-hidden">{detail.title}</h2>}
                {detail.renderBody({
                  tabs: (  // tek sekme olsa da sekme şeridi görünür (K-171)
                    <OverflowTabs<K> label={detail.tabsLabel} value={detail.tab} onChange={detail.onTab}
                                     options={detail.tabs.map((t) => ({ value: t.value, label: t.label, disabled: t.disabled }))} />
                  ),
                  controls,
                })}
              </>
            ) : (
              <>
                <header className="sc-md-head">
                  {hideTitle ? <h2 className="sc-visually-hidden">{detail.title}</h2> : <h2>{detail.title}</h2>}
                  {detail.tabs.length > 1 && (  // tek sekmede seçim şeridi yok (ör. zamanlanmış işin geçmişi)
                    <Segment<K> label={detail.tabsLabel} hideLabel value={detail.tab} onChange={detail.onTab} options={detail.tabs.map((t) => ({ value: t.value, label: t.label, disabled: t.disabled }))} />
                  )}
                  <div className="sc-md-actions">{controls}</div>
                </header>
                {detail.body}
              </>
            )}
          </section>
        </>
      )}
    </div>
  );
}

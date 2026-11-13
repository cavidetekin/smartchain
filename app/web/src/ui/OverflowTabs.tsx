// Tablo şeridinin sekmeleri (K-173, docs/12): ekran sekmeleriyle aynı görünüm (Segment); sığmayan sekmeler sondaki "Diğer ▾" menüsüne girer,
// seçili sekme oradaysa menünün adında görünür. Genişlik ölçülemiyorsa (ör. test ortamı) bütün sekmeler görünür.
import { ChevronDown } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useLayoutEffect, useRef, useState } from "react";

import { tr } from "../i18n/tr";
import { MenuItem, RowPopMenu } from "./PopMenu";

export interface TabOption<T> { value: T; label: ReactNode; disabled?: boolean }

export function OverflowTabs<T extends string | number>({ label, options, value, onChange }: {
  label: string; options: TabOption<T>[]; value: T; onChange(v: T): void;
}) {
  const box = useRef<HTMLDivElement>(null);
  const measure = useRef<HTMLDivElement>(null);
  const moreRef = useRef<HTMLButtonElement>(null);
  const [fit, setFit] = useState(options.length);
  const [open, setOpen] = useState(false);

  useLayoutEffect(() => {
    const el = box.current;
    const m = measure.current;
    if (!el || !m) return undefined;
    const parent = el.parentElement;
    const compute = () => {
      // Kullanılabilir genişlik: şeridin sol yarısı eksi yanındaki öğeler (ör. tablo seçimi); kendi genişliği değil (yoksa büyüyünce açılmaz)
      let avail = el.clientWidth;
      if (parent) {
        const gap = parseFloat(getComputedStyle(parent).columnGap || "0") || 0;
        const others = [...parent.children].filter((c) => c !== el).reduce((sum, c) => sum + (c as HTMLElement).offsetWidth + gap, 0);
        avail = parent.clientWidth - others;
        // Tablo şeridinde: şeridin genişliği eksi sağdaki düğmeler (önce sekmeler Diğer'e çekilir, her şey tek satıra sığar)
        const bar = parent.parentElement;
        const tools = bar?.classList.contains("sc-table-toolbar") ? bar.querySelector<HTMLElement>(":scope > .sc-table-tools") : null;
        if (bar && tools && bar.clientWidth) {
          const barGap = parseFloat(getComputedStyle(bar).columnGap || "0") || 0;
          avail = Math.min(avail, bar.clientWidth - tools.offsetWidth - barGap - others);
        }
      }
      const widths = [...m.querySelectorAll<HTMLElement>("[data-tab]")].map((b) => b.offsetWidth);
      const more = m.querySelector<HTMLElement>("[data-more]")?.offsetWidth ?? 0;
      // Seçili sekme Diğer'e düşerse düğme onun adını taşır: genişliği o adla ölçülür
      const current = options.findIndex((o) => o.value === value);
      const moreFor = m.querySelector<HTMLElement>(`[data-more-for="${String(value)}"]`)?.offsetWidth ?? more;
      if (!avail || widths.every((w) => w === 0)) {
        setFit(options.length);
        return;
      }
      const pad = 8;  // şeridin iç boşluğu
      let used = pad;
      let k = 0;
      for (; k < widths.length; k++) {
        const rest = k + 1 < widths.length ? (current > k ? Math.max(more, moreFor) : more) : 0;
        if (used + widths[k] + rest > avail) break;
        used += widths[k];
      }
      setFit(k);  // gerekirse bütün sekmeler Diğer'e (seçili sekme düğmenin adında)
    };
    compute();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(compute) : null;
    ro?.observe(parent ?? el);
    if (parent?.parentElement) ro?.observe(parent.parentElement);
    return () => ro?.disconnect();
  }, [options, value]);

  const shown = options.slice(0, fit);
  const hidden = options.slice(fit);
  const hiddenCurrent = hidden.find((o) => o.value === value);
  const index = shown.findIndex((o) => o.value === value);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!step || index < 0) return;
    e.preventDefault();
    let i = index;
    for (let n = 0; n < shown.length; n++) {
      i = (i + step + shown.length) % shown.length;
      if (!shown[i].disabled) break;
    }
    if (shown[i].disabled) return;
    onChange(shown[i].value);
    (e.currentTarget.querySelector(`[data-value="${String(shown[i].value)}"]`) as HTMLElement | null)?.focus();
  };

  return (
    <div className="sc-overflow-tabs" ref={box}>
      <div className="sc-segment" role="radiogroup" aria-label={label} onKeyDown={onKey}>
        {shown.map((o) => (
          <button key={String(o.value)} type="button" role="radio" aria-checked={o.value === value} data-value={String(o.value)}
                  tabIndex={o.value === value ? 0 : -1} disabled={o.disabled} onClick={() => onChange(o.value)}>
            {o.label}
          </button>
        ))}
        {hidden.length > 0 && (
          <button type="button" ref={moreRef} aria-haspopup="menu" aria-expanded={open}
                  className={`sc-overflow-more${hiddenCurrent ? " is-current" : ""}`} onClick={() => setOpen((v) => !v)}>
            <span className="sc-overflow-more-label">{hiddenCurrent ? hiddenCurrent.label : tr.ui.moreTabs}</span> <ChevronDown aria-hidden="true" />
          </button>
        )}
      </div>
      {open && moreRef.current && (
        <RowPopMenu label={tr.ui.moreTabs} anchor={moreRef.current} onClose={() => setOpen(false)}>
          {hidden.map((o) => (
            <MenuItem key={String(o.value)} label={String(o.label)} state={{ allowed: !o.disabled }} onClick={() => { setOpen(false); onChange(o.value); }} />
          ))}
        </RowPopMenu>
      )}
      {/* ölçü: bütün sekmeler ve "Diğer" görünmeden */}
      <div className="sc-segment sc-overflow-measure" ref={measure} aria-hidden="true">
        {options.map((o) => <button key={String(o.value)} type="button" tabIndex={-1} data-tab="">{o.label}</button>)}
        <button type="button" tabIndex={-1} data-more="" className="sc-overflow-more">{tr.ui.moreTabs} <ChevronDown aria-hidden="true" /></button>
        {options.map((o) => (
          <button key={`m${String(o.value)}`} type="button" tabIndex={-1} data-more-for={String(o.value)} className="sc-overflow-more">
            <span className="sc-overflow-more-label">{o.label}</span> <ChevronDown aria-hidden="true" />
          </button>
        ))}
      </div>
    </div>
  );
}

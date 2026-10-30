// Renk seçici (U-24, K-96): Excel benzeri palet. Ürün renkleri (öneri), tema renkleri (10 × 6), standart renkler,
// renksiz, "Diğer renk" (#rrggbb). Kutular arasında ok tuşlarıyla gezilir; her kutunun adı ürün renginde adıyla,
// diğerlerinde hex ile okunur. Pencere (Dialog) içinde de çalışır: Esc yalnız seçiciyi kapatır.
import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";

import { tr } from "../i18n/tr";
import { isHex } from "./contrast";
import { PRODUCT_COLORS, STANDARD_COLORS, THEME_GRID } from "./palette";
import { useFloating } from "./popover";

const T = tr.table;

interface Swatch {
  hex: string;
  name: string;
}

/** Izgarada ok tuşlarıyla gezinme: bir sekme durağı, seçili ya da ilk kutu odaklanır (roving tabindex). */
function SwatchGrid({ label, rows, value, onPick }: {
  label: string; rows: Swatch[][]; value?: string; onPick(hex: string): void;
}) {
  const flat = rows.flat();
  const focusIndex = Math.max(0, flat.findIndex((s) => s.hex === value));
  const ref = useRef<HTMLDivElement>(null);
  const onKey = (e: KeyboardEvent, r: number, c: number) => {
    const move: Record<string, [number, number]> = { ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [-1, 0], ArrowDown: [1, 0] };
    const d = move[e.key];
    if (!d) return;
    e.preventDefault();
    const nr = Math.min(rows.length - 1, Math.max(0, r + d[0]));
    const nc = Math.min(rows[nr].length - 1, Math.max(0, c + d[1]));
    ref.current?.querySelector<HTMLButtonElement>(`[data-cell="${nr}-${nc}"]`)?.focus();
  };
  let i = 0;
  return (
    <div className="sc-color-section">
      <div className="sc-color-section-title">{label}</div>
      <div ref={ref} className="sc-color-grid" role="group" aria-label={label}>
        {rows.map((row, r) => (
          <div key={r} className="sc-color-row">
            {row.map((s, c) => {
              const index = i++;
              return (
                <button key={`${s.hex}-${c}`} type="button" className="sc-swatch-btn" data-cell={`${r}-${c}`}
                        tabIndex={index === focusIndex ? 0 : -1} aria-label={s.name} title={s.name}
                        aria-pressed={s.hex === value} style={{ backgroundColor: s.hex }}
                        onKeyDown={(e) => onKey(e, r, c)} onClick={() => onPick(s.hex)} />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

const named = (hex: string): Swatch => ({ hex, name: hex });

export function ColorPicker({ label, value, onChange, emptyLabel = T.colorNone, emptyColor }: {
  label: string; value?: string; onChange(hex: string | undefined): void;
  /** Boş seçeneğin adı (ör. ikon renginde "Varsayılan") ve gösterilen rengi. */
  emptyLabel?: string; emptyColor?: string;
}) {
  const [open, setOpen] = useState(false);
  const [other, setOther] = useState(value ?? "");
  const [error, setError] = useState<string | null>(null);
  const button = useRef<HTMLButtonElement>(null);
  const pop = useRef<HTMLDivElement>(null);
  const labelId = useId();
  useFloating(pop, button, open);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!pop.current?.contains(e.target as Node) && !button.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    pop.current?.querySelector<HTMLButtonElement>(".sc-swatch-btn[tabindex='0']")?.focus();
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const pick = (hex: string | undefined) => {
    onChange(hex);
    setOpen(false);
    button.current?.focus();
  };
  const applyOther = () => {
    const v = other.trim().toLowerCase();
    const hex = v.startsWith("#") ? v : `#${v}`;
    if (!isHex(hex)) {
      setError(T.colorInvalid);
      return;
    }
    setError(null);
    pick(hex);
  };
  const onPopKey = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      e.stopPropagation();  // pencereyi değil yalnız seçiciyi kapatır
      setOpen(false);
      button.current?.focus();
    }
  };
  const rows = (list: Swatch[], width = 10) =>
    Array.from({ length: Math.ceil(list.length / width) }, (_, r) => list.slice(r * width, r * width + width));

  return (
    <div className="sc-field sc-color-field">
      <span className="sc-field-label" id={labelId}>{label}</span>
      <button ref={button} type="button" className="sc-color-button" aria-haspopup="dialog" aria-expanded={open}
              aria-label={T.colorChoose(label, value ?? emptyLabel)} onClick={() => setOpen((o) => !o)}>
        <span className={`sc-swatch${value || emptyColor ? "" : " is-empty"}`}
              style={value || emptyColor ? { backgroundColor: value ?? emptyColor } : undefined} />
        <span className="sc-num">{value ?? emptyLabel}</span>
      </button>
      {open && (
        <div ref={pop} className="sc-color-pop sc-floating" role="dialog" aria-labelledby={labelId} onKeyDown={onPopKey}>
          <SwatchGrid label={T.colorProduct} value={value} onPick={pick}
                      rows={rows(PRODUCT_COLORS.map((p) => ({ hex: p.hex, name: `${T.colorNames[p.token] ?? p.token} ${p.hex}` })), 6)} />
          <SwatchGrid label={T.colorTheme} value={value} onPick={pick} rows={THEME_GRID.map((r) => r.map(named))} />
          <SwatchGrid label={T.colorStandard} value={value} onPick={pick} rows={[STANDARD_COLORS.map(named)]} />
          <div className="sc-color-actions">
            <button type="button" className="sc-btn sc-btn--ghost sc-btn--sm" onClick={() => pick(undefined)}>{emptyLabel}</button>
            <label className="sc-color-other">
              <span>{T.colorOther}</span>
              <input className="sc-input sc-num" value={other} placeholder={T.colorOtherHint} maxLength={7}
                     aria-invalid={Boolean(error)} onChange={(e) => setOther(e.target.value)}
                     onKeyDown={(e) => {
                       if (e.key === "Enter") {
                         e.preventDefault();
                         applyOther();
                       }
                     }} />
            </label>
            <button type="button" className="sc-btn sc-btn--secondary sc-btn--sm" onClick={applyOther}>{T.apply}</button>
          </div>
          {error && <p className="sc-field-error" role="alert">{error}</p>}
        </div>
      )}
    </div>
  );
}

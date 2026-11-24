// Aramalı çoklu seçim (K-196, docs/12 "Pencere ve form standardı"): listeden birden çok değer seçmek için yazılabilir kutu. Kutuda seçilenler
// yazar; sığmıyorsa yazı kesilmez, "3 seçili" gibi özet yazar ve tamamı ipucundadır; hiçbiri ya da hepsi seçiliyse yer tutucu (ör. "Tümü"). Tıklayınca ya da yazınca liste açılır, yazdıkça süzülür, eşleşen kısım
// vurgulanır; her seçenek işaret kutuludur: tıklamak ya da Enter seçer ve kaldırır (liste açık kalır); ok tuşlarıyla gezilir; Esc listeyi kapatır
// (pencereyi değil). Liste ekranda yüzer: pencerenin boyutu seçimle değişmez.
import { Check, ChevronDown } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";

import { tr } from "../i18n/tr";
import { useFloating } from "./popover";

const fold = (s: string) => s.toLocaleLowerCase("tr");

function marked(text: string, query: string): ReactNode {
  const at = query ? fold(text).indexOf(fold(query)) : -1;
  if (at < 0) return text;
  return <>{text.slice(0, at)}<mark>{text.slice(at, at + query.length)}</mark>{text.slice(at + query.length)}</>;
}

export function MultiSelect<T extends string | number>({ label, options, value, onChange, placeholder, emptyText, disabled }: {
  label: string; options: readonly T[]; value: readonly T[]; onChange(next: T[]): void;
  /** Hiçbiri ya da hepsi seçiliyken kutuda yazan (ör. "Tümü"). */
  placeholder: string;
  /** Eşleşen yokken listede yazan metin. */
  emptyText: string; disabled?: boolean;
}) {
  const id = useId();
  const [query, setQuery] = useState<string | null>(null);     // null: yazılmıyor (kutuda seçilenler)
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const q = (query ?? "").trim();
  const shown = useMemo(() => (q ? options.filter((o) => fold(String(o)).includes(fold(q))) : [...options]), [options, q]);
  useFloating(list, input, open);
  useEffect(() => { if (active >= shown.length) setActive(0); }, [shown, active]);
  useEffect(() => {   // etkin öğe görünür kalsın
    if (open) list.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView?.({ block: "nearest" });
  }, [active, open]);

  const toggle = (o: T) => onChange(value.includes(o) ? value.filter((x) => x !== o) : options.filter((x) => x === o || value.includes(x)));
  const close = () => { setOpen(false); setQuery(null); };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) { setOpen(true); return; }
      setActive((i) => (shown.length ? (i + (e.key === "ArrowDown" ? 1 : -1) + shown.length) % shown.length : 0));
    } else if (e.key === "Enter" && open) {
      e.preventDefault();   // liste açıkken Enter seçer; pencereyi kaydetmez
      if (shown[active] !== undefined) toggle(shown[active]);
    } else if (e.key === "Escape" && open) {
      e.preventDefault();
      e.stopPropagation();  // önce liste kapanır
      setOpen(false);
      setQuery("");         // odak kutuda kalır: yeniden yazınca arama baştan başlar (seçilenler yer tutucuda yazar)
    }
  };
  const some = value.length > 0 && value.length < options.length;   // hepsini seçmek ile hiç seçmemek aynıdır
  const full = some ? value.map(String).join(", ") : "";
  // sığmayan seçim kesilmez, sayıyla özetlenir (kutunun yazı tipiyle ölçülür; ölçülemeyen ortamda tam yazı)
  const [fits, setFits] = useState(true);
  useLayoutEffect(() => {
    const el = input.current;
    const ctx = el && full ? document.createElement("canvas").getContext?.("2d") : null;
    if (!el || !ctx) { setFits(true); return; }
    const style = getComputedStyle(el);
    ctx.font = style.font || `${style.fontSize} ${style.fontFamily}`;
    const room = el.clientWidth - parseFloat(style.paddingLeft || "0") - parseFloat(style.paddingRight || "0");
    setFits(room <= 0 || ctx.measureText(full).width <= room);
  }, [full]);
  const summary = fits ? full : tr.ui.selectedCount(value.length);
  return (
    <div className="sc-field sc-search-select sc-multi-select">
      <label htmlFor={id} className="sc-field-label">{label}</label>
      <div className="sc-search-select-box">
        <input ref={input} id={id} className="sc-input" role="combobox" autoComplete="off" disabled={disabled} aria-expanded={open} aria-controls={`${id}-list`}
               aria-autocomplete="list" aria-activedescendant={open && shown[active] !== undefined ? `${id}-o${active}` : undefined}
               value={query ?? summary} placeholder={summary || placeholder} title={full && !fits ? full : undefined}
               onChange={(e) => { setQuery(e.target.value); setOpen(true); setActive(0); }}
               onFocus={() => setQuery("")} onClick={() => { setOpen(true); setQuery((s) => s ?? ""); }} onKeyDown={onKey} onBlur={close} />
        <ChevronDown aria-hidden="true" />
      </div>
      {open && (
        <ul ref={list} id={`${id}-list`} role="listbox" aria-label={label} aria-multiselectable="true" className="sc-search-select-list sc-multi-select-list sc-floating"
            style={{ width: input.current?.offsetWidth }} onMouseDown={(e) => e.preventDefault()}>
          {shown.map((o, i) => (
            <li key={String(o)} id={`${id}-o${i}`} data-index={i} role="option" aria-selected={value.includes(o)} className={i === active ? "is-active" : undefined}
                onMouseEnter={() => setActive(i)} onClick={() => toggle(o)}>
              <span className="sc-multi-select-box" aria-hidden="true">{value.includes(o) && <Check />}</span>
              <span>{marked(String(o), q)}</span>
            </li>
          ))}
          {!shown.length && <li className="sc-search-select-empty" role="presentation">{emptyText}</li>}
        </ul>
      )}
    </div>
  );
}

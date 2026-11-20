// Aramalı seçim (K-187, docs/12 "Pencere ve form standardı"): uzun listeden seçim için yazılabilir kutu. Koda ya da ada göre yazınca liste
// süzülür, eşleşen kısım vurgulanır; ok tuşları ve Enter ya da tıklama seçer; Esc listeyi kapatır (pencereyi değil). Seçili öğe "KOD · Ad" yazar.
import { ChevronDown, CircleAlert } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useEffect, useId, useMemo, useRef, useState } from "react";

import { useFloating } from "./popover";

export interface SearchOption { value: string; code: string; name?: string }

const MAX_SHOWN = 100;
const fold = (s: string) => s.toLocaleLowerCase("tr");
const textOf = (o: SearchOption | undefined) => (o ? (o.name ? `${o.code} · ${o.name}` : o.code) : "");

/** Eşleşen kısım vurgulu. */
function marked(text: string, query: string): ReactNode {
  const at = query ? fold(text).indexOf(fold(query)) : -1;
  if (at < 0) return text;
  return <>{text.slice(0, at)}<mark>{text.slice(at, at + query.length)}</mark>{text.slice(at + query.length)}</>;
}

export function SearchSelect({ label, value, onChange, options, error, disabled, emptyText }: {
  label: string; value: string; onChange(value: string): void; options: SearchOption[]; error?: string; disabled?: boolean;
  /** Eşleşen yokken listede yazan metin. */
  emptyText: string;
}) {
  const id = useId();
  const selected = useMemo(() => options.find((o) => o.value === value), [options, value]);
  const [query, setQuery] = useState<string | null>(null);     // null: yazılmıyor (kutuda seçili öğe)
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);
  const shown = useMemo(() => {
    const q = fold((query ?? "").trim());
    const found = q ? options.filter((o) => fold(o.code).includes(q) || fold(o.name ?? "").includes(q)) : options;
    return found.slice(0, MAX_SHOWN);
  }, [options, query]);
  useFloating(list, input, open);
  useEffect(() => { if (active >= shown.length) setActive(0); }, [shown, active]);
  useEffect(() => {   // etkin öğe görünür kalsın
    if (open) list.current?.querySelector<HTMLElement>(`[data-index="${active}"]`)?.scrollIntoView?.({ block: "nearest" });
  }, [active, open]);

  const pick = (o: SearchOption) => { onChange(o.value); setQuery(null); setOpen(false); };
  const close = () => { setOpen(false); setQuery(null); };
  const onKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) { setOpen(true); return; }
      setActive((i) => (shown.length ? (i + (e.key === "ArrowDown" ? 1 : -1) + shown.length) % shown.length : 0));
    } else if (e.key === "Enter" && open) {
      e.preventDefault();   // liste açıkken Enter seçer; pencereyi kaydetmez
      if (shown[active]) pick(shown[active]);
    } else if (e.key === "Escape" && open) {
      e.preventDefault();
      e.stopPropagation();  // önce liste kapanır
      close();
    }
  };
  return (
    <div className={`sc-field sc-search-select${error ? " is-invalid" : ""}`}>
      <label htmlFor={id} className="sc-field-label">{label}</label>
      <div className="sc-search-select-box">
        <input ref={input} id={id} className="sc-input" role="combobox" autoComplete="off" disabled={disabled} aria-expanded={open} aria-controls={`${id}-list`}
               aria-autocomplete="list" aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-msg` : undefined}
               aria-activedescendant={open && shown[active] ? `${id}-o${active}` : undefined}
               value={query ?? textOf(selected)}
               onChange={(e) => { setQuery(e.target.value); setOpen(true); setActive(0); if (!e.target.value) onChange(""); }}
               onFocus={(e) => e.target.select()} onClick={() => setOpen(true)} onKeyDown={onKey} onBlur={close} />
        <ChevronDown aria-hidden="true" />
      </div>
      {open && (
        <ul ref={list} id={`${id}-list`} role="listbox" aria-label={label} className="sc-search-select-list sc-floating"
            style={{ width: input.current?.offsetWidth }} onMouseDown={(e) => e.preventDefault()}>
          {shown.map((o, i) => (
            <li key={o.value} id={`${id}-o${i}`} data-index={i} role="option" aria-selected={o.value === value} className={i === active ? "is-active" : undefined}
                onMouseEnter={() => setActive(i)} onClick={() => pick(o)}>
              <span className="sc-search-select-code">{marked(o.code, (query ?? "").trim())}</span>
              {o.name && <span className="sc-search-select-name">{marked(o.name, (query ?? "").trim())}</span>}
            </li>
          ))}
          {!shown.length && <li className="sc-search-select-empty" role="presentation">{emptyText}</li>}
        </ul>
      )}
      {error && <p className="sc-field-error" id={`${id}-msg`}><CircleAlert aria-hidden="true" /> {error}</p>}
    </div>
  );
}

// Form alanları (mockup m24f-0757): etiket, yardım, zorunlu işareti, hata (kiremit, ikonlu, U-3), pasif.
// Sayı ve tarih Türkçe girilir ve gösterilir (U-19).
import { CalendarDays, CircleAlert, Search } from "lucide-react";
import {
  type InputHTMLAttributes, type KeyboardEvent, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes,
  useEffect, useId, useLayoutEffect, useRef, useState,
} from "react";

import { formatDate, formatNumber, parseTrDate, parseTrNumber } from "../format";
import { tr } from "../i18n/tr";
import { Calendar } from "./Calendar";
import { placePopover, viewportSize } from "./popover";

interface FieldProps {
  label: string;
  help?: string;
  error?: string;
  required?: boolean;
}

function Field({ label, help, error, required, id, children }: FieldProps & { id: string; children: ReactNode }) {
  return (
    <div className={`sc-field${error ? " is-invalid" : ""}`}>
      <label htmlFor={id} className="sc-field-label">
        {label}
        {required && <span className="sc-field-required"> ({tr.ui.required})</span>}
      </label>
      {children}
      {error ? (
        <p className="sc-field-error" id={`${id}-msg`}><CircleAlert aria-hidden="true" /> {error}</p>
      ) : help ? (
        <p className="sc-field-help" id={`${id}-msg`}>{help}</p>
      ) : null}
    </div>
  );
}

type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange"> & FieldProps;

function describedBy(id: string, p: FieldProps) {
  return p.error || p.help ? `${id}-msg` : undefined;
}

export function TextField({ label, help, error, required, value, onChange, ...rest }: InputProps & {
  value: string; onChange(v: string): void;
}) {
  const id = useId();
  return (
    <Field {...{ label, help, error, required, id }}>
      <input id={id} className="sc-input" value={value} required={required} aria-invalid={Boolean(error)}
             aria-describedby={describedBy(id, { label, help, error })} onChange={(e) => onChange(e.target.value)} {...rest} />
    </Field>
  );
}

/** Sayı: Inter, eşit genişlikte rakam (K-86), sağa yaslı; "1.234,5" biçiminde girilir; geçersizse hata ve değer değişmez. */
export function NumberField({ label, help, error, required, value, onChange, decimals = 0, ...rest }: InputProps & {
  value: number | null; onChange(v: number | null): void; decimals?: number;
}) {
  const id = useId();
  const [text, setText] = useState(value === null ? "" : formatNumber(value, decimals));
  const [invalid, setInvalid] = useState(false);
  const commit = () => {
    if (!text.trim()) {
      setInvalid(false);
      onChange(null);
      return;
    }
    const n = parseTrNumber(text);
    setInvalid(n === null);
    if (n !== null) {
      onChange(n);
      setText(formatNumber(n, decimals));
    }
  };
  const shownError = error ?? (invalid ? tr.ui.invalidNumber : undefined);
  return (
    <Field {...{ label, help, error: shownError, required, id }}>
      <input id={id} className="sc-input sc-input--number" inputMode="decimal" value={text} required={required}
             aria-invalid={Boolean(shownError)} aria-describedby={describedBy(id, { label, help, error: shownError })}
             onChange={(e) => setText(e.target.value)} onBlur={commit}
             onKeyDown={(e) => e.key === "Enter" && commit()} {...rest} />
    </Field>
  );
}

/** Tarih: gg.aa.yyyy (U-19) elle ya da takvimden; geçersizse hata. */
export function DateField({ label, help, error, required, value, onChange, ...rest }: InputProps & {
  value: Date | null; onChange(v: Date | null): void;
}) {
  const id = useId();
  const [text, setText] = useState(value ? formatDate(value) : "");
  const [invalid, setInvalid] = useState(false);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {  // takvim görünür alana sığacak şekilde (docs/12)
    const pop = popRef.current?.firstElementChild as HTMLElement | null | undefined;
    if (!open || !pop || !wrapRef.current) return;
    const at = placePopover(wrapRef.current.getBoundingClientRect(), pop.getBoundingClientRect(), viewportSize());
    popRef.current!.style.left = `${at.left}px`;
    popRef.current!.style.top = `${at.top}px`;
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const close = () => {
    setOpen(false);
    buttonRef.current?.focus();
  };
  const pick = (d: Date) => {
    setText(formatDate(d));
    setInvalid(false);
    onChange(d);
    close();
  };
  const commit = () => {
    if (!text.trim()) {
      setInvalid(false);
      onChange(null);
      return;
    }
    const d = parseTrDate(text);
    setInvalid(d === null);
    if (d) {
      onChange(d);
      setText(formatDate(d));
    }
  };
  const shownError = error ?? (invalid ? tr.ui.invalidDate : undefined);
  return (
    <Field {...{ label, help, error: shownError, required, id }}>
      <div className="sc-date" ref={wrapRef}>
        <input id={id} className="sc-input sc-input--date" placeholder={tr.ui.datePlaceholder} value={text}
               required={required} aria-invalid={Boolean(shownError)}
               aria-describedby={describedBy(id, { label, help, error: shownError })}
               onChange={(e) => setText(e.target.value)} onBlur={commit}
               onKeyDown={(e) => e.key === "Enter" && commit()} {...rest} />
        <button type="button" className="sc-date-btn" ref={buttonRef} aria-label={`${label}: ${tr.ui.calendar.open}`}
                aria-haspopup="dialog" aria-expanded={open} disabled={rest.disabled} onClick={() => setOpen((o) => !o)}>
          <CalendarDays aria-hidden="true" />
        </button>
        {open && (
          <div className="sc-cal-pop" ref={popRef}>
            <Calendar value={parseTrDate(text) ?? value} onSelect={pick} onClose={close} />
          </div>
        )}
      </div>
    </Field>
  );
}

export function SelectField({ label, help, error, required, options, value, onChange, ...rest }:
  Omit<SelectHTMLAttributes<HTMLSelectElement>, "value" | "onChange"> & FieldProps & {
    options: { value: string; label: string }[]; value: string; onChange(v: string): void;
  }) {
  const id = useId();
  return (
    <Field {...{ label, help, error, required, id }}>
      <select id={id} className="sc-input sc-select" value={value} required={required} aria-invalid={Boolean(error)}
              onChange={(e) => onChange(e.target.value)} {...rest}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </Field>
  );
}

export function TextareaField({ label, help, error, required, value, onChange, ...rest }:
  Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "value" | "onChange"> & FieldProps & {
    value: string; onChange(v: string): void;
  }) {
  const id = useId();
  return (
    <Field {...{ label, help, error, required, id }}>
      <textarea id={id} className="sc-input sc-textarea" value={value} required={required}
                aria-invalid={Boolean(error)} onChange={(e) => onChange(e.target.value)} {...rest} />
    </Field>
  );
}

export function Checkbox({ label, checked, onChange, disabled }: {
  label: string; checked: boolean; onChange(v: boolean): void; disabled?: boolean;
}) {
  return (
    <label className={`sc-check${disabled ? " is-disabled" : ""}`}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

export function RadioGroup({ label, options, value, onChange }: {
  label: string; options: { value: string; label: string }[]; value: string; onChange(v: string): void;
}) {
  const name = useId();
  return (
    <fieldset className="sc-radio-group">
      <legend className="sc-field-label">{label}</legend>
      <div className="sc-radio-options">
        {options.map((o) => (
          <label key={o.value} className="sc-check">
            <input type="radio" name={name} value={o.value} checked={value === o.value} onChange={() => onChange(o.value)} />
            <span>{o.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

/** Segment (ör. Günlük / Haftalık / Aylık): tek seçim; ok tuşlarıyla gezilir. Etiket üstte görünür;
 *  başlığı zaten yazan yerde (kullanıcı menüsü) hideLabel ile yalnız erişilebilir ad kalır. */
export function Segment<T extends string | number>({ label, options, value, onChange, hideLabel }: {
  label: string; options: { value: T; label: ReactNode }[]; value: T; onChange(v: T): void; hideLabel?: boolean;
}) {
  const id = useId();
  const index = options.findIndex((o) => o.value === value);
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = options[(index + step + options.length) % options.length];
    onChange(next.value);
    (e.currentTarget.querySelector(`[data-value="${String(next.value)}"]`) as HTMLElement | null)?.focus();
  };
  const group = (
    <div className="sc-segment" role="radiogroup" aria-label={hideLabel ? label : undefined}
         aria-labelledby={hideLabel ? undefined : id} onKeyDown={onKey}>
      {options.map((o) => (
        <button key={String(o.value)} type="button" role="radio" aria-checked={o.value === value}
                data-value={String(o.value)} tabIndex={o.value === value ? 0 : -1} onClick={() => onChange(o.value)}>
          {o.label}
        </button>
      ))}
    </div>
  );
  if (hideLabel) return group;
  return (
    <div className="sc-field sc-segment-field">
      <span className="sc-field-label" id={id}>{label}</span>
      {group}
    </div>
  );
}

export function SearchField({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange(v: string): void; placeholder?: string;
}) {
  return (
    <label className="sc-search-field">
      <Search aria-hidden="true" />
      <input type="search" aria-label={label} placeholder={placeholder ?? tr.ui.search} value={value}
             onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}

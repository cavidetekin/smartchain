// Tablo şeridinde etiketli seçim ve kutu (K-171): etiket alanın solunda, aynı satırda; şeritteki öteki kutularla aynı yükseklikte.
import { useId } from "react";

export function StripSelect({ label, value, onChange, options }: {
  label: string; value: string; onChange(v: string): void; options: { value: string; label: string }[];
}) {
  const id = useId();
  return (
    <span className="sc-strip-field">
      <label htmlFor={id}>{label}</label>
      <select id={id} className="sc-input sc-select" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </span>
  );
}

export function StripText({ label, value, onChange, disabled, inputMode, wide }: {
  label: string; value: string; onChange(v: string): void; disabled?: boolean; inputMode?: "decimal" | "text"; wide?: boolean;
}) {
  const id = useId();
  return (
    <span className="sc-strip-field">
      <label htmlFor={id}>{label}</label>
      <input id={id} className={`sc-input${wide ? " is-wide" : ""}`} value={value} disabled={disabled} inputMode={inputMode} onChange={(e) => onChange(e.target.value)} />
    </span>
  );
}

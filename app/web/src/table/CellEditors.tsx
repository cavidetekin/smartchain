// Hücre içi düzenleyiciler (K-132, docs/12): ortak tablonun cellRender'ıyla kullanılır, 6.x elle değer düzeltme de kullanır.
// Kaydetmezler: değeri useTableEdits tutar, Kaydet toplu yazar. Değişen hücre indigo çerçevelidir (U-4). Yetki yoksa değer düz görünür.
import type { MouseEvent } from "react";

const stop = (e: MouseEvent) => e.stopPropagation();  // satır seçimi tetiklenmesin
const edited = (changed?: boolean) => (changed ? " is-edited" : "");

export function SelectCell({ label, value, options, editable, changed, onChange }: {
  label: string; value: string; options: readonly string[]; editable: boolean; changed?: boolean; onChange(next: string): void;
}) {
  if (!editable) return <>{value}</>;
  return (
    <select className={`sc-cell-input${edited(changed)}`} aria-label={label} value={value} onClick={stop} onChange={(e) => onChange(e.target.value)}>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

/** Aç/kapa anahtarı (U-4). Kapatırken sebep, açarken uyarı üst bileşenin (ekran 02). */
export function SwitchCell({ label, checked, editable, changed, onToggle }: {
  label: string; checked: boolean; editable: boolean; changed?: boolean; onToggle(next: boolean): void;
}) {
  return (
    <label className={`sc-toggle${edited(changed)}`} onClick={stop}>
      <input type="checkbox" role="switch" aria-label={label} checked={checked} disabled={!editable} onClick={stop} onChange={(e) => onToggle(e.target.checked)} />
      <span className="sc-toggle-track" aria-hidden="true" />
    </label>
  );
}

export function TextCell({ label, value, placeholder, editable, changed, onChange }: {
  label: string; value: string; placeholder?: string; editable: boolean; changed?: boolean; onChange(next: string): void;
}) {
  if (!editable) return <>{value}</>;
  return (
    <input className={`sc-cell-input${edited(changed)}`} aria-label={label} value={value} placeholder={placeholder} onClick={stop} onChange={(e) => onChange(e.target.value)} />
  );
}

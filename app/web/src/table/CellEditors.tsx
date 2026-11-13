// Hücre içi anahtar (K-132, docs/12): ortak tablonun cellRender'ıyla kullanılır. Metin ve seçenek hücreleri kutusuz düzenlenir
// (hücre düzenleme standardı, K-172; table/cellEditing.tsx). Kaydetmez: değeri useTableEdits tutar, Kaydet toplu yazar.
import type { MouseEvent } from "react";

const stop = (e: MouseEvent) => e.stopPropagation();  // satır seçimi tetiklenmesin
const edited = (changed?: boolean) => (changed ? " is-edited" : "");

/** Aç/kapa anahtarı (U-4). Kapatırken sebep, açarken uyarı üst bileşenin (ekran 02). */
/** Anahtar (K-166): tablo satırında küçük; formda ve pencerede size="md" (~44 × 24 px). */
export function SwitchCell({ label, checked, editable, changed, onToggle, size = "sm" }: {
  label: string; checked: boolean; editable: boolean; changed?: boolean; onToggle(next: boolean): void; size?: "sm" | "md";
}) {
  return (
    <label className={`sc-toggle${size === "md" ? " sc-toggle--md" : ""}${edited(changed)}`} onClick={stop}>
      <input type="checkbox" role="switch" aria-label={label} checked={checked} disabled={!editable} onClick={stop} onChange={(e) => onToggle(e.target.checked)} />
      <span className="sc-toggle-track" aria-hidden="true" />
    </label>
  );
}

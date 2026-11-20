// Gün kutuları (K-187, docs/12 "Pencere ve form standardı"): haftanın günleri tek sırada kutu; kutuda günün adı, doluluk çizgisi ve değeri tam
// yazar. Tıklamak ya da boşluk tuşu değeri sırayla döndürür (Tam → Yarım → Çalışılmıyor).
import { useId } from "react";

export interface DayBox { key: string; label: string }

export function DayBoxes({ label, days, values, order, levels, onChange }: {
  label: string; days: DayBox[]; values: Record<string, string>;
  /** Değerlerin dönme sırası (ilk değer en dolu). */
  order: readonly string[];
  /** Değer → doluluk çizgisi (0–1). */
  levels: Record<string, number>;
  onChange(key: string, value: string): void;
}) {
  const id = useId();
  return (
    <div className="sc-field sc-day-boxes-field">
      <span className="sc-field-label" id={id}>{label}</span>
      <div className="sc-day-boxes" role="group" aria-labelledby={id}>
        {days.map((d) => {
          const value = values[d.key] ?? order[order.length - 1];
          const level = levels[value] ?? 0;
          return (
            <button key={d.key} type="button" className={`sc-day-box${level === 0 ? " is-off" : ""}`} aria-label={`${d.label}: ${value}`}
                    onClick={() => onChange(d.key, order[(order.indexOf(value) + 1) % order.length])}>
              <b>{d.label}</b>
              <span className="sc-day-bar" aria-hidden="true"><span style={{ width: `${level * 100}%` }} /></span>
              <i>{value}</i>
            </button>
          );
        })}
      </div>
    </div>
  );
}

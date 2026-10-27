// Takvim (docs/12 · Form alanları): Türkçe ay ve gün adları, hafta Pazartesi başlar, satırda ISO hafta (H44),
// "Bugün". Klavye: oklar gün/hafta, Page Up/Down ay, Home/End hafta başı/sonu, Enter seçer, Esc kapatır.
import { ChevronLeft, ChevronRight } from "lucide-react";
import { type KeyboardEvent, useEffect, useId, useRef, useState } from "react";

import { toIsoDate, weekLabel } from "../format";
import { tr } from "../i18n/tr";
import { Button } from "./Button";

const C = tr.ui.calendar;

const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
const addMonths = (d: Date, n: number) => {
  const target = new Date(d.getFullYear(), d.getMonth() + n, 1);
  const last = new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate();
  return new Date(target.getFullYear(), target.getMonth(), Math.min(d.getDate(), last));
};
const sameDay = (a: Date | null, b: Date) => Boolean(a) && toIsoDate(a!) === toIsoDate(b);
/** Pazartesi 0 … Pazar 6 */
const weekday = (d: Date) => (d.getDay() + 6) % 7;

/** Ayı kapsayan haftalar; her hafta Pazartesi'den başlar. */
export function monthWeeks(month: Date): Date[][] {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const last = new Date(month.getFullYear(), month.getMonth() + 1, 0);
  const weeks: Date[][] = [];
  for (let start = addDays(first, -weekday(first)); start <= last; start = addDays(start, 7)) {
    weeks.push(Array.from({ length: 7 }, (_, i) => addDays(start, i)));
  }
  return weeks;
}

export function dayLabel(d: Date): string {
  return `${d.getDate()} ${C.months[d.getMonth()]} ${d.getFullYear()} ${C.days[weekday(d)]}`;
}

export function Calendar({ value, onSelect, onClose }: {
  value: Date | null;
  onSelect(d: Date): void;
  onClose(): void;
}) {
  const today = new Date();
  const [focus, setFocus] = useState<Date>(value ?? today);
  const gridRef = useRef<HTMLTableElement>(null);
  const titleId = useId();
  const weeks = monthWeeks(focus);

  useEffect(() => {
    gridRef.current?.querySelector<HTMLButtonElement>(`[data-date="${toIsoDate(focus)}"]`)?.focus();
  }, [focus]);

  const onKey = (e: KeyboardEvent) => {
    const moves: Record<string, () => Date> = {
      ArrowLeft: () => addDays(focus, -1), ArrowRight: () => addDays(focus, 1),
      ArrowUp: () => addDays(focus, -7), ArrowDown: () => addDays(focus, 7),
      PageUp: () => addMonths(focus, -1), PageDown: () => addMonths(focus, 1),
      Home: () => addDays(focus, -weekday(focus)), End: () => addDays(focus, 6 - weekday(focus)),
    };
    if (moves[e.key]) {
      e.preventDefault();
      setFocus(moves[e.key]());
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(focus);
    }
  };

  return (
    <div className="sc-cal" role="dialog" aria-modal="false" aria-labelledby={titleId}
         onKeyDown={(e) => {
           if (e.key === "Escape") {
             e.stopPropagation();  // yalnız takvim kapanır, içinde bulunduğu menü değil
             onClose();
           }
         }}>
      <div className="sc-cal-head">
        <button type="button" className="sc-cal-nav" aria-label={C.prevMonth} onClick={() => setFocus(addMonths(focus, -1))}>
          <ChevronLeft aria-hidden="true" />
        </button>
        <span className="sc-cal-title" id={titleId} aria-live="polite">
          {C.months[focus.getMonth()]} {focus.getFullYear()}
        </span>
        <button type="button" className="sc-cal-nav" aria-label={C.nextMonth} onClick={() => setFocus(addMonths(focus, 1))}>
          <ChevronRight aria-hidden="true" />
        </button>
      </div>
      <table className="sc-cal-grid" role="grid" aria-labelledby={titleId} ref={gridRef} onKeyDown={onKey}>
        <thead>
          <tr>
            <th scope="col" abbr={C.week} className="sc-cal-week">{C.weekShort}</th>
            {C.daysShort.map((d, i) => <th key={d} scope="col" abbr={C.days[i]}>{d}</th>)}
          </tr>
        </thead>
        <tbody>
          {weeks.map((week) => (
            <tr key={toIsoDate(week[0])}>
              <th scope="row" className="sc-cal-week sc-num">{weekLabel(week[0])}</th>
              {week.map((d) => {
                const outside = d.getMonth() !== focus.getMonth();
                const selected = sameDay(value, d);
                return (
                  <td key={toIsoDate(d)} role="gridcell" aria-selected={selected}>
                    <button type="button" data-date={toIsoDate(d)} tabIndex={sameDay(focus, d) ? 0 : -1}
                            aria-label={dayLabel(d)} aria-current={sameDay(today, d) ? "date" : undefined}
                            className={`sc-cal-day sc-num${outside ? " is-outside" : ""}${selected ? " is-selected" : ""}`}
                            onClick={() => onSelect(d)}>
                      {d.getDate()}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="sc-cal-foot">
        <Button size="sm" variant="ghost" onClick={() => onSelect(addDays(today, 0))}>{C.today}</Button>
      </div>
    </div>
  );
}

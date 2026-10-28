// Kolon menüsü (U-10, K-90; docs/12 "Görünüm"): taşı, sabitle, grupla, ara toplam (sayı alanlarında), gizle,
// genişliği sıfırla. Klavyeyle de erişilir (↑ / ↓ öğeler arasında).
import { ChevronDown, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { tr } from "../i18n/tr";
import { SelectField } from "../ui";
import { useFloating } from "../ui/popover";
import type { AggFn, AggSpec, ListColumn } from "./types";
import { aggregateOf, MAX_GROUP_FIELDS, type TableState } from "./viewState";

const T = tr.table;

export type ColumnAction = "left" | "right" | "pin" | "unpin" | "group" | "hide" | "resetWidth";

export const isGroupable = (c: ListColumn) => c.filter !== "number";
const isNumber = (c: ListColumn) => c.type === "number" || c.type === "integer";
const FNS: AggFn[] = ["sum", "avg", "avg_nonzero", "wavg", "min", "max", "count", "none"];

export function ColumnMenu({ column, columns, state, onAction, onAggregate }: {
  column: ListColumn;
  columns: ListColumn[];
  state: TableState;
  onAction(action: ColumnAction): void;
  onAggregate(spec: AggSpec): void;
}) {
  const i = state.order.indexOf(column.field);
  const pinned = i < state.pinned;
  const current = aggregateOf(column, state);
  const [aggOpen, setAggOpen] = useState(false);
  const [weighted, setWeighted] = useState(current.fn === "wavg");
  const weights = columns.filter((c) => isNumber(c) && c.field !== column.field);
  const items: { action: ColumnAction; label: string; disabled?: boolean }[] = [
    { action: "left", label: T.moveLeft, disabled: i <= 0 },
    { action: "right", label: T.moveRight, disabled: i >= state.order.length - 1 },
    pinned ? { action: "unpin", label: T.unpin } : { action: "pin", label: T.pinHere },
    { action: "group", label: T.groupByThis,
      disabled: !isGroupable(column) || state.groupBy.includes(column.field) || state.groupBy.length >= MAX_GROUP_FIELDS },
    { action: "hide", label: T.hide, disabled: state.order.length <= 1 },
    { action: "resetWidth", label: T.resetWidth, disabled: state.widths[column.field] === undefined },
  ];
  const ref = useRef<HTMLDivElement>(null);
  const subTriggerRef = useRef<HTMLButtonElement>(null);
  const subRef = useRef<HTMLDivElement>(null);
  useFloating(subRef, subTriggerRef, aggOpen, "side");
  useEffect(() => ref.current?.querySelector<HTMLButtonElement>("button:not([disabled])")?.focus(), []);

  const item = (it: (typeof items)[number]) => (
    <button key={it.action} type="button" role="menuitem" className="sc-popmenu-item" disabled={it.disabled}
            onClick={() => onAction(it.action)}>
      {it.label}
    </button>
  );
  return (
    <div className="sc-popmenu" role="menu" ref={ref} aria-label={T.columnMenu(column.label)}
         onKeyDown={(e) => {
           if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
           e.preventDefault();
           const buttons = [...e.currentTarget.querySelectorAll<HTMLButtonElement>("button:not([disabled])")];
           const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
           buttons[(at + (e.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length]?.focus();
         }}>
      {items.slice(0, 4).map(item)}
      {isNumber(column) && (
        <>
          <button type="button" role="menuitem" className="sc-popmenu-item sc-popmenu-sub" aria-haspopup="menu" ref={subTriggerRef}
                  aria-expanded={aggOpen} onClick={() => setAggOpen((o) => !o)}>
            <span>{T.aggregate}</span>
            <span className="sc-muted">{T.aggFns[current.fn]}</span>
            {aggOpen ? <ChevronDown aria-hidden="true" /> : <ChevronRight aria-hidden="true" />}
          </button>
          {aggOpen && (
            <div ref={subRef} className="sc-popmenu sc-popmenu-subpanel sc-floating" role="group" aria-label={T.aggregate}>
              {FNS.map((fn) => (
                <button key={fn} type="button" role="menuitemradio" className="sc-popmenu-item"
                        aria-checked={fn === "wavg" ? weighted : !weighted && current.fn === fn}
                        disabled={fn === "wavg" && weights.length === 0}
                        onClick={() => (fn === "wavg" ? setWeighted(true) : onAggregate({ fn }))}>
                  {T.aggFns[fn]}{fn === "wavg" ? "…" : ""}
                </button>
              ))}
              {weighted && (
                <div className="sc-popmenu-field">
                  <SelectField label={T.weightField} value={current.fn === "wavg" ? current.weight ?? "" : ""}
                               onChange={(weight) => weight && onAggregate({ fn: "wavg", weight })}
                               options={[{ value: "", label: T.weightPlaceholder },
                                         ...weights.map((c) => ({ value: c.field, label: c.label }))]} />
                </div>
              )}
            </div>
          )}
        </>
      )}
      {items.slice(4).map(item)}
    </div>
  );
}

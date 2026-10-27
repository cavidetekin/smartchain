// Kolon menüsü (U-10, docs/12 "Görünüm"): taşı, sabitle, grupla, gizle, genişliği sıfırla. Klavyeyle de erişilir.
import { useEffect, useRef } from "react";

import { tr } from "../i18n/tr";
import type { ListColumn } from "./types";
import { MAX_GROUP_FIELDS, type TableState } from "./viewState";

const T = tr.table;

export type ColumnAction = "left" | "right" | "pin" | "unpin" | "group" | "hide" | "resetWidth";

export const isGroupable = (c: ListColumn) => c.filter !== "number";

export function ColumnMenu({ column, state, onAction }: {
  column: ListColumn;
  state: TableState;
  onAction(action: ColumnAction): void;
}) {
  const i = state.order.indexOf(column.field);
  const pinned = i < state.pinned;
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
  useEffect(() => ref.current?.querySelector<HTMLButtonElement>("button:not([disabled])")?.focus(), []);
  return (
    <div className="sc-popmenu" role="menu" ref={ref} aria-label={T.columnMenu(column.label)}
         onKeyDown={(e) => {
           if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
           e.preventDefault();
           const buttons = [...e.currentTarget.querySelectorAll<HTMLButtonElement>("button:not([disabled])")];
           const at = buttons.indexOf(document.activeElement as HTMLButtonElement);
           buttons[(at + (e.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length]?.focus();
         }}>
      {items.map((it) => (
        <button key={it.action} type="button" role="menuitem" className="sc-popmenu-item" disabled={it.disabled}
                onClick={() => onAction(it.action)}>
          {it.label}
        </button>
      ))}
    </div>
  );
}

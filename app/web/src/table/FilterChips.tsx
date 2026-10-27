// Aktif filtre etiketleri (U-12, mockup m24f-0379): sayacın yanında her filtre bir etiket; etikete tıklayınca filtre
// menüsü açılır, × tek tıkla kaldırır.
import { X } from "lucide-react";

import { tr } from "../i18n/tr";
import { describeFilter } from "./filters";
import type { ListColumn, ListFilter } from "./types";

const T = tr.table;

export function FilterChips({ filters, byField, onEdit, onRemove }: {
  filters: ListFilter[];
  byField: Map<string, ListColumn>;
  onEdit(field: string, anchor: HTMLElement): void;
  onRemove(field: string): void;
}) {
  if (!filters.length) return null;
  return (
    <ul className="sc-chips" aria-label={T.activeFilters}>
      {filters.map((f) => {
        const col = byField.get(f.field);
        if (!col) return null;
        return (
          <li key={f.field} className="sc-chip-filter">
            <button type="button" className="sc-chip-filter-text" title={T.chipEdit(col.label)}
                    onClick={(e) => onEdit(f.field, e.currentTarget)}>
              <span className="sc-chip-filter-label">{col.label}:</span> {describeFilter(f, col)}
            </button>
            <button type="button" className="sc-chip-filter-x" aria-label={T.chipRemove(col.label)}
                    onClick={() => onRemove(f.field)}>
              <X aria-hidden="true" />
            </button>
          </li>
        );
      })}
    </ul>
  );
}

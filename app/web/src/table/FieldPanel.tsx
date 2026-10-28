// Alan paneli (U-6): listenin bütün alanları aramalı onay kutusu listesinde; kapalı alanlar buradan geri açılır.
import { type Ref, useState } from "react";

import { fold } from "../format";
import { tr } from "../i18n/tr";
import { Button, Checkbox, SearchField } from "../ui";
import type { ListColumn } from "./types";

const T = tr.table;

export function FieldPanel({ ref, columns, visibility, onToggle, onReset }: {
  ref?: Ref<HTMLDivElement>;
  columns: ListColumn[];
  visibility: Record<string, boolean>;
  onToggle(field: string, on: boolean): void;
  onReset(): void;
}) {
  const [search, setSearch] = useState("");
  const q = fold(search.trim());
  const visibleCount = columns.filter((c) => visibility[c.field]).length;
  return (
    <div ref={ref} className="sc-table-pop sc-table-fields sc-floating" role="dialog" aria-label={T.fields(visibleCount, columns.length)}>
      <SearchField label={T.fieldSearch} value={search} onChange={setSearch} />
      <div className="sc-table-pop-list">
        {columns.filter((c) => !q || fold(c.label).includes(q)).map((c) => {
          const on = Boolean(visibility[c.field]);
          const last = on && visibleCount === 1;
          return (
            <div key={c.field} className="sc-table-pop-option" title={last ? `${c.label} · ${T.lastField}` : c.label}>
              <Checkbox label={c.label} checked={on} disabled={last} onChange={(v) => onToggle(c.field, v)} />
            </div>
          );
        })}
      </div>
      <div className="sc-table-pop-actions">
        <Button size="sm" variant="ghost" onClick={onReset}>{T.resetFields}</Button>
      </div>
    </div>
  );
}

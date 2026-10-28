// Gruplama paneli (U-11, K-90): bir ya da birden çok alan, sıralı; yukarı / aşağı / kaldır, alan ekle.
import { ArrowDown, ArrowUp, X } from "lucide-react";
import type { Ref } from "react";

import { tr } from "../i18n/tr";
import { Button, SelectField } from "../ui";
import { isGroupable } from "./ColumnMenu";
import type { ListColumn } from "./types";
import { MAX_GROUP_FIELDS } from "./viewState";

const T = tr.table;

export function GroupPanel({ ref, columns, groupBy, onChange }: {
  ref?: Ref<HTMLDivElement>;
  columns: ListColumn[];
  groupBy: string[];
  onChange(groupBy: string[]): void;
}) {
  const byField = new Map(columns.map((c) => [c.field, c]));
  const move = (i: number, d: number) => {
    const next = [...groupBy];
    [next[i], next[i + d]] = [next[i + d], next[i]];
    onChange(next);
  };
  const candidates = columns.filter((c) => isGroupable(c) && !groupBy.includes(c.field));
  return (
    <div ref={ref} className="sc-table-pop sc-table-group-panel sc-floating" role="dialog" aria-label={T.groupPanel}>
      {groupBy.length > 0 && (
        <ol className="sc-tgroup-list">
          {groupBy.map((f, i) => (
            <li key={f}>
              <span className="sc-tgroup-name">{byField.get(f)?.label ?? f}</span>
              <button type="button" className="sc-tool-btn" aria-label={`${byField.get(f)?.label}: ${T.up}`}
                      disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp aria-hidden="true" /></button>
              <button type="button" className="sc-tool-btn" aria-label={`${byField.get(f)?.label}: ${T.down}`}
                      disabled={i === groupBy.length - 1} onClick={() => move(i, 1)}><ArrowDown aria-hidden="true" /></button>
              <button type="button" className="sc-tool-btn" aria-label={`${byField.get(f)?.label}: ${T.remove}`}
                      onClick={() => onChange(groupBy.filter((g) => g !== f))}><X aria-hidden="true" /></button>
            </li>
          ))}
        </ol>
      )}
      {groupBy.length < MAX_GROUP_FIELDS && (
        <SelectField label={T.addGroup} value="" onChange={(f) => f && onChange([...groupBy, f])}
                     options={[{ value: "", label: T.addGroupPlaceholder },
                               ...candidates.map((c) => ({ value: c.field, label: c.label }))]} />
      )}
      {groupBy.length > 0 && (
        <div className="sc-table-pop-actions">
          <Button size="sm" variant="ghost" onClick={() => onChange([])}>{T.removeGroups}</Button>
        </div>
      )}
    </div>
  );
}

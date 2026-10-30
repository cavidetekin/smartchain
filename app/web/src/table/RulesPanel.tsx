// Koşullu biçim kural listesi (U-24, K-95; mockup m24f-0413'teki düzen): sıra, aktif anahtarı, alan ve koşul özeti,
// biçim örneği, düzenle, sil (satır sayısı gösterilmez). Sıra sürükle-bırak ya da Alt+↑ / Alt+↓; aynı biçim
// özelliğinde üstteki kural geçerlidir. Kolon menüsündeki "Biçimi yönet…" açar.
import { GripVertical, Pencil, Trash2 } from "lucide-react";
import { type DragEvent, type KeyboardEvent, type Ref, useState } from "react";

import { tr } from "../i18n/tr";
import { Button } from "../ui";
import { RuledValue } from "./RuleIcon";
import { describeCondition, dropRule, formatStyle, moveRule } from "./rules";
import { type FormatRule, type ListColumn, MAX_RULES } from "./types";

const T = tr.table;

export function RulesPanel({ ref, rules, columns, visible, onChange, onEdit, onAdd }: {
  ref?: Ref<HTMLDivElement>;
  rules: FormatRule[];
  columns: ListColumn[];
  /** Görünen alanlar: gizli alanın kuralı soluk ve "alan gizli". */
  visible: string[];
  onChange(rules: FormatRule[]): void;
  onEdit(rule: FormatRule): void;
  onAdd(): void;
}) {
  const byField = new Map(columns.map((c) => [c.field, c]));
  const [drag, setDrag] = useState<{ id: string; over?: string; side?: "before" | "after" } | null>(null);

  const onKey = (id: string, e: KeyboardEvent) => {
    if (!e.altKey || (e.key !== "ArrowUp" && e.key !== "ArrowDown")) return;
    e.preventDefault();
    onChange(moveRule(rules, id, e.key === "ArrowUp" ? -1 : 1));
    requestAnimationFrame(() => (document.querySelector(`[data-rule="${id}"]`) as HTMLElement | null)?.focus());
  };
  const over = (id: string, e: DragEvent<HTMLLIElement>) => {
    if (!drag || drag.id === id) return;
    e.preventDefault();
    const r = e.currentTarget.getBoundingClientRect();
    const side = e.clientY < r.top + r.height / 2 ? "before" : "after";
    if (drag.over !== id || drag.side !== side) setDrag({ ...drag, over: id, side });
  };
  const drop = (id: string, e: DragEvent) => {
    e.preventDefault();
    if (drag && drag.id !== id) onChange(dropRule(rules, drag.id, id, drag.side ?? "before"));
    setDrag(null);
  };

  return (
    <div ref={ref} className="sc-table-pop sc-rules-panel sc-floating" role="dialog" aria-label={T.rulesPanel}>
      <div className="sc-popover-title">{T.rulesPanel}</div>
      {rules.length === 0 ? <p className="sc-muted">{T.rulesEmpty}</p> : (
        <ol className="sc-rules-list">
          {rules.map((r, i) => {
            const col = byField.get(r.field);
            const label = `${col?.label ?? r.field} ${describeCondition(r, byField)}`;
            const hidden = !visible.includes(r.field);
            const classes = ["sc-rule-row", hidden ? "is-hidden" : "", r.enabled ? "" : "is-off",
                             drag?.over === r.id ? `is-drop-${drag.side}` : ""].filter(Boolean).join(" ");
            return (
              <li key={r.id} className={classes} draggable tabIndex={0} data-rule={r.id}
                  aria-label={T.ruleRowLabel(i + 1, label)}
                  onKeyDown={(e) => onKey(r.id, e)}
                  onDragStart={(e) => { e.dataTransfer?.setData("text/plain", r.id); setDrag({ id: r.id }); }}
                  onDragOver={(e) => over(r.id, e)} onDrop={(e) => drop(r.id, e)} onDragEnd={() => setDrag(null)}>
                <GripVertical className="sc-rule-grip" aria-hidden="true" />
                <span className="sc-rule-n sc-num">{i + 1}</span>
                <input type="checkbox" className="sc-switch" checked={r.enabled} aria-label={T.ruleActive(label)}
                       onChange={(e) => onChange(rules.map((x) => (x.id === r.id ? { ...x, enabled: e.target.checked } : x)))} />
                <span className="sc-rule-text">
                  <span className="sc-rule-field">{col?.label ?? r.field}</span> {describeCondition(r, byField)}
                  {hidden && <span className="sc-tag sc-rule-tag">{T.ruleHidden}</span>}
                </span>
                <span className="sc-rule-sample" style={formatStyle(r.format)}>
                  <RuledValue format={r.format} numeric><span className="sc-num">1.234</span></RuledValue>
                </span>
                <button type="button" className="sc-tool-btn" aria-label={T.ruleEdit(label)} onClick={() => onEdit(r)}>
                  <Pencil aria-hidden="true" />
                </button>
                <button type="button" className="sc-tool-btn" aria-label={T.ruleDelete(label)}
                        onClick={() => onChange(rules.filter((x) => x.id !== r.id))}>
                  <Trash2 aria-hidden="true" />
                </button>
              </li>
            );
          })}
        </ol>
      )}
      <div className="sc-table-pop-actions">
        {rules.length >= MAX_RULES && <span className="sc-muted">{T.ruleLimit(MAX_RULES)}</span>}
        <Button size="sm" variant="primary" disabled={rules.length >= MAX_RULES} onClick={onAdd}>{T.ruleAdd}</Button>
      </div>
    </div>
  );
}

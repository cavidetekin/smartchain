// Pivot ayar paneli (K-183, docs/12 "Pivot standardı"): Satırlar · Sütunlar · Değerler · Değerlerin yeri · Toplamlar · Sıralama.
// Grafik panelinin deseni ve sınıfları; alanlar tutamakla sürüklenir. Alan seçici Alanlar panelinin seçici kipidir (ilişkili alanlar dahil).
import { ChevronDown, ChevronRight, GripVertical, Plus, X } from "lucide-react";
import { type DragEvent, type ReactNode, useState } from "react";

import { tr } from "../i18n/tr";
import { BUCKETS, type ChartBucket } from "../ui/chart/chartModel";
import { NumberField, Segment, SelectField, TextField } from "../ui";
import { SwitchCell } from "./CellEditors";
import { FieldPanel } from "./FieldPanel";
import {
  canRule, defaultFn, dropOrphans, fnLabel, fnsFor, isAxisField, isCalc, isDate, isNumeric, isOperand, isPivotField, nextValueId, type PivotAxis, type PivotConfig,
  type PivotFn, PIVOT_MAX_AXIS, PIVOT_MAX_DISTINCT, PIVOT_MAX_RULES, PIVOT_MAX_VALUES, type PivotOp, PIVOT_OPS, type PivotRule, type PivotValue, valueDisplay,
  valueLabel, valueName,
} from "./pivotModel";
import { RuleDialog } from "./RuleDialog";
import { describeCondition, formatStyle, newRuleId } from "./rules";
import type { FormatRule, ListColumn, RelatedCatalog, RelationHeading } from "./types";

const T = tr.pivot;
type SectionKey = "rows" | "columns" | "values" | "place" | "totals" | "sort";

function Section({ id, title, count, open, onToggle, children }: { id: string; title: string; count?: number; open: boolean; onToggle(): void; children: ReactNode }) {
  return (
    <section className="sc-chart-section">
      <h3>
        <button type="button" aria-expanded={open} aria-controls={id} onClick={onToggle}>
          {open ? <ChevronDown aria-hidden="true" /> : <ChevronRight aria-hidden="true" />}
          <span>{title}</span>
          {count !== undefined && count > 0 && <span className="sc-chart-count sc-num">{count}</span>}
        </button>
      </h3>
      {open && <div id={id} className="sc-chart-section-body">{children}</div>}
    </section>
  );
}

function Toggle({ label, checked, onToggle }: { label: string; checked: boolean; onToggle(next: boolean): void }) {
  return (
    <div className="sc-field sc-field--inline sc-chart-toggle">
      <span className="sc-field-label">{label}</span>
      <SwitchCell label={label} checked={checked} editable size="md" onToggle={onToggle} />
    </div>
  );
}

export function PivotPanel({ pivot, columns, baseColumns, relations, usedFields, loadRelated, onRelated, onChange, onClose }: {
  pivot: PivotConfig;
  /** Bilinen bütün kolonlar (tablonun kolonları ve tanınan ilişkili kolonlar): etiket ve tip için. */
  columns: ListColumn[];
  /** Tablonun kendi kolonları: seçicinin üst listesi. */
  baseColumns: ListColumn[];
  relations: RelationHeading[];
  /** İlişkili alan sınırına sayılan alanlar (pivotun alanları ve filtreler). */
  usedFields: string[];
  loadRelated(path: string): Promise<RelatedCatalog>;
  /** Seçilen ilişkili alan tabloya kolon eklenmeden tanınır. */
  onRelated(columns: ListColumn[]): void;
  onChange(next: PivotConfig): void;
  onClose(): void;
}) {
  // Panel açıldığında bölümler kapalı gelir (grafik panelindeki gibi; başlıkta öğe sayısı görünür). Pivot henüz kurulmamışsa Satırlar, Sütunlar
  // ve Değerler açık gelir. Durum panelle yaşar: açılan bölüm panel kapanana kadar açık kalır, hiçbir yerde saklanmaz (K-183).
  const [open, setOpen] = useState<Record<SectionKey, boolean>>(() => {
    const fresh = pivot.rows.length === 0 && pivot.values.length === 0;
    return { rows: fresh, columns: fresh, values: fresh, place: false, totals: false, sort: false };
  });
  const [adding, setAdding] = useState<"rows" | "columns" | "values" | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [drag, setDrag] = useState<{ list: "rows" | "columns" | "values"; key: string } | null>(null);
  const [ruleEdit, setRuleEdit] = useState<{ value: string; rule: FormatRule; isNew: boolean } | null>(null);
  const byField = new Map(columns.map((c) => [c.field, c]));
  const section = (key: SectionKey) => ({ id: `pivot-${key}`, open: open[key], onToggle: () => setOpen((o) => ({ ...o, [key]: !o[key] })) });
  const axisUsed = new Set([...pivot.rows, ...pivot.columns].map((a) => a.field));
  const distinctCount = pivot.values.filter((v) => v.fn === "distinct").length;

  const pickAxis = (list: "rows" | "columns", col: ListColumn) => {
    if (col.related) onRelated([col]);
    const axis: PivotAxis = { field: col.field, bucket: isDate(col) ? "month" : null };
    onChange({ ...pivot, [list]: [...pivot[list], axis] });
    setAdding(null);
  };
  const pickValue = (col: ListColumn) => {
    if (col.related) onRelated([col]);
    const fn = defaultFn(col) === "distinct" && distinctCount >= PIVOT_MAX_DISTINCT ? "count" : defaultFn(col);
    // varsayılan hesaplama ağırlıklı ortalamaysa ağırlık alanı da liste tanımından (K-183)
    const value: PivotValue = { id: nextValueId(pivot.values), field: fn === "count" ? null : col.field, fn, weight: fn === "wavg" ? col.aggregate_weight ?? null : null,
                                decimals: null };
    onChange({ ...pivot, values: [...pivot.values, value] });
    setAdding(null);
  };
  const operands = pivot.values.filter((v) => isOperand(v, byField));
  const addCalc = () => {
    const id = nextValueId(pivot.values);
    const value: PivotValue = { id, kind: "calc", field: null, fn: "sum", weight: null, decimals: null, name: null,
                                a: operands[0].id, op: "div", b: (operands[1] ?? operands[0]).id, percent: false };
    onChange({ ...pivot, values: [...pivot.values, value] });
    setAdding(null);
    setExpanded(id);
  };
  // Kuralın penceresi tablodaki koşullu biçimlendirmeninkidir: değer, sayı tipinde tek "alan" olarak verilir
  const ruleColumn = (v: PivotValue): ListColumn => {
    const col = byField.get(v.field ?? "");
    const numeric = !isCalc(v) && v.fn !== "count" && v.fn !== "distinct" && isNumeric(col);
    return { ...(col ?? columns[0]), field: v.id, label: valueName(v, byField), type: "number", options: null,
             percent: isCalc(v) ? Boolean(v.percent) : numeric && Boolean(col?.percent),
             decimals: v.decimals ?? (isCalc(v) ? 2 : numeric ? col?.decimals ?? 0 : 0) } as ListColumn;
  };
  const setRules = (id: string, rules: PivotRule[]) => setValue(id, { rules });
  const setAxis = (list: "rows" | "columns", field: string, patch: Partial<PivotAxis>) =>
    onChange({ ...pivot, [list]: pivot[list].map((a) => (a.field === field ? { ...a, ...patch } : a)) });
  const setValue = (id: string, patch: Partial<PivotValue>) =>
    onChange(dropOrphans({ ...pivot, values: pivot.values.map((v) => (v.id === id ? { ...v, ...patch } : v)) }, byField));
  const removeValue = (id: string) =>
    onChange(dropOrphans({ ...pivot, values: pivot.values.filter((v) => v.id !== id), sort: pivot.sort.by === id ? { by: "name", dir: "asc" } : pivot.sort }, byField));
  const drop = (e: DragEvent, list: "rows" | "columns" | "values", target: string) => {
    e.preventDefault();
    if (!drag || drag.list !== list || drag.key === target) return;
    const keyOf = (x: PivotAxis | PivotValue) => ("id" in x ? x.id : x.field);
    const items = [...pivot[list]] as (PivotAxis | PivotValue)[];
    const moved = items.find((x) => keyOf(x) === drag.key)!;
    const rest = items.filter((x) => keyOf(x) !== drag.key);
    rest.splice(rest.findIndex((x) => keyOf(x) === target), 0, moved);
    onChange({ ...pivot, [list]: rest });
    setDrag(null);
  };
  const dragProps = (list: "rows" | "columns" | "values", key: string) => ({
    className: drag?.key === key && drag.list === list ? "is-dragging" : undefined, draggable: true,
    onDragStart: () => setDrag({ list, key }), onDragEnd: () => setDrag(null),
    onDragOver: (e: DragEvent) => { if (drag && drag.list === list && drag.key !== key) e.preventDefault(); },
    onDrop: (e: DragEvent) => drop(e, list, key),
  });

  // Değerin koşullu biçimi: kural satırları (renk örneği, koşul, ✕), "+ Kural ekle", "Toplamlara da uygula"
  const rulesOf = (v: PivotValue) => {
    const rules = v.rules ?? [];
    const col = ruleColumn(v);
    const one = new Map([[col.field, col]]);
    const name = valueName(v, byField);
    return (
      <div className="sc-field sc-pivot-rules" role="group" aria-label={`${T.rules}: ${name}`}>
        <span className="sc-field-label">{T.rules}</span>
        {rules.length > 0 && (
          <ul className="sc-pivot-rule-list">
            {rules.map((r) => {
              const text = describeCondition({ field: col.field, condition: r.condition }, one);
              return (
                <li key={r.id}>
                  <span className="sc-pivot-rule-swatch sc-num" style={formatStyle(r.format)} aria-hidden="true">12</span>
                  <button type="button" className="sc-pivot-rule-text" aria-label={T.editRule(text)} title={T.editRule(text)}
                          onClick={() => setRuleEdit({ value: v.id, rule: { ...r, field: col.field }, isNew: false })}>{text}</button>
                  <button type="button" className="sc-tool-btn" aria-label={T.removeRule(text)} title={T.removeRule(text)}
                          onClick={() => setRules(v.id, rules.filter((x) => x.id !== r.id))}><X aria-hidden="true" /></button>
                </li>
              );
            })}
          </ul>
        )}
        <button type="button" className="sc-chart-add" disabled={rules.length >= PIVOT_MAX_RULES}
                onClick={() => setRuleEdit({ value: v.id, isNew: true,
                                             rule: { id: newRuleId(rules.map((r) => ({ ...r, field: col.field }))), field: col.field, enabled: true, condition: { op: "gt" }, format: {} } })}>
          <Plus aria-hidden="true" />{T.addRule}
        </button>
        {rules.length > 0 && <Toggle label={T.rulesOnTotals} checked={Boolean(v.rules_on_totals)} onToggle={(on) => setValue(v.id, { rules_on_totals: on })} />}
      </div>
    );
  };

  const picker = (list: "rows" | "columns" | "values") => adding === list && (
    <FieldPanel columns={baseColumns} visibility={{}} onToggle={() => undefined} onReset={() => undefined} relations={relations} order={usedFields}
                loadRelated={loadRelated} label={list === "values" ? T.addValue : T.addField}
                allowed={(c) => (list === "values" ? isPivotField(c) : isAxisField(c) && !axisUsed.has(c.field))}
                pick={(c) => (list === "values" ? pickValue(c) : pickAxis(list, c))} />
  );
  const axes = (list: "rows" | "columns") => (
    <>
      <ul className="sc-chart-series">
        {pivot[list].map((a) => {
          const col = byField.get(a.field);
          const name = col?.label ?? a.field;
          return (
            <li key={a.field} {...dragProps(list, a.field)}>
              <div className="sc-chart-series-head">
                <GripVertical className="sc-seq-grip" aria-hidden="true" />
                <span className="sc-chart-series-name sc-pivot-chip" title={col?.note ?? name}><span>{name}</span></span>
                {isDate(col) && (
                  <select className="sc-input sc-select sc-pivot-bucket" aria-label={T.bucketOf(name)} value={a.bucket ?? "month"}
                          onChange={(e) => setAxis(list, a.field, { bucket: e.target.value as ChartBucket })}>
                    {BUCKETS.map((b) => <option key={b} value={b}>{tr.chart.buckets[b]}</option>)}
                  </select>
                )}
                <button type="button" className="sc-tool-btn" aria-label={T.remove(name)} title={T.remove(name)}
                        onClick={() => onChange({ ...pivot, [list]: pivot[list].filter((x) => x.field !== a.field) })}><X aria-hidden="true" /></button>
              </div>
            </li>
          );
        })}
      </ul>
      <button type="button" className="sc-chart-add" disabled={pivot[list].length >= PIVOT_MAX_AXIS} aria-expanded={adding === list}
              onClick={() => setAdding(adding === list ? null : list)}><Plus aria-hidden="true" />{T.addField}</button>
      {picker(list)}
    </>
  );

  return (
    <aside className="sc-chart-panel sc-pivot-panel" aria-label={T.settings}>
      <div className="sc-pivot-panel-head">
        <span>{T.settings}</span>
        <button type="button" className="sc-tool-btn" aria-label={T.closePanel} title={T.closePanel} onClick={onClose}><X aria-hidden="true" /></button>
      </div>
      <Section title={T.rows} count={pivot.rows.length} {...section("rows")}>{axes("rows")}</Section>
      <Section title={T.columns} count={pivot.columns.length} {...section("columns")}>{axes("columns")}</Section>
      <Section title={T.values} count={pivot.values.length} {...section("values")}>
        <ul className="sc-chart-series">
          {pivot.values.map((v) => {
            const col = byField.get(v.field ?? "");
            const name = valueName(v, byField);
            const shown = valueDisplay(v, byField);
            const isOpen = expanded === v.id;
            const fns = v.fn === "count" && !v.field ? (["count"] as PivotFn[]) : fnsFor(col);
            return (
              <li key={v.id} {...dragProps("values", v.id)}>
                <div className="sc-chart-series-head">
                  <GripVertical className="sc-seq-grip" aria-hidden="true" />
                  <button type="button" className="sc-chart-series-name sc-pivot-value-chip" aria-expanded={isOpen} aria-label={name} title={shown.full}
                          onClick={() => setExpanded(isOpen ? null : v.id)}>
                    <span>{shown.top}</span>
                    {shown.bottom !== null && <span className="sc-pivot-calc">{shown.bottom}</span>}
                  </button>
                  <button type="button" className="sc-tool-btn" aria-label={T.remove(name)} title={T.remove(name)} onClick={() => removeValue(v.id)}><X aria-hidden="true" /></button>
                </div>
                {isOpen && isCalc(v) && (
                  <div className="sc-chart-series-body">
                    <TextField label={T.valueName} value={v.name ?? ""} maxLength={60} placeholder={T.calcName}
                               onChange={(text) => setValue(v.id, { name: text ? text : null })} />
                    <SelectField label={T.operandA} value={v.a ?? ""} options={operands.map((o) => ({ value: o.id, label: valueName(o, byField) }))}
                                 onChange={(a) => setValue(v.id, { a })} />
                    <Segment<PivotOp> label={T.operation} value={v.op ?? "div"} onChange={(op) => setValue(v.id, { op })}
                                      options={PIVOT_OPS.map((op) => ({ value: op, label: T.ops[op] }))} />
                    <SelectField label={T.operandB} value={v.b ?? ""} options={operands.map((o) => ({ value: o.id, label: valueName(o, byField) }))}
                                 onChange={(b) => setValue(v.id, { b })} />
                    <Segment<"number" | "percent"> label={T.display} value={v.percent ? "percent" : "number"} onChange={(d) => setValue(v.id, { percent: d === "percent" })}
                                                    options={[{ value: "number", label: T.asNumber }, { value: "percent", label: T.asPercent }]} />
                    <NumberField label={T.decimals} value={v.decimals ?? null} onChange={(n) => setValue(v.id, { decimals: n === null ? null : Math.max(0, Math.min(6, Math.round(n))) })} />
                    {rulesOf(v)}
                  </div>
                )}
                {isOpen && !isCalc(v) && (
                  <div className="sc-chart-series-body">
                    <TextField label={T.valueName} value={v.name ?? ""} maxLength={60} placeholder={valueLabel(v, byField)}
                               onChange={(text) => setValue(v.id, { name: text ? text : null })} />
                    <SelectField label={T.calculation} value={v.fn}
                                 options={fns.map((fn) => ({ value: fn, label: fnLabel(fn, col), disabled: fn === "distinct" && v.fn !== "distinct" && distinctCount >= PIVOT_MAX_DISTINCT }))}
                                 onChange={(fn) => setValue(v.id, { fn: fn as PivotFn, weight: fn === "wavg" ? v.weight : null })} />
                    {v.fn === "wavg" && (
                      <SelectField label={T.weight} value={v.weight ?? ""}
                                   options={[{ value: "", label: "" }, ...columns.filter((c) => isNumeric(c) && isPivotField(c) && c.field !== v.field).map((c) => ({ value: c.field, label: c.label }))]}
                                   onChange={(weight) => setValue(v.id, { weight: weight || null })} />
                    )}
                    {v.fn !== "count" && v.fn !== "distinct" && (
                      <NumberField label={T.decimals} value={v.decimals ?? null} onChange={(n) => setValue(v.id, { decimals: n === null ? null : Math.max(0, Math.min(6, Math.round(n))) })} />
                    )}
                    {canRule(v, byField) && rulesOf(v)}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
        <button type="button" className="sc-chart-add" disabled={pivot.values.length >= PIVOT_MAX_VALUES} aria-expanded={adding === "values"}
                onClick={() => setAdding(adding === "values" ? null : "values")}><Plus aria-hidden="true" />{T.addValue}</button>
        {adding === "values" && (
          <button type="button" className="sc-table-pick" disabled={pivot.values.some((v) => v.fn === "count")}
                  onClick={() => { onChange({ ...pivot, values: [...pivot.values, { id: nextValueId(pivot.values), field: null, fn: "count", weight: null, decimals: null }] }); setAdding(null); }}>
            {T.fn.count}
          </button>
        )}
        {picker("values")}
        <button type="button" className="sc-chart-add" disabled={pivot.values.length >= PIVOT_MAX_VALUES || operands.length === 0} onClick={addCalc}>
          <Plus aria-hidden="true" />{T.addCalc}
        </button>
      </Section>
      <Section title={T.valuesOn} {...section("place")}>
        <Segment label={T.valuesOn} hideLabel value={pivot.values_on} onChange={(values_on) => onChange({ ...pivot, values_on })}
                 options={[{ value: "columns", label: T.onColumns }, { value: "rows", label: T.onRows }]} />
      </Section>
      <Section title={T.totals} {...section("totals")}>
        <Toggle label={T.rowTotal} checked={pivot.totals.rows} onToggle={(rows) => onChange({ ...pivot, totals: { ...pivot.totals, rows } })} />
        <Toggle label={T.columnTotal} checked={pivot.totals.columns} onToggle={(cols) => onChange({ ...pivot, totals: { ...pivot.totals, columns: cols } })} />
        <Toggle label={T.subtotals} checked={pivot.totals.subtotals} onToggle={(subtotals) => onChange({ ...pivot, totals: { ...pivot.totals, subtotals } })} />
      </Section>
      <Section title={T.sort} {...section("sort")}>
        <SelectField label={T.sortBy} value={pivot.sort.by}
                     options={[{ value: "name", label: T.sortName }, ...pivot.values.map((v) => ({ value: v.id, label: valueName(v, byField) }))]}
                     onChange={(by) => onChange({ ...pivot, sort: { by, dir: by === "name" ? "asc" : "desc" } })} />
        <Segment label={T.sortDir} hideLabel value={pivot.sort.dir} onChange={(dir) => onChange({ ...pivot, sort: { ...pivot.sort, dir } })}
                 options={[{ value: "asc", label: T.asc }, { value: "desc", label: T.desc }]} />
      </Section>
      {ruleEdit && (() => {
        const v = pivot.values.find((x) => x.id === ruleEdit.value);
        if (!v) return null;
        return (
          <RuleDialog plain rule={ruleEdit.rule} isNew={ruleEdit.isNew} columns={[ruleColumn(v)]} onClose={() => setRuleEdit(null)}
                      onSave={(r) => {
                        const rule: PivotRule = { id: r.id, enabled: true, condition: r.condition, format: r.format };
                        const rules = v.rules ?? [];
                        setRules(v.id, ruleEdit.isNew ? [...rules, rule] : rules.map((x) => (x.id === rule.id ? rule : x)));
                        setRuleEdit(null);
                      }} />
        );
      })()}
    </aside>
  );
}

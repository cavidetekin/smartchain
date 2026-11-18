// Pivot ayar paneli (K-183, docs/12 "Pivot standardı"): Satırlar · Sütunlar · Değerler · Değerlerin yeri · Toplamlar · Sıralama.
// Grafik panelinin deseni ve sınıfları; alanlar tutamakla sürüklenir. Alan seçici Alanlar panelinin seçici kipidir (ilişkili alanlar dahil).
import { ChevronDown, ChevronRight, GripVertical, Plus, X } from "lucide-react";
import { type DragEvent, type ReactNode, useState } from "react";

import { tr } from "../i18n/tr";
import { BUCKETS, type ChartBucket } from "../ui/chart/chartModel";
import { NumberField, Segment, SelectField } from "../ui";
import { SwitchCell } from "./CellEditors";
import { FieldPanel } from "./FieldPanel";
import {
  defaultFn, fnLabel, fnsFor, isAxisField, isDate, isNumeric, nextValueId, type PivotAxis, type PivotConfig, type PivotFn, PIVOT_MAX_AXIS,
  PIVOT_MAX_DISTINCT, PIVOT_MAX_VALUES, type PivotValue, valueLabel, valueParts,
} from "./pivotModel";
import type { ListColumn, RelatedCatalog, RelationHeading } from "./types";

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
  const [open, setOpen] = useState<Record<SectionKey, boolean>>({ rows: true, columns: true, values: true, place: true, totals: true, sort: false });
  const [adding, setAdding] = useState<"rows" | "columns" | "values" | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [drag, setDrag] = useState<{ list: "rows" | "columns" | "values"; key: string } | null>(null);
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
    const value: PivotValue = { id: nextValueId(pivot.values), field: fn === "count" ? null : col.field, fn, weight: null, decimals: null };
    onChange({ ...pivot, values: [...pivot.values, value] });
    setAdding(null);
  };
  const setAxis = (list: "rows" | "columns", field: string, patch: Partial<PivotAxis>) =>
    onChange({ ...pivot, [list]: pivot[list].map((a) => (a.field === field ? { ...a, ...patch } : a)) });
  const setValue = (id: string, patch: Partial<PivotValue>) =>
    onChange({ ...pivot, values: pivot.values.map((v) => (v.id === id ? { ...v, ...patch } : v)) });
  const removeValue = (id: string) =>
    onChange({ ...pivot, values: pivot.values.filter((v) => v.id !== id), sort: pivot.sort.by === id ? { by: "name", dir: "asc" } : pivot.sort });
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

  const picker = (list: "rows" | "columns" | "values") => adding === list && (
    <FieldPanel columns={baseColumns} visibility={{}} onToggle={() => undefined} onReset={() => undefined} relations={relations} order={usedFields}
                loadRelated={loadRelated} label={list === "values" ? T.addValue : T.addField}
                allowed={(c) => (list === "values" ? true : isAxisField(c) && !axisUsed.has(c.field))}
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
            const name = valueLabel(v, byField);
            const parts = valueParts(v, byField);
            const isOpen = expanded === v.id;
            const fns = v.fn === "count" && !v.field ? (["count"] as PivotFn[]) : fnsFor(col);
            return (
              <li key={v.id} {...dragProps("values", v.id)}>
                <div className="sc-chart-series-head">
                  <GripVertical className="sc-seq-grip" aria-hidden="true" />
                  <button type="button" className="sc-chart-series-name sc-pivot-value-chip" aria-expanded={isOpen} aria-label={name} title={name}
                          onClick={() => setExpanded(isOpen ? null : v.id)}>
                    {parts.field !== null && <span>{parts.field}</span>}
                    <span className={parts.field !== null ? "sc-pivot-calc" : undefined}>{parts.calc}</span>
                  </button>
                  <button type="button" className="sc-tool-btn" aria-label={T.remove(name)} title={T.remove(name)} onClick={() => removeValue(v.id)}><X aria-hidden="true" /></button>
                </div>
                {isOpen && (
                  <div className="sc-chart-series-body">
                    <SelectField label={T.calculation} value={v.fn}
                                 options={fns.map((fn) => ({ value: fn, label: fnLabel(fn, col), disabled: fn === "distinct" && v.fn !== "distinct" && distinctCount >= PIVOT_MAX_DISTINCT }))}
                                 onChange={(fn) => setValue(v.id, { fn: fn as PivotFn, weight: fn === "wavg" ? v.weight : null })} />
                    {v.fn === "wavg" && (
                      <SelectField label={T.weight} value={v.weight ?? ""}
                                   options={[{ value: "", label: "" }, ...columns.filter((c) => isNumeric(c) && c.field !== v.field).map((c) => ({ value: c.field, label: c.label }))]}
                                   onChange={(weight) => setValue(v.id, { weight: weight || null })} />
                    )}
                    {v.fn !== "count" && v.fn !== "distinct" && (
                      <NumberField label={T.decimals} value={v.decimals ?? null} onChange={(n) => setValue(v.id, { decimals: n === null ? null : Math.max(0, Math.min(6, Math.round(n))) })} />
                    )}
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
                     options={[{ value: "name", label: T.sortName }, ...pivot.values.map((v) => ({ value: v.id, label: valueLabel(v, byField) }))]}
                     onChange={(by) => onChange({ ...pivot, sort: { by, dir: by === "name" ? "asc" : "desc" } })} />
        <Segment label={T.sortDir} hideLabel value={pivot.sort.dir} onChange={(dir) => onChange({ ...pivot, sort: { ...pivot.sort, dir } })}
                 options={[{ value: "asc", label: T.asc }, { value: "desc", label: T.desc }]} />
      </Section>
    </aside>
  );
}

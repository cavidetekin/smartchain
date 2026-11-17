// Grafiğin ayar paneli (K-178, docs/12 "Grafik standardı"): Veri · Seriler · Çubuklar · Eksenler · Referans çizgileri · Görünüm. Panel açıldığında
// bütün bölümler kapalıdır. Her değişiklik anında grafiğe yansır; panelde Kaydet yoktur (kalıcılık görünümün Kaydet'iyle). Alan listeleri tablonun
// bütün alanlarıdır (gizli alanlar dahil). Renkler koşullu biçimlendirmedeki renk seçiciyle seçilir (ui/ColorPicker).
import { ChevronDown, ChevronRight, GripVertical, Plus, Trash2 } from "lucide-react";
import { type DragEvent, type ReactNode, useId, useState } from "react";

import { tr } from "../../i18n/tr";
import { SwitchCell } from "../../table/CellEditors";
import type { ListColumn } from "../../table/types";
import { ColorPicker } from "../ColorPicker";
import { NumberField, Segment, SelectField, TextField } from "../fields";
import {
  type AxisSide, type BarMode, type BarWidth, BUCKETS, CATEGORY_LIMITS, type ChartBucket, type ChartConfig, type ChartFn, type ChartSeries, FNS, isDateField,
  type LegendPosition, MAX_REF_LINES, MAX_SERIES, newSeries, nextId, numericFields, type RefKind, type RefLine, SERIES_TYPES, type SeriesType,
  splitFields, type TitleAlign, type TitleSize, type ValueAxis, withSeriesFn, withXField, xFields,
} from "./chartModel";
import { PALETTE, seriesLabel, THRESHOLD_COLOR } from "./chartOption";

const T = tr.chart;
type SectionKey = "data" | "series" | "bars" | "axes" | "refs" | "look";
const CLOSED: Record<SectionKey, boolean> = { data: false, series: false, bars: false, axes: false, refs: false, look: false };

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

function SeriesEditor({ s, auto, columns, onChange }: { s: ChartSeries; auto: string; columns: ListColumn[]; onChange(next: ChartSeries): void }) {
  const numeric = numericFields(columns);
  return (
    <div className="sc-chart-series-body">
      <SelectField label={T.aggregate} value={s.fn} onChange={(fn) => onChange(withSeriesFn(s, fn as ChartFn, columns))}
                   options={FNS.filter((fn) => fn === "count" || numeric.length > 0).map((fn) => ({ value: fn, label: T.fn[fn] }))} />
      {s.fn !== "count" && (
        <SelectField label={T.field} value={s.field ?? ""} onChange={(field) => onChange({ ...s, field })}
                     options={numeric.map((c) => ({ value: c.field, label: c.label }))} />
      )}
      <SelectField label={T.type} value={s.type} onChange={(type) => onChange({ ...s, type: type as SeriesType })}
                   options={SERIES_TYPES.map((t) => ({ value: t, label: T.types[t] }))} />
      <Segment<AxisSide> label={T.axis} value={s.axis} onChange={(axis) => onChange({ ...s, axis })}
                         options={[{ value: "primary", label: T.primary }, { value: "secondary", label: T.secondary }]} />
      <ColorPicker label={T.color} value={s.color ?? undefined} emptyLabel={T.colorAuto} emptyColor={auto} onChange={(color) => onChange({ ...s, color: color ?? null })} />
      <Toggle label={T.dataLabels} checked={s.labels.show} onToggle={(show) => onChange({ ...s, labels: { ...s.labels, show } })} />
      {s.labels.show && (
        <>
          <SelectField label={T.decimals} value={String(s.labels.decimals)} onChange={(v) => onChange({ ...s, labels: { ...s.labels, decimals: Number(v) } })}
                       options={[0, 1, 2, 3, 4].map((n) => ({ value: String(n), label: String(n) }))} />
          <Toggle label={T.showZero} checked={s.labels.zero} onToggle={(zero) => onChange({ ...s, labels: { ...s.labels, zero } })} />
        </>
      )}
      <NumberField label={T.thresholdValue} value={s.threshold?.value ?? null} decimals={2}
                   onChange={(value) => onChange({ ...s, threshold: value === null ? null : { value, color: s.threshold?.color ?? THRESHOLD_COLOR, line: s.threshold?.line ?? false } })} />
      {s.threshold && (
        <>
          <ColorPicker label={T.thresholdColor} value={s.threshold.color} emptyLabel={T.colorAuto} emptyColor={THRESHOLD_COLOR}
                       onChange={(color) => onChange({ ...s, threshold: { ...s.threshold!, color: color ?? THRESHOLD_COLOR } })} />
          <Toggle label={T.thresholdLine} checked={s.threshold.line} onToggle={(line) => onChange({ ...s, threshold: { ...s.threshold!, line } })} />
        </>
      )}
    </div>
  );
}

function AxisEditor({ title, axis, onChange }: { title: string; axis: ValueAxis; onChange(next: ValueAxis): void }) {
  return (
    <fieldset className="sc-chart-fieldset">
      <legend>{title}</legend>
      <TextField label={T.axisTitle} value={axis.title} maxLength={60} onChange={(v) => onChange({ ...axis, title: v })} />
      <div className="sc-chart-pair">
        <NumberField label={T.axisMin} value={axis.min} decimals={2} onChange={(min) => onChange({ ...axis, min })} />
        <NumberField label={T.axisMax} value={axis.max} decimals={2} onChange={(max) => onChange({ ...axis, max })} />
      </div>
      <TextField label={T.axisUnit} value={axis.unit} maxLength={20} onChange={(v) => onChange({ ...axis, unit: v })} />
      <Toggle label={T.gridLines} checked={axis.grid} onToggle={(grid) => onChange({ ...axis, grid })} />
    </fieldset>
  );
}

export function ChartPanel({ chart, columns, onChange }: { chart: ChartConfig; columns: ListColumn[]; onChange(next: ChartConfig): void }) {
  const base = useId();
  const [open, setOpen] = useState<Record<SectionKey, boolean>>(CLOSED);  // panel açıldığında bütün bölümler kapalı
  const [expanded, setExpanded] = useState<string | null>(null);
  const [drag, setDrag] = useState<string | null>(null);
  const byField = new Map(columns.map((c) => [c.field, c]));
  const xCol = byField.get(chart.x.field);
  const hasBars = chart.series.some((s) => s.type === "bar");
  const hasSecondary = chart.series.some((s) => s.axis === "secondary");
  const section = (key: SectionKey) => ({ id: `${base}-${key}`, open: open[key], onToggle: () => setOpen((o) => ({ ...o, [key]: !o[key] })) });
  const setSeries = (series: ChartSeries[]) => onChange({
    ...chart, series, ref_lines: chart.ref_lines.filter((r) => r.kind === "value" || series.some((s) => s.id === r.series)) });
  const addSeries = () => {
    const id = nextId("s", chart.series.map((s) => s.id));
    const used = new Set(chart.series.map((s) => s.field));
    const field = numericFields(columns).find((c) => !used.has(c.field)) ?? numericFields(columns)[0];
    setSeries([...chart.series, field ? newSeries(id, field.field, "sum", "line") : newSeries(id, null, "count", "line")]);
    setExpanded(id);
  };
  const drop = (e: DragEvent, target: string) => {
    e.preventDefault();
    if (!drag || drag === target) return;
    const rest = chart.series.filter((s) => s.id !== drag);
    const moved = chart.series.find((s) => s.id === drag)!;
    rest.splice(rest.findIndex((s) => s.id === target), 0, moved);
    setSeries(rest);
    setDrag(null);
  };
  const setRef = (id: string, patch: Partial<RefLine>) => onChange({ ...chart, ref_lines: chart.ref_lines.map((r) => (r.id === id ? { ...r, ...patch } : r)) });
  const addRef = () => onChange({ ...chart, ref_lines: [...chart.ref_lines, {
    id: nextId("r", chart.ref_lines.map((r) => r.id)), kind: "avg", value: null, series: chart.series[0].id, name: "", color: null, show_name: true, show_value: true }] });

  return (
    <aside className="sc-chart-panel" aria-label={T.settings}>
      <Section title={T.sections.data} {...section("data")}>
        <SelectField label={T.xField} value={chart.x.field} options={xFields(columns).map((c) => ({ value: c.field, label: c.label }))}
                     onChange={(f) => { const col = byField.get(f); if (col) onChange(withXField(chart, col)); }} />
        {isDateField(xCol) ? (
          <SelectField label={T.bucket} value={chart.x.bucket ?? "month"} options={BUCKETS.map((b) => ({ value: b, label: T.buckets[b] }))}
                       onChange={(b) => onChange({ ...chart, x: { ...chart.x, bucket: b as ChartBucket } })} />
        ) : (
          <>
            <Segment<"value" | "name"> label={T.order} value={chart.order} onChange={(order) => onChange({ ...chart, order })}
                                      options={[{ value: "value", label: T.orderValue }, { value: "name", label: T.orderName }]} />
            <SelectField label={T.limit} help={T.limitTip} value={String(chart.limit)} onChange={(v) => onChange({ ...chart, limit: Number(v) })}
                         options={[...new Set([...CATEGORY_LIMITS, chart.limit])].sort((a, b) => a - b).map((n) => ({ value: String(n), label: String(n) }))} />
          </>
        )}
        <SelectField label={T.split} value={chart.split ?? ""} onChange={(f) => onChange({ ...chart, split: f || null })}
                     options={[{ value: "", label: T.none }, ...splitFields(columns, chart.x.field).map((c) => ({ value: c.field, label: c.label }))]} />
      </Section>

      <Section title={T.sections.series} count={chart.series.length} {...section("series")}>
        <ul className="sc-chart-series">
          {chart.series.map((s, i) => {
            const name = seriesLabel(s, byField);
            const isOpen = expanded === s.id;
            return (
              <li key={s.id} className={drag === s.id ? "is-dragging" : undefined} draggable onDragStart={() => setDrag(s.id)} onDragEnd={() => setDrag(null)}
                  onDragOver={(e) => drag && drag !== s.id && e.preventDefault()} onDrop={(e) => drop(e, s.id)}>
                <div className="sc-chart-series-head">
                  <GripVertical className="sc-seq-grip" aria-hidden="true" />
                  <span className="sc-chart-dot" style={{ background: s.color ?? PALETTE[i % PALETTE.length] }} aria-hidden="true" />
                  <button type="button" className="sc-chart-series-name" aria-expanded={isOpen} onClick={() => setExpanded(isOpen ? null : s.id)}>
                    <span>{name}</span><span className="sc-chart-series-type">{T.types[s.type]}</span>
                  </button>
                  <button type="button" className="sc-tool-btn" aria-label={T.removeSeries(name)} title={T.removeSeries(name)} disabled={chart.series.length === 1}
                          onClick={() => setSeries(chart.series.filter((x) => x.id !== s.id))}><Trash2 aria-hidden="true" /></button>
                </div>
                {isOpen && <SeriesEditor s={s} auto={PALETTE[i % PALETTE.length]} columns={columns} onChange={(next) => setSeries(chart.series.map((x) => (x.id === s.id ? next : x)))} />}
              </li>
            );
          })}
        </ul>
        <button type="button" className="sc-chart-add" disabled={chart.series.length >= MAX_SERIES} title={chart.series.length >= MAX_SERIES ? T.maxSeries(MAX_SERIES) : undefined}
                onClick={addSeries}><Plus aria-hidden="true" /> {T.addSeries}</button>
      </Section>

      <Section title={T.sections.bars} {...section("bars")}>
        {!hasBars && <p className="sc-chart-note">{T.noBars}</p>}
        <Segment<BarMode> label={T.barMode} value={chart.bars.mode} onChange={(mode) => onChange({ ...chart, bars: { ...chart.bars, mode } })}
                          options={[{ value: "group", label: T.barModes.group }, { value: "stack", label: T.barModes.stack }, { value: "percent", label: T.barModes.percent }]} />
        <Segment<BarWidth> label={T.barWidth} value={chart.bars.width} onChange={(width) => onChange({ ...chart, bars: { ...chart.bars, width } })}
                           options={[{ value: "thin", label: T.barWidths.thin }, { value: "medium", label: T.barWidths.medium }, { value: "thick", label: T.barWidths.thick }]} />
        {chart.bars.mode === "stack" && <Toggle label={T.totals} checked={chart.bars.totals} onToggle={(totals) => onChange({ ...chart, bars: { ...chart.bars, totals } })} />}
        <Toggle label={T.horizontal} checked={chart.bars.horizontal} onToggle={(horizontal) => onChange({ ...chart, bars: { ...chart.bars, horizontal } })} />
      </Section>

      <Section title={T.sections.axes} {...section("axes")}>
        <TextField label={T.xTitle} value={chart.axes.x.title} maxLength={60} onChange={(title) => onChange({ ...chart, axes: { ...chart.axes, x: { title } } })} />
        <AxisEditor title={T.primaryAxis} axis={chart.axes.primary} onChange={(primary) => onChange({ ...chart, axes: { ...chart.axes, primary } })} />
        {hasSecondary && (
          <AxisEditor title={T.secondaryAxis} axis={chart.axes.secondary} onChange={(secondary) => onChange({ ...chart, axes: { ...chart.axes, secondary } })} />
        )}
      </Section>

      <Section title={T.sections.refs} count={chart.ref_lines.length} {...section("refs")}>
        {chart.ref_lines.map((r) => (
          <fieldset key={r.id} className="sc-chart-fieldset">
            <legend>{r.name || T.refKind[r.kind]}</legend>
            <SelectField label={T.refType} value={r.kind} options={(["value", "avg", "min", "max"] as RefKind[]).map((k) => ({ value: k, label: T.refKind[k] }))}
                         onChange={(k) => setRef(r.id, k === "value" ? { kind: "value", series: null, value: r.value ?? 0 } : { kind: k as RefKind, value: null, series: r.series ?? chart.series[0].id })} />
            {r.kind === "value" ? (
              <NumberField label={T.refValue} value={r.value} decimals={2} onChange={(value) => setRef(r.id, { value: value ?? 0 })} />
            ) : (
              <SelectField label={T.refSeries} value={r.series ?? ""} options={chart.series.map((s) => ({ value: s.id, label: seriesLabel(s, byField) }))}
                           onChange={(series) => setRef(r.id, { series })} />
            )}
            <TextField label={T.refName} value={r.name} maxLength={40} onChange={(name) => setRef(r.id, { name })} />
            <Toggle label={T.showName} checked={r.show_name} onToggle={(show_name) => setRef(r.id, { show_name })} />
            <Toggle label={T.showValue} checked={r.show_value} onToggle={(show_value) => setRef(r.id, { show_value })} />
            <ColorPicker label={T.color} value={r.color ?? undefined} emptyLabel={T.colorAuto} onChange={(color) => setRef(r.id, { color: color ?? null })} />
            <button type="button" className="sc-chart-add" onClick={() => onChange({ ...chart, ref_lines: chart.ref_lines.filter((x) => x.id !== r.id) })}>
              <Trash2 aria-hidden="true" /> {T.removeRef}
            </button>
          </fieldset>
        ))}
        <button type="button" className="sc-chart-add" disabled={chart.ref_lines.length >= MAX_REF_LINES} onClick={addRef}><Plus aria-hidden="true" /> {T.addRef}</button>
      </Section>

      <Section title={T.sections.look} {...section("look")}>
        <TextField label={T.title} value={chart.title} maxLength={80} onChange={(title) => onChange({ ...chart, title })} />
        <Segment<TitleAlign> label={T.titleAlign} value={chart.title_align} onChange={(title_align) => onChange({ ...chart, title_align })}
                             options={[{ value: "left", label: T.aligns.left }, { value: "center", label: T.aligns.center }, { value: "right", label: T.aligns.right }]} />
        <Segment<TitleSize> label={T.titleSize} value={chart.title_size} onChange={(title_size) => onChange({ ...chart, title_size })}
                            options={[{ value: "small", label: T.sizes.small }, { value: "medium", label: T.sizes.medium }, { value: "large", label: T.sizes.large }]} />
        <Toggle label={T.legend} checked={chart.legend.show} onToggle={(show) => onChange({ ...chart, legend: { ...chart.legend, show } })} />
        {chart.legend.show && (
          <Segment<LegendPosition> label={T.legendPosition} value={chart.legend.position} onChange={(position) => onChange({ ...chart, legend: { ...chart.legend, position } })}
                                   options={[{ value: "top", label: T.positions.top }, { value: "bottom", label: T.positions.bottom }, { value: "right", label: T.positions.right }]} />
        )}
      </Section>
    </aside>
  );
}

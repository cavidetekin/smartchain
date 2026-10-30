// Kural penceresi (U-24, K-95, K-96): alan, koşul (tipe göre; sayı ve tarihte "Değer / Alan", sayı alanı
// karşılaştırmasında "Boşları 0 say"), biçim (zemin, yazı rengi, kalın, ikon ve ikon rengi), önizleme. Yazı rengi
// seçilmezse zemine göre okunur renk kendiliğinden (uyarı yok). Değer girişleri filtre menüsündekilerle aynı ortak alanlar.
import { useMemo, useState } from "react";

import { formatDate, formatNumber, toIsoDate } from "../format";
import { tr } from "../i18n/tr";
import { Checkbox, DateField, Dialog, NumberField, RadioGroup, Segment, SelectField, TextareaField, TextField } from "../ui";
import { ColorPicker } from "../ui/ColorPicker";
import { valueLabel } from "./filters";
import { RuledValue, RuleIconView } from "./RuleIcon";
import { canUseFieldRef, formatStyle, iconColor, RULE_OPS, refCandidates, ruleKind } from "./rules";
import { type FormatRule, type ListColumn, RULE_ICONS, type RuleCondition, type RuleFormat, type RuleIcon, type RuleOp } from "./types";

const T = tr.table;

const parseIso = (s: string | undefined) => {
  if (!s) return null;
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
};

/** Koşul tamam mı (Kaydet için): değer girişleri dolu. */
export function conditionReady(col: ListColumn, c: RuleCondition): boolean {
  if (c.op === "empty" || c.op === "always") return true;
  if (c.field_ref !== undefined) return Boolean(c.field_ref);
  if (c.op === "between") return ruleKind(col) === "date" ? Boolean(c.from || c.to) : c.min !== undefined || c.max !== undefined;
  if (c.op === "relative") return typeof c.value === "string";
  if (c.op === "in") return Boolean(c.values?.length);
  if (ruleKind(col) === "text") return typeof c.value === "string" && Boolean(c.value.trim());
  return c.value !== undefined && c.value !== "";
}

export function RuleDialog({ rule, isNew, columns, onClose, onSave }: {
  /** Düzenlenen kural ya da yeni kural taslağı (alanı seçili). */
  rule: FormatRule;
  isNew: boolean;
  columns: ListColumn[];
  onClose(): void;
  onSave(rule: FormatRule): void;
}) {
  const byField = useMemo(() => new Map(columns.map((c) => [c.field, c])), [columns]);
  const [field, setField] = useState(rule.field);
  const col = byField.get(field) ?? columns[0];
  const kind = ruleKind(col);
  const [cond, setCond] = useState<RuleCondition>(rule.condition);
  const [format, setFormat] = useState<RuleFormat>(rule.format);
  const ops = RULE_OPS[kind];
  const op = ops.includes(cond.op) ? cond.op : ops[0];
  const byRef = cond.field_ref !== undefined && canUseFieldRef(col, op);
  const refs = refCandidates(col, columns);

  const changeField = (f: string) => {
    const next = byField.get(f)!;
    setField(f);
    if (ruleKind(next) !== kind) setCond({ op: RULE_OPS[ruleKind(next)][0] });
    else if (cond.field_ref === f) setCond({ op: cond.op, field_ref: "" });
  };
  const setOp = (o: RuleOp) => setCond(canUseFieldRef(col, o) && cond.field_ref !== undefined ? { op: o, field_ref: cond.field_ref }
    : { op: o, ...(o === "relative" ? { value: "this_week" } : {}) });

  const hasFormat = Boolean(format.fill || format.color || format.bold || format.icon);
  const condition: RuleCondition = { ...cond, op };
  const ready = conditionReady(col, condition) && hasFormat;

  const sample = kind === "number" ? formatNumber(1234, col.decimals ?? 0) : kind === "date" ? formatDate(new Date())
    : kind === "bool" ? T.yes : col.label;

  const valueInputs = () => {
    if (op === "empty" || op === "always") return null;  // "Her zaman": değer alanı yok
    if (byRef) {
      return (
        <>
          <SelectField label={T.ruleRefField} value={cond.field_ref ?? ""}
                       onChange={(v) => setCond({ ...cond, op, field_ref: v })}
                       options={[{ value: "", label: "—" }, ...refs.map((c) => ({ value: c.field, label: c.label }))]} />
          {kind === "number" && (  // sayıda boşlar 0 sayılır (varsayılan açık); tarihte boşsa tutmaz (K-95)
            <Checkbox label={T.ruleEmptyAsZero} checked={cond.empty_as_zero !== false}
                      onChange={(on) => setCond({ ...cond, op, empty_as_zero: on })} />
          )}
        </>
      );
    }
    if (kind === "number") {
      const decimals = col.decimals ?? 3;
      if (op === "between") {
        return (
          <div className="sc-table-pop-pair">
            <NumberField label={T.min} value={cond.min ?? null} decimals={decimals}
                         onChange={(v) => setCond({ ...cond, op, min: v ?? undefined })} />
            <NumberField label={T.max} value={cond.max ?? null} decimals={decimals}
                         onChange={(v) => setCond({ ...cond, op, max: v ?? undefined })} />
          </div>
        );
      }
      return <NumberField label={T.value} value={typeof cond.value === "number" ? cond.value : null} decimals={decimals}
                          onChange={(v) => setCond({ op, ...(v !== null ? { value: v } : {}) })} />;
    }
    if (kind === "date") {
      if (op === "relative") {
        return <RadioGroup label={T.dateRelative} value={String(cond.value ?? "this_week")} onChange={(v) => setCond({ op, value: v })}
                           options={Object.entries(T.relative).map(([v, label]) => ({ value: v, label }))} />;
      }
      if (op === "between") {
        return (
          <div className="sc-table-pop-pair">
            <DateField label={T.from} value={parseIso(cond.from)}
                       onChange={(d) => setCond({ ...cond, op, from: d ? toIsoDate(d) : undefined })} />
            <DateField label={T.to} value={parseIso(cond.to)}
                       onChange={(d) => setCond({ ...cond, op, to: d ? toIsoDate(d) : undefined })} />
          </div>
        );
      }
      return <DateField label={T.value} value={parseIso(typeof cond.value === "string" ? cond.value : undefined)}
                        onChange={(d) => setCond({ op, ...(d ? { value: toIsoDate(d) } : {}) })} />;
    }
    if (kind === "bool") {
      const values = cond.values ?? [];
      return (
        <div className="sc-rule-values" role="group" aria-label={T.ruleOps.in}>
          {[true, false].map((v) => (
            <Checkbox key={String(v)} label={valueLabel(v)} checked={values.includes(v)}
                      onChange={(on) => setCond({ op, values: on ? [...values, v] : values.filter((x) => x !== v) })} />
          ))}
        </div>
      );
    }
    if (op === "in") {
      return <TextareaField label={T.ruleValues} rows={3} value={(cond.values ?? []).join("\n")}
                            onChange={(t) => setCond({ op, values: t.split("\n").map((s) => s.trim()).filter(Boolean) })} />;
    }
    return <TextField label={T.value} value={typeof cond.value === "string" ? cond.value : ""} autoFocus
                      onChange={(v) => setCond({ op, value: v })} />;
  };

  const opLabel = (o: RuleOp) => (kind === "date" && T.ruleDateOps[o]) || T.ruleOps[o];
  const save = () => {
    if (!ready) return;
    const clean: RuleFormat = {
      ...(format.fill ? { fill: format.fill } : {}), ...(format.color ? { color: format.color } : {}),
      ...(format.bold ? { bold: true } : {}), ...(format.icon ? { icon: format.icon } : {}),
      ...(format.icon && format.icon_color ? { icon_color: format.icon_color } : {}),
    };
    onSave({ ...rule, field, condition, format: clean });
  };

  return (
    <Dialog wide title={isNew ? T.ruleTitleNew : T.ruleTitleEdit} onClose={onClose}
            onSubmit={save} submitLabel={T.ruleSave} submitDisabled={!ready}>
      <div className="sc-rule-grid">
        <SelectField label={T.ruleField} value={field} onChange={changeField}
                     options={columns.map((c) => ({ value: c.field, label: c.label }))} />
        <SelectField label={T.ruleCondition} value={op} onChange={(v) => setOp(v as RuleOp)}
                     options={ops.map((o) => ({ value: o, label: opLabel(o) }))} />
      </div>
      {canUseFieldRef(col, op) && (
        <Segment<"value" | "field"> label={T.ruleCompare} value={byRef ? "field" : "value"}
                                    onChange={(m) => setCond(m === "field" ? { op, field_ref: "" } : { op })}
                                    options={[{ value: "value", label: T.ruleCompareValue }, { value: "field", label: T.ruleCompareField }]} />
      )}
      {valueInputs()}

      <fieldset className="sc-rule-format">
        <legend className="sc-field-label">{T.ruleFormat}</legend>
        <div className="sc-rule-grid">
          <ColorPicker label={T.ruleFill} value={format.fill} onChange={(fill) => setFormat({ ...format, fill })} />
          <ColorPicker label={T.ruleColor} value={format.color} onChange={(color) => setFormat({ ...format, color })} />
        </div>
        <Checkbox label={T.ruleBold} checked={Boolean(format.bold)} onChange={(bold) => setFormat({ ...format, bold })} />
        <Segment<RuleIcon | "none"> label={T.ruleIcon} value={format.icon ?? "none"}
                                    onChange={(v) => setFormat({ ...format, icon: v === "none" ? undefined : v })}
                                    options={[{ value: "none", label: T.ruleNoIcon },
                                              ...RULE_ICONS.map((i) => ({ value: i, label: <><RuleIconView name={i} color={iconColor({ icon: i })} /><span className="sc-visually-hidden">{T.ruleIcons[i]}</span></> }))]} />
        {format.icon && (
          <ColorPicker label={T.ruleIconColor} value={format.icon_color} emptyLabel={T.ruleIconDefault}
                       emptyColor={iconColor({ icon: format.icon })} onChange={(icon_color) => setFormat({ ...format, icon_color })} />
        )}
      </fieldset>

      <div className="sc-field">
        <span className="sc-field-label">{T.rulePreview}</span>
        <div className={`sc-rule-preview${kind === "number" ? " is-num" : ""}`} data-testid="rule-preview" style={formatStyle(format)}>
          <RuledValue format={format} numeric={kind === "number"}>
            <span className={kind === "text" || kind === "bool" ? undefined : "sc-num"}>{sample}</span>
          </RuledValue>
        </div>
      </div>
      {!hasFormat && <p className="sc-muted">{T.ruleNeedsFormat}</p>}
    </Dialog>
  );
}

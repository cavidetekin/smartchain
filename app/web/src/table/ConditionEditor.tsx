// Koşul editörü (ortak bileşen; K-136, K-139, docs/12): validasyon kuralları ve veri kuralları (4.1, K-141) kullanır.
// "Koşullar" bölümü; her grup "Koşul Grubu n" kartı, gruplar arası belirgin "VEYA". Her koşul tek satır: alan, operatör,
// "Değer / Alan" anahtarı ve değer ya da öteki alan; ikinci satırdan itibaren solda "ve". Boş ve Boş değil'de değer yok.
import { Plus, X } from "lucide-react";
import { Fragment, useId } from "react";

import { tr } from "../i18n/tr";
import { Button, DateField, SelectField, TextField } from "../ui";

const T = tr.conditions;

/** Operatörler (K-139): karşılaştırmalar sembolle, ötekiler adıyla; veri kurallarıyla aynı liste (app/validation/conditions.py). */
export const OPERATORS = ["=", "≠", ">", "<", "≥", "≤", "İçerir", "İle başlar", "Listede", "Boş", "Boş değil"] as const;
export const NO_VALUE = ["Boş", "Boş değil"];
const TEXT_ONLY = ["İçerir", "İle başlar"];
const EQUALITY = ["=", "≠"];

export interface ConditionField {
  name: string;
  label: string;
  kind: "text" | "number" | "integer" | "date" | "bool";
  values: string[];
}

export interface ConditionRow {
  field: string;
  operator: string;
  value: string | null;
  compare_field: string | null;
}

const blank = (fields: ConditionField[]): ConditionRow => ({ field: fields[0]?.name ?? "", operator: "=", value: null, compare_field: null });

/** İzin verilen operatörler: metin dışında İçerir ve İle başlar yok. */
export function operatorsFor(kind: ConditionField["kind"]): string[] {
  return OPERATORS.filter((op) => kind === "text" || !TEXT_ONLY.includes(op));
}

/** Öteki alanla karşılaştırılabilir mi: yalnız karşılaştırma operatörleri. */
export function canCompare(operator: string): boolean {
  return !NO_VALUE.includes(operator) && operator !== "Listede" && !TEXT_ONLY.includes(operator);
}

/** Satır tamam mı: alan ve operatör; Boş ve Boş değil dışında değer ya da karşılaştırılan alan. */
export function rowComplete(row: ConditionRow): boolean {
  if (!row.field || !row.operator) return false;
  if (NO_VALUE.includes(row.operator)) return true;
  return Boolean(row.compare_field) || Boolean(row.value && row.value.trim());
}

export function groupsComplete(groups: ConditionRow[][]): boolean {
  return groups.length > 0 && groups.every((g) => g.length > 0 && g.every(rowComplete));
}

/** Alan tipine göre değer girişi; veri kuralının Sonuç bölümü de kullanır (K-141).
 *  Koşulda değer serbest yazıdır, değer listesi öneri olarak çıkar: staging ERP'nin dilindedir (K-143). strict: Sonuç bölümünde
 *  Smartchain değeri yazılır, değer listesinden seçilir. */
export function ValueInput({ field, row, onChange, disabled, label = T.value, strict = false }: {
  field: ConditionField | undefined; row: ConditionRow; onChange(v: string | null): void; disabled?: boolean; label?: string; strict?: boolean;
}) {
  const listId = useId();
  const value = row.value ?? "";
  if (field?.kind === "bool") {
    return <SelectField label={label} value={value} disabled={disabled} onChange={(v) => onChange(v || null)}
                        options={[{ value: "", label: "—" }, { value: "1", label: T.yes }, { value: "0", label: T.no }]} />;
  }
  if (field?.kind === "date" && row.operator !== "Listede") {
    const parsed = value ? new Date(`${value}T00:00:00`) : null;
    return <DateField label={label} value={parsed && !Number.isNaN(parsed.getTime()) ? parsed : null} disabled={disabled}
                      onChange={(d) => onChange(d ? `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}` : null)} />;
  }
  if (strict && field?.values.length && EQUALITY.includes(row.operator)) {
    return <SelectField label={label} value={value} disabled={disabled} onChange={(v) => onChange(v || null)}
                        options={[{ value: "", label: "—" }, ...field.values.map((v) => ({ value: v, label: v }))]} />;
  }
  const suggest = !strict && field?.kind === "text" && field.values.length > 0;
  return (
    <>
      <TextField label={label} value={value} disabled={disabled} placeholder={row.operator === "Listede" ? T.listHint : undefined} list={suggest ? listId : undefined}
                 inputMode={field?.kind === "number" || field?.kind === "integer" ? "decimal" : undefined} onChange={(v) => onChange(v || null)} />
      {suggest && <datalist id={listId}>{field.values.map((v) => <option key={v} value={v} />)}</datalist>}
    </>
  );
}

/** "Değer / Alan" anahtarı: değer kutusunun solunda, küçük. */
function SourceSwitch({ comparing, disabled, onChange }: { comparing: boolean; disabled?: boolean; onChange(field: boolean): void }) {
  return (
    <div className="sc-condition-source" role="radiogroup" aria-label={T.source}>
      {[false, true].map((isField) => (
        <button key={String(isField)} type="button" role="radio" aria-checked={comparing === isField} disabled={disabled}
                onClick={() => onChange(isField)}>{isField ? T.sourceField : T.sourceValue}</button>
      ))}
    </div>
  );
}

export function ConditionEditor({ fields, groups, onChange, disabled }: {
  fields: ConditionField[]; groups: ConditionRow[][]; onChange(next: ConditionRow[][]): void; disabled?: boolean;
}) {
  const byName = new Map(fields.map((f) => [f.name, f]));
  const setRow = (gi: number, ri: number, patch: Partial<ConditionRow>) =>
    onChange(groups.map((g, i) => (i !== gi ? g : g.map((r, j) => (j !== ri ? r : { ...r, ...patch })))));
  const removeRow = (gi: number, ri: number) =>
    onChange(groups.map((g, i) => (i !== gi ? g : g.filter((_, j) => j !== ri))).filter((g) => g.length));
  const addRow = (gi: number) => onChange(groups.map((g, i) => (i !== gi ? g : [...g, blank(fields)])));
  const addGroup = () => onChange([...groups, [blank(fields)]]);

  return (
    <section className="sc-condition-editor" aria-label={T.title}>
      <h3 className="sc-condition-title">{T.title}</h3>
      {groups.length === 0 && <p className="sc-muted">{T.empty}</p>}
      {groups.map((group, gi) => (
        <Fragment key={gi}>
          {gi > 0 && <div className="sc-condition-or" aria-hidden="true"><span>{T.or}</span></div>}
          <section className="sc-condition-group" aria-label={T.group(gi + 1)}>
            <h4 className="sc-condition-group-title">{T.group(gi + 1)}</h4>
            {group.map((row, ri) => {
              const field = byName.get(row.field);
              const comparing = row.compare_field !== null;
              const noValue = NO_VALUE.includes(row.operator);
              return (
                <div key={ri} className="sc-condition-row">
                  <span className="sc-condition-join">{ri > 0 ? T.and : ""}</span>
                  <SelectField label={T.field} value={row.field} disabled={disabled}
                               options={fields.map((f) => ({ value: f.name, label: f.label }))}
                               onChange={(v) => {
                                 const kind = byName.get(v)?.kind ?? "text";
                                 setRow(gi, ri, { field: v, value: null, compare_field: null, operator: operatorsFor(kind).includes(row.operator) ? row.operator : "=" });
                               }} />
                  <SelectField label={T.operator} value={row.operator} disabled={disabled}
                               options={operatorsFor(field?.kind ?? "text").map((o) => ({ value: o, label: o }))}
                               onChange={(v) => setRow(gi, ri, {
                                 operator: v,
                                 ...(NO_VALUE.includes(v) ? { value: null, compare_field: null } : !canCompare(v) ? { compare_field: null } : {}),
                               })} />
                  {noValue ? <span className="sc-condition-source-slot" /> : canCompare(row.operator) ? (
                    <SourceSwitch comparing={comparing} disabled={disabled}
                                  onChange={(isField) => setRow(gi, ri, isField ? { compare_field: "", value: null } : { compare_field: null })} />
                  ) : <span className="sc-condition-source-slot" />}
                  {noValue ? <span /> : comparing ? (
                    <SelectField label={T.compareField} value={row.compare_field ?? ""} disabled={disabled}
                                 options={[{ value: "", label: "—" }, ...fields.filter((f) => f.name !== row.field).map((f) => ({ value: f.name, label: f.label }))]}
                                 onChange={(v) => setRow(gi, ri, { compare_field: v || "" })} />
                  ) : <ValueInput field={field} row={row} disabled={disabled} onChange={(v) => setRow(gi, ri, { value: v })} />}
                  <Button variant="ghost" size="sm" aria-label={T.removeRow} disabled={disabled} onClick={() => removeRow(gi, ri)}><X aria-hidden /></Button>
                </div>
              );
            })}
            <div><Button variant="ghost" size="sm" disabled={disabled} onClick={() => addRow(gi)}><Plus aria-hidden />{T.addAnd}</Button></div>
          </section>
        </Fragment>
      ))}
      <div><Button variant="secondary" size="sm" disabled={disabled} onClick={addGroup}><Plus aria-hidden />{T.addOr}</Button></div>
    </section>
  );
}

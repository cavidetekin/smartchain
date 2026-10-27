// Filtre menüleri (U-8, docs/12): filtre tipi alanın tipinden gelir. Uygula ve Temizle; değerler sözleşme biçiminde.
// Her menüde "boş" seçilebilir (U-13). describeFilter aktif filtre etiketinin metnidir (U-12).
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { fold, formatDate, formatNumber, toIsoDate } from "../format";
import { tr } from "../i18n/tr";
import { Button, Checkbox, DateField, NumberField, RadioGroup, SearchField, Segment, SelectField, TextField } from "../ui";
import { listApi, type ListColumn, type ListFilter, type ListValue, type NumberOp, type ValueCount } from "./types";

const T = tr.table;

interface MenuProps {
  list: string;
  column: ListColumn;
  filter: ListFilter | undefined;
  /** Diğer alanların filtreleri: liste filtresinin değerleri bunlarla daraltılır. */
  others: ListFilter[];
  onApply(filter: ListFilter | null): void;
}

export function valueLabel(v: ListValue): string {
  return typeof v === "boolean" ? (v ? T.yes : T.no) : v;
}

function parseIso(s: string | undefined): Date | null {
  if (!s) return null;
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** Aktif filtre etiketinin metni (U-12): "içerir 'mil'", "10–100", "bu hafta", "Çubuk, Levha +2", "boş". */
export function describeFilter(f: ListFilter, column: ListColumn): string {
  const num = (n: number | undefined) => formatNumber(n ?? 0, column.decimals ?? (Number.isInteger(n) ? 0 : 2));
  const date = (s: string | undefined) => formatDate(parseIso(s)!);
  switch (f.op) {
    case "empty": return T.chipEmpty;
    case "contains": case "not_contains": case "equals": case "starts_with":
      return `${T.textOps[f.op].toLocaleLowerCase("tr")} '${f.value}'`;
    case "in": {
      const labels = (f.values ?? []).map(valueLabel).concat(f.empty ? [T.chipEmpty] : []);
      return labels.length > 2 ? `${labels.slice(0, 2).join(", ")} ${T.chipMore(labels.length - 2)}` : labels.join(", ");
    }
    case "eq": return `= ${num(f.value as number)}`;
    case "gt": return `> ${num(f.value as number)}`;
    case "lt": return `< ${num(f.value as number)}`;
    case "relative": return T.chipRelative[String(f.value)] ?? String(f.value);
    case "between":
      if (column.filter === "date") {
        if (f.from && f.to) return `${date(f.from)}–${date(f.to)}`;
        return f.from ? T.chipFrom(date(f.from)) : T.chipTo(date(f.to));
      }
      if (f.min !== undefined && f.max !== undefined) return `${num(f.min)}–${num(f.max)}`;
      return f.min !== undefined ? `≥ ${num(f.min)}` : `≤ ${num(f.max)}`;
    default: return "";
  }
}

/** Durum + anında okunan son değer: Enter alanı işler ve aynı tuşla form gönderilir; gönderim yeni değeri görmeli. */
function useLatest<V>(initial: V): [V, (v: V) => void, () => V] {
  const ref = useRef(initial);
  const [value, setValue] = useState(initial);
  return [value, (v: V) => { ref.current = v; setValue(v); }, () => ref.current];
}

function Actions({ canApply, onClear }: { canApply: boolean; onClear(): void }) {
  return (
    <div className="sc-table-pop-actions">
      <Button size="sm" variant="ghost" onClick={onClear}>{T.clear}</Button>
      <Button size="sm" variant="primary" type="submit" disabled={!canApply}>{T.apply}</Button>
    </div>
  );
}

export function FilterMenu(props: MenuProps) {
  const { column } = props;
  switch (column.filter) {
    case "text": return <TextFilter {...props} />;
    case "list": return <ListFilterMenu {...props} />;
    case "number": return <NumberFilter {...props} />;
    default: return <DateFilter {...props} />;
  }
}

function TextFilter({ column, filter, onApply }: MenuProps) {
  const [op, setOp] = useState<string>(filter?.op ?? "contains");
  const [value, setValue] = useState(typeof filter?.value === "string" ? filter.value : "");
  const empty = op === "empty";
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (empty) onApply({ field: column.field, op: "empty" });
    else if (value.trim()) onApply({ field: column.field, op: op as ListFilter["op"], value: value.trim() });
  };
  return (
    <form className="sc-table-pop-form" onSubmit={submit}>
      <SelectField label={T.operator} value={op} onChange={setOp}
                   options={[...Object.entries(T.textOps).map(([v, label]) => ({ value: v, label })),
                             { value: "empty", label: T.emptyOnly }]} />
      {!empty && <TextField label={T.value} value={value} onChange={setValue} autoFocus />}
      <Actions canApply={empty || Boolean(value.trim())} onClear={() => onApply(null)} />
    </form>
  );
}

function ListFilterMenu({ list, column, filter, others, onApply }: MenuProps) {
  const [selected, setSelected] = useState<ListValue[]>(filter?.values ?? []);
  const [empty, setEmpty] = useState(filter?.op === "empty" || Boolean(filter?.empty));
  const [search, setSearch] = useState("");
  const [server, setServer] = useState<ValueCount[] | null>(null);

  useEffect(() => {
    if (!column.values_from_server) return;
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      listApi(list).values({ field: column.field, search, filters: others }, ctrl.signal)
        .then(setServer).catch(() => setServer([]));
    }, search ? 300 : 0);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [list, column, search, others]);

  const options: { value: ListValue; count?: number }[] = useMemo(() => {
    if (column.values_from_server) return (server ?? []).filter((v): v is ValueCount & { value: ListValue } => v.value !== null);
    const q = fold(search.trim());
    return (column.values ?? []).filter((v) => !q || fold(valueLabel(v)).includes(q)).map((value) => ({ value }));
  }, [column, server, search]);
  const emptyCount = server?.find((v) => v.value === null)?.count;

  const toggle = (v: ListValue, on: boolean) =>
    setSelected((s) => (on ? [...s, v] : s.filter((x) => x !== v)));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (selected.length) onApply({ field: column.field, op: "in", values: selected, ...(empty ? { empty: true } : {}) });
    else if (empty) onApply({ field: column.field, op: "empty" });
  };
  return (
    <form className="sc-table-pop-form" onSubmit={submit}>
      <SearchField label={T.valueSearch} value={search} onChange={setSearch} />
      <div className="sc-table-pop-list" role="group" aria-label={column.label}>
        {!search.trim() && (
          <div className="sc-table-pop-option">
            <Checkbox label={T.emptyOption} checked={empty} onChange={setEmpty} />
            {emptyCount !== undefined && <span className="sc-num sc-muted">{formatNumber(emptyCount)}</span>}
          </div>
        )}
        {options.length === 0 && server !== null && <p className="sc-muted">{T.noValues}</p>}
        {options.map((o) => (
          <div key={String(o.value)} className="sc-table-pop-option">
            <Checkbox label={valueLabel(o.value)} checked={selected.includes(o.value)} onChange={(on) => toggle(o.value, on)} />
            {o.count !== undefined && <span className="sc-num sc-muted">{formatNumber(o.count)}</span>}
          </div>
        ))}
      </div>
      <Actions canApply={selected.length > 0 || empty} onClear={() => onApply(null)} />
    </form>
  );
}

type NumberMode = NumberOp | "empty";

function NumberFilter({ column, filter, onApply }: MenuProps) {
  const [op, setOp] = useState<NumberMode>((filter?.op as NumberMode) ?? "between");
  const [min, setMin, getMin] = useLatest<number | null>(filter?.min ?? null);
  const [max, setMax, getMax] = useLatest<number | null>(filter?.max ?? null);
  const [value, setValue, getValue] = useLatest<number | null>(typeof filter?.value === "number" ? filter.value : null);
  const decimals = column.decimals ?? 3;  // birimden gelen miktarda girişi yuvarlamamak için en çok 3
  const ready = op === "empty" || (op === "between" ? min !== null || max !== null : value !== null);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const [lo, hi, v] = [getMin(), getMax(), getValue()];
    if (op === "empty") {
      onApply({ field: column.field, op: "empty" });
    } else if (op === "between" && (lo !== null || hi !== null)) {
      onApply({ field: column.field, op, ...(lo !== null ? { min: lo } : {}), ...(hi !== null ? { max: hi } : {}) });
    } else if (op !== "between" && v !== null) {
      onApply({ field: column.field, op, value: v });
    }
  };
  return (
    <form className="sc-table-pop-form" onSubmit={submit}>
      <Segment<NumberMode> label={T.operator} value={op} onChange={setOp}
                           options={[...(Object.keys(T.numberOps) as NumberOp[]).map((v) => ({ value: v, label: T.numberOps[v] })),
                                     { value: "empty" as const, label: T.emptyShort }]} />
      {op === "between" && (
        <div className="sc-table-pop-pair">
          <NumberField label={T.min} value={min} onChange={setMin} decimals={decimals} />
          <NumberField label={T.max} value={max} onChange={setMax} decimals={decimals} />
        </div>
      )}
      {op !== "between" && op !== "empty" && <NumberField label={T.value} value={value} onChange={setValue} decimals={decimals} />}
      <Actions canApply={ready} onClear={() => onApply(null)} />
    </form>
  );
}

type DateMode = "between" | "relative" | "empty";

function DateFilter({ column, filter, onApply }: MenuProps) {
  const [mode, setMode] = useState<DateMode>(filter?.op === "relative" || filter?.op === "empty" ? filter.op : "between");
  const [from, setFrom, getFrom] = useLatest<Date | null>(parseIso(filter?.from));
  const [to, setTo, getTo] = useLatest<Date | null>(parseIso(filter?.to));
  const [relative, setRelative] = useState<string>(typeof filter?.value === "string" ? filter.value : "this_week");
  const ready = mode !== "between" || from !== null || to !== null;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const [lo, hi] = [getFrom(), getTo()];
    if (mode === "relative") {
      onApply({ field: column.field, op: "relative", value: relative });  // göreli saklanır (K-89)
    } else if (mode === "empty") {
      onApply({ field: column.field, op: "empty" });
    } else if (lo || hi) {
      onApply({ field: column.field, op: "between", ...(lo ? { from: toIsoDate(lo) } : {}), ...(hi ? { to: toIsoDate(hi) } : {}) });
    }
  };
  return (
    <form className="sc-table-pop-form" onSubmit={submit}>
      <Segment<DateMode> label={T.dateMode} value={mode} onChange={setMode}
                         options={[{ value: "between", label: T.dateRange }, { value: "relative", label: T.dateRelative },
                                   { value: "empty", label: T.emptyShort }]} />
      {mode === "between" && (
        <div className="sc-table-pop-pair">
          <DateField label={T.from} value={from} onChange={setFrom} />
          <DateField label={T.to} value={to} onChange={setTo} />
        </div>
      )}
      {mode === "relative" && (
        <RadioGroup label={T.dateRelative} value={relative} onChange={setRelative}
                    options={Object.entries(T.relative).map(([v, label]) => ({ value: v, label }))} />
      )}
      <Actions canApply={ready} onClear={() => onApply(null)} />
    </form>
  );
}

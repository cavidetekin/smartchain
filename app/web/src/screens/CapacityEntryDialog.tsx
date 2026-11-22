// Kapasite yönetimi · "Yeni kayıt" ve "Düzenle" penceresi (K-185, K-187; docs/12 "Pencere ve form standardı", "Kapasite yönetimi"). Bütün
// girişlerde aynı düzen: iki kolonlu ızgara; seviye ve kod, tarihler, değerler. Kaynak ya da kaynak grubu aramalı seçilir; kısa listeler düğmedir;
// çalışma düzeninin günleri kutudur. Zorunlu alan boşken Kaydet pasiftir ("(zorunlu)" yazmaz); sunucunun reddettiği alanın altında neden yazar.
// Pencere dolu alanla açılmaz (K-138): yalnız çalışma düzeninin günleri Pzt–Cum Tam gelir. Düzenlemede seviye ve kod değişmez.
import { useEffect, useMemo, useState } from "react";

import { ApiError, emitNotice } from "../api/client";
import { tr } from "../i18n/tr";
import { listApi, type Row } from "../table/types";
import { Alert, DateField, DayBoxes, Dialog, NumberField, SearchSelect, Segment, TextField } from "../ui";
import { capacityApi, DAY_CHOICES, DAYS, type EntryDialogProps, type EntryField, type EntryKind, type EntrySpec, isoDate, parseIso } from "./capacityModel";

const T = tr.capacity;
type Values = Record<string, unknown>;
const OFF = DAY_CHOICES[2];
const DEFAULT_DAYS: Values = Object.fromEntries(DAYS.map((d, i) => [d, i < 5 ? DAY_CHOICES[0] : OFF]));   // varsayılan Pzt–Cum Tam
const DAY_LEVELS: Record<string, number> = { [DAY_CHOICES[0]]: 1, [DAY_CHOICES[1]]: 0.5, [OFF]: 0 };
const UNIT_FIELDS = new Set(["DailyCapacity", "DailyLimit"]);   // grubun kapasite biriminde

function initial(spec: EntrySpec, row: Row | null): Values {
  if (!row) return spec.kind === "work-patterns" ? { ...DEFAULT_DAYS } : {};
  return Object.fromEntries(spec.fields.map((f) => {
    const v = row[f.name];
    if (f.kind === "date") return [f.name, parseIso(v)];
    if (f.kind === "day") return [f.name, v === "—" ? OFF : v];
    return [f.name, v ?? (f.kind === "number" ? null : "")];
  }));
}

/** Pencerenin değeri sunucuya: tarih ISO, boş metin null. */
function wire(f: EntryField, v: unknown): unknown {
  if (f.kind === "date") return v instanceof Date ? isoDate(v) : null;
  if (typeof v === "string") return v.trim() === "" ? null : v;
  return v ?? null;
}

const filled = (f: EntryField, v: unknown) => (f.kind === "date" ? v instanceof Date : f.kind === "number" ? typeof v === "number" : typeof v === "string" && v.trim() !== "");

export function CapacityEntryDialog({ spec, scenario, row, owner, onClose, onSaved }: EntryDialogProps) {
  const kind = spec.kind as EntryKind;   // bu pencere kapasite girişlerinindir (başka girişin penceresi `spec.adapter.Dialog`)
  const editing = row !== null;
  const start = useMemo(() => initial(spec, row), [spec, row]);
  const [values, setValues] = useState<Values>(start);
  const [level, setLevel] = useState<"group" | "resource">(owner?.level === "resource" ? "resource" : "group");
  const [ownerId, setOwnerId] = useState(owner ? String(owner.id) : "");
  const [options, setOptions] = useState<{ group: Row[]; resource: Row[] } | null>(null);
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {   // seviye ve kod seçenekleri: güncel kaynak grupları ve kaynaklar (kapasite birimiyle)
    if (!spec.owner || editing) return undefined;
    const ctrl = new AbortController();
    // liste ucu parça parça verir (en çok ListChunkSize satır): hepsi okunana kadar sürer
    const read = async (list: string): Promise<Row[]> => {
      const all: Row[] = [];
      for (;;) {
        const page = await listApi(list).query({ offset: all.length, limit: 100, sort: [{ field: "Code", dir: "asc" }], filters: [], fields: ["LocationCode", "Code", "Name", "CapacityUnit"] },
                                               ctrl.signal);
        all.push(...page.rows);
        if (!page.rows.length || all.length >= page.filtered) return all;
      }
    };
    const readResources = async (): Promise<Row[]> => {   // kaynakta birim görünen alan değil, her satırda dönen alandır
      const all: Row[] = [];
      for (;;) {
        const page = await listApi("capacity-resources").query({ offset: all.length, limit: 100, sort: [{ field: "Code", dir: "asc" }], filters: [], fields: ["LocationCode", "Code", "Name"] },
                                                               ctrl.signal);
        all.push(...page.rows);
        if (!page.rows.length || all.length >= page.filtered) return all;
      }
    };
    Promise.all([read("capacity-resource-groups"), readResources()])
      .then(([group, resource]) => setOptions({ group, resource }))
      .catch(() => { if (!ctrl.signal.aborted) { setOptions({ group: [], resource: [] }); setError(T.failed); } });
    return () => ctrl.abort();
  }, [spec.owner, editing]);

  const set = (name: string, v: unknown) => setValues((all) => ({ ...all, [name]: v }));
  const list = options?.[level] ?? [];
  // Veride birden çok lokasyon varsa seçenek "lokasyon · kod · ad" yazılır (K-189); tek lokasyonda yalnız kod ve ad
  const manyLocations = new Set([...(options?.group ?? []), ...(options?.resource ?? [])].map((o) => o.LocationCode).filter(Boolean)).size > 1;
  const codeOf = (o: Row) => (manyLocations && o.LocationCode ? `${String(o.LocationCode)} · ${String(o.Code)}` : String(o.Code));
  const picked = list.find((o) => String(o.Id) === ownerId);
  const unit = editing ? row.CapacityUnit : picked?.CapacityUnit;
  // Zorunlu alan boşken Kaydet pasif (K-187); alan adında işaret yoktur
  const missing = spec.fields.some((f) => f.required && !filled(f, values[f.name])) || (spec.owner && !editing && !ownerId);

  const submit = async () => {
    setBusy(true);
    setProblems({});
    setError(null);
    try {
      let warnings: string[] | undefined;
      if (editing) {
        const changes = spec.fields.filter((f) => JSON.stringify(wire(f, values[f.name])) !== JSON.stringify(wire(f, start[f.name])))
          .map((f) => ({ id: row.Id, field: f.name, value: wire(f, values[f.name]) }));
        if (changes.length) warnings = (await capacityApi.change(kind, scenario, changes)).warnings;
      } else {
        const body: Values = Object.fromEntries(spec.fields.map((f) => [f.name, wire(f, values[f.name])]));
        if (spec.owner) body[level === "group" ? "ResourceGroupId" : "ResourceId"] = ownerId ? Number(ownerId) : null;
        warnings = (await capacityApi.create(kind, scenario, body)).warnings;
      }
      for (const w of warnings ?? []) emitNotice(w);
      onSaved();
    } catch (e) {
      if (e instanceof ApiError && e.details.length) setProblems(Object.fromEntries(e.details.map((d) => [d.field, d.problem])));
      else setError(e instanceof ApiError ? e.message : T.failed);
    } finally {
      setBusy(false);
    }
  };

  const field = (f: EntryField) => {
    const common = { label: f.label, error: problems[f.name] };
    if (f.kind === "date") return <DateField key={f.name} {...common} value={(values[f.name] as Date | null) ?? null} onChange={(v) => set(f.name, v)} />;
    if (f.kind === "number") {
      return <NumberField key={f.name} {...common} live decimals={f.decimals ?? 2} unit={UNIT_FIELDS.has(f.name) && typeof unit === "string" ? unit : null}
                          value={(values[f.name] as number | null) ?? null} onChange={(v) => set(f.name, v)} />;
    }
    if (f.kind === "choice") {   // üç ve daha az seçenek: yan yana düğme; varsayılan yok (boş gelir)
      return (
        <div key={f.name} className="sc-form-full">
          <Segment<string> label={f.label} value={String(values[f.name] ?? "")} onChange={(v) => set(f.name, v)} options={(f.options ?? []).map((o) => ({ value: o, label: o }))} />
          {problems[f.name] && <p className="sc-field-error">{problems[f.name]}</p>}
        </div>
      );
    }
    return <div key={f.name} className="sc-form-full"><TextField {...common} value={String(values[f.name] ?? "")} onChange={(v) => set(f.name, v)} /></div>;
  };
  const dayFields = spec.fields.filter((f) => f.kind === "day");
  const dayProblem = dayFields.map((f) => problems[f.name]).find(Boolean);
  const ownerProblem = problems.ResourceGroupId ?? problems.ResourceId;

  return (
    <Dialog title={editing ? T.editTitle(spec.title) : T.newTitle(spec.title)} onClose={onClose} onSubmit={() => void submit()} submitLabel={tr.table.editSave} busy={busy}
            submitDisabled={Boolean(missing)} className="sc-dialog--form">
      <div className="sc-form-grid">
        {spec.owner && !editing && (
          <div className="sc-form-full sc-form-owner">
            <Segment<"group" | "resource"> label={T.level} value={level} onChange={(v) => { setLevel(v); setOwnerId(""); }}
                                           options={[{ value: "group", label: T.levelGroup }, { value: "resource", label: T.levelResource }]} />
            <SearchSelect label={level === "group" ? T.resourceGroup : T.resource} value={ownerId} onChange={setOwnerId} error={ownerProblem} emptyText={T.noMatch}
                          options={list.map((o) => ({ value: String(o.Id), code: codeOf(o), name: o.Name ? String(o.Name) : undefined }))} />
          </div>
        )}
        {spec.owner && editing && (
          <div className="sc-form-full sc-form-owner">
            <TextField label={T.level} value={String(row.Level ?? "")} onChange={() => undefined} disabled />
            <TextField label={T.code} value={String(row.Code ?? "")} onChange={() => undefined} disabled />
          </div>
        )}
        {spec.fields.filter((f) => f.kind !== "day").map(field)}
        {dayFields.length > 0 && (
          <div className="sc-form-full">
            <DayBoxes label={T.days} days={dayFields.map((f) => ({ key: f.name, label: f.label }))} order={DAY_CHOICES} levels={DAY_LEVELS}
                      values={Object.fromEntries(dayFields.map((f) => [f.name, String(values[f.name] ?? OFF)]))} onChange={set} />
            {dayProblem && <p className="sc-field-error">{dayProblem}</p>}
          </div>
        )}
      </div>
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}

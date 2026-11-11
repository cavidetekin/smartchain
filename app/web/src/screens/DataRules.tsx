// Veri kuralları (ekran 04, fonksiyon 16, 18, 19; K-140…K-142, docs/12). Validasyon kuralları ile aynı desen: üst şerit, ortak tablo,
// toplu kayıt (K-132). Sıra tablo seçiliyken Sıra hücresindeki tutamakla sürüklenir ya da Alt + ↑ / ↓ ile taşınır; taslak sıra
// Kaydet'le yazılır. Kural penceresi 3.4 düzeninde, altında Sonuç (Değer / Alan / Formül / Boşalt) ve Seçenek. Kayıt kendiliğinden
// uygulanmaz: "Kurallar yeniden uygulansın mı?" ve şeritte "Kuralları yeniden uygula".
import { GripVertical } from "lucide-react";
import { type DragEvent, type HTMLAttributes, useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, JOB_VALIDATION } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can, forbiddenReason } from "../auth/permissions";
import { formatDateTime, serverDate } from "../format";
import { tr } from "../i18n/tr";
import { SwitchCell } from "../table/CellEditors";
import { type ConditionField, ConditionEditor, type ConditionRow, groupsComplete, ValueInput } from "../table/ConditionEditor";
import { DataTable, type FieldHints, type RowMenuSpec } from "../table/DataTable";
import { listApi, type ListFilter, type Row } from "../table/types";
import { EditBar, UnsavedGuard, useTableEdits } from "../table/useTableEdits";
import { Alert, type BadgeTone, Button, ConfirmDialog, Dialog, Segment, SelectField, TextField, Tooltip, TopStrip } from "../ui";
import {
  DATE_OPERATORS, type DataRuleChange, type DataRuleField, dataRulesApi, emptyResult, KIND_CLEAR, KIND_FIELD, KIND_FORMULA, KIND_VALUE,
  MODE_ALWAYS, MODE_ONLY_EMPTY, NUMBER_OPERATORS, RESULT_KINDS, resultComplete, type RuleResult, STATUS_FAILED, STATUS_RAN,
} from "./dataRulesApi";
import { useFlowLock } from "../shell/FlowStatus";
import { useJobRefresh } from "../shell/useJobRefresh";
import { MenuItem, RowPopMenu } from "./RowPopMenu";

const T = tr.dataRules;
const ALL = "";
const ALLOWED = { allowed: true };
const NUMERIC = ["number", "integer"];

interface Entity { table: string; name: string }
interface Editing {
  id?: number; entity: string; name: string; target: string; result: RuleResult; mode: string; active: boolean; groups: ConditionRow[][];
}

const errorText = (e: unknown, fallback: string = T.saveFailed) => (e instanceof ApiError ? e.message : fallback);

const VALIDATION_JOBS = [JOB_VALIDATION];
const PAGE = 100;  // liste sözleşmesinin bir istekteki en çok satırı (ListChunkSize, docs/08)

/** Tablonun kural Id'leri sıra numarasına göre; sayfa sayfa okunur (500 istemek 422 dönüyor, sıra boş kalıyordu; K-143). */
export async function ruleIds(entity: string, signal?: AbortSignal): Promise<string[]> {
  const out: string[] = [];
  for (let offset = 0; ; offset += PAGE) {
    const r = await listApi("data-rules").query({ fields: ["Seq"], sort: [{ field: "Seq", dir: "asc" }], filters: [{ field: "EntityName", op: "equals", value: entity }],
                                                  offset, limit: PAGE }, signal);
    out.push(...r.rows.map((x) => String(x.Id)));
    if (r.rows.length < PAGE || out.length >= r.filtered) return out;
  }
}


/** Sürükle-bırak: kuralı hedefin önüne ya da arkasına koyar. */
export function dropId(ids: string[], id: string, target: string, side: "before" | "after"): string[] {
  if (id === target || !ids.includes(id)) return ids;
  const rest = ids.filter((x) => x !== id);
  const at = rest.indexOf(target) + (side === "after" ? 1 : 0);
  return [...rest.slice(0, at), id, ...rest.slice(at)];
}

/** Sonuç bölümü (K-141): Değer / Alan / Formül / Boşalt; formül yalnız sayı ve tarih hedefte. */
function ResultEditor({ fields, target, result, onChange }: { fields: DataRuleField[]; target: DataRuleField | undefined; result: RuleResult; onChange(r: RuleResult): void }) {
  const kind = target?.kind ?? "text";
  const isDate = kind === "date";
  const formulaOk = NUMERIC.includes(kind) || isDate;
  const set = (patch: Partial<RuleResult>) => onChange({ ...result, ...patch });
  const sourceOptions = fields.filter((f) => f.name !== target?.name && (result.kind === KIND_FIELD
    ? kind === "text" || f.kind === kind || (NUMERIC.includes(kind) && NUMERIC.includes(f.kind))
    : isDate ? f.kind === "date" : NUMERIC.includes(f.kind)));
  const numberFields = fields.filter((f) => NUMERIC.includes(f.kind));
  const operators = isDate ? DATE_OPERATORS : NUMBER_OPERATORS;
  const byField = result.operand_field !== null;
  return (
    <section className="sc-rule-result" aria-label={T.result}>
      <h3 className="sc-condition-title">{T.result}</h3>
      <Segment<string> label={T.result} hideLabel value={result.kind}
                       options={RESULT_KINDS.map((k) => ({ value: k, label: T.resultKinds[k] }))}
                       onChange={(k) => onChange({ ...emptyResult(), kind: k })} />
      <div className="sc-rule-result-row">
        {result.kind === KIND_VALUE && (
          <ValueInput label={T.value} strict field={target as ConditionField | undefined} row={{ field: target?.name ?? "", operator: "=", value: result.value, compare_field: null }}
                      onChange={(v) => set({ value: v })} />
        )}
        {result.kind === KIND_FIELD && (
          <SelectField label={T.sourceField} value={result.source_field ?? ""} onChange={(v) => set({ source_field: v || null })}
                       options={[{ value: "", label: "—" }, ...sourceOptions.map((f) => ({ value: f.name, label: f.label }))]} />
        )}
        {result.kind === KIND_FORMULA && !formulaOk && <p className="sc-muted">{T.noFormula}</p>}
        {result.kind === KIND_FORMULA && formulaOk && (
          <>
            <SelectField label={T.formulaField} value={result.source_field ?? ""} onChange={(v) => set({ source_field: v || null })}
                         options={[{ value: "", label: "—" }, ...sourceOptions.map((f) => ({ value: f.name, label: f.label }))]} />
            <SelectField label={T.operator} value={result.operator ?? ""} onChange={(v) => set({ operator: v || null })}
                         options={[{ value: "", label: "—" }, ...operators.map((o) => ({ value: o, label: isDate ? `${o} ${T.days}` : o }))]} />
            <Segment<string> label={tr.conditions.source} hideLabel value={byField ? "field" : "value"}
                             options={[{ value: "value", label: tr.conditions.sourceValue }, { value: "field", label: tr.conditions.sourceField }]}
                             onChange={(v) => set(v === "field" ? { operand_field: "", operand_value: null } : { operand_field: null })} />
            {byField ? (
              <SelectField label={T.operandField} value={result.operand_field ?? ""} onChange={(v) => set({ operand_field: v })}
                           options={[{ value: "", label: "—" }, ...numberFields.map((f) => ({ value: f.name, label: f.label }))]} />
            ) : (
              <TextField label={isDate ? `${T.operand} (${T.days})` : T.operand} value={result.operand_value ?? ""} inputMode="decimal"
                         onChange={(v) => set({ operand_value: v || null })} />
            )}
          </>
        )}
        {result.kind === KIND_CLEAR && <p className="sc-muted">{T.clearNote}</p>}
      </div>
    </section>
  );
}

function RuleDialog({ editing, onClose, onSaved }: { editing: Editing; onClose(): void; onSaved(changed: string[]): void }) {
  const [draft, setDraft] = useState(editing);
  const [fields, setFields] = useState<DataRuleField[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    dataRulesApi.fields(editing.entity, ctrl.signal).then(setFields).catch((e: unknown) => { if (!ctrl.signal.aborted) setError(errorText(e)); });
    return () => ctrl.abort();
  }, [editing.entity]);

  const target = fields.find((f) => f.name === draft.target);
  const mode = draft.result.kind === KIND_CLEAR ? MODE_ALWAYS : draft.mode;
  const save = async () => {
    if (!draft.name.trim() || !draft.target) return setError(T.needName);
    if (!resultComplete(draft.result)) return setError(T.needResult);
    if (draft.groups.length && !groupsComplete(draft.groups)) return setError(tr.conditions.incomplete);
    setBusy(true);
    setError(null);
    try {
      const change: DataRuleChange = {
        ...(draft.id ? { id: draft.id } : { entity: draft.entity }), name: draft.name.trim(), target: draft.target, result: draft.result, mode,
        active: draft.active, groups: draft.groups,
      };
      const r = await dataRulesApi.save([change], []);
      onSaved(r.changed_entities);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };

  return (
    <Dialog title={draft.id ? T.dialogEdit : T.dialogNew} onClose={onClose} onSubmit={() => void save()} submitLabel={tr.table.editSave} busy={busy} xwide
            titleAside={(
              <span className="sc-dialog-aside">
                <span>{T.activeLabel}</span>
                <SwitchCell label={T.activeLabel} checked={draft.active} editable onToggle={(v) => setDraft({ ...draft, active: v })} />
              </span>
            )}>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="sc-rule-head">
        <TextField label={T.name} value={draft.name} required maxLength={200} onChange={(v) => setDraft({ ...draft, name: v })} />
        <SelectField label={T.target} value={draft.target} required onChange={(v) => setDraft({ ...draft, target: v, result: { ...emptyResult(), kind: draft.result.kind } })}
                     options={[{ value: "", label: "—" }, ...fields.filter((f) => f.target).map((f) => ({ value: f.name, label: f.label }))]} />
      </div>
      {fields.length > 0 && (
        <>
          <ConditionEditor fields={fields} groups={draft.groups} onChange={(groups) => setDraft({ ...draft, groups })} />
          {draft.groups.length === 0 && <p className="sc-muted">{T.noCondition}</p>}
          <ResultEditor fields={fields} target={target} result={draft.result} onChange={(result) => setDraft({ ...draft, result })} />
          <Segment<string> label={T.mode} value={mode} options={[{ value: MODE_ONLY_EMPTY, label: T.onlyEmpty }, { value: MODE_ALWAYS, label: T.always }]}
                           onChange={(v) => { if (draft.result.kind !== KIND_CLEAR) setDraft({ ...draft, mode: v }); }} />
        </>
      )}
    </Dialog>
  );
}

/** Sıra hücresi: tutamak işareti ve sıra numarası, sola hizalı (K-145). Sıra yalnız satırı sürükleyerek değişir; tablo seçili değilse tutamak soluk. */
function SeqCell({ seq, movable, reason }: { seq: number; movable: boolean; reason: string | null }) {
  return (
    <span className={`sc-seq-cell${movable ? "" : " is-locked"}`} title={reason ?? undefined}>
      <GripVertical className="sc-seq-grip" aria-hidden="true" />
      <span className="sc-num">{seq}</span>
    </span>
  );
}

const SEQ_HINTS: FieldHints = { Seq: { width: 4.5, left: true } };  // dar ve sola hizalı (K-145)
const STATE_TONE: Record<string, BadgeTone> = { [STATUS_RAN]: "ok", [STATUS_FAILED]: "critical" };

/** Durum (K-145): her zaman dolu; Çalıştı soluk yeşil (ipucunda son çalışma), Çalışmadı kırmızı (ipucunda neden), Pasif ve Uygulanmadı gri. */
function StateCell({ state, row }: { state: string; row: Row }) {
  const tone = STATE_TONE[state] ?? "neutral";
  const tip = state === STATUS_FAILED ? (row.LastRunMessage ? String(row.LastRunMessage) : null)
    : state === STATUS_RAN && row.LastRunAt ? T.ranAt(formatDateTime(serverDate(String(row.LastRunAt)))) : null;
  const chip = <span className={`sc-tag sc-tag--${tone}${tone === "ok" ? " sc-tag--soft" : ""}`}>{state}</span>;
  return tip ? <Tooltip content={tip} focusable>{chip}</Tooltip> : chip;
}

export function DataRules() {
  const me = useAuth().me!;
  const canWrite = can(me, 16, "write");
  const flowLock = useFlowLock();  // K-163: zamanlanmış iş sürerken kural kaydedilmez
  const writeReason = canWrite ? flowLock : forbiddenReason(16, "write");
  const orderReason = can(me, 18, "write") ? flowLock : forbiddenReason(18, "write");
  const applyReason = can(me, 19, "write") ? flowLock : forbiddenReason(19, "write");
  const [entities, setEntities] = useState<Entity[]>([]);
  const [entity, setEntity] = useState(ALL);
  const edits = useTableEdits();
  const [ids, setIds] = useState<string[]>([]);
  const [order, setOrder] = useState<string[] | null>(null);
  const [drag, setDrag] = useState<{ id: string; over?: string; side?: "before" | "after" } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [menu, setMenu] = useState<{ row: Row; anchor: HTMLElement } | null>(null);
  const [editing, setEditing] = useState<Editing | null>(null);
  const [deleting, setDeleting] = useState<Row | null>(null);
  const [ask, setAsk] = useState<string[] | "all" | null>(null);
  const refresh = useCallback(() => setReloadKey((k) => k + 1), []);
  useJobRefresh(VALIDATION_JOBS, refresh);  // "Kuralları yeniden uygula" bitince Durum güncellenir (K-143)

  useEffect(() => {
    const ctrl = new AbortController();
    listApi("data-entities").query({ fields: ["Entity", "Name"], sort: [{ field: "CatalogOrder", dir: "asc" }], filters: [], offset: 0, limit: 100 }, ctrl.signal)
      .then((r) => setEntities(r.rows.map((x) => ({ table: String(x.Entity), name: String(x.Name) })))).catch(() => undefined);
    return () => ctrl.abort();
  }, []);
  useEffect(() => {  // seçili tablonun kural sırası: taslak sıra bunun üzerinde
    setOrder(null);
    if (!entity) return setIds([]);
    const ctrl = new AbortController();
    void ruleIds(entity, ctrl.signal).then(setIds).catch(() => undefined);
    return () => ctrl.abort();
  }, [entity, reloadKey]);

  const nameOf = useCallback((table: string) => entities.find((e) => e.table === table)?.name ?? table, [entities]);
  const baseFilters: ListFilter[] = useMemo(() => (entity ? [{ field: "EntityName", op: "equals", value: entity }] : []), [entity]);
  const orderDirty = order !== null && order.join(",") !== ids.join(",");
  const dirty = edits.dirty || orderDirty;
  const movableReason = !entity ? T.pickTableOrder : orderReason;

  const discard = () => {
    edits.discard();
    setOrder(null);
  };
  const afterSave = (changed: string[]) => {
    setEditing(null);
    setDeleting(null);
    refresh();
    if (changed.length) setAsk(changed);
  };

  const saveEdits = async () => {
    setSaving(true);
    setError(null);
    try {
      const changes: DataRuleChange[] = Object.entries(edits.drafts).map(([key, d]) => ({ id: Number(key), ...("IsActive" in d ? { active: Boolean(d.IsActive) } : {}) }));
      const orders = orderDirty && order ? [{ entity, ids: order.map(Number) }] : [];
      const r = await dataRulesApi.save(changes, orders);
      discard();
      afterSave(r.changed_entities);
    } catch (e) {
      setError(errorText(e));
      if (e instanceof ApiError && e.status === 409) {  // sıra eskidi: liste yenilenir
        setOrder(null);
        refresh();
      }
    } finally {
      setSaving(false);
    }
  };

  const apply = async (target: string[] | "all") => {  // çipler "Sırada" olur, iş panelinde görünür; onay bandı yok (K-139)
    setAsk(null);
    try {
      if (target === "all") await dataRulesApi.apply(null);
      else for (const t of target) await dataRulesApi.apply(t);
    } catch (e) {
      setError(errorText(e, T.applyFailed));
    }
  };

  const remove = async () => {
    if (!deleting) return;
    try {
      const r = await dataRulesApi.save([{ id: Number(deleting.Id), delete: true }], []);
      afterSave(r.changed_entities);
    } catch (e) {
      setError(errorText(e));
      setDeleting(null);
    }
  };

  const openEdit = async (row: Row) => {
    setMenu(null);
    try {
      const rule = await dataRulesApi.rule(Number(row.Id));
      setEditing({ id: rule.id, entity: rule.entity, name: rule.name, target: rule.target, result: rule.result, mode: rule.mode, active: rule.active,
                   groups: rule.groups });
    } catch (e) {
      setError(errorText(e));
    }
  };

  const current = order ?? ids;

  const cellRender = useMemo(() => ({
    Seq: (value: unknown, row: Row) => {
      const id = String(row.Id);
      const at = order ? order.indexOf(id) : -1;
      return (
        <SeqCell seq={at >= 0 ? at + 1 : Number(value)} movable={!movableReason} reason={movableReason} />
      );
    },
    IsActive: (value: unknown, row: Row) => {
      const key = String(row.Id);
      return <SwitchCell label={T.active(String(row.RuleName))} checked={edits.get(key, "IsActive", Boolean(value))} editable={canWrite}
                         changed={edits.changed(key, "IsActive")} onToggle={(next) => edits.set(key, "IsActive", next, Boolean(value))} />;
    },
    RunState: (value: unknown, row: Row) => (value ? <StateCell state={String(value)} row={row} /> : null),
  }), [canWrite, edits, order, movableReason]);

  /** Sürükle-bırak (K-143): satır tutulur, satırın tamamı bırakma yeridir; üst yarı önüne, alt yarı arkasına. */
  const rowProps = useCallback((row: Row): HTMLAttributes<HTMLTableRowElement> => {
    if (movableReason) return {};
    const id = String(row.Id);
    return {
      draggable: true,
      className: drag?.over === id ? `is-drop-${drag.side}` : drag?.id === id ? "is-dragging" : undefined,
      onDragStart: (e: DragEvent<HTMLTableRowElement>) => {
        e.dataTransfer?.setData("text/plain", id);
        if (e.dataTransfer) e.dataTransfer.effectAllowed = "move";
        setDrag({ id });
      },
      onDragOver: (e: DragEvent<HTMLTableRowElement>) => {
        if (!drag || drag.id === id) return;
        e.preventDefault();
        if (e.dataTransfer) e.dataTransfer.dropEffect = "move";
        const r = e.currentTarget.getBoundingClientRect();
        const side = e.clientY < r.top + r.height / 2 ? "before" : "after";
        if (drag.over !== id || drag.side !== side) setDrag({ ...drag, over: id, side });
      },
      onDrop: (e: DragEvent<HTMLTableRowElement>) => {
        e.preventDefault();
        const from = drag?.id ?? e.dataTransfer?.getData("text/plain");
        if (from && from !== id) setOrder(dropId(current, from, id, drag?.side ?? "before"));
        setDrag(null);
      },
      onDragEnd: () => setDrag(null),
    };
  }, [movableReason, drag, current]);

  const rowMenu: RowMenuSpec = useMemo(() => ({
    label: (row: Row) => T.rowMenu(String(row.RuleName)),
    onOpen: (row: Row, anchor: HTMLElement) => setMenu({ row, anchor }),
  }), []);
  const writeState = writeReason ? { allowed: false, reason: writeReason } : ALLOWED;

  return (
    <section className="sc-page--fill">
      <header className="sc-page-head sc-page-head--row">
        <h1>{T.title}</h1>
      </header>
      {error && <Alert tone="error">{error}</Alert>}
      <TopStrip label={T.stripLabel}>
        <SelectField label={T.table} value={entity} onChange={setEntity}
                     options={[{ value: ALL, label: T.all }, ...entities.map((e) => ({ value: e.table, label: e.name }))]} />
        <Button variant="primary" disabledReason={writeReason ?? (entity ? null : T.pickTable)}
                onClick={() => setEditing({ entity, name: "", target: "", result: emptyResult(), mode: MODE_ONLY_EMPTY, active: true, groups: [] })}>{T.newRule}</Button>
        <Button variant="secondary" disabledReason={applyReason} onClick={() => setAsk(entity ? [entity] : "all")}>{T.apply}</Button>
      </TopStrip>
      <DataTable list="data-rules" baseFilters={baseFilters} cellRender={cellRender} rowMenu={rowMenu} reloadKey={reloadKey} rowOrder={orderDirty ? order : null} rowProps={rowProps} fieldHints={SEQ_HINTS}
                 toolbarActions={<EditBar dirty={dirty} busy={saving} onSave={() => void saveEdits()} onDiscard={discard} disabledReason={flowLock} />} />
      <UnsavedGuard dirty={dirty} />
      {menu && (
        <RowPopMenu label={T.rowMenu(String(menu.row.RuleName))} anchor={menu.anchor} onClose={() => setMenu(null)}>
          <MenuItem label={T.edit} state={writeState} onClick={() => void openEdit(menu.row)} />
          <MenuItem label={T.remove} state={writeState} onClick={() => { setDeleting(menu.row); setMenu(null); }} />
        </RowPopMenu>
      )}
      {editing && <RuleDialog editing={editing} onClose={() => setEditing(null)} onSaved={afterSave} />}
      {deleting && <ConfirmDialog title={T.remove} message={T.removeText(String(deleting.RuleName), String(deleting.ResultText ?? ""))} confirmLabel={T.remove} danger
                                  onCancel={() => setDeleting(null)} onConfirm={() => void remove()} />}
      {ask && (
        <ConfirmDialog title={T.applyTitle} message={ask === "all" ? T.applyAllText : T.applyText(ask.map(nameOf).join(", "))} confirmLabel={T.applyNow}
                       onCancel={() => setAsk(null)} onConfirm={() => void apply(ask)} />
      )}
    </section>
  );
}

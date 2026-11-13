// Validasyon kuralları (ekran 27, fonksiyon 100; K-136, K-139, docs/12). Yapısal kontroller listede görünmez, arka planda çalışır.
// Sınıf (pastel çip, tıklayınca seçim) ve aktiflik tablo içinde düzenlenir ve toplu kaydedilir (K-132). Kullanıcı kuralı ve koşulu
// editörle ifade edilen hazır kural pencerede düzenlenir; hazır kural "İlk hâline döndür" ile katalogdaki hâline döner. Eşik ve
// "Yeni kural" seçili tablonun şeridinde, tek satırda.
import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, emitNotice, JOB_VALIDATION } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can, forbiddenReason } from "../auth/permissions";
import { tr } from "../i18n/tr";
import { SwitchCell } from "../table/CellEditors";
import { type ConditionField, ConditionEditor, type ConditionRow, groupsComplete } from "../table/ConditionEditor";
import { DataTable, type RowMenuSpec } from "../table/DataTable";
import { listApi, type ListFilter, type Row } from "../table/types";
import { EditBar, UnsavedGuard, useTableEdits } from "../table/useTableEdits";
import { Alert, Badge, type BadgeTone, Button, ConfirmDialog, Dialog, StripSelect, StripText, TextField } from "../ui";
import { useFlowLock } from "../shell/FlowStatus";
import { useJobRefresh } from "../shell/useJobRefresh";
import { type MenuAction, MenuActions, MenuItem, RowPopMenu } from "./RowPopMenu";
import { SEVERITY_CLASS, SeverityTag } from "./ValidationDrawer";
import { KIND_BUILTIN, KIND_USER, type RuleChange, SEVERITIES, validationApi } from "./validationApi";

const T = tr.validationRules;
const ALL = "";
const KIND_TONE: Record<string, BadgeTone> = { [KIND_BUILTIN]: "info", [KIND_USER]: "risk" };
const THRESHOLD = "threshold";
const ALLOWED = { allowed: true };
const VALIDATION_JOBS = [JOB_VALIDATION];

interface Entity { table: string; name: string }
interface Editing {
  id?: number; entity: string; kind: string; name: string; message: string; severity: string; active: boolean; groups: ConditionRow[][];
}

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : T.saveFailed);

/** Sınıf hücresi: saydam pastel çip; düzenlenebilirse tıklayınca seçim kutusu açılır (K-139). */
function SeverityCell({ label, value, editable, changed, onChange }: { label: string; value: string; editable: boolean; changed: boolean; onChange(v: string): void }) {
  if (!editable) return <SeverityTag severity={value} />;
  return (
    <select className={`sc-tag sc-tag--soft ${SEVERITY_CLASS[value] ?? ""} sc-severity-select${changed ? " is-edited" : ""}`} aria-label={label} value={value}
            onClick={(e) => e.stopPropagation()} onChange={(e) => onChange(e.target.value)}>
      {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
    </select>
  );
}

/** Sınıf seçimi: üç parça, seçili olan kendi pastel renginde (K-139). */
function SeverityPicker({ value, onChange }: { value: string; onChange(v: string): void }) {
  return (
    <div className="sc-field">
      <span className="sc-field-label" id="rule-severity">{T.severityLabel}</span>
      <div className="sc-severity-picker" role="radiogroup" aria-labelledby="rule-severity">
        {SEVERITIES.map((s) => (
          <button key={s} type="button" role="radio" aria-checked={value === s}
                  className={value === s ? `sc-tag--soft ${SEVERITY_CLASS[s]}` : undefined} onClick={() => onChange(s)}>{s}</button>
        ))}
      </div>
    </div>
  );
}

function RuleDialog({ editing, onClose, onSaved, onReset }: { editing: Editing; onClose(): void; onSaved(changed: string[]): void; onReset?(): void }) {
  const [draft, setDraft] = useState(editing);
  const [fields, setFields] = useState<ConditionField[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    validationApi.fields(editing.entity, ctrl.signal).then((f) => {
      setFields(f);
      setDraft((d) => (d.groups.length ? d : { ...d, groups: [[{ field: f[0]?.name ?? "", operator: "Boş", value: null, compare_field: null }]] }));
    }).catch((e: unknown) => { if (!ctrl.signal.aborted) setError(errorText(e)); });
    return () => ctrl.abort();
  }, [editing.entity]);

  const ready = draft.name.trim() && draft.message.trim() && groupsComplete(draft.groups);
  const save = async () => {
    if (!ready) {
      setError(draft.name.trim() && draft.message.trim() ? tr.conditions.incomplete : T.needName);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      // Hazır kuralda yalnız değişen parçalar gider: sınıf ya da aktiflik değişikliği kuralı "düzenlenmiş" yapmaz (K-139).
      const builtin = draft.kind === KIND_BUILTIN;
      const name = draft.name.trim();
      const message = draft.message.trim();
      const groupsChanged = JSON.stringify(draft.groups) !== JSON.stringify(editing.groups);
      const change: RuleChange = {
        ...(draft.id ? { id: draft.id } : { entity: draft.entity }), severity: draft.severity, active: draft.active,
        ...(!builtin || name !== editing.name ? { name } : {}),
        ...(!builtin || message !== editing.message ? { message } : {}),
        ...(!builtin || groupsChanged ? { groups: draft.groups } : {}),
      };
      const r = await validationApi.save([change], []);
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
            )}
            extraActions={onReset && <Button variant="neutral" onClick={onReset}>{T.reset}</Button>}>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="sc-rule-head">
        <TextField label={T.name} value={draft.name} required maxLength={200} onChange={(v) => setDraft({ ...draft, name: v })} />
        <TextField label={T.message} value={draft.message} required maxLength={400} onChange={(v) => setDraft({ ...draft, message: v })} />
      </div>
      <SeverityPicker value={draft.severity} onChange={(v) => setDraft({ ...draft, severity: v })} />
      {fields.length > 0 && <ConditionEditor fields={fields} groups={draft.groups} onChange={(groups) => setDraft({ ...draft, groups })} />}
    </Dialog>
  );
}

export function ValidationRules() {
  const me = useAuth().me!;
  const canWrite = can(me, 100, "write");
  const flowLock = useFlowLock();  // K-163
  const writeReason = canWrite ? flowLock : forbiddenReason(100, "write");
  const [entities, setEntities] = useState<Entity[]>([]);
  const [entity, setEntity] = useState(ALL);
  const [thresholds, setThresholds] = useState<Record<string, string>>({});
  const edits = useTableEdits();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [menu, setMenu] = useState<{ row: Row; anchor: HTMLElement; extra?: MenuAction[] } | null>(null);
  const [editing, setEditing] = useState<Editing | null>(null);
  const [deleting, setDeleting] = useState<Row | null>(null);
  const [resetting, setResetting] = useState<{ id: number; name: string } | null>(null);
  const [ask, setAsk] = useState<string[] | null>(null);
  const refresh = useCallback(() => setReloadKey((k) => k + 1), []);
  useJobRefresh(VALIDATION_JOBS, refresh);  // yeniden validasyon bitince liste güncellenir (K-143)

  useEffect(() => {
    const ctrl = new AbortController();
    listApi("data-entities").query({ fields: ["Entity", "Name"], sort: [{ field: "CatalogOrder", dir: "asc" }], filters: [], offset: 0, limit: 100 }, ctrl.signal)
      .then((r) => setEntities(r.rows.map((x) => ({ table: String(x.Entity), name: String(x.Name) })))).catch(() => undefined);
    return () => ctrl.abort();
  }, []);
  useEffect(() => {  // eşikler: tablonun çekmece özetinden
    if (!entity || entity in thresholds) return;
    const ctrl = new AbortController();
    validationApi.summary(entity, ctrl.signal).then((s) => setThresholds((t) => ({ ...t, [entity]: s.threshold === null ? "" : String(s.threshold).replace(".", ",") })))
      .catch(() => undefined);
    return () => ctrl.abort();
  }, [entity, thresholds]);

  const nameOf = useCallback((table: string) => entities.find((e) => e.table === table)?.name ?? table, [entities]);
  const baseFilters: ListFilter[] = useMemo(() => (entity ? [{ field: "EntityName", op: "equals", value: entity }] : []), [entity]);

  const afterSave = (changed: string[]) => {
    setEditing(null);
    setDeleting(null);
    setResetting(null);
    refresh();
    if (changed.length) setAsk(changed);
  };

  const saveEdits = async () => {
    setSaving(true);
    setError(null);
    try {
      const changes: RuleChange[] = [];
      const limits: { entity: string; value: string | null }[] = [];
      for (const [key, d] of Object.entries(edits.drafts)) {
        if (key.startsWith(`${THRESHOLD}:`)) limits.push({ entity: key.slice(THRESHOLD.length + 1), value: String(d.value ?? "") || null });
        else changes.push({ id: Number(key), ...("Severity" in d ? { severity: String(d.Severity) } : {}), ...("IsActive" in d ? { active: Boolean(d.IsActive) } : {}) });
      }
      const r = await validationApi.save(changes, limits);
      edits.discard();
      setThresholds({});
      afterSave(r.changed_entities);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSaving(false);
    }
  };

  const revalidate = async (tables: string[]) => {  // çipler "Sırada" olur, iş panelinde görünür; onay bandı yok (K-139)
    setAsk(null);
    for (const t of tables) {
      try {
        await validationApi.revalidate(t);
      } catch { /* sürüyor ya da veri yok: atlanır */ }
    }
  };

  const remove = async () => {
    if (!deleting) return;
    try {
      const r = await validationApi.save([{ id: Number(deleting.Id), delete: true }], []);
      afterSave(r.changed_entities);
    } catch (e) {
      setError(errorText(e));
      setDeleting(null);
    }
  };

  const reset = async () => {
    if (!resetting) return;
    try {
      const r = await validationApi.save([{ id: resetting.id, reset: true }], []);
      afterSave(r.changed_entities);
    } catch (e) {
      setError(errorText(e));
      setResetting(null);
    }
  };

  const openEdit = async (row: Row) => {
    setMenu(null);
    try {
      const rule = await validationApi.rule(Number(row.Id));
      setEditing({ id: rule.id, entity: rule.entity, kind: rule.kind, name: rule.name, message: rule.message, severity: rule.severity, active: rule.active,
                   groups: rule.groups });
    } catch (e) {
      setError(errorText(e));
    }
  };

  const cellRender = useMemo(() => ({
    Kind: (value: unknown) => (value ? <Badge tone={KIND_TONE[String(value)] ?? "neutral"}>{String(value)}</Badge> : null),
    Severity: (value: unknown, row: Row) => {
      const key = String(row.Id);
      return <SeverityCell label={T.severity(String(row.RuleName))} value={String(edits.get(key, "Severity", String(value)))} editable={canWrite}
                           changed={edits.changed(key, "Severity")} onChange={(next) => edits.set(key, "Severity", next, String(value))} />;
    },
    IsActive: (value: unknown, row: Row) => {
      const key = String(row.Id);
      return <SwitchCell label={T.active(String(row.RuleName))} checked={edits.get(key, "IsActive", Boolean(value))} editable={canWrite}
                         changed={edits.changed(key, "IsActive")} onToggle={(next) => edits.set(key, "IsActive", next, Boolean(value))} />;
    },
  }), [canWrite, edits]);

  const rowMenu: RowMenuSpec = useMemo(() => ({
    label: (row: Row) => T.rowMenu(String(row.RuleName)),
    onOpen: (row: Row, anchor: HTMLElement, extra?: MenuAction[]) => setMenu({ row, anchor, extra }),
  }), []);

  const thresholdKey = `${THRESHOLD}:${entity}`;
  const savedThreshold = entity ? thresholds[entity] ?? "" : "";
  const shownThreshold = edits.get(thresholdKey, "value", savedThreshold);
  const editState = (row: Row) => (writeReason ? { allowed: false, reason: writeReason } : row.Editable ? ALLOWED : { allowed: false, reason: T.notEditable });
  const deleteState = (row: Row) => (row.Kind !== KIND_USER ? { allowed: false, reason: T.builtinNoDelete } : writeReason ? { allowed: false, reason: writeReason } : ALLOWED);

  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{T.title}</h1>
      </header>
      {error && <Alert tone="error">{error}</Alert>}
      {/* Tablo seçimi, hata eşiği ve ekranın işlemi şeridin solunda (K-171) */}
      <DataTable list="validation-rules" baseFilters={baseFilters} cellRender={cellRender} rowMenu={rowMenu} reloadKey={reloadKey}
                 toolbarActions={<EditBar dirty={edits.dirty} busy={saving} onSave={() => void saveEdits()} onDiscard={edits.discard} disabledReason={flowLock} />}
                 toolbarLead={(
                   <>
                     <StripSelect label={T.table} value={entity} onChange={setEntity}
                                  options={[{ value: ALL, label: T.all }, ...entities.map((e) => ({ value: e.table, label: e.name }))]} />
                     <StripText label={T.threshold} value={String(shownThreshold ?? "")} disabled={!entity || !canWrite} inputMode="decimal"
                                onChange={(v) => edits.set(thresholdKey, "value", v, savedThreshold)} />
                     <Button variant="primary" disabledReason={writeReason}
                             onClick={() => (entity ? setEditing({ entity, kind: KIND_USER, name: "", message: "", severity: "Uyarı", active: true, groups: [] }) : emitNotice(T.pickTable))}>{T.newRule}</Button>
                   </>
                 )} />
      <UnsavedGuard dirty={edits.dirty} />
      {menu && (
        <RowPopMenu label={T.rowMenu(String(menu.row.RuleName))} anchor={menu.anchor} onClose={() => setMenu(null)}>
          <MenuActions items={menu.extra} onDone={() => setMenu(null)} />
          <MenuItem label={T.edit} state={editState(menu.row)} onClick={() => void openEdit(menu.row)} />
          {menu.row.Kind === KIND_BUILTIN ? (
            <MenuItem label={T.reset} state={writeReason ? { allowed: false, reason: writeReason } : ALLOWED}
                      onClick={() => { setResetting({ id: Number(menu.row.Id), name: String(menu.row.RuleName) }); setMenu(null); }} />
          ) : (
            <MenuItem label={T.remove} state={deleteState(menu.row)} onClick={() => { setDeleting(menu.row); setMenu(null); }} />
          )}
        </RowPopMenu>
      )}
      {editing && (
        <RuleDialog editing={editing} onClose={() => setEditing(null)} onSaved={afterSave}
                    onReset={editing.kind === KIND_BUILTIN && editing.id ? () => { setResetting({ id: editing.id!, name: editing.name }); setEditing(null); } : undefined} />
      )}
      {deleting && <ConfirmDialog title={T.remove} message={`${String(deleting.RuleName)} · ${String(deleting.ConditionText ?? "")}`} confirmLabel={T.remove} danger
                                  onCancel={() => setDeleting(null)} onConfirm={() => void remove()} />}
      {resetting && <ConfirmDialog title={T.resetTitle} message={T.resetText(resetting.name)} confirmLabel={T.reset}
                                   onCancel={() => setResetting(null)} onConfirm={() => void reset()} />}
      {ask && <ConfirmDialog title={T.revalidateTitle} message={T.revalidateText(ask.map(nameOf).join(", "))} confirmLabel={T.revalidateNow}
                             onCancel={() => setAsk(null)} onConfirm={() => void revalidate(ask)} />}
    </section>
  );
}

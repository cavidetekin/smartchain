// Zamanlanmış işler (Sistem ayarları sekmesi, fonksiyon 92; K-163, K-164, K-171). Tek şerit: solda sekmeler, ana işlem "Yeni zamanlanmış iş" ve
// "Bekleme süreleri" (iki süre küçük pencerede, Vazgeç / Kaydet); sağda tablo düğmeleri. Satıra tıklayınca alt kartta o işin geçmişi (ana–detay,
// K-161). Satır menüsü: Detay (geçmiş kartı), Düzenle (Admin'de Görüntüle), Şimdi çalıştır (System owner, onaylı). Pencere adımları sabit sırayla: İş tanımı, Zamanlama, Veri çekimi,
// Veri aktarımı, Ham veri temizliği.
import { type HTMLAttributes, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, emitNotice, JOB_CLEANUP, JOB_PULL, JOB_TRANSFER, JOB_VALIDATION } from "../api/client";
import { forbiddenReason } from "../auth/permissions";
import { formatDateTime, formatNumber, parseTrNumber, serverDate } from "../format";
import { tr } from "../i18n/tr";
import { useFlowStatus } from "../shell/FlowStatus";
import { useJobRefresh } from "../shell/useJobRefresh";
import { SwitchCell } from "../table/CellEditors";
import { DataTable, type FieldHints, type RowMenuSpec } from "../table/DataTable";
import type { Row } from "../table/types";
import { Alert, Badge, type BadgeTone, Button, ConfirmDialog, type DetailTab, Dialog, MasterDetail, Segment, TextField, Tooltip, useMasterDetail } from "../ui";
import { type Flow, type FlowBody, type FlowOptions, type FlowSettings, type FlowsResponse, flowsApi, FLOW_DONE, FLOW_STOPPED, FLOW_NOT_STARTED,
  MODE_FULL, MODE_PARTIAL, SCOPE_ALL, SCOPE_SELECTED } from "./flowsApi";
import { type MenuAction, MenuActions, MenuItem, RowPopMenu } from "./RowPopMenu";

const T = tr.flows;
const ALLOWED = { allowed: true };
const JOBS = [JOB_PULL, JOB_VALIDATION, JOB_TRANSFER, JOB_CLEANUP] as const;
const DAYS = [1, 2, 3, 4, 5, 6, 7];
const SETTING_KEYS: (keyof FlowSettings)[] = ["FlowWaitMinutes", "FlowRefreshWaitMinutes"];
const SQL = "SQL";
const errorText = (e: unknown) => (e instanceof ApiError ? e.message : T.failed);
const STATE_TONE: Record<string, BadgeTone> = { [FLOW_DONE]: "ok", [FLOW_STOPPED]: "critical", [FLOW_NOT_STARTED]: "critical" };

const transferText = (f: Flow) => (f.transfer_mode === MODE_PARTIAL ? `${MODE_PARTIAL} · ${f.transfer_groups.join(", ")}` : MODE_FULL);

function emptyBody(): FlowBody {
  return { name: "", is_active: true, run_time: "02:00", days: [1, 2, 3, 4, 5], pull_scope: SCOPE_ALL, pull_tables: [], transfer_mode: MODE_FULL, transfer_groups: [], cleanup: false };
}

function Step({ no, title, required, children }: { no: number; title: string; required?: boolean; children: ReactNode }) {
  return (
    <section className="sc-flow-step" aria-label={title}>
      <h3>{`${no} · ${title}`}{required && <span className="sc-req" aria-hidden="true">*</span>}</h3>
      <div className="sc-flow-step-body">{children}</div>
    </section>
  );
}

/** Başlıktaki "tümünü seç": bir kısmı seçiliyse yarım işaret. */
function GroupCheck({ label, checked, partial, disabled, onChange }: { label: string; checked: boolean; partial: boolean; disabled: boolean; onChange(v: boolean): void }) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = partial;
  }, [partial]);
  return <input ref={ref} type="checkbox" aria-label={label} checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />;
}

/** Zamanlanmış iş penceresi (System owner; K-164, K-166, mockup akis-formu-v2). Bütün kontroller tek hizada; yıldız adım adında; yer tutucu yok.
 *  Kısmi veri aktarımında grup seçilince ya da kaldırılınca Veri çekimi o grubun SQL tablolarını ekler ya da çıkarır. */
export function FlowDialog({ flow, options, onClose, onSaved }: { flow: Flow | null; options: FlowOptions; onClose(): void; onSaved(r: FlowsResponse): void }) {
  const [body, setBody] = useState<FlowBody>(() => (flow ? {
    name: flow.name, is_active: flow.is_active, run_time: flow.run_time, days: flow.days, pull_scope: flow.pull_scope, pull_tables: flow.pull_tables,
    transfer_mode: flow.transfer_mode, transfer_groups: flow.transfer_groups, cleanup: flow.cleanup,
  } : emptyBody()));
  const [pullTouched, setPullTouched] = useState(Boolean(flow));
  const [error, setError] = useState<string | null>(null);
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const set = (patch: Partial<FlowBody>) => setBody((b) => ({ ...b, ...patch }));
  const groupSql = (groups: string[]) => options.groups.filter((g) => groups.includes(g.name)).flatMap((g) => g.sql_tables);

  const toggleGroup = (name: string, on: boolean) => {
    const tables = groupSql([name]);
    set({
      transfer_groups: on ? [...body.transfer_groups, name] : body.transfer_groups.filter((x) => x !== name),
      pull_scope: SCOPE_SELECTED,
      pull_tables: on ? [...new Set([...body.pull_tables, ...tables])] : body.pull_tables.filter((t) => !tables.includes(t)),
    });
  };
  const setMode = (mode: string) => {
    if (pullTouched) set({ transfer_mode: mode });
    else if (mode === MODE_FULL) set({ transfer_mode: mode, pull_scope: SCOPE_ALL, pull_tables: [] });
    else set({ transfer_mode: mode, pull_scope: SCOPE_SELECTED, pull_tables: groupSql(body.transfer_groups) });
  };
  const toggleTables = (tables: string[], on: boolean) => {
    setPullTouched(true);
    set({ pull_tables: on ? [...new Set([...body.pull_tables, ...tables])] : body.pull_tables.filter((t) => !tables.includes(t)) });
  };

  const save = async () => {
    setBusy(true);
    setError(null);
    setProblems({});
    try {
      onSaved(flow ? await flowsApi.update(flow.id, body) : await flowsApi.create(body));
    } catch (e) {
      if (e instanceof ApiError && e.details.length) setProblems(Object.fromEntries(e.details.map((d) => [d.field ?? "", d.problem])));
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const fieldError = (key: string) => problems[key] && <p className="sc-field-error">{problems[key]}</p>;

  return (
    <Dialog title={flow ? T.editTitle(flow.name) : T.newFlow} onClose={onClose} onSubmit={() => void save()} submitLabel={T.save} busy={busy} xwide className="sc-dialog--flow"
            titleAside={(
              <span className="sc-dialog-aside">
                <span>{T.active}</span>
                <SwitchCell label={T.active} checked={body.is_active} editable size="md" onToggle={(v) => set({ is_active: v })} />
              </span>
            )}>
      {error && <Alert tone="error">{error}</Alert>}
      <Step no={1} title={T.stepDefinition} required>
        <input className="sc-input" aria-label={`${T.name} (${T.required})`} value={body.name} maxLength={100} onChange={(e) => set({ name: e.target.value })} />
        {fieldError("name")}
      </Step>
      <Step no={2} title={T.stepSchedule} required>
        <div className="sc-flow-time">
          <input className="sc-input sc-input--time" aria-label={`${T.runTime} (${T.required})`} value={body.run_time} maxLength={5} onChange={(e) => set({ run_time: e.target.value })} />
          <div className="sc-day-picker" role="group" aria-label={T.days}>
            {DAYS.map((d) => {
              const on = body.days.includes(d);
              return (
                <button key={d} type="button" aria-pressed={on} className={on ? "is-on" : undefined}
                        onClick={() => set({ days: on ? body.days.filter((x) => x !== d) : [...body.days, d].sort() })}>{T.dayNames[d - 1]}</button>
              );
            })}
          </div>
        </div>
        {fieldError("run_time")}{fieldError("days")}
      </Step>
      <Step no={3} title={T.stepPull}>
        <div className="sc-segment-fill">
          <Segment<string> label={T.stepPull} hideLabel value={body.pull_scope} onChange={(v) => { setPullTouched(true); set({ pull_scope: v }); }}
                           options={[{ value: SCOPE_ALL, label: T.pullAll }, { value: SCOPE_SELECTED, label: T.pullSelected }]} />
        </div>
        {body.pull_scope === SCOPE_SELECTED && (
          <div className="sc-group-rows">
            {options.pull_sets.map((s) => {
              const selectable = s.tables.filter((t) => t.method === SQL).map((t) => t.entity);
              const chosen = selectable.filter((t) => body.pull_tables.includes(t));
              return (
                <div key={s.name} className="sc-group-row" role="group" aria-label={s.name}>
                  <span className="sc-group-name">
                    <GroupCheck label={T.selectAll(s.name)} checked={selectable.length > 0 && chosen.length === selectable.length}
                                partial={chosen.length > 0 && chosen.length < selectable.length} disabled={!selectable.length}
                                onChange={(on) => toggleTables(selectable, on)} />
                    <span>{s.name}</span>
                    <span className="sc-pull-count">{`${chosen.length} / ${selectable.length}`}</span>
                  </span>
                  <span className="sc-chips">
                    {s.tables.map((t) => {
                      const excel = t.method !== SQL;
                      const on = body.pull_tables.includes(t.entity);
                      return (
                        <button key={t.entity} type="button" className={`sc-chip-toggle${on ? " is-on" : ""}${excel ? " is-excel" : ""}`} disabled={excel}
                                aria-pressed={excel ? undefined : on} onClick={() => toggleTables([t.entity], !on)}>
                          {t.name}{excel && <span className="sc-mini-tag">{T.excel}</span>}
                        </button>
                      );
                    })}
                  </span>
                </div>
              );
            })}
          </div>
        )}
        {fieldError("pull_tables")}
      </Step>
      <Step no={4} title={T.stepTransfer}>
        <div className="sc-segment-fill">
          <Segment<string> label={T.stepTransfer} hideLabel value={body.transfer_mode} onChange={setMode}
                           options={[{ value: MODE_FULL, label: T.full }, { value: MODE_PARTIAL, label: T.partial }]} />
        </div>
        {body.transfer_mode === MODE_PARTIAL && (
          <div className="sc-group-rows">
            {options.groups.map((g) => {
              const on = body.transfer_groups.includes(g.name);
              return (
                <label key={g.name} className={`sc-group-row${on ? " is-on" : ""}`}>
                  <span className="sc-group-name">
                    <input type="checkbox" aria-label={T.transferGroup(g.name)} checked={on} onChange={(e) => toggleGroup(g.name, e.target.checked)} />
                    <span>{g.name}</span>
                  </span>
                  <span className="sc-group-tables">{g.tables.map((t) => t.name).join(" · ")}</span>
                </label>
              );
            })}
          </div>
        )}
        {fieldError("transfer_groups")}
      </Step>
      <Step no={5} title={T.stepCleanup}>
        <span className="sc-flow-inline">
          <SwitchCell label={`${T.stepCleanup}: ${T.afterTransfer}`} checked={body.cleanup} editable size="md" onToggle={(v) => set({ cleanup: v })} />
          <span>{T.afterTransfer}</span>
        </span>
      </Step>
    </Dialog>
  );
}

/** Admin'in salt okunur özeti. */
function FlowSummary({ flow, options, onClose }: { flow: Flow; options: FlowOptions; onClose(): void }) {
  const names = new Map(options.tables.map((t) => [t.entity, t.name]));
  const rows: [string, string][] = [
    [T.stepSchedule, `${flow.days_text} ${flow.run_time}`],
    [T.stepPull, flow.pull_scope === SCOPE_ALL ? T.pullAll : flow.pull_tables.map((t) => names.get(t) ?? t).join(", ")],
    [T.stepTransfer, transferText(flow)], [T.stepCleanup, flow.cleanup ? T.yes : T.no], [T.active, flow.is_active ? T.yes : T.no],
    [T.updated, `${formatDateTime(serverDate(flow.updated_at))} · ${flow.updated_by_name}`],
  ];
  return (
    <Dialog title={T.editTitle(flow.name)} onClose={onClose} onSubmit={onClose} submitLabel={tr.ui.close} noCancel>
      <dl className="sc-detail-rows">
        {rows.map(([k, v]) => <div key={k} style={{ display: "contents" }}><dt>{k}</dt><dd>{v}</dd></div>)}
      </dl>
    </Dialog>
  );
}

type Selected = { id: number; name: string };
const tabsOf = (): readonly DetailTab<"history">[] => [{ value: "history", label: T.history, count: 0 }];
const keyOf = (s: Selected) => s.id;

function LastState({ row }: { row: Row }) {
  if (!row.LastState) return null;
  const state = String(row.LastState);
  const at = row.LastAt ? ` · ${formatDateTime(serverDate(String(row.LastAt)))}` : "";
  const reason = row.LastReason ? String(row.LastReason) : null;
  return <Tooltip content={reason} focusable={Boolean(reason)}><Badge tone={STATE_TONE[state] ?? "neutral"}>{`${state}${at}`}</Badge></Tooltip>;
}

const CELLS = { LastState: (_v: unknown, row: Row) => <LastState row={row} /> };
/** Liste ekrana sığar (U-kuralı, K-166 görsel kontrol): varsayılan genişliklerle 8 kolon 1440 px'te taşıyordu. */
const FLOW_HINTS: FieldHints = { Name: { width: 13 }, Schedule: { width: 10 }, PullText: { width: 9 }, TransferText: { width: 11 }, Cleanup: { width: 6 },
  NextRunAt: { width: 10 }, LastState: { width: 15 }, IsActive: { width: 6 } };

/** Bekleme süreleri penceresi (K-171): iki süre, ipuçları alanın adında; Kaydet değişmeyince ya da sınır dışındayken pasif. */
function WaitDialog({ data, writeReason, onClose, onSaved }: { data: FlowsResponse; writeReason: string | null; onClose(): void; onSaved(r: FlowsResponse): void }) {
  const [values, setValues] = useState<Record<string, string>>(() => Object.fromEntries(SETTING_KEYS.map((k) => [k, formatNumber(data.settings[k], 0)])));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const parsed = Object.fromEntries(SETTING_KEYS.map((k) => [k, parseTrNumber(values[k] ?? "")]));
  const changed = SETTING_KEYS.filter((k) => parsed[k] !== data.settings[k]);
  const invalidOf = (k: keyof FlowSettings) => parsed[k] === null || parsed[k]! < data.limits[k].min || parsed[k]! > data.limits[k].max;
  const invalid = SETTING_KEYS.some(invalidOf);
  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      onSaved(await flowsApi.saveSettings(Object.fromEntries(changed.map((k) => [k, parsed[k]]))));
      emitNotice(T.settingsSaved);
    } catch (e) {
      setError(errorText(e));
      setSaving(false);
    }
  };
  return (
    <Dialog title={T.waitTitle} onClose={onClose} onSubmit={() => void save()} submitLabel={T.save} busy={saving} submitDisabled={!changed.length || invalid} submitReason={writeReason}>
      {error && <Alert tone="error">{error}</Alert>}
      {SETTING_KEYS.map((k) => (
        <TextField key={k} label={T.settings[k]} tip={T.settingTips[k]} inputMode="numeric" value={values[k] ?? ""} disabled={Boolean(writeReason)}
                   error={invalidOf(k) ? tr.systemOwner.limit(data.limits[k].min, data.limits[k].max) : undefined}
                   onChange={(v) => setValues((s) => ({ ...s, [k]: v }))} />
      ))}
    </Dialog>
  );
}

/** Sekmenin içeriği. initialFlow: çipteki "Geçmiş" ile gelen işin geçmişi açık gelir. lead: Sistem ayarları'nın sekmeleri (şeridin başında, K-171). */
export function ScheduledJobs({ initialFlow, lead }: { initialFlow?: number | null; lead?: ReactNode }) {
  const [data, setData] = useState<FlowsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [waiting, setWaiting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [menu, setMenu] = useState<{ row: Row; anchor: HTMLElement; extra?: MenuAction[] } | null>(null);
  const [editing, setEditing] = useState<Flow | "new" | null>(null);
  const [viewing, setViewing] = useState<Flow | null>(null);
  const [confirm, setConfirm] = useState<Flow | null>(null);
  const { selected, toggle, close } = useMasterDetail<Selected, "history">(tabsOf, keyOf);
  const opened = useRef(false);
  const flowStatus = useFlowStatus();
  const reload = useCallback(() => setReloadKey((k) => k + 1), []);
  useJobRefresh(JOBS, reload);

  const show = useCallback((r: FlowsResponse) => setData(r), []);
  useEffect(() => {
    const ctrl = new AbortController();
    flowsApi.list(ctrl.signal).then(show).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, [show]);
  const running = flowStatus.status?.running;
  const runKey = running ? `${running.id}:${running.state}:${running.step}` : "";
  const first = useRef(true);
  useEffect(() => {  // zamanlanmış iş başlayınca, adım değişince ve bitince liste tazelenir (son çalışma, sıradaki)
    if (first.current) {
      first.current = false;
      return;
    }
    reload();
  }, [runKey, reload]);
  useEffect(() => {
    if (opened.current || !data || !initialFlow) return;
    const f = data.flows.find((x) => x.id === initialFlow);
    if (f) toggle({ id: f.id, name: f.name });
    opened.current = true;
  }, [data, initialFlow, toggle]);

  const canEdit = Boolean(data?.can_edit);
  const runNow = async (f: Flow) => {
    setConfirm(null);
    setError(null);
    try {
      await flowsApi.runNow(f.id);
      flowStatus.refresh();
      reload();
    } catch (e) {
      setError(errorText(e));
    }
  };

  const flowOf = (row: Row) => data?.flows.find((f) => f.id === Number(row.Id)) ?? null;
  const writeReason = canEdit ? null : forbiddenReason(92, "write");
  const runState = writeReason ? { allowed: false, reason: writeReason } : data?.running ? { allowed: false, reason: T.alreadyRunning(data.running.flow_name) } : ALLOWED;
  const rowMenu: RowMenuSpec = useMemo(() => ({
    label: (row: Row) => T.rowMenu(String(row.Name)),
    onOpen: (row: Row, anchor: HTMLElement, extra?: MenuAction[]) => setMenu({ row, anchor, extra }),
  }), []);
  const rowProps = useCallback((row: Row): HTMLAttributes<HTMLTableRowElement> => {
    const open = () => toggle({ id: Number(row.Id), name: String(row.Name) });
    return { className: "is-clickable", tabIndex: 0, onClick: open, onKeyDown: (e) => { if (e.key === "Enter") open(); } };
  }, [toggle]);

  return (
    <div className="sc-flows-tab">
      {error && <Alert tone="error">{error}</Alert>}
      <MasterDetail<"history">
        id="scheduled-jobs"
        master={(
          <DataTable list="flows" rowMenu={rowMenu} rowProps={rowProps} cellRender={CELLS} fieldHints={FLOW_HINTS} reloadKey={reloadKey} selectedRowId={selected?.id ?? null}
                     toolbarLead={(
                       <>
                         {lead}
                         <Button variant="primary" disabledReason={writeReason} onClick={() => setEditing("new")}>{T.newFlow}</Button>
                         <Button variant="secondary" disabled={!data} onClick={() => setWaiting(true)}>{T.waitTitle}</Button>
                       </>
                     )} />
        )}
        onClose={close} hideTitle
        detail={selected ? {
          title: T.historyOf(selected.name), tabsLabel: T.history, tabs: tabsOf(), tab: "history", onTab: () => undefined,
          // Kartın şeridi tablo standardında (K-173): sağda tablo düğmeleri, Büyüt ve ✕
          renderBody: ({ tabs, controls }) => (
            <DataTable key={selected.id} list="flow-runs" baseFilters={[{ field: "FlowId", op: "eq", value: selected.id }]} reloadKey={reloadKey} compact
                       toolbarLead={tabs} toolbarEnd={controls} />
          ),
        } : null} />
      {menu && data && (() => {
        const f = flowOf(menu.row);
        return (
          <RowPopMenu label={T.rowMenu(String(menu.row.Name))} anchor={menu.anchor} onClose={() => setMenu(null)}>
            <MenuActions items={menu.extra} onDone={() => setMenu(null)} />
            <MenuItem label={tr.table.detailItem} state={ALLOWED} onClick={() => { if (!selected || selected.id !== Number(menu.row.Id)) toggle({ id: Number(menu.row.Id), name: String(menu.row.Name) }); setMenu(null); }} />
            {canEdit
              ? <MenuItem label={T.edit} state={ALLOWED} onClick={() => { setEditing(f); setMenu(null); }} />
              : <MenuItem label={T.view} state={ALLOWED} onClick={() => { setViewing(f); setMenu(null); }} />}
            <MenuItem label={T.runNow} state={runState} onClick={() => { setConfirm(f); setMenu(null); }} />
          </RowPopMenu>
        );
      })()}
      {editing && data && (
        <FlowDialog flow={editing === "new" ? null : editing} options={data.options} onClose={() => setEditing(null)}
                    onSaved={(r) => { setEditing(null); show(r); reload(); }} />
      )}
      {waiting && data && <WaitDialog data={data} writeReason={writeReason} onClose={() => setWaiting(false)} onSaved={(r) => { setWaiting(false); show(r); }} />}
      {viewing && data && <FlowSummary flow={viewing} options={data.options} onClose={() => setViewing(null)} />}
      {confirm && (
        <ConfirmDialog title={T.runNowTitle} message={T.runNowMessage(confirm.name, transferText(confirm))} confirmLabel={T.runNow}
                       onCancel={() => setConfirm(null)} onConfirm={() => void runNow(confirm)} />
      )}
    </div>
  );
}

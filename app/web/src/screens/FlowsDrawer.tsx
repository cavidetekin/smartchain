// Zamanlanmış akışlar (ekran 23, fonksiyon 92; K-163). Entegrasyon'un üst şeridindeki düğme sağdan çekmeceyi açar: akışlar listesi,
// satır menüsünde düzenle (Admin'de görüntüle), şimdi çalıştır (System owner, onaylı) ve geçmiş. Akış penceresi adımları sabit sırayla
// gösterir: ad ve zaman → Veri çek → aktarım → ham veri temizliği.
import { MoreHorizontal } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, JOB_PULL, JOB_TRANSFER, JOB_CLEANUP, JOB_VALIDATION } from "../api/client";
import { formatDateTime, serverDate } from "../format";
import { tr } from "../i18n/tr";
import { forbiddenReason } from "../auth/permissions";
import { useFlowStatus } from "../shell/FlowStatus";
import { useJobRefresh } from "../shell/useJobRefresh";
import { DataTable } from "../table/DataTable";
import { type LocalColumn, LocalTable } from "../table/LocalTable";
import { Alert, Badge, type BadgeTone, Button, Checkbox, ConfirmDialog, Dialog, Drawer, RadioGroup, TextField, Tooltip } from "../ui";
import { type Flow, type FlowBody, type FlowOptions, type FlowRun, type FlowsResponse, flowsApi, FLOW_DONE, FLOW_STOPPED, FLOW_NOT_STARTED, MODE_FULL, MODE_PARTIAL,
  SCOPE_ALL, SCOPE_SELECTED } from "./flowsApi";
import { MenuItem, RowPopMenu } from "./RowPopMenu";

const T = tr.flows;
const ALLOWED = { allowed: true };
const JOBS = [JOB_PULL, JOB_VALIDATION, JOB_TRANSFER, JOB_CLEANUP] as const;
const DAYS = [1, 2, 3, 4, 5, 6, 7];
const errorText = (e: unknown) => (e instanceof ApiError ? e.message : T.failed);
const when = (iso: string | null) => (iso ? formatDateTime(serverDate(iso)) : "");
const STATE_TONE: Record<string, BadgeTone> = { [FLOW_DONE]: "ok", [FLOW_STOPPED]: "critical", [FLOW_NOT_STARTED]: "critical" };

export function RunState({ run }: { run: FlowRun | null }) {
  if (!run) return <span className="sc-muted">{T.neverRan}</span>;
  const tone = STATE_TONE[run.state] ?? "neutral";
  const text = `${run.state} · ${when(run.ended_at ?? run.started_at ?? run.scheduled_at)}`;
  return <Tooltip content={run.reason} focusable={Boolean(run.reason)}><Badge tone={tone}>{text}</Badge></Tooltip>;
}

const pullText = (f: Flow, options: FlowOptions) => {
  if (f.pull_scope === SCOPE_ALL) return T.pullAll;
  const names = new Map(options.tables.map((t) => [t.entity, t.name]));
  return f.pull_tables.map((t) => names.get(t) ?? t).join(", ");
};
const transferText = (f: Flow) => (f.transfer_mode === MODE_PARTIAL ? `${MODE_PARTIAL} · ${f.transfer_groups.join(", ")}` : MODE_FULL);

function emptyBody(): FlowBody {
  return { name: "", is_active: true, run_time: "02:00", days: [1, 2, 3, 4, 5], pull_scope: SCOPE_ALL, pull_tables: [], transfer_mode: MODE_FULL, transfer_groups: [], cleanup: false };
}

function Step({ no, title, children }: { no: number; title: string; children: ReactNode }) {
  return (
    <fieldset className="sc-flow-step">
      <legend className="sc-field-label">{`${no} · ${title}`}</legend>
      {children}
    </fieldset>
  );
}

/** Akış penceresi (System owner). Kısmi aktarımda Veri çek kapsamı varsayılan olarak seçilen grupların SQL tabloları. */
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
  const toggle = (list: string[], v: string, on: boolean) => (on ? [...list, v] : list.filter((x) => x !== v));
  const names = useMemo(() => new Map(options.tables.map((t) => [t.entity, t.name])), [options]);
  const groupSql = (groups: string[]) => options.groups.filter((g) => groups.includes(g.name)).flatMap((g) => g.sql_tables);

  const setGroups = (groups: string[]) => {
    set({ transfer_groups: groups, ...(!pullTouched ? { pull_scope: SCOPE_SELECTED, pull_tables: groupSql(groups) } : {}) });
  };
  const setMode = (mode: string) => {
    if (mode === MODE_FULL && !pullTouched) set({ transfer_mode: mode, pull_scope: SCOPE_ALL, pull_tables: [] });
    else if (mode === MODE_PARTIAL && !pullTouched) set({ transfer_mode: mode, pull_scope: SCOPE_SELECTED, pull_tables: groupSql(body.transfer_groups) });
    else set({ transfer_mode: mode });
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

  return (
    <Dialog title={flow ? T.editTitle(flow.name) : T.newTitle} onClose={onClose} onSubmit={() => void save()} submitLabel={T.save} busy={busy} wide>
      {error && <Alert tone="error">{error}</Alert>}
      <Step no={1} title={T.stepTime}>
        <TextField label={T.name} value={body.name} onChange={(v) => set({ name: v })} error={problems.name} required />
        <TextField label={T.runTime} help={T.runTimeHelp} value={body.run_time} onChange={(v) => set({ run_time: v })} error={problems.run_time} required />
        <div className="sc-flow-days" role="group" aria-label={T.days}>
          {DAYS.map((d) => (
            <Checkbox key={d} label={T.dayNames[d - 1]} checked={body.days.includes(d)}
                      onChange={(on) => set({ days: on ? [...body.days, d].sort() : body.days.filter((x) => x !== d) })} />
          ))}
        </div>
        {problems.days && <p className="sc-field-error">{problems.days}</p>}
      </Step>
      <Step no={2} title={T.stepPull}>
        <RadioGroup label={T.pullScope} value={body.pull_scope} options={[{ value: SCOPE_ALL, label: T.pullAll }, { value: SCOPE_SELECTED, label: T.pullSelected }]}
                    onChange={(v) => { setPullTouched(true); set({ pull_scope: v }); }} />
        {body.pull_scope === SCOPE_SELECTED && (
          options.sql_tables.length ? (
            <div className="sc-flow-tables">
              {options.sql_tables.map((t) => (
                <Checkbox key={t} label={names.get(t) ?? t} checked={body.pull_tables.includes(t)}
                          onChange={(on) => { setPullTouched(true); set({ pull_tables: toggle(body.pull_tables, t, on) }); }} />
              ))}
            </div>
          ) : <p className="sc-muted">{T.noSqlTables}</p>
        )}
        {problems.pull_tables && <p className="sc-field-error">{problems.pull_tables}</p>}
        <p className="sc-muted">{T.excelNote}</p>
      </Step>
      <Step no={3} title={T.stepTransfer}>
        <RadioGroup label={T.transferMode} value={body.transfer_mode} options={[{ value: MODE_FULL, label: T.full }, { value: MODE_PARTIAL, label: T.partial }]} onChange={setMode} />
        {body.transfer_mode === MODE_PARTIAL && (
          <div className="sc-flow-tables">
            {options.groups.map((g) => (
              <Checkbox key={g.name} label={`${g.name} (${g.tables.map((t) => t.name).join(", ")})`} checked={body.transfer_groups.includes(g.name)}
                        onChange={(on) => setGroups(toggle(body.transfer_groups, g.name, on))} />
            ))}
          </div>
        )}
        {problems.transfer_groups && <p className="sc-field-error">{problems.transfer_groups}</p>}
        <p className="sc-muted">{T.stopNote}</p>
      </Step>
      <Step no={4} title={T.stepCleanup}>
        <Checkbox label={T.cleanup} checked={body.cleanup} onChange={(on) => set({ cleanup: on })} />
      </Step>
      <Checkbox label={T.active} checked={body.is_active} onChange={(on) => set({ is_active: on })} />
    </Dialog>
  );
}

/** Admin'in salt okunur görünümü. */
function FlowSummary({ flow, options, onClose }: { flow: Flow; options: FlowOptions; onClose(): void }) {
  const rows: [string, string][] = [
    [T.stepTime, `${flow.days_text} ${flow.run_time}`], [T.stepPull, pullText(flow, options)], [T.stepTransfer, transferText(flow)],
    [T.stepCleanup, flow.cleanup ? T.yes : T.no], [T.active, flow.is_active ? T.yes : T.no], [T.updated, `${when(flow.updated_at)} · ${flow.updated_by_name}`],
  ];
  return (
    <Dialog title={flow.name} onClose={onClose} onSubmit={onClose} submitLabel={tr.ui.close} noCancel>
      <dl className="sc-flow-summary">
        {rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}
      </dl>
    </Dialog>
  );
}

export function FlowsDrawer({ initialHistory, onClose }: { initialHistory?: number | null; onClose(): void }) {
  const [data, setData] = useState<FlowsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [menu, setMenu] = useState<{ flow: Flow; anchor: HTMLElement } | null>(null);
  const [editing, setEditing] = useState<Flow | "new" | null>(null);
  const [viewing, setViewing] = useState<Flow | null>(null);
  const [confirm, setConfirm] = useState<Flow | null>(null);
  const [history, setHistory] = useState<number | null>(initialHistory ?? null);
  const flowStatus = useFlowStatus();
  const reload = useCallback(() => setReloadKey((k) => k + 1), []);
  useJobRefresh(JOBS, reload);

  useEffect(() => {
    const ctrl = new AbortController();
    flowsApi.list(ctrl.signal).then(setData).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, [reloadKey, flowStatus.status]);

  const canEdit = Boolean(data?.can_edit);
  const writeState = canEdit ? ALLOWED : { allowed: false, reason: forbiddenReason(92, "write") };
  const runState = !canEdit ? writeState : data?.running ? { allowed: false, reason: T.alreadyRunning(data.running.flow_name) } : ALLOWED;
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

  const columns: LocalColumn<Flow>[] = data ? [
    { key: "name", label: T.name, value: (f) => f.name },
    { key: "time", label: T.time, value: (f) => `${f.run_time} ${f.days_text}`, render: (f) => `${f.days_text} ${f.run_time}` },
    { key: "pull", label: T.stepPull, wrap: true, value: (f) => pullText(f, data.options) },
    { key: "transfer", label: T.stepTransfer, value: (f) => transferText(f) },
    { key: "cleanup", label: T.stepCleanup, value: (f) => (f.cleanup ? T.yes : T.no) },
    { key: "active", label: T.active, value: (f) => (f.is_active ? T.yes : T.no), render: (f) => <Badge tone={f.is_active ? "ok" : "neutral"}>{f.is_active ? T.yes : T.no}</Badge> },
    { key: "next", label: T.next, value: (f) => f.next_at, render: (f) => when(f.next_at) },
    { key: "last", label: T.last, value: (f) => f.last?.scheduled_at ?? null, render: (f) => <RunState run={f.last} /> },
    { key: "menu", label: "", render: (f) => (
      <button type="button" className="sc-icon-btn" aria-label={T.rowMenu(f.name)} onClick={(e) => setMenu({ flow: f, anchor: e.currentTarget })}>
        <MoreHorizontal aria-hidden="true" width={16} height={16} />
      </button>
    ) },
  ] : [];

  const historyFlow = data?.flows.find((f) => f.id === history) ?? null;
  const subtitle = data?.running ? T.runningNow(data.running.flow_name, data.running.state) : data ? T.waits(data.settings.FlowWaitMinutes, data.settings.FlowRefreshWaitMinutes) : null;
  return (
    <Drawer title={T.title} subtitle={subtitle} onClose={onClose}
            actions={<Button variant="primary" disabledReason={canEdit ? null : forbiddenReason(92, "write")} onClick={() => setEditing("new")}>{T.newFlow}</Button>}>
      {error && <Alert tone="error">{error}</Alert>}
      {data && (data.flows.length ? <LocalTable label={T.title} columns={columns} rows={data.flows} rowKey={(f) => String(f.id)} /> : <p className="sc-muted">{T.none}</p>)}
      {historyFlow && (
        <section className="sc-flow-history" aria-label={T.historyOf(historyFlow.name)}>
          <h2>{T.historyOf(historyFlow.name)}</h2>
          <DataTable list="flow-runs" baseFilters={[{ field: "FlowId", op: "eq", value: historyFlow.id }]} reloadKey={reloadKey} fit />
        </section>
      )}
      {menu && data && (
        <RowPopMenu label={T.rowMenu(menu.flow.name)} anchor={menu.anchor} onClose={() => setMenu(null)}>
          {canEdit
            ? <MenuItem label={T.edit} state={ALLOWED} onClick={() => { setEditing(menu.flow); setMenu(null); }} />
            : <MenuItem label={T.view} state={ALLOWED} onClick={() => { setViewing(menu.flow); setMenu(null); }} />}
          <MenuItem label={T.runNow} state={runState} onClick={() => { setConfirm(menu.flow); setMenu(null); }} />
          <MenuItem label={T.history} state={ALLOWED} onClick={() => { setHistory(menu.flow.id); setMenu(null); }} />
        </RowPopMenu>
      )}
      {editing && data && (
        <FlowDialog flow={editing === "new" ? null : editing} options={data.options} onClose={() => setEditing(null)}
                    onSaved={(r) => { setEditing(null); setData(r); }} />
      )}
      {viewing && data && <FlowSummary flow={viewing} options={data.options} onClose={() => setViewing(null)} />}
      {confirm && (
        <ConfirmDialog title={T.runNowTitle} message={T.runNowMessage(confirm.name, transferText(confirm))} confirmLabel={T.runNow}
                       onCancel={() => setConfirm(null)} onConfirm={() => void runNow(confirm)} />
      )}
    </Drawer>
  );
}

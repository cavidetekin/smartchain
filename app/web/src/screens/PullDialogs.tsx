// Veri çek pencereleri (ekran 02, fonksiyon 01; K-130, K-132): onay, sonuç, çekim anahtarı. Durum çipi renkleri K-132; "Okunacak" durum değildir, çip olmaz.
import { useEffect, useMemo, useState } from "react";

import { ApiError, JOB_DONE, JOB_FAILED } from "../api/client";
import { formatDateTime, formatNumber, serverDate } from "../format";
import { tr } from "../i18n/tr";
import { DataTable } from "../table/DataTable";
import { type LocalColumn, LocalTable } from "../table/LocalTable";
import { Alert, Badge, Button, Checkbox, ConfirmDialog, Dialog, TextareaField, Tooltip } from "../ui";
import type { BadgeTone } from "../ui/Badge";
import { integrationApi, METHOD_SQL, type PullPlan, type PullPlanRow, type PullResult, type PullTable } from "./integrationApi";
import { FINDING_CELLS, FINDING_WRAP } from "./ImportDialog";

const T = tr.pull;
const POLL_MS = 2000;
const READ_STATE = "Okunacak";
const NO_NEW = "Yeni veri yok";
const errorText = (e: unknown) => (e instanceof ApiError ? e.message : T.failed);
const count = (v: number | null) => (v === null ? "—" : formatNumber(v, 0));

const TONES: Record<string, BadgeTone> = {
  "Alındı": "ok", "Uyumlu": "ok", "Uyarılı": "risk", "Tamamlanmadı": "risk", "Hata": "critical", "Hatalı": "critical",
  "Atlandı": "neutral", [NO_NEW]: "neutral", "Veri güncellemesi devam ediyor": "neutral",
};

/** Durum çipi; neden ipucunda. */
export function StateChip({ state, reason }: { state: string | null; reason?: string | null }) {
  if (!state || state === READ_STATE) return null;
  return <Tooltip content={reason} focusable={Boolean(reason)}><Badge tone={TONES[state] ?? "neutral"}>{state}</Badge></Tooltip>;
}

export function PullStartDialog({ entity, onClose, onStarted }: { entity?: string; onClose(): void; onStarted(jobId: number): void }) {
  const [plan, setPlan] = useState<PullPlan | null>(null);
  const [anyway, setAnyway] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    integrationApi.pullPlan(ctrl.signal).then(setPlan).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, []);

  const rows = useMemo(() => (plan?.tables ?? []).filter((t) => t.method === METHOD_SQL && (!entity || t.entity === entity)), [plan, entity]);
  const chosen = rows.filter((t) => t.state === READ_STATE || (t.state === NO_NEW && anyway.has(t.entity))).map((t) => t.entity);

  const toggle = (name: string, on: boolean) => setAnyway((old) => {
    const next = new Set(old);
    if (on) next.add(name);
    else next.delete(name);
    return next;
  });
  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      onStarted((await integrationApi.startPull(chosen, chosen.filter((name) => anyway.has(name)))).job_id);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };

  const columns: LocalColumn<PullPlanRow>[] = [
    { key: "name", label: T.table, value: (t) => t.name },
    { key: "source", label: T.source, value: (t) => t.source },
    { key: "state", label: T.state, value: (t) => t.state, render: (t) => <StateChip state={t.state} reason={t.reason} /> },
    { key: "anyway", label: T.readAnyway, render: (t) => (t.state === NO_NEW ? <Checkbox label={T.readAnyway} checked={anyway.has(t.entity)} onChange={(on) => toggle(t.entity, on)} /> : null) },
  ];

  return (
    <Dialog title={T.startTitle} subtitle={entity ? rows[0]?.name : undefined} onClose={onClose} onSubmit={() => void start()} submitLabel={T.startCount(chosen.length)}
            submitDisabled={!plan || chosen.length === 0} busy={busy} wide>
      {error && <Alert tone="error">{error}</Alert>}
      {plan && <LocalTable label={T.startTitle} columns={columns} rows={rows} rowKey={(t) => t.entity} />}
      {plan?.last && <p className="sc-muted">{T.last(formatDateTime(serverDate(plan.last.at)), plan.last.by)}</p>}
    </Dialog>
  );
}

export function PullResultDialog({ jobId, onClose, onRetry, onChanged }: { jobId: number; onClose(): void; onRetry(jobId: number): void; onChanged(): void }) {
  const [result, setResult] = useState<PullResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [findingsOf, setFindingsOf] = useState<{ name: string; batch: number } | null>(null);
  const ended = result?.status === JOB_DONE || result?.status === JOB_FAILED;

  useEffect(() => {
    const ctrl = new AbortController();
    const load = () => integrationApi.pullResult(jobId, ctrl.signal).then(setResult).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    void load();
    if (ended) return () => ctrl.abort();
    const timer = setInterval(() => void load(), POLL_MS);
    return () => {
      clearInterval(timer);
      ctrl.abort();
    };
  }, [jobId, ended]);

  useEffect(() => {
    if (ended) onChanged();
  }, [ended, onChanged]);

  const retry = async (entity: string) => {
    setError(null);
    try {
      onRetry((await integrationApi.startPull([entity], [])).job_id);
    } catch (e) {
      setError(errorText(e));
    }
  };
  const canRetry = (t: PullTable) => ended && (t.status === "Hata" || t.status === "Tamamlanmadı");
  const hasFindings = (t: PullTable) => Boolean(t.batch_id && t.errors);

  const columns: LocalColumn<PullTable>[] = [
    { key: "name", label: T.table, value: (t) => t.name },
    { key: "source", label: T.source, value: (t) => t.source },
    { key: "read", label: T.read, numeric: true, value: (t) => t.read, render: (t) => count(t.read) },
    { key: "valid", label: T.valid, numeric: true, value: (t) => t.valid, render: (t) => count(t.valid) },
    { key: "errors", label: T.errors, numeric: true, value: (t) => t.errors, render: (t) => count(t.errors) },
    { key: "status", label: T.state, value: (t) => t.status, render: (t) => <StateChip state={t.status} /> },
    {
      key: "reason", label: T.reason, wrap: true, value: (t) => t.reason,
      render: (t) => (
        <>
          {t.reason ?? ""}
          {t.attempts.map((a) => <div key={a.attempt} className="sc-muted">{T.attempt(a.attempt, formatDateTime(serverDate(a.at)), a.message)}</div>)}
        </>
      ),
    },
    {
      key: "actions", label: T.actions,
      render: (t) => (
        <span className="sc-row-actions">
          {hasFindings(t) && <Button size="sm" variant="secondary" className="sc-btn--row" onClick={() => setFindingsOf({ name: t.name, batch: t.batch_id! })}>{T.findings}</Button>}
          {canRetry(t) && <Button size="sm" variant="secondary" className="sc-btn--row" onClick={() => void retry(t.entity)}>{T.retry}</Button>}
        </span>
      ),
    },
  ];

  return (
    <>
      <Dialog title={T.resultTitle} subtitle={result ? `${result.status}${result.progress ? ` · ${result.progress}` : ""}` : undefined}
              onClose={onClose} onSubmit={onClose} submitLabel={tr.ui.close} noCancel xwide>
        {error && <Alert tone="error">{error}</Alert>}
        {result?.error && <Alert tone="error">{result.error}</Alert>}
        {result && !ended && <p role="status">{T.running}</p>}
        {result && <LocalTable label={T.resultTitle} columns={columns} rows={result.tables} rowKey={(t) => t.entity} />}
      </Dialog>
      {findingsOf && (
        <Dialog title={T.findingsTitle(findingsOf.name)} onClose={() => setFindingsOf(null)} onSubmit={() => setFindingsOf(null)} submitLabel={tr.ui.close} noCancel xwide>
          <div className="sc-import-findings">
            <DataTable list="import-findings" cellRender={FINDING_CELLS} baseFilters={[{ field: "ImportBatchId", op: "eq", value: findingsOf.batch }]} fit wrapFields={FINDING_WRAP} />
          </div>
        </Dialog>
      )}
    </>
  );
}

/** Çekim anahtarı: kapatırken sebep zorunlu, açarken uyarı. Değişiklik tablonun Kaydet'iyle yazılır (K-132). */
export function PullSwitchDialog({ name, enabling, onClose, onConfirm }: { name: string; enabling: boolean; onClose(): void; onConfirm(reason: string): void }) {
  const [reason, setReason] = useState("");
  if (enabling) {
    return <ConfirmDialog title={T.enableTitle(name)} message={T.enableText} confirmLabel={T.enable} onCancel={onClose} onConfirm={() => onConfirm("")} />;
  }
  return (
    <Dialog title={T.disableTitle(name)} subtitle={T.disableText} onClose={onClose} onSubmit={() => onConfirm(reason.trim())} submitLabel={T.disable} submitDisabled={!reason.trim()} danger>
      <TextareaField label={T.reasonLabel} required value={reason} maxLength={400} onChange={setReason} />
    </Dialog>
  );
}

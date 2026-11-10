// Tam aktarım pencereleri (ekran 02, fonksiyon 05; K-149, K-151, K-153): onay ve sonuç. Kısmi aktarım 5.3'te.
import { useEffect, useState } from "react";

import { ApiError, JOB_DONE, JOB_FAILED } from "../api/client";
import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { type LocalColumn, LocalTable } from "../table/LocalTable";
import { Alert, Badge, Dialog } from "../ui";
import { STATUS_READY, transferApi, type TransferPlan, type TransferPlanRow, type TransferResult, type TransferTable } from "./transferApi";

const T = tr.transfer;
const POLL_MS = 2000;
const errorText = (e: unknown) => (e instanceof ApiError ? e.message : T.failed);
const count = (v: number | null) => (v === null ? "—" : formatNumber(v, 0));

export function TransferStartDialog({ onClose, onStarted }: { onClose(): void; onStarted(jobId: number): void }) {
  const [plan, setPlan] = useState<TransferPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    transferApi.plan(ctrl.signal).then(setPlan).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, []);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      onStarted((await transferApi.start()).job_id);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };

  const ready = (plan?.tables ?? []).filter((t) => t.status === STATUS_READY).length;
  const columns: LocalColumn<TransferPlanRow>[] = [
    { key: "name", label: T.table, value: (t) => t.name },
    { key: "current", label: T.currentRows, numeric: true, value: (t) => t.current_rows, render: (t) => count(t.current_rows) },
    { key: "errors", label: T.errorRows, numeric: true, value: (t) => t.error_rows, render: (t) => count(t.error_rows) },
    { key: "status", label: T.state, value: (t) => t.status,
      render: (t) => <Badge tone={t.status === STATUS_READY ? "ok" : "neutral"}>{t.status === STATUS_READY ? T.ready : T.skipped}</Badge> },
    { key: "note", label: T.note, wrap: true, value: (t) => t.note },
  ];

  return (
    <Dialog title={T.startTitle} subtitle={plan ? T.startSubtitle(ready) : undefined} onClose={onClose} onSubmit={() => void start()} submitLabel={T.start}
            submitDisabled={!plan || Boolean(plan.blocked) || ready === 0} busy={busy} xwide className="sc-dialog--pull">
      {error && <Alert tone="error">{error}</Alert>}
      {plan?.blocked && <Alert tone="risk">{plan.blocked.reason}{plan.blocked.tables.length > 0 && ` ${T.blockedTables(plan.blocked.tables.join(", "))}`}</Alert>}
      {plan && <LocalTable label={T.startTitle} columns={columns} rows={plan.tables} rowKey={(t) => t.entity} />}
    </Dialog>
  );
}

export function TransferResultDialog({ jobId, onClose, onChanged }: { jobId: number; onClose(): void; onChanged(): void }) {
  const [result, setResult] = useState<TransferResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ended = result?.status === JOB_DONE || result?.status === JOB_FAILED;

  useEffect(() => {
    const ctrl = new AbortController();
    const load = () => transferApi.result(jobId, ctrl.signal).then(setResult).catch((e: unknown) => {
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

  const columns: LocalColumn<TransferTable>[] = [
    { key: "name", label: T.table, value: (t) => t.name },
    { key: "new", label: T.newRows, numeric: true, value: (t) => t.new, render: (t) => count(t.new) },
    { key: "changed", label: T.changedRows, numeric: true, value: (t) => t.changed, render: (t) => count(t.changed) },
    { key: "closed", label: T.closedRows, numeric: true, value: (t) => t.closed, render: (t) => count(t.closed) },
    { key: "not", label: T.notTransferred, numeric: true, value: (t) => t.not_transferred, render: (t) => count(t.not_transferred) },
    { key: "note", label: T.note, wrap: true, value: (t) => t.note },
  ];
  const subtitle = result ? (result.data_version ? T.resultSubtitle(result.status, result.data_version) : `${result.status}${result.progress ? ` · ${result.progress}` : ""}`) : undefined;

  return (
    <Dialog title={T.resultTitle} subtitle={subtitle} onClose={onClose} onSubmit={onClose} submitLabel={tr.ui.close} noCancel xwide>
      {error && <Alert tone="error">{error}</Alert>}
      {result?.error && <Alert tone="error">{result.error}</Alert>}
      {result && !ended && <p role="status">{T.running}</p>}
      {result && result.tables.length > 0 && <LocalTable label={T.resultTitle} columns={columns} rows={result.tables} rowKey={(t) => t.entity} />}
    </Dialog>
  );
}

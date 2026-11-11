// Veri aktarım geçmişi ve ham veri temizliği (ekran 02, fonksiyon 08 ve 09; K-151, K-156). Sağdan çekmece: üstte son temizlik ve
// "Ham veri temizliği" (yalnız System owner), altında geçmiş aktarımların ortak tablosu; satıra tıklayınca Veri aktarım raporu.
import { type HTMLAttributes, useCallback, useEffect, useState } from "react";

import { ApiError, JOB_CLEANUP, JOB_DONE, JOB_FAILED, JOB_TRANSFER } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can, forbiddenReason } from "../auth/permissions";
import { formatDateTime, formatNumber, serverDate } from "../format";
import { tr } from "../i18n/tr";
import { useJobRefresh } from "../shell/useJobRefresh";
import { DataTable } from "../table/DataTable";
import { type LocalColumn, LocalTable } from "../table/LocalTable";
import type { Row } from "../table/types";
import { Alert, Button, Dialog, Drawer } from "../ui";
import { type CleanupPlan, type CleanupState, type CleanupSummary, cleanupApi } from "./transferApi";

const T = tr.history;
const JOBS = [JOB_TRANSFER, JOB_CLEANUP] as const;
const errorText = (e: unknown) => (e instanceof ApiError ? e.message : T.failed);
const count = (n: number) => formatNumber(n, 0);

export function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${formatNumber(bytes / 1024, 1)} KB`;
  return `${formatNumber(bytes / (1024 * 1024), 1)} MB`;
}

function lastText(state: CleanupState): string {
  const last = state.last;
  if (!last) return T.neverCleaned;
  const when = formatDateTime(serverDate(last.ended_at ?? last.requested_at));
  if (last.status === JOB_FAILED) return T.lastCleanup(when, T.cleanupFailed);
  if (last.status !== JOB_DONE) return T.lastCleanup(when, T.cleanupRunning);
  const r = last.result;
  if (!r || !("batches" in r)) return T.lastCleanup(when, r?.note ?? "");
  return T.lastCleanup(when, T.cleanupCounts(count(r.batches), count(r.rows), count(r.files), formatSize(r.size)));
}

export function TransferHistoryDrawer({ onClose, onOpenReport }: { onClose(): void; onOpenReport(jobId: number): void }) {
  const me = useAuth().me!;
  const canClean = can(me, 9, "write");
  const [state, setState] = useState<CleanupState | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [cleaning, setCleaning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => setReloadKey((k) => k + 1), []);
  useJobRefresh(JOBS, reload);

  useEffect(() => {
    const ctrl = new AbortController();
    cleanupApi.state(ctrl.signal).then(setState).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, [reloadKey]);

  const rowProps = useCallback((row: Row): HTMLAttributes<HTMLTableRowElement> => ({
    className: "is-clickable",
    tabIndex: 0,
    onClick: () => onOpenReport(Number(row.Id)),
    onKeyDown: (e) => {
      if (e.key === "Enter") onOpenReport(Number(row.Id));
    },
  }), [onOpenReport]);

  const retention = state ? (state.retention_days === null ? T.noRetention : T.retention(state.retention_days)) : null;
  return (
    <Drawer title={T.title} subtitle={state && <>{retention} · {lastText(state)}</>} onClose={onClose}
            actions={<Button variant="secondary" disabledReason={canClean ? null : forbiddenReason(9, "write")} onClick={() => setCleaning(true)}>{T.cleanup}</Button>}>
      {error && <Alert tone="error">{error}</Alert>}
      <p className="sc-muted">{T.subtitle}</p>
      <DataTable list="transfer-history" rowProps={rowProps} reloadKey={reloadKey} fit />
      {cleaning && <CleanupDialog onClose={() => setCleaning(false)} onStarted={() => { setCleaning(false); reload(); }} />}
    </Drawer>
  );
}

const PREVIEW_COLUMNS: LocalColumn<CleanupSummary["tables"][number]>[] = [
  { key: "name", label: T.table, value: (t) => t.name },
  { key: "rows", label: T.rows, numeric: true, value: (t) => t.rows, render: (t) => count(t.rows) },
];

/** Onay penceresi (K-156): silinecek parti, satır ve dosya; başlatılamıyorsa nedeni. */
export function CleanupDialog({ onClose, onStarted }: { onClose(): void; onStarted(jobId: number): void }) {
  const [plan, setPlan] = useState<CleanupPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    cleanupApi.plan(ctrl.signal).then(setPlan).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, []);

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      onStarted((await cleanupApi.start()).job_id);
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  };

  const p = plan?.preview;
  const empty = p !== null && p !== undefined && p.batches === 0 && p.rows === 0;
  return (
    <Dialog title={T.cleanupTitle} onClose={onClose} onSubmit={() => void start()} submitLabel={T.cleanupStart} danger
            submitDisabled={!plan || Boolean(plan.blocked) || !p || empty} busy={busy} wide>
      {error && <Alert tone="error">{error}</Alert>}
      {plan?.blocked && <Alert tone="risk">{plan.blocked}</Alert>}
      {p && (
        <>
          <p>{T.warning(p.retention_days)}</p>
          <p><strong>{empty ? T.nothing : T.previewCounts(count(p.batches), count(p.rows), count(p.files), formatSize(p.size))}</strong></p>
          {p.tables.length > 0 && <LocalTable label={T.cleanupTitle} columns={PREVIEW_COLUMNS} rows={p.tables} rowKey={(t) => t.entity} />}
        </>
      )}
    </Dialog>
  );
}

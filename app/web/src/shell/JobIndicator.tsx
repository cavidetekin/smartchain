// İş kuyruğu göstergesi (K-69, fonksiyon 48): açılışta /api/jobs, sonra WebSocket ile canlı.
// Bağlantı koparsa 10 sn'de yeniden bağlanır; bu arada 30 sn'de bir sorgulanır (yedek mod).
// Excel aktarımı çalışırken çip ilerlemeyi yazar ("Excel hazırlanıyor · 120.000 / 142.000 satır"); biten aktarım
// listede indirilir (K-91). Sıradaki işte "İptal": kendi işi herkese (48), başkasının işi Admin ve System owner'a (93);
// "Herkesin işleri" seçeneği yalnız onlarda açık, diğer rollerde pasif ve ipuçlu (K-100).
import { Activity, LoaderCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { useNavigate } from "react-router";

import { api, emitNotice, HEALTH_EVENT, importResultPath, JOB_DONE, JOB_EXPORT, JOB_FAILED, JOB_LOAD, JOB_PRECHECK, JOB_PULL, pullResultPath, type Job } from "../api/client";
import { connect, type ConnectionState, socketUrl } from "../api/socket";
import { useAuth } from "../auth/AuthContext";
import { can, forbiddenReason } from "../auth/permissions";
import { tr } from "../i18n/tr";
import { CancelJobDialog } from "../screens/CancelJobDialog";
import { Checkbox } from "../ui";

export const POLL_MS = 30_000;
export const ALL_POLL_MS = 10_000;  // herkesin işleri WebSocket'le gelmez; panel açıkken sorgulanır
const RUNNING = "Çalışıyor";
const QUEUED = "Sırada";
const CANCELLED = "İptal";
const SYSTEM_OWNER = "System owner";

/** "120.000 / 142.000 satır" → 0,845; okunamazsa null (çubuk çizilmez). */
export function progressRatio(progress: string | null | undefined): number | null {
  const m = /^([\d.]+) \/ ([\d.]+)/.exec(progress ?? "");
  if (!m) return null;
  const [done, all] = [Number(m[1].replaceAll(".", "")), Number(m[2].replaceAll(".", ""))];
  return all > 0 ? Math.min(1, done / all) : null;
}

export function JobIndicator({ onJob }: { onJob?: (job: Job) => void }) {
  const [jobs, setJobs] = useState<Map<number, Job>>(new Map());
  const [conn, setConn] = useState<ConnectionState>("reconnecting");
  const [open, setOpen] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [everyone, setEveryone] = useState<Job[] | null>(null);  // "Herkesin işleri" seçiliyken
  const me = useAuth().me!;
  const navigate = useNavigate();
  const canSeeAll = can(me, 93, "read", false);
  const [cancelling, setCancelling] = useState<Job | null>(null);
  const toldCancelled = useRef(new Set<number>());
  const onJobRef = useRef(onJob);
  useEffect(() => {
    onJobRef.current = onJob;
  });

  const refresh = useCallback(async () => {
    try {
      const r = await api.jobs();
      setJobs(new Map(r.jobs.map((j) => [j.id, j])));
      r.jobs.forEach((j) => onJobRef.current?.(j));
    } catch {
      // bağlantı yok; gösterge son bilinen durumda kalır
    }
  }, []);

  useEffect(() => {
    refresh();
    const handle = connect(
      socketUrl("/api/ws"),  // oturum çerezle (K-97)
      (msg) => {
        if (msg.type === "job") {
          const job = msg.job as Job;
          setJobs((prev) => new Map(prev).set(job.id, job));
          onJobRef.current?.(job);
          // Başkası iptal etti (mesaj yalnız sahibine gelir; kendi iptalinde neden yok, K-107)
          if (job.status === CANCELLED && job.cancel_reason && !toldCancelled.current.has(job.id)) {
            toldCancelled.current.add(job.id);
            emitNotice(tr.jobs.cancelledByOther(job.summary ?? job.job_type, job.cancel_reason));
          }
        } else if (msg.type === "health") {
          window.dispatchEvent(new Event(HEALTH_EVENT));
        }
      },
      (state) => {
        setConn(state);
        if (state === "connected") refresh();
      },
    );
    return () => handle.close();
  }, [refresh]);

  useEffect(() => {
    if (conn === "connected") return;
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [conn, refresh]);

  const showAll = everyone !== null;
  const loadAll = useCallback(async () => {
    try {
      setEveryone((await api.jobs("all")).jobs);
    } catch {
      // 403 tek yerde bildirilir; liste son bilinen hâlde kalır
    }
  }, []);
  useEffect(() => {
    if (!open || !showAll) return;
    const t = setInterval(loadAll, ALL_POLL_MS);
    return () => clearInterval(t);
  }, [open, showAll, loadAll]);

  const afterCancel = async () => {
    await refresh();
    if (showAll) await loadAll();
  };
  const cancel = async (j: Job) => {
    if (j.requested_by !== me.id) {  // başkasının işi: neden zorunlu (K-107)
      setCancelling(j);
      return;
    }
    setDownloadError(null);
    try {
      await api.cancelJob(j.id);
    } catch (e) {
      setDownloadError(e instanceof Error ? e.message : String(e));
    }
    await afterCancel();
  };
  const canCancel = (j: Job) => j.status === QUEUED && j.job_type !== JOB_LOAD && (j.requested_by === me.id
    || (can(me, 93, "write", false) && (!j.is_protected || me.role === SYSTEM_OWNER)));

  const all = [...jobs.values()];
  const running = all.filter((j) => j.status === RUNNING).length;
  const queued = all.filter((j) => j.status === QUEUED).length;
  const delayed = conn === "connected" ? undefined : tr.jobs.delayed;  // sorun yokken metin yok
  const recent = (everyone ?? all).sort((a, b) => b.id - a.id).slice(0, showAll ? 30 : 10);
  const exporting = all.find((j) => j.job_type === JOB_EXPORT && j.status === RUNNING)
    ?? all.find((j) => j.job_type === JOB_EXPORT && j.status === QUEUED);
  const ratio = exporting?.status === RUNNING ? progressRatio(exporting.progress) : null;

  const download = async (j: Job) => {
    setDownloadError(null);
    try {
      await api.downloadExport(j.id, "smartchain.xlsx");
    } catch (e) {
      setDownloadError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="sc-jobs">
      <button type="button" className="sc-chip sc-chip-btn" aria-haspopup="dialog" aria-expanded={open}
              onClick={() => setOpen(!open)} title={delayed} data-testid="job-indicator">
        {running ? <LoaderCircle aria-hidden="true" className="sc-spin" /> : <Activity aria-hidden="true" />}
        <span>
          {exporting
            ? exporting.status === RUNNING ? tr.jobs.exporting(exporting.progress) : tr.jobs.exportQueued
            : tr.jobs.count(running, queued)}
        </span>
        {ratio !== null && (
          <span className="sc-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100}
                aria-valuenow={Math.round(ratio * 100)}>
            <span className="sc-progress-fill" style={{ width: `${ratio * 100}%` }} />
          </span>
        )}
        <span className={`sc-dot is-${conn}`} {...(delayed ? { "aria-label": delayed, role: "img" } : { "aria-hidden": true })} />
      </button>
      {open && (
        <div className="sc-popover" role="dialog" aria-label={tr.jobs.title}>
          <div className="sc-popover-title">{tr.jobs.title}</div>
          {delayed && <p className="sc-muted">{delayed}</p>}
          <span title={canSeeAll ? undefined : forbiddenReason(93, "read")}>
            <Checkbox label={tr.jobs.allJobs} checked={showAll} disabled={!canSeeAll}
                      onChange={(on) => (on ? void loadAll() : setEveryone(null))} />
          </span>
          {recent.length === 0 ? (
            <p className="sc-muted">{tr.jobs.empty}</p>
          ) : (
            <ul className="sc-job-list">
              {recent.map((j) => (
                <li key={j.id}>
                  {j.summary ?? j.job_type} · {j.status}
                  {j.queue_position ? ` · ${tr.jobs.queuePosition(j.queue_position)}` : j.progress ? ` · ${j.progress}` : ""}
                  {showAll && j.requested_by !== me.id && j.requested_by_name && ` · ${tr.jobs.ownerOf(j.requested_by_name)}`}
                  {j.job_type === JOB_EXPORT && j.status === JOB_DONE && (j.requested_by ?? me.id) === me.id && (
                    <> · <button type="button" className="sc-link-btn" onClick={() => download(j)}>{tr.jobs.download}</button></>
                  )}
                  {j.job_type === JOB_PRECHECK && j.status === JOB_DONE && j.import_batch_id && (j.requested_by ?? me.id) === me.id && (
                    <> · <button type="button" className="sc-link-btn" onClick={() => { setOpen(false); navigate(importResultPath(j.import_batch_id!)); }}>{tr.jobs.openResult}</button></>
                  )}
                  {j.job_type === JOB_PULL && (j.status === JOB_DONE || j.status === JOB_FAILED) && (j.requested_by ?? me.id) === me.id && (
                    <> · <button type="button" className="sc-link-btn" onClick={() => { setOpen(false); navigate(pullResultPath(j.id)); }}>{tr.jobs.openResult}</button></>
                  )}
                  {j.cancel_reason && ` · ${j.cancel_reason}`}
                  {canCancel(j) && (
                    <> · <button type="button" className="sc-link-btn" onClick={() => void cancel(j)}
                                 aria-label={tr.jobs.cancelOf(j.id)}>{tr.jobs.cancel}</button></>
                  )}
                </li>
              ))}
            </ul>
          )}
          {downloadError && <p className="sc-field-error" role="alert">{downloadError}</p>}
        </div>
      )}
      {cancelling && (
        <CancelJobDialog jobId={cancelling.id} onClose={() => setCancelling(null)}
                         summary={[cancelling.summary ?? cancelling.job_type, cancelling.requested_by_name,
                                   cancelling.queue_position ? tr.jobs.queuePosition(cancelling.queue_position) : null]
                           .filter(Boolean).join(" · ")}
                         onDone={() => {
                           setCancelling(null);
                           void afterCancel();
                         }} />
      )}
    </div>
  );
}

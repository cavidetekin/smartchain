// İş kuyruğu göstergesi (K-69, fonksiyon 48): açılışta /api/jobs, sonra WebSocket ile canlı.
// Bağlantı koparsa 10 sn'de yeniden bağlanır; bu arada 30 sn'de bir sorgulanır (yedek mod).
// Excel aktarımı çalışırken çip ilerlemeyi yazar ("Excel hazırlanıyor · 120.000 / 142.000 satır"); biten aktarım
// listede indirilir (K-91).
import { Activity, LoaderCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { api, JOB_DONE, JOB_EXPORT, type Job } from "../api/client";
import { connect, type ConnectionState, socketUrl } from "../api/socket";
import { tr } from "../i18n/tr";

export const POLL_MS = 30_000;
const RUNNING = "Çalışıyor";
const QUEUED = "Sırada";

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

  const all = [...jobs.values()];
  const running = all.filter((j) => j.status === RUNNING).length;
  const queued = all.filter((j) => j.status === QUEUED).length;
  const connText =
    conn === "connected" ? tr.jobs.connection.connected
    : `${tr.jobs.connection.reconnecting}. ${tr.jobs.connection.polling}`;
  const recent = all.sort((a, b) => b.id - a.id).slice(0, 10);
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
              onClick={() => setOpen(!open)} title={connText} data-testid="job-indicator">
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
        <span className={`sc-dot is-${conn}`} aria-label={connText} role="img" />
      </button>
      {open && (
        <div className="sc-popover" role="dialog" aria-label={tr.jobs.title}>
          <div className="sc-popover-title">{tr.jobs.title}</div>
          <p className="sc-muted">{connText}</p>
          {recent.length === 0 ? (
            <p className="sc-muted">{tr.jobs.empty}</p>
          ) : (
            <ul className="sc-job-list">
              {recent.map((j) => (
                <li key={j.id}>
                  <span className="sc-num">#{j.id}</span> {j.job_type} · {j.status}
                  {j.queue_position ? ` · ${tr.jobs.queuePosition(j.queue_position)}` : j.progress ? ` · ${j.progress}` : ""}
                  {j.job_type === JOB_EXPORT && j.status === JOB_DONE && (
                    <> · <button type="button" className="sc-link-btn" onClick={() => download(j)}>{tr.jobs.download}</button></>
                  )}
                </li>
              ))}
            </ul>
          )}
          {downloadError && <p className="sc-field-error" role="alert">{downloadError}</p>}
        </div>
      )}
    </div>
  );
}

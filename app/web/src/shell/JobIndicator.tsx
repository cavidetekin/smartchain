// İş kuyruğu göstergesi (K-69, fonksiyon 48): açılışta /api/jobs, sonra WebSocket ile canlı.
// Bağlantı koparsa 10 sn'de yeniden bağlanır; bu arada 30 sn'de bir sorgulanır (yedek mod).
import { Activity, LoaderCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api, type Job } from "../api/client";
import { connect, type ConnectionState, socketUrl } from "../api/socket";
import { tr } from "../i18n/tr";

export const POLL_MS = 30_000;
const RUNNING = "Çalışıyor";
const QUEUED = "Sırada";

export function JobIndicator({ userId }: { userId: number }) {
  const [jobs, setJobs] = useState<Map<number, Job>>(new Map());
  const [conn, setConn] = useState<ConnectionState>("reconnecting");
  const [open, setOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const r = await api.jobs(userId);
      setJobs(new Map(r.jobs.map((j) => [j.id, j])));
    } catch {
      // bağlantı yok; gösterge son bilinen durumda kalır
    }
  }, [userId]);

  useEffect(() => {
    refresh();
    const handle = connect(
      socketUrl(`/api/ws?user_id=${userId}`),
      (msg) => {
        if (msg.type === "job") {
          const job = msg.job as Job;
          setJobs((prev) => new Map(prev).set(job.id, job));
        }
      },
      (state) => {
        setConn(state);
        if (state === "connected") refresh();
      },
    );
    return () => handle.close();
  }, [userId, refresh]);

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

  return (
    <div className="sc-jobs">
      <button type="button" className="sc-badge sc-badge-btn" aria-haspopup="dialog" aria-expanded={open}
              onClick={() => setOpen(!open)} title={connText} data-testid="job-indicator">
        {running ? <LoaderCircle aria-hidden="true" className="sc-spin" /> : <Activity aria-hidden="true" />}
        <span>{tr.jobs.count(running, queued)}</span>
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
                  <span className="sc-mono">#{j.id}</span> {j.job_type} · {j.status}
                  {j.queue_position ? ` · ${tr.jobs.queuePosition(j.queue_position)}` : j.progress ? ` · ${j.progress}` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

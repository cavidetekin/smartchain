// Arka plandaki Excel aktarımının bildirimi (K-91; mockup m24f-0725): sağ altta "Malzeme listesi hazır · 4,8 MB",
// altında dosya adı ve "İndir". İş Hata ile biterse nedeni yazar. Kapatılana ya da indirilene kadar kalır.
import { X } from "lucide-react";
import { useState } from "react";

import { api, JOB_DONE, JOB_FAILED, type Job } from "../api/client";
import { tr } from "../i18n/tr";
import type { TrackedExport } from "./ShellContext";

export type ExportItem = TrackedExport & { job?: Job };

/** "Hazır · 4,8 MB" → "4,8 MB" (iş ilerlemesi, services/export.run_job). */
export const readySize = (progress: string | null | undefined) => progress?.split(" · ")[1] ?? "";

export function ExportToasts({ userId, items, onDismiss }: {
  userId: number; items: ExportItem[]; onDismiss(jobId: number): void;
}) {
  const shown = items.filter((e) => e.job && (e.job.status === JOB_DONE || e.job.status === JOB_FAILED));
  if (!shown.length) return null;
  return (
    <div className="sc-toasts" role="region" aria-label={tr.jobs.notifications}>
      {shown.map((e) => <ExportToast key={e.jobId} userId={userId} item={e} onDismiss={() => onDismiss(e.jobId)} />)}
    </div>
  );
}

function ExportToast({ userId, item, onDismiss }: { userId: number; item: ExportItem; onDismiss(): void }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const failed = item.job?.status === JOB_FAILED;
  const download = async () => {
    setBusy(true);
    try {
      await api.downloadExport(userId, item.jobId, item.fileName);
      onDismiss();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };
  return (
    <div className={`sc-toast${failed || error ? " is-error" : ""}`} role="status">
      <div className="sc-toast-body">
        <p className="sc-toast-title">
          {failed ? tr.jobs.exportFailed(item.title) : tr.jobs.exportReady(item.title, readySize(item.job?.progress))}
        </p>
        <p className="sc-toast-sub">
          {failed ? item.job?.error_text : error ?? (
            <>
              <span className="sc-num">{item.fileName}</span> ·{" "}
              <button type="button" className="sc-toast-link" disabled={busy} onClick={download}
                      aria-label={tr.jobs.downloadOf(item.fileName)}>{tr.jobs.download}</button>
            </>
          )}
        </p>
      </div>
      <button type="button" className="sc-toast-close" onClick={onDismiss} aria-label={tr.ui.close} title={tr.ui.close}>
        <X aria-hidden="true" />
      </button>
    </div>
  );
}

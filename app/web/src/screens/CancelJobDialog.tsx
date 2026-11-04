// Başkasının işini iptal (fonksiyon 93, K-107; ekran 24 ve iş paneli): neden zorunlu, sahibine bildirimle gider.
import { useState } from "react";

import { api, ApiError } from "../api/client";
import { tr } from "../i18n/tr";
import { Alert, Dialog, TextField } from "../ui";

const T = tr.jobs;
const REASON_MAX = 200;

export function CancelJobDialog({ jobId, summary, onClose, onDone }: {
  jobId: number; summary: string; onClose(): void; onDone(): void;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trimmed = reason.trim();

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.cancelJob(jobId, trimmed);
      onDone();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : tr.users.failed);
      setBusy(false);
    }
  };

  return (
    <Dialog title={T.cancelTitle} subtitle={summary} onClose={onClose} onSubmit={() => void submit()} submitLabel={T.cancelSubmit}
            danger busy={busy} submitDisabled={!trimmed}>
      <p className="sc-dialog-message">{T.cancelText}</p>
      <TextField label={T.cancelReason} required maxLength={REASON_MAX} value={reason} onChange={setReason} />
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}

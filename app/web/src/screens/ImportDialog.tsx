// Excel'den yükle penceresi (ekran 02, fonksiyon 03, K-129): Dosya → Ön kontrol → Doğrulama (3.4). Küçük dosya istek içinde biter,
// büyük dosya iş olur; pencere iş bitene kadar özeti yoklar, kapatılırsa iş sürer ve yeniden açınca kaldığı yerden döner.
import { Upload } from "lucide-react";
import { type DragEvent, type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { type CellRender, DataTable } from "../table/DataTable";
import { Alert, Badge, type BadgeTone, Button, ChoiceCards, Dialog, KpiCard } from "../ui";
import { dataLoadApi, type ImportSummary, MODE_CHANGED, MODE_FULL } from "./dataLoadApi";

const T = tr.dataLoad.import;
const POLL_MS = 1000;
const PENDING = "Ön kontrol";
const INCOMPLETE = "Tamamlanmadı";
const CANCELLED = "Vazgeçildi";
const RECEIVED = new Set(["Alındı", "Doğrulandı", "Yüklendi"]);
const JOB_QUEUED = "Sırada";
const SEVERITY_TONE: Record<string, BadgeTone> = { Hata: "critical", Uyarı: "risk", Bilgi: "info" };
/** Bulgu tablosunda kalan genişliği alan ve alt satıra kayan kolon (docs/12 pencere kipi). */
export const FINDING_WRAP = ["Message"] as const;

export const FINDING_CELLS: CellRender = {
  Severity: (value: unknown): ReactNode => (value ? <Badge tone={SEVERITY_TONE[String(value)] ?? "neutral"}>{String(value)}</Badge> : null),
};

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : T.failed);
const sizeText = (bytes: number) => (bytes >= 1024 * 1024 ? `${formatNumber(bytes / 1024 / 1024, 1)} MB` : `${formatNumber(Math.max(1, Math.round(bytes / 1024)), 0)} KB`);

type Step = 1 | 2;

/** İş sıradaysa "sırada"; çalışıyor ama henüz ilerleme yazmadıysa dosya açılıyordur (iş #535, 3.2 demosu). */
const progressText = (s: ImportSummary) => {
  if (s.job?.status === JOB_QUEUED) return T.queued;
  return s.job?.progress && s.job.progress !== "Dosya açılıyor" ? T.running(s.job.progress) : T.opening;
};

function Steps({ step, done }: { step: Step; done?: boolean }) {
  const items = [T.stepFile, T.stepCheck, T.stepValidate];
  return (
    <ol className="sc-steps" aria-label={T.steps}>
      {items.map((label, i) => {
        const n = i + 1;
        const later = n === 3;
        const state = later ? "is-later" : n < step || done ? "is-done" : n === step ? "is-current" : "";
        return (
          <li key={label} className={`sc-step ${state}`} aria-current={n === step && !done ? "step" : undefined}
              aria-disabled={later || undefined} title={later ? T.validateLater : undefined}>
            {`${n}. ${label}`}
          </li>
        );
      })}
    </ol>
  );
}

function Dropzone({ file, onFile, onReject }: { file: File | null; onFile(f: File): void; onReject(): void }) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const take = (f: File | undefined) => {
    if (!f) return;
    if (f.name.toLowerCase().endsWith(".xlsx")) onFile(f);
    else onReject();
  };
  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    take(e.dataTransfer.files[0]);
  };
  return (
    <div className={`sc-dropzone${over ? " is-over" : ""}`} onDrop={drop}
         onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}>
      {file ? (
        <>
          <strong>{file.name}</strong>
          <span className="sc-dropzone-note sc-num">{sizeText(file.size)}</span>
        </>
      ) : (
        <>
          <Upload className="sc-dropzone-icon" aria-hidden="true" />
          <span>{T.dropHere}</span>
        </>
      )}
      <Button size="sm" variant="secondary" onClick={() => input.current?.click()}>{T.choose}</Button>
      <input ref={input} type="file" accept=".xlsx" hidden aria-label={T.choose}
             onChange={(e) => { take(e.target.files?.[0]); e.target.value = ""; }} />
    </div>
  );
}

/** entity ve name: satır menüsünden; batchId: "Sonucu aç"tan (K-129), tablo özetten gelir. */
export function ImportDialog({ entity, name, batchId: opened, onClose, onReceived }: {
  entity?: string; name?: string; batchId?: number; onClose(): void; onReceived(): void;
}) {
  const [loading, setLoading] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState(MODE_CHANGED);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<ImportSummary | null>(null);

  const fail = useCallback((e: unknown) => setError(errorText(e)), []);

  useEffect(() => {  // pencere kapatıldıysa açık ön kontrole dön
    const ctrl = new AbortController();
    const load = opened !== undefined ? dataLoadApi.summary(opened, ctrl.signal) : dataLoadApi.pending(entity ?? "", ctrl.signal);
    load.then(setSummary).catch((e: unknown) => {
      if (!ctrl.signal.aborted) fail(e);
    }).finally(() => {
      if (!ctrl.signal.aborted) setLoading(false);
    });
    return () => ctrl.abort();
  }, [entity, opened, fail]);

  const waiting = !!summary && !summary.checked && summary.status === PENDING;
  const batchId = summary?.batch_id;
  useEffect(() => {
    if (!waiting || batchId === undefined) return undefined;
    const timer = window.setInterval(() => {
      dataLoadApi.summary(batchId).then(setSummary).catch(fail);
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [waiting, batchId, fail]);

  const start = async () => {
    if (!file || !entity) return;
    setBusy(true);
    setError(null);
    try {
      const reply = await dataLoadApi.upload(entity, mode, file);
      setSummary("job_id" in reply ? await dataLoadApi.summary(reply.batch_id) : reply);
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    if (!summary) return onClose();
    setBusy(true);
    try {
      await dataLoadApi.cancel(summary.batch_id);
      onClose();
    } catch (e) {
      fail(e);
      setBusy(false);
    }
    return undefined;
  };

  const proceed = async () => {
    if (!summary) return;
    setBusy(true);
    setError(null);
    try {
      setSummary(await dataLoadApi.continueBatch(summary.batch_id));
      onReceived();
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  };

  const report = () => {
    if (!summary) return;
    setError(null);
    dataLoadApi.errorReport(summary.batch_id).catch(fail);
  };

  const filters = useMemo(() => (batchId === undefined ? [] : [{ field: "ImportBatchId", op: "eq" as const, value: batchId }]), [batchId]);

  if (loading) return null;

  if (!summary && opened !== undefined) {  // "Sonucu aç": parti bulunamadı
    return (
      <Dialog title={T.title} onClose={onClose} onSubmit={onClose} submitLabel={T.close} noCancel>
        {error && <Alert tone="error">{error}</Alert>}
      </Dialog>
    );
  }

  const shownName = summary?.name ?? name ?? "";

  if (summary && RECEIVED.has(summary.status)) {
    return (
      <Dialog title={T.title} subtitle={`${shownName} · ${summary.file_name}`} onClose={onClose} onSubmit={onClose} submitLabel={T.close} noCancel>
        <Steps step={2} done />
        <Alert tone="ok">{T.received(formatNumber(summary.valid ?? 0, 0))}</Alert>
      </Dialog>
    );
  }

  if (summary && (summary.status === INCOMPLETE || summary.status === CANCELLED)) {
    return (
      <Dialog title={T.title} subtitle={`${shownName} · ${summary.file_name}`} onClose={onClose} onSubmit={onClose} submitLabel={T.close} noCancel>
        <Alert tone={summary.status === INCOMPLETE ? "error" : "info"}>{summary.status === INCOMPLETE ? T.incomplete : T.closed}</Alert>
      </Dialog>
    );
  }

  if (waiting && summary) {
    return (
      <Dialog title={T.title} subtitle={`${shownName} · ${summary.file_name}`} onClose={cancel} onSubmit={onClose} submitLabel={T.close}
              cancelLabel={T.cancelUpload} dismissible={false} busy={busy}>
        <Steps step={2} />
        {error && <Alert tone="error">{error}</Alert>}
        <p role="status">{progressText(summary)}</p>
        <p className="sc-dialog-message">{T.canClose}</p>
      </Dialog>
    );
  }

  if (summary) {
    const valid = summary.valid ?? 0;
    const errors = summary.errors ?? 0;
    const current = summary.template_version === summary.current_version;
    const version = summary.template_version === null ? T.versionUnknown : T.version(summary.template_version, current);
    return (
      <Dialog title={T.checkTitle(summary.file_name)} subtitle={`${summary.name} · ${version}`} xwide busy={busy} dismissible={false}
              onClose={cancel} onSubmit={proceed} cancelLabel={T.cancelUpload}
              submitLabel={T.continueWith(formatNumber(valid, 0))} submitDisabled={valid === 0}
              extraActions={errors > 0 ? <Button variant="secondary" onClick={report}>{T.errorReport}</Button> : undefined}>
        <Steps step={2} />
        {error && <Alert tone="error">{error}</Alert>}
        <div className="sc-import-cards">
          <KpiCard label={T.read} value={formatNumber(summary.read ?? 0, 0)} />
          <KpiCard label={T.valid} value={formatNumber(valid, 0)} />
          <KpiCard label={T.errors} value={formatNumber(errors, 0)} tone={errors > 0 ? "over" : undefined} />
          <KpiCard label={T.notes} value={formatNumber(summary.notes ?? 0, 0)} />
        </div>
        {summary.file_findings.filter((f) => f.severity !== "Bilgi").map((f) => (  // bilgi tabloda satır olarak görünür
          <Alert key={f.message} tone={f.severity === "Hata" ? "error" : f.severity === "Uyarı" ? "risk" : "info"}>{f.message}</Alert>
        ))}
        <div className="sc-import-findings">
          <DataTable list="import-findings" cellRender={FINDING_CELLS} baseFilters={filters} fit wrapFields={FINDING_WRAP} />
        </div>
        {errors > 0 && <Alert tone="risk">{valid > 0 ? T.errorsNote(formatNumber(errors, 0)) : T.allBad}</Alert>}
      </Dialog>
    );
  }

  return (
    <Dialog title={T.title} subtitle={shownName} className="sc-dialog--upload" busy={busy} onClose={onClose} onSubmit={start}
            submitLabel={T.start} submitDisabled={!file || !!error}>
      <div className="sc-upload-body">
        <Steps step={1} />
        {error && <Alert tone="error">{error}</Alert>}
        <Dropzone file={file} onFile={(f) => { setFile(f); setError(null); }} onReject={() => setError(T.onlyXlsx)} />
        <ChoiceCards label={T.mode} value={mode} onChange={setMode}
                     options={[{ value: MODE_CHANGED, title: T.modeChangedName, text: T.modeChanged },
                               { value: MODE_FULL, title: T.modeFullName, text: T.modeFull }]} />
      </div>
    </Dialog>
  );
}

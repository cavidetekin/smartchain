// Veri yükle: birden çok Excel dosyası (ekran 02, fonksiyon 03; K-129, K-158). Her dosyanın tablosu şablondaki teknik addan anlaşılır, hepsi tek listede
// ön kontrol edilir; tanınmayan şablon, eski sürüm ve aynı tabloya ikinci dosya satırda nedeniyle reddedilir. Mod dosya başına (başlangıçta Ekle / güncelle);
// "Devam" kontrolden geçen bütün dosyaları alır (hatalı satırlı dosya da), "Vazgeç" hepsini bırakır; her dosya ayrı yüklemedir.
import { useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { type LocalColumn, LocalTable } from "../table/LocalTable";
import { Alert, Badge, type BadgeTone, Button, Dialog } from "../ui";
import { dataLoadApi, type ImportSummary, MODE_CHANGED, MODE_FULL } from "./dataLoadApi";

const T = tr.dataLoad.multi;
const POLL_MS = 1000;
const PENDING = "Ön kontrol";

type State = "waiting" | "uploading" | "checking" | "checked" | "rejected" | "failed";
interface Item {
  key: string;
  file: File;
  state: State;
  mode: string;
  entity?: string;
  name?: string;
  summary?: ImportSummary;
  reason?: string;
}

const count = (n: number | null | undefined) => (n === null || n === undefined ? "—" : formatNumber(n, 0));
const passed = (i: Item) => i.state === "checked" && (i.summary?.valid ?? 0) > 0;
const firstError = (s: ImportSummary) => s.file_findings.find((f) => f.severity === "Hata")?.message ?? T.checkFailed;

function stateBadge(i: Item): { tone: BadgeTone; text: string } {
  switch (i.state) {
    case "waiting": return { tone: "neutral", text: T.waiting };
    case "uploading": return { tone: "neutral", text: T.uploading };
    case "checking": return { tone: "neutral", text: T.checking };
    case "rejected": return { tone: "critical", text: T.rejected };
    case "failed": return { tone: "critical", text: T.failedState };
    default: return (i.summary?.valid ?? 0) === 0 ? { tone: "critical", text: T.noValid }
      : (i.summary?.errors ?? 0) > 0 ? { tone: "risk", text: T.withErrors } : { tone: "ok", text: T.ready };
  }
}

export function MultiImportDialog({ files, onClose, onReceived }: { files: File[]; onClose(): void; onReceived(): void }) {
  const [items, setItems] = useState<Item[]>(() => files.map((file, i) => ({ key: `${i}-${file.name}`, file, state: "waiting", mode: MODE_CHANGED })));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);
  const update = (key: string, patch: Partial<Item>) => setItems((all) => all.map((i) => (i.key === key ? { ...i, ...patch } : i)));

  // Dosyalar sırayla gider: sunucu kabul edilen tabloları bilir, aynı tabloya ikinci dosya parti açmadan reddedilir (K-158).
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    void (async () => {
      const accepted: string[] = [];
      for (const item of items) {
        update(item.key, { state: "uploading" });
        try {
          const reply = await dataLoadApi.uploadAny(item.file, MODE_CHANGED, accepted);
          accepted.push(reply.entity);
          if ("job_id" in reply) {
            update(item.key, { state: "checking", entity: reply.entity, name: reply.name, summary: await dataLoadApi.summary(reply.batch_id) });
          } else {
            update(item.key, { state: reply.status === PENDING && reply.checked ? "checked" : "failed", entity: reply.entity, name: reply.name, summary: reply,
                               reason: reply.status === PENDING ? undefined : firstError(reply) });
          }
        } catch (e) {
          const detail = e instanceof ApiError ? e.details[0] as { name?: string } | undefined : undefined;
          update(item.key, { state: "rejected", name: detail?.name, reason: e instanceof ApiError ? e.message : T.uploadFailed });
        }
      }
    })();
  }, [items]);

  // Arka planda kontrol edilen büyük dosyalar (K-129): bitene kadar özet okunur.
  const checking = items.filter((i) => i.state === "checking" && i.summary).map((i) => i.summary!.batch_id).join(",");
  useEffect(() => {
    if (!checking) return;
    const timer = setInterval(() => {
      for (const item of items.filter((i) => i.state === "checking" && i.summary)) {
        dataLoadApi.summary(item.summary!.batch_id).then((s) => {
          if (s.checked || s.status !== PENDING) {
            update(item.key, { summary: s, state: s.status === PENDING ? "checked" : "failed", reason: s.status === PENDING ? undefined : firstError(s) });
          } else update(item.key, { summary: s });
        }).catch(() => undefined);
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [checking, items]);

  const working = items.some((i) => ["waiting", "uploading", "checking"].includes(i.state));
  const ready = items.filter(passed);
  const open = items.filter((i) => i.summary && (i.state === "checked" || i.state === "checking"));

  const proceed = async () => {
    setBusy(true);
    setError(null);
    try {
      for (const i of ready) await dataLoadApi.continueBatch(i.summary!.batch_id, i.mode);
      for (const i of open.filter((x) => !passed(x))) await dataLoadApi.cancel(i.summary!.batch_id);  // geçerli satırı olmayan bırakılır
      onReceived();
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : T.continueFailed);
      setBusy(false);
    }
  };

  const cancelAll = async () => {
    setBusy(true);
    try {
      for (const i of open) await dataLoadApi.cancel(i.summary!.batch_id).catch(() => undefined);
    } finally {
      onClose();
    }
  };

  const columns: LocalColumn<Item>[] = [
    { key: "file", label: T.file, value: (i) => i.file.name },
    { key: "table", label: T.table, value: (i) => i.name ?? "" },
    { key: "rows", label: T.rows, numeric: true, value: (i) => i.summary?.read ?? null, render: (i) => count(i.summary?.read) },
    { key: "errors", label: T.errors, numeric: true, value: (i) => i.summary?.errors ?? null, render: (i) => count(i.summary?.errors) },
    { key: "state", label: T.state, value: (i) => stateBadge(i).text, render: (i) => <Badge tone={stateBadge(i).tone}>{stateBadge(i).text}</Badge> },
    { key: "mode", label: T.mode, value: (i) => i.mode, render: (i) => (passed(i) ? (
      <select className="sc-cell-input" aria-label={T.modeOf(i.file.name)} value={i.mode} onChange={(e) => update(i.key, { mode: e.target.value })}>
        <option value={MODE_CHANGED}>{T.modeChanged}</option>
        <option value={MODE_FULL}>{T.modeFull}</option>
      </select>
    ) : "") },
    { key: "note", label: T.note, wrap: true, value: (i) => i.reason ?? "", render: (i) => (
      <>
        {i.reason}
        {i.state === "checked" && (i.summary?.errors ?? 0) > 0 && (
          <Button variant="neutral" size="sm" onClick={() => void dataLoadApi.errorReport(i.summary!.batch_id).catch(() => setError(T.reportFailed))}>{T.errorReport}</Button>
        )}
      </>
    ) },
  ];

  return (
    <Dialog title={T.title} subtitle={T.subtitle(items.length, ready.length)} onClose={() => void cancelAll()} onSubmit={() => void proceed()}
            submitLabel={T.continueWith(ready.length)} submitDisabled={working || ready.length === 0} cancelLabel={T.cancel} dismissible={false}
            busy={busy} xwide>
      {error && <Alert tone="error">{error}</Alert>}
      <LocalTable label={T.title} columns={columns} rows={items} rowKey={(i) => i.key} />
    </Dialog>
  );
}

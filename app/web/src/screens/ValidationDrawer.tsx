// Validasyon çipi ve çekmecesi (ekran 02, fonksiyon 04; K-134, K-139, docs/12). Çekmece staging'in güncel hâlinin validasyonunu gösterir:
// son parti; dört kart (Hatalı, Uyarılı, Bilgilendirme satırı, Hata oranı); kural bazında Bulgular, kurala tıklayınca o kurala süzülmüş
// Kayıtlar; indirme ve yeniden validasyon. Yapılan işin onayı bant değildir: çip ve iş paneli gösterir (K-139).
import { LoaderCircle, X } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/client";
import { formatDateTime, formatNumber, serverDate } from "../format";
import { tr } from "../i18n/tr";
import { type CellRender, DataTable } from "../table/DataTable";
import { type LocalColumn, LocalTable } from "../table/LocalTable";
import { Alert, Badge, type BadgeTone, Button, Drawer, KpiCard, Segment } from "../ui";
import { recordsList, type RuleCount, ruleFilter, RUNNING_STATES, STATE_DONE, STATE_FAILED, validationApi, type ValidationSummary } from "./validationApi";

const T = tr.validation;
const POLL_MS = 2000;

const TONES: Record<string, BadgeTone> = { "Geçti": "ok", "Uyarılı": "risk", "Hatalı": "critical", [STATE_FAILED]: "critical" };

/** Sınıf çipi: saydam pastel (Hata açık kırmızı, Uyarı açık sarı, Bilgi açık mavi-gri; K-139). */
export function SeverityTag({ severity }: { severity: string }) {
  return <span className={`sc-tag sc-tag--soft ${SEVERITY_CLASS[severity] ?? ""}`}>{severity}</span>;
}
export const SEVERITY_CLASS: Record<string, string> = { Hata: "sc-tag--critical", Uyarı: "sc-tag--risk", Bilgi: "sc-tag--info" };

const SEVERITY_CELLS: CellRender = {
  Severity: (value: unknown): ReactNode => (value ? <SeverityTag severity={String(value)} /> : null),
};

/** Çipin metni ve tonu: bittiyse sonuç ve sayı, sürüyorsa durum (K-134). */
export function chipOf(state: string | null, errors: number, warnings: number): { text: string; tone: BadgeTone; running: boolean } | null {
  if (!state) return null;
  const running = RUNNING_STATES.includes(state);
  const count = state === "Hatalı" ? errors : state === "Uyarılı" ? warnings : null;
  return { text: T.chip(state, count), tone: TONES[state] ?? "neutral", running };
}

export function ValidationChip({ name, state, errors, warnings, onOpen }: {
  name: string; state: string | null; errors: number; warnings: number; onOpen(): void;
}) {
  const chip = chipOf(state, errors, warnings);
  if (!chip) return null;
  return (
    <button type="button" className="sc-validation-chip" onClick={onOpen} aria-label={T.open(name, chip.text)}>
      <span className={`sc-tag sc-tag--${chip.tone}`}>
        {chip.running && <LoaderCircle className="sc-spin" aria-hidden width={12} height={12} />}
        {chip.text}
      </span>
    </button>
  );
}

const percent = (v: number | null) => (v === null ? null : formatNumber(v, 2));

export function ValidationDrawer({ entity, name, canRevalidate, revalidateReason, onClose, onChanged }: {
  entity: string; name: string; canRevalidate: boolean; revalidateReason?: string | null; onClose(): void; onChanged?(): void;
}) {
  const [summary, setSummary] = useState<ValidationSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"findings" | "records">("findings");
  const [rule, setRule] = useState<RuleCount | null>(null);  // Kayıtlar bu kurala süzülü
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      setSummary(await validationApi.summary(entity, signal));
    } catch (e) {
      if (!signal?.aborted) setError(e instanceof ApiError ? e.message : T.failed);
    }
  }, [entity]);

  useEffect(() => {
    const ctrl = new AbortController();
    void load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  const running = summary?.state ? RUNNING_STATES.includes(summary.state) : false;
  useEffect(() => {  // sürerken yoklanır; bitince tablolar yenilenir
    if (!running) return;
    const timer = window.setInterval(() => {
      void validationApi.summary(entity).then((s) => {
        setSummary(s);
        if (!RUNNING_STATES.includes(s.state ?? "")) {
          setReloadKey((k) => k + 1);
          onChanged?.();
        }
      }).catch(() => undefined);
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [running, entity, onChanged]);

  const revalidate = async () => {
    setBusy(true);
    setError(null);
    try {
      await validationApi.revalidate(entity);  // çip "Sırada" olur; iş panelinde görünür (onay bandı yok, K-139)
      await load();
      onChanged?.();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : T.failed);
    } finally {
      setBusy(false);
    }
  };

  const download = async () => {
    setError(null);
    try {
      await validationApi.downloadRecords(entity);  // büyük dosya arka planda; bildirim gelir
    } catch (e) {
      setError(e instanceof ApiError ? e.message : T.failed);
    }
  };

  const showRule = (r: RuleCount) => {
    setRule(r);
    setView("records");
  };
  const ruleColumns: LocalColumn<RuleCount>[] = useMemo(() => [
    {
      key: "name", label: T.rule, wrap: true, value: (r) => r.name,
      render: (r) => (r.message ? <>{r.name} <span className="sc-muted">· {r.message}</span></> : (
        <button type="button" className="sc-link-btn" onClick={() => showRule(r)} aria-label={T.showRule(r.name)}>{r.name}</button>
      )),
    },
    { key: "severity", label: T.severity, value: (r) => r.severity, render: (r) => <SeverityTag severity={r.severity} /> },
    { key: "rows", label: T.rowCount, numeric: true, value: (r) => r.rows, render: (r) => (r.message ? "—" : formatNumber(r.rows, 0)) },
  ], []);
  const recordFilters = useMemo(() => (rule ? [ruleFilter(rule.id)] : []), [rule]);

  const state = summary?.state === STATE_DONE ? summary.outcome : summary?.state ?? null;
  const chip = summary ? chipOf(state, summary.error_rows, summary.warning_rows) : null;
  const batch = summary?.batch;
  const over = summary && summary.threshold !== null && summary.error_rate !== null && summary.error_rate > summary.threshold;

  return (
    <Drawer
      title={<>{T.title(summary?.name ?? name)}{chip && <Badge tone={chip.tone}>{chip.text}</Badge>}</>}
      subtitle={summary && (
        <>
          {batch ? T.lastBatch(formatDateTime(serverDate(batch.received_at)), batch.method, batch.uploaded_by_name) : T.noBatch}
          {" · "}{T.currentRows(formatNumber(summary.current_rows, 0))}
        </>
      )}
      onClose={onClose}
      actions={(
        <>
          <Button variant="secondary" onClick={() => void download()} disabled={!summary || (!summary.error_rows && !summary.warning_rows && !summary.info_rows)}>{T.download}</Button>
          <Button variant="secondary" busy={busy} onClick={() => void revalidate()} disabled={running}
                  disabledReason={canRevalidate ? null : revalidateReason ?? null}>{T.revalidate}</Button>
        </>
      )}>
      {error && <Alert tone="error">{error}</Alert>}
      {summary?.state === STATE_FAILED && <Alert tone="error">{T.failedRun}</Alert>}
      {summary && (
        <>
          <div className="sc-validation-kpis">
            <KpiCard label={T.errorRows} value={formatNumber(summary.error_rows, 0)} tone={summary.error_rows ? "over" : undefined} />
            <KpiCard label={T.warningRows} value={formatNumber(summary.warning_rows, 0)} tone={summary.warning_rows ? "risk" : undefined} />
            <KpiCard label={T.infoRows} value={formatNumber(summary.info_rows, 0)} />
            <KpiCard label={T.errorRate} value={T.rate(percent(summary.error_rate) ?? "0")} note={T.threshold(percent(summary.threshold))}
                     tone={over ? "over" : undefined} />
          </div>
          {over && <Alert tone="risk">{T.overThreshold}</Alert>}
          <Segment<"findings" | "records"> label={T.view} hideLabel value={view} onChange={setView}
                   options={[{ value: "findings", label: T.findings }, { value: "records", label: T.records }]} />
          {view === "findings" ? (
            summary.rules.length
              ? <LocalTable label={T.findings} columns={ruleColumns} rows={summary.rules} rowKey={(r) => `${r.id}:${r.severity}`} />
              : <p className="sc-muted">{T.noFindings}</p>
          ) : (
            <>
              {rule && (
                <ul className="sc-chips">
                  <li className="sc-chip-filter">
                    <span className="sc-chip-filter-text">{T.ruleFilter(rule.name)}</span>
                    <button type="button" className="sc-chip-filter-x" aria-label={T.clearRule} onClick={() => setRule(null)}><X aria-hidden="true" /></button>
                  </li>
                </ul>
              )}
              <DataTable key={`records:${rule?.id ?? ""}`} list={recordsList(entity)} baseFilters={recordFilters} cellRender={SEVERITY_CELLS} reloadKey={reloadKey} />
            </>
          )}
        </>
      )}
    </Drawer>
  );
}

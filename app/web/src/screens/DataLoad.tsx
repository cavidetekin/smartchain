// Veri yükleme (ekran 02; K-110, K-129, K-130, K-134, docs/12). Tablo listesi, yöntem ve çekim, doğrulama çipi ve çekmecesi, satır menüsü,
// Excel'den yükle, Veri çek; sayılar 5.5'te.
import { ChevronDown, TriangleAlert } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { ApiError, JOB_PRECHECK, JOB_PULL, JOB_TRANSFER, JOB_VALIDATION } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can, forbiddenReason } from "../auth/permissions";
import { formatDateTime, serverDate } from "../format";
import { tr } from "../i18n/tr";
import { SelectCell, SwitchCell } from "../table/CellEditors";
import { DataTable, type RowMenuSpec } from "../table/DataTable";
import type { Row } from "../table/types";
import { EditBar, UnsavedGuard, useTableEdits } from "../table/useTableEdits";
import { Alert, Button, Dialog, Tooltip } from "../ui";
import { dataLoadApi, type TemplateInfo } from "./dataLoadApi";
import { ImportDialog } from "./ImportDialog";
import { type EntityChange, integrationApi, METHOD_SQL, METHODS } from "./integrationApi";
import { PullResultDialog, PullStartDialog, PullSwitchDialog } from "./PullDialogs";
import { PartialTransferDialog, TransferResultDialog, TransferStartDialog } from "./TransferDialogs";
import { TransferHistoryDrawer } from "./TransferHistory";
import { useJobRefresh } from "../shell/useJobRefresh";
import { MenuItem, RowPopMenu } from "./RowPopMenu";
import { ValidationChip, ValidationDrawer } from "./ValidationDrawer";
import { RUNNING_STATES } from "./validationApi";

const T = tr.dataLoad;
const ALLOWED = { allowed: true };
const later = (step: string) => ({ allowed: false, reason: T.comingIn(step) });
const RELOAD_MS = 3000;
const DATA_JOBS = [JOB_PULL, JOB_VALIDATION, JOB_PRECHECK, JOB_TRANSFER];

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : T.failed);
const fileFallback = (row: Row) => `smartchain_${String(row.Entity)}.xlsx`;

function InfoDialog({ row, onClose, onDownload }: { row: Row; onClose(): void; onDownload(): void }) {
  const [info, setInfo] = useState<TemplateInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    dataLoadApi.info(String(row.Entity), ctrl.signal).then(setInfo).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, [row.Entity]);

  return (
    <Dialog title={T.info} subtitle={String(row.Name)} onClose={onClose} onSubmit={onDownload} submitLabel={T.downloadButton} submitDisabled={!info} wide>
      {error && <Alert tone="error">{error}</Alert>}
      {info && (
        <dl className="sc-detail-rows">
          <dt>{T.version}</dt><dd className="sc-num">v{info.version}</dd>
          <dt>{T.fileName}</dt><dd>{info.file_name}</dd>
          <dt>{T.fieldCount}</dt><dd className="sc-num">{info.field_count}</dd>
          {info.required.length > 0 && <><dt>{T.required}</dt><dd>{info.required.join(", ")}</dd></>}
        </dl>
      )}
    </Dialog>
  );
}

export function DataLoad() {
  const me = useAuth().me!;
  const canMethod = can(me, 96, "write");
  const canSwitch = can(me, 91, "write");
  const canPull = can(me, 1, "write");
  const canRevalidate = can(me, 4, "write");
  const canTransfer = can(me, 5, "write");
  const canPartial = can(me, 6, "write");
  const canHistory = can(me, 8, "read");
  const [transferStart, setTransferStart] = useState(false);
  const [partialStart, setPartialStart] = useState(false);
  const [transferMenu, setTransferMenu] = useState<HTMLElement | null>(null);  // "Veri aktarımı ▾" (K-157)
  const [transferJob, setTransferJob] = useState<number | null>(null);
  const [drawer, setDrawer] = useState<{ entity: string; name: string; all?: boolean } | null>(null);
  const running = useRef(false);  // bir çip sürüyorsa tablo kendini yeniler
  const [pullStart, setPullStart] = useState<{ entity?: string } | null>(null);
  const [pullJob, setPullJob] = useState<number | null>(null);
  const [switching, setSwitching] = useState<Row | null>(null);
  const [saving, setSaving] = useState(false);
  const edits = useTableEdits();
  const [menu, setMenu] = useState<{ row: Row; anchor: HTMLElement } | null>(null);
  const [infoRow, setInfoRow] = useState<Row | null>(null);
  const [uploadRow, setUploadRow] = useState<Row | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const { pathname, search } = useLocation();
  const navigate = useNavigate();
  const resultBatch = Number(new URLSearchParams(search).get("parti")) || null;  // "Sonucu aç" (K-129)
  const resultPull = Number(new URLSearchParams(search).get("cekim")) || null;  // "Sonucu aç" (K-130)
  const shownPull = pullJob ?? resultPull;
  const resultValidation = new URLSearchParams(search).get("validasyon");  // "Sonucu aç" (K-134)
  const resultTransfer = Number(new URLSearchParams(search).get("aktarim")) || null;  // "Sonucu aç" (K-153)
  const shownTransfer = transferJob ?? resultTransfer;
  const resultHistory = new URLSearchParams(search).get("gecmis") === "1";  // "Sonucu aç" (temizlik, K-156)
  const [history, setHistory] = useState(false);
  const refresh = useCallback(() => setReloadKey((k) => k + 1), []);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (running.current) {
        running.current = false;  // yeni çizimde süren çip yeniden işaretler
        setReloadKey((k) => k + 1);
      }
    }, RELOAD_MS);
    return () => window.clearInterval(timer);
  }, []);
  useJobRefresh(DATA_JOBS, refresh);  // kullanıcının çekim, ön kontrol ve validasyon işleri değişince satırlar yenilenir (tablolar arası dahil, K-143)
  useEffect(() => {
    if (resultValidation) setDrawer({ entity: resultValidation, name: resultValidation });
  }, [resultValidation]);
  useEffect(() => {
    if (resultHistory) setHistory(true);
  }, [resultHistory]);

  const rowMenu: RowMenuSpec = useMemo(() => ({
    label: (row: Row) => T.rowMenu(String(row.Name)),
    onOpen: (row: Row, anchor: HTMLElement) => setMenu({ row, anchor }),
  }), []);

  const toggle = useCallback((row: Row) => {
    const key = String(row.Entity);
    if (edits.changed(key, "IsPullEnabled")) {  // kaydedilmemiş değişikliği geri alır
      edits.set(key, "IsPullEnabled", Boolean(row.IsPullEnabled), Boolean(row.IsPullEnabled));
      edits.set(key, "PullReason", "", "");
    } else {
      setSwitching(row);
    }
  }, [edits]);
  const confirmSwitch = (reason: string) => {
    const row = switching!;
    const key = String(row.Entity);
    edits.set(key, "IsPullEnabled", !row.IsPullEnabled, Boolean(row.IsPullEnabled));
    edits.set(key, "PullReason", reason, "");
    setSwitching(null);
  };
  const saveEdits = async () => {
    setSaving(true);
    setError(null);
    try {
      const changes: EntityChange[] = Object.entries(edits.drafts).map(([entity, d]) => ({
        entity,
        ...("Method" in d ? { method: String(d.Method) } : {}),
        ...("IsPullEnabled" in d ? { pull_enabled: Boolean(d.IsPullEnabled), reason: d.PullReason ? String(d.PullReason) : undefined } : {}),
      }));
      await integrationApi.saveEntities(changes);
      edits.discard();
      refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : T.saveFailed);
    } finally {
      setSaving(false);
    }
  };

  const cellRender = useMemo(() => ({
    Validation: (value: unknown, row: Row) => {
      const state = value ? String(value) : null;
      if (state && RUNNING_STATES.includes(state)) running.current = true;
      return <ValidationChip name={String(row.Name)} state={state} errors={Number(row.ValidationErrors ?? 0)} warnings={Number(row.ValidationWarnings ?? 0)}
                             onOpen={() => setDrawer({ entity: String(row.Entity), name: String(row.Name) })} />;
    },
    Name: (value: unknown, row: Row) => (
      <span className="sc-name-cell">
        <span className="sc-name-text">{String(value)}</span>
        {Boolean(row.Warning) && <Tooltip content={String(row.Warning)} focusable><TriangleAlert className="sc-warn-icon" aria-label={T.warningOf(String(value), String(row.Warning))} /></Tooltip>}
      </span>
    ),
    Method: (value: unknown, row: Row) => {
      const key = String(row.Entity);
      return <SelectCell label={T.method(String(row.Name))} value={edits.get(key, "Method", String(value))} options={METHODS} editable={canMethod} changed={edits.changed(key, "Method")}
                         onChange={(next) => edits.set(key, "Method", next, String(value))} />;
    },
    IsPullEnabled: (value: unknown, row: Row) => {
      const key = String(row.Entity);
      const on = edits.get(key, "IsPullEnabled", Boolean(value));
      const draftReason = edits.get(key, "PullReason", "");
      const reason = draftReason || row.DisabledReason;
      return (
        <Tooltip content={on ? null : (
          <>
            <div>{T.pullOff}</div>
            {Boolean(reason) && <div>{T.pullReason(String(reason))}</div>}
            {!edits.changed(key, "IsPullEnabled") && Boolean(row.DisabledAt) && <div>{T.pullBy(String(row.DisabledByName ?? ""), formatDateTime(serverDate(String(row.DisabledAt))))}</div>}
          </>
        )}>
          <SwitchCell label={T.pullSwitch(String(row.Name))} checked={on} editable={canSwitch} changed={edits.changed(key, "IsPullEnabled")} onToggle={() => toggle(row)} />
        </Tooltip>
      );
    },
  }), [canMethod, canSwitch, edits, toggle]);

  const download = (row: Row) => {
    setError(null);
    setMenu(null);
    setInfoRow(null);
    dataLoadApi.download(String(row.Entity), fileFallback(row)).catch((e: unknown) => setError(errorText(e)));
  };

  return (
    <section className="sc-page--fill">
      <header className="sc-page-head sc-page-head--row">
        <h1>{T.title}</h1>
        <div className="sc-page-head-actions">
          <Button variant="primary" disabledReason={canPull ? null : forbiddenReason(1, "write")} onClick={() => setPullStart({})}>{T.pullNow}</Button>
          <Button variant="secondary" aria-haspopup="menu" aria-expanded={Boolean(transferMenu)}
                  onClick={(e) => { const at = e.currentTarget; setTransferMenu((open) => (open ? null : at)); }}>
            {tr.transfer.menu}<ChevronDown aria-hidden="true" className="sc-btn-caret" />
          </Button>
        </div>
      </header>
      {error && <Alert tone="error">{error}</Alert>}
      <DataTable list="data-entities" rowMenu={rowMenu} cellRender={cellRender} reloadKey={reloadKey}
                 toolbarActions={<EditBar dirty={edits.dirty} busy={saving} onSave={() => void saveEdits()} onDiscard={edits.discard} />} />
      <UnsavedGuard dirty={edits.dirty} />
      {menu && (
        <RowPopMenu label={T.rowMenu(String(menu.row.Name))} anchor={menu.anchor} onClose={() => setMenu(null)}>
          <MenuItem label={T.download(menu.row.Version)} state={ALLOWED} onClick={() => download(menu.row)} />
          <MenuItem label={T.viewData} state={ALLOWED}
                    onClick={() => { setDrawer({ entity: String(menu.row.Entity), name: String(menu.row.Name), all: true }); setMenu(null); }} />
          <MenuItem label={T.info} state={ALLOWED} onClick={() => { setInfoRow(menu.row); setMenu(null); }} />
          <MenuItem label={T.upload} state={ALLOWED} onClick={() => { setUploadRow(menu.row); setMenu(null); }} />
          <MenuItem label={T.lastUpload} state={later("5.5")} onClick={() => undefined} />
          {menu.row.Method === METHOD_SQL && (
            <MenuItem label={T.pullNow} state={canPull ? ALLOWED : { allowed: false, reason: forbiddenReason(1, "write") }}
                      onClick={() => { setPullStart({ entity: String(menu.row.Entity) }); setMenu(null); }} />
          )}
        </RowPopMenu>
      )}
      {pullStart && <PullStartDialog entity={pullStart.entity} onClose={() => setPullStart(null)} onStarted={(job) => { setPullStart(null); setPullJob(job); }} />}
      {shownPull && <PullResultDialog key={shownPull} jobId={shownPull} onRetry={setPullJob} onChanged={refresh}
                                      onClose={() => { setPullJob(null); if (resultPull) navigate(pathname, { replace: true }); }} />}
      {transferStart && <TransferStartDialog onClose={() => setTransferStart(false)} onStarted={(job) => { setTransferStart(false); setTransferJob(job); }} />}
      {transferMenu && (
        <RowPopMenu label={tr.transfer.menu} anchor={transferMenu} onClose={() => setTransferMenu(null)}>
          <MenuItem label={tr.transfer.startTitle} state={canTransfer ? ALLOWED : { allowed: false, reason: forbiddenReason(5, "write") }}
                    onClick={() => { setTransferMenu(null); setTransferStart(true); }} />
          <MenuItem label={tr.transfer.partialTitle} state={canPartial ? ALLOWED : { allowed: false, reason: forbiddenReason(6, "write") }}
                    onClick={() => { setTransferMenu(null); setPartialStart(true); }} />
          <div role="separator" className="sc-popmenu-sep" />
          <MenuItem label={tr.history.button} state={canHistory ? ALLOWED : { allowed: false, reason: forbiddenReason(8, "read") }}
                    onClick={() => { setTransferMenu(null); setHistory(true); }} />
        </RowPopMenu>
      )}
      {history && <TransferHistoryDrawer onClose={() => { setHistory(false); if (resultHistory) navigate(pathname, { replace: true }); }}
                                         onOpenReport={setTransferJob} />}
      {partialStart && <PartialTransferDialog onClose={() => setPartialStart(false)} onStarted={(job) => { setPartialStart(false); setTransferJob(job); }} />}
      {shownTransfer && <TransferResultDialog key={shownTransfer} jobId={shownTransfer} onChanged={refresh}
                                              onClose={() => { setTransferJob(null); if (resultTransfer) navigate(pathname, { replace: true }); }} />}
      {drawer && <ValidationDrawer key={`${drawer.entity}:${drawer.all ? "all" : ""}`} entity={drawer.entity} name={drawer.name} canRevalidate={canRevalidate}
                                   initial={drawer.all ? { view: "records", scope: "all" } : undefined} refreshKey={reloadKey}
                                   revalidateReason={canRevalidate ? null : forbiddenReason(4, "write")} onChanged={refresh}
                                   onClose={() => { setDrawer(null); if (resultValidation) navigate(pathname, { replace: true }); }} />}
      {switching && <PullSwitchDialog name={String(switching.Name)} enabling={!switching.IsPullEnabled} onClose={() => setSwitching(null)} onConfirm={confirmSwitch} />}
      {infoRow && <InfoDialog row={infoRow} onClose={() => setInfoRow(null)} onDownload={() => download(infoRow)} />}
      {uploadRow && <ImportDialog entity={String(uploadRow.Entity)} name={String(uploadRow.Name)} onClose={() => setUploadRow(null)}
                                  onReceived={() => setReloadKey((k) => k + 1)} />}
      {resultBatch && !uploadRow && <ImportDialog key={resultBatch} batchId={resultBatch} onClose={() => navigate(pathname, { replace: true })}
                                                  onReceived={() => setReloadKey((k) => k + 1)} />}
    </section>
  );
}

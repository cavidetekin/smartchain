// Denetim izi (ekran 26, fonksiyon 98; K-108, docs/12): ortak tablo, detay penceresi, nesnenin geçmişi. Kayıtlar yalnız okunur. Nesnesi veri
// kaydı olan satırda "Kayda git": ilgili ekran, kayıt seçili, kart Geçmiş'te (K-173).
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";

import { ApiError } from "../api/client";
import { formatDate, formatTime } from "../format";
import { tr } from "../i18n/tr";
import { DataTable } from "../table/DataTable";
import { useRowMenu } from "../table/rowMenu";
import { Alert, Button, Dialog } from "../ui";
import { type AuditDetail, type AuditHistory, auditLogApi } from "./auditLogApi";
import { recordUrl } from "./dataScreenTabs";

const T = tr.auditLog;

const errorText = (e: unknown) => (e instanceof ApiError ? e.message : tr.users.failed);
const fullTime = (iso: string) => {
  const d = new Date(iso);
  return `${formatDate(d)} ${formatTime(d)}`;
};

function Detail({ detail, onHistory }: { detail: AuditDetail; onHistory(): void }) {
  const navigate = useNavigate();
  const target = detail.target ? recordUrl(detail.target.list, detail.target.id) : null;
  return (
    <>
      <dl className="sc-detail-rows">
        <dt>{T.time}</dt><dd className="sc-num">{fullTime(detail.at)}</dd>
        <dt>{T.user}</dt><dd>{detail.actor}</dd>
        <dt>{T.action}</dt><dd>{detail.action}</dd>
        <dt>{T.objectType}</dt><dd>{detail.object_type ?? ""}</dd>
        <dt>{T.object}</dt><dd>{detail.object ?? ""}</dd>
      </dl>
      {detail.changes.length > 0 && (
        <table className="sc-matrix sc-audit-changes" aria-label={T.changes}>
          <thead>
            <tr>
              <th scope="col">{T.field}</th>
              <th scope="col">{T.oldValue}</th>
              <th scope="col">{T.newValue}</th>
            </tr>
          </thead>
          <tbody>
            {detail.changes.map((c) => (
              <tr key={c.field}>
                <th scope="row">{c.field}</th>
                <td>{c.old}</td>
                <td>{c.new}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="sc-inline-actions">
        <Button variant="secondary" disabledReason={detail.has_object ? null : T.noObject} onClick={onHistory}>{T.history}</Button>
        {(detail.target !== undefined || detail.target_reason) && (
          <Button variant="secondary" disabledReason={target ? null : detail.target_reason ?? T.noObject} onClick={() => target && navigate(target)}>{T.goToRecord}</Button>
        )}
      </div>
    </>
  );
}

function History({ history, onOpen }: { history: AuditHistory; onOpen(id: number): void }) {
  return (
    <>
      {history.truncated && <p className="sc-muted">{T.truncated(history.rows.length)}</p>}
      <table className="sc-matrix" aria-label={T.history}>
        <thead>
          <tr>
            <th scope="col">{T.time}</th>
            <th scope="col">{T.user}</th>
            <th scope="col">{T.action}</th>
          </tr>
        </thead>
        <tbody>
          {history.rows.map((r) => (
            <tr key={r.id}>
              <td className="sc-num"><button type="button" className="sc-link-btn" onClick={() => onOpen(r.id)}>{fullTime(r.at)}</button></td>
              <td>{r.actor}</td>
              <td>{r.action}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

function AuditDialog({ id, onClose }: { id: number; onClose(): void }) {
  const [current, setCurrent] = useState(id);
  const [detail, setDetail] = useState<AuditDetail | null>(null);
  const [history, setHistory] = useState<AuditHistory | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    setError(null);
    auditLogApi.detail(current, ctrl.signal).then(setDetail).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, [current]);

  const openHistory = () => {
    setError(null);
    auditLogApi.history(current).then(setHistory).catch((e: unknown) => setError(errorText(e)));
  };

  return (
    <Dialog title={history ? T.history : T.detailTitle} subtitle={history ? detail?.object ?? undefined : undefined}
            onClose={onClose} onSubmit={onClose} submitLabel={tr.ui.close} noCancel xwide>
      {history ? (
        <>
          <History history={history} onOpen={(next) => {
            setHistory(null);
            setCurrent(next);
          }} />
          <div><Button onClick={() => setHistory(null)}>{T.back}</Button></div>
        </>
      ) : detail && <Detail detail={detail} onHistory={openHistory} />}
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}

export function AuditLog() {
  const [open, setOpen] = useState<number | null>(null);
  // ⋯ menüsü (K-171): Detay → kayıt detayı penceresi
  const rowMenu = useRowMenu(() => T.detailTitle, (row) => [{ label: tr.table.detailItem, onClick: () => setOpen(row.Id) }]);
  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{T.title}</h1>
      </header>
      <DataTable list="audit-log" rowMenu={rowMenu.rowMenu} />
      {rowMenu.element}
      {open !== null && <AuditDialog id={open} onClose={() => setOpen(null)} />}
    </section>
  );
}

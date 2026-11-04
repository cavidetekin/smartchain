// Veri yükleme (ekran 02; K-110, docs/12): 3.1'de iskelet. Tablo listesi ve satır menüsü; yükleme zamanı, yöntem ve sayılar sonraki adımlarda.
import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/client";
import { tr } from "../i18n/tr";
import { DataTable, type RowMenuSpec } from "../table/DataTable";
import type { Row } from "../table/types";
import { Alert, Dialog } from "../ui";
import { dataLoadApi, type TemplateInfo } from "./dataLoadApi";
import { MenuItem, RowPopMenu } from "./RowPopMenu";

const T = tr.dataLoad;
const ALLOWED = { allowed: true };
const later = (step: string) => ({ allowed: false, reason: T.comingIn(step) });

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
  const [menu, setMenu] = useState<{ row: Row; anchor: HTMLElement } | null>(null);
  const [infoRow, setInfoRow] = useState<Row | null>(null);
  const [error, setError] = useState<string | null>(null);

  const rowMenu: RowMenuSpec = useMemo(() => ({
    label: (row: Row) => T.rowMenu(String(row.Name)),
    onOpen: (row: Row, anchor: HTMLElement) => setMenu({ row, anchor }),
  }), []);

  const download = (row: Row) => {
    setError(null);
    setMenu(null);
    setInfoRow(null);
    dataLoadApi.download(String(row.Entity), fileFallback(row)).catch((e: unknown) => setError(errorText(e)));
  };

  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{T.title}</h1>
      </header>
      {error && <Alert tone="error">{error}</Alert>}
      <DataTable list="data-entities" rowMenu={rowMenu} />
      {menu && (
        <RowPopMenu label={T.rowMenu(String(menu.row.Name))} anchor={menu.anchor} onClose={() => setMenu(null)}>
          <MenuItem label={T.download(menu.row.Version)} state={ALLOWED} onClick={() => download(menu.row)} />
          <MenuItem label={T.info} state={ALLOWED} onClick={() => { setInfoRow(menu.row); setMenu(null); }} />
          <MenuItem label={T.upload} state={later("3.2")} onClick={() => undefined} />
          <MenuItem label={T.lastUpload} state={later("5.4")} onClick={() => undefined} />
          <MenuItem label={T.exclude} state={later("3.3")} onClick={() => undefined} />
        </RowPopMenu>
      )}
      {infoRow && <InfoDialog row={infoRow} onClose={() => setInfoRow(null)} onDownload={() => download(infoRow)} />}
    </section>
  );
}

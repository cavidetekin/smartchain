// Entegrasyon (ekran 23, fonksiyon 91; K-130, K-132, docs/12). SQL view kartı, tablolar, bağlantı testi, önizleme, view sürümleri. API 11.5'te, zamanlanmış işler 5.6'da.
import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can, forbiddenReason } from "../auth/permissions";
import { formatDateTime, serverDate } from "../format";
import { tr } from "../i18n/tr";
import { SelectCell, TextCell } from "../table/CellEditors";
import { DataTable, type RowMenuSpec } from "../table/DataTable";
import { type LocalColumn, LocalTable } from "../table/LocalTable";
import type { Row } from "../table/types";
import { EditBar, UnsavedGuard, useTableEdits } from "../table/useTableEdits";
import { Alert, Badge, Button, Dialog, TextField, Tooltip } from "../ui";
import { type EntityChange, integrationApi, METHOD_SQL, METHODS, type Connection, type Preview, type TestResult, type TestTable, type ViewVersion } from "./integrationApi";
import { StateChip } from "./PullDialogs";
import { MenuItem, RowPopMenu } from "./RowPopMenu";

const T = tr.integration;
const ALLOWED = { allowed: true };
const errorText = (e: unknown) => (e instanceof ApiError ? e.message : T.failed);
const when = (iso: string | null) => (iso ? formatDateTime(serverDate(iso)) : T.never);

/** Alan uyumu (K-132): tam uyumda yeşil, yalnız isteğe bağlı kolon eksikse sarı, zorunlu kolon eksikse kırmızı (tablo okunamaz). */
function FieldMatch({ text, status, note }: { text: string; status: string | null; note?: string | null }) {
  const tone = status === "Uyumlu" ? "ok" : status === "Hatalı" ? "critical" : "risk";
  return <Tooltip content={note} focusable={Boolean(note)}><Badge tone={tone}>{text}</Badge></Tooltip>;
}

function TestDialog({ result, onClose }: { result: TestResult; onClose(): void }) {
  const columns: LocalColumn<TestTable>[] = [
    { key: "name", label: T.table, value: (t) => t.name },
    { key: "view", label: T.source, value: (t) => t.view },
    { key: "match", label: T.fieldMatch, value: (t) => t.matched, render: (t) => <FieldMatch text={`${t.matched} / ${t.expected}`} status={t.status} /> },
    { key: "note", label: T.note, wrap: true, value: (t) => [...t.errors, ...t.warnings, ...t.notes].join(" ") },
  ];
  return (
    <Dialog title={T.testTitle} subtitle={result.database} onClose={onClose} onSubmit={onClose} submitLabel={tr.ui.close} noCancel xwide>
      <ul className="sc-step-list">
        {result.steps.map((s) => (
          <li key={s.key}>
            <Badge tone={s.ok ? "ok" : "critical"}>{s.ok ? T.stepOk : T.stepBad}</Badge>
            <strong>{s.label}</strong>
            <span>{s.detail}</span>
          </li>
        ))}
      </ul>
      {result.tables.length > 0 && <LocalTable label={T.testTitle} columns={columns} rows={result.tables} rowKey={(t) => t.entity} />}
    </Dialog>
  );
}

type PreviewRow = Preview["rows"][number] & { no: number };

function PreviewDialog({ row, onClose }: { row: Row; onClose(): void }) {
  const [data, setData] = useState<Preview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    integrationApi.preview(String(row.Entity)).then((d) => alive && setData(d)).catch((e: unknown) => alive && setError(errorText(e)));
    return () => {
      alive = false;
    };
  }, [row.Entity]);

  const rows: PreviewRow[] = useMemo(() => (data?.rows ?? []).map((r, i) => ({ ...r, no: i })), [data]);
  const columns: LocalColumn<PreviewRow>[] = useMemo(() => [
    ...(data?.columns ?? []).map((c): LocalColumn<PreviewRow> => ({
      key: c.field, label: c.label,
      value: (r) => {
        const v = r.values[c.field];
        return v === null || v === undefined ? null : typeof v === "number" ? v : String(v);
      },
    })),
    { key: "_problem", label: T.problem, wrap: true, value: (r) => r.findings.map((f) => f.message).join(" "),
      render: (r) => r.findings.map((f) => `${f.field ? `${f.field}: ` : ""}${f.message}`).join(" · ") },
  ], [data]);

  return (
    <Dialog title={T.previewTitle(String(row.Name))} subtitle={data ? `${data.view} · ${T.previewRows(data.rows.length)}` : undefined} onClose={onClose} onSubmit={onClose} submitLabel={tr.ui.close} noCancel xwide>
      {error && <Alert tone="error">{error}</Alert>}
      {data?.errors.map((m) => <Alert key={m} tone="error">{m}</Alert>)}
      {data?.warnings.map((m) => <Alert key={m} tone="risk">{m}</Alert>)}
      {rows.length > 0 && <LocalTable label={T.preview} columns={columns} rows={rows} rowKey={(r) => String(r.no)} />}
    </Dialog>
  );
}

function VersionsDialog({ row, onClose }: { row: Row; onClose(): void }) {
  const [items, setItems] = useState<ViewVersion[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    integrationApi.viewVersions(String(row.Entity), ctrl.signal).then(setItems).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, [row.Entity]);

  return (
    <Dialog title={T.versionsTitle(String(row.Name))} onClose={onClose} onSubmit={onClose} submitLabel={tr.ui.close} noCancel xwide>
      {error && <Alert tone="error">{error}</Alert>}
      {items?.length === 0 && <p className="sc-muted">{T.noVersions}</p>}
      {items?.map((v) => (
        <details key={`${v.view}-${v.version}`} className="sc-version" open={v === items[0]}>
          <summary>{T.versionLine(v.version, v.view, when(v.seen_at), v.app_version)}</summary>
          <pre>{v.definition}</pre>
        </details>
      ))}
    </Dialog>
  );
}

export function Integration() {
  const me = useAuth().me!;
  const isOwner = can(me, 96, "write");
  const canTest = can(me, 91, "write");
  const [connection, setConnection] = useState<Connection | null>(null);
  const [database, setDatabase] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [test, setTest] = useState<TestResult | null>(null);
  const [menu, setMenu] = useState<{ row: Row; anchor: HTMLElement } | null>(null);
  const [previewRow, setPreviewRow] = useState<Row | null>(null);
  const [versionRow, setVersionRow] = useState<Row | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const edits = useTableEdits();

  const refresh = useCallback(() => setReloadKey((k) => k + 1), []);
  useEffect(() => {
    const ctrl = new AbortController();
    integrationApi.connection(ctrl.signal).then((c) => {
      setConnection(c);
      setDatabase(c.database ?? "");
    }).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(errorText(e));
    });
    return () => ctrl.abort();
  }, [reloadKey]);

  const saveDatabase = async () => {
    setError(null);
    try {
      setConnection(await integrationApi.saveConnection(database.trim()));
    } catch (e) {
      setError(errorText(e));
    }
  };
  const runTest = async () => {
    setBusy(true);
    setError(null);
    try {
      setTest(await integrationApi.test());
      refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const saveEdits = async () => {
    setSaving(true);
    setError(null);
    try {
      const changes: EntityChange[] = Object.entries(edits.drafts).map(([entity, d]) => ({
        entity,
        ...("Method" in d ? { method: String(d.Method) } : {}),
        ...("ViewName" in d ? { view: String(d.ViewName) } : {}),
      }));
      await integrationApi.saveEntities(changes);
      edits.discard();
      refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setSaving(false);
    }
  };

  const rowMenu: RowMenuSpec = useMemo(() => ({
    label: (row: Row) => T.rowMenu(String(row.Name)),
    onOpen: (row: Row, anchor: HTMLElement) => setMenu({ row, anchor }),
  }), []);
  const cellRender = useMemo(() => ({
    Method: (value: unknown, row: Row) => {
      const key = String(row.Entity);
      return <SelectCell label={T.methodOf(String(row.Name))} value={edits.get(key, "Method", String(value))} options={METHODS} editable={isOwner} changed={edits.changed(key, "Method")}
                         onChange={(next) => edits.set(key, "Method", next, String(value))} />;
    },
    ViewName: (value: unknown, row: Row) => {
      const key = String(row.Entity);
      if (edits.get(key, "Method", String(row.Method)) !== METHOD_SQL) return "";
      return <TextCell label={T.viewOf(String(row.Name))} value={edits.get(key, "ViewName", String(value ?? ""))} placeholder={T.viewPlaceholder} editable={isOwner} changed={edits.changed(key, "ViewName")}
                       onChange={(next) => edits.set(key, "ViewName", next, String(value ?? ""))} />;
    },
    ColumnMatch: (value: unknown, row: Row) => (value ? <FieldMatch text={String(value)} status={row.LastCheckStatus ? String(row.LastCheckStatus) : null} note={row.LastCheckMessage ? String(row.LastCheckMessage) : null} /> : ""),
    LastPullStatus: (value: unknown, row: Row) => <StateChip state={value ? String(value) : null} reason={row.LastPullMessage ? String(row.LastPullMessage) : null} />,
  }), [isOwner, edits]);
  const needsView = (row: Row) => (row.ViewName ? ALLOWED : { allowed: false, reason: T.needsView });
  const testButton = (
    <Button size="sm" variant="secondary" busy={busy} disabledReason={canTest ? (connection?.database ? null : T.needsDatabase) : forbiddenReason(91, "write")} onClick={() => void runTest()}>{T.test}</Button>
  );

  return (
    <section className="sc-page--fill">
      <header className="sc-page-head">
        <h1>{T.title}</h1>
      </header>
      {error && <Alert tone="error">{error}</Alert>}
      <div className="sc-integration-strip">
        {isOwner ? (
          <>
            <TextField label={T.database} value={database} onChange={setDatabase} />
            <Button size="sm" variant="primary" disabled={database.trim() === (connection?.database ?? "")} onClick={() => void saveDatabase()}>{T.save}</Button>
          </>
        ) : <p>{T.database}: <strong>{connection?.database ?? T.undefinedDatabase}</strong></p>}
        {testButton}
        {connection && <p className="sc-muted">{T.account(connection.account)}</p>}
      </div>
      <DataTable list="integration-entities" rowMenu={rowMenu} cellRender={cellRender} reloadKey={reloadKey}
                 toolbarActions={<EditBar dirty={edits.dirty} busy={saving} onSave={() => void saveEdits()} onDiscard={edits.discard} />} />
      <UnsavedGuard dirty={edits.dirty} />
      {menu && (
        <RowPopMenu label={T.rowMenu(String(menu.row.Name))} anchor={menu.anchor} onClose={() => setMenu(null)}>
          <MenuItem label={T.preview} state={needsView(menu.row)} onClick={() => { setPreviewRow(menu.row); setMenu(null); }} />
          <MenuItem label={T.versions} state={ALLOWED} onClick={() => { setVersionRow(menu.row); setMenu(null); }} />
        </RowPopMenu>
      )}
      {test && <TestDialog result={test} onClose={() => setTest(null)} />}
      {previewRow && <PreviewDialog row={previewRow} onClose={() => setPreviewRow(null)} />}
      {versionRow && <VersionsDialog row={versionRow} onClose={() => setVersionRow(null)} />}
    </section>
  );
}

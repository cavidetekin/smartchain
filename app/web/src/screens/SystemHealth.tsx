// Sistem sağlığı (ekran 24, fonksiyon 94, 93; K-106, K-107, docs/12): kartlar, servis şeridi, üç ortak tablo.
// Canlılık: "health" WebSocket mesajı (en sık THROTTLE_MS'te bir) ve POLL_MS yedek yenileme. Ulaşılamazsa son değerler kalır.
import { Eye } from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, ApiError, emitNotice, HEALTH_EVENT } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { formatDateTime, formatNumber, formatTime } from "../format";
import { tr } from "../i18n/tr";
import { DataTable, type RowMenuSpec } from "../table/DataTable";
import type { Row } from "../table/types";
import { Alert, Badge, type BadgeTone, Card, Dialog, KpiCard, Segment } from "../ui";
import { CancelJobDialog } from "./CancelJobDialog";
import { MenuItem, type MenuState, RowPopMenu } from "./RowPopMenu";
import { type EventDetail, type HealthSummary, type ServiceInfo, systemHealthApi } from "./systemHealthApi";

const T = tr.systemHealth;
const POLL_MS = 30_000;
const THROTTLE_MS = 2_000;
const QUEUED = "Sırada";
const TRANSFER = "Aktarım";
const NIGHT = "Gece";
const SYSTEM_OWNER = "System owner";

const SERVICE_TONE: Record<string, BadgeTone> = { Çalışıyor: "ok", Yavaş: "risk", "Yanıt vermiyor": "critical", Kapalı: "critical" };
const JOB_TONE: Record<string, BadgeTone> = { Çalışıyor: "info", Sırada: "risk", Bitti: "ok", Hata: "critical", İptal: "neutral" };

const CELLS = {
  Status: (value: unknown): ReactNode => (value ? <Badge tone={JOB_TONE[String(value)] ?? "neutral"}>{String(value)}</Badge> : null),
};

export function formatBytes(bytes: number): string {
  const gb = bytes / 1024 ** 3;
  return gb >= 1 ? `${formatNumber(gb, 1)} GB` : `${formatNumber(bytes / 1024 ** 2, 0)} MB`;
}

const clock = (iso?: string | null) => (iso ? formatTime(new Date(iso)) : null);

function serviceNote(s: ServiceInfo, summary: HealthSummary): string {
  switch (s.key) {
    case "app":
      return T.version(s.version ?? "");
    case "engine":
      return [clock(s.heartbeat_at) && T.lastSignal(clock(s.heartbeat_at)!), T.busy(s.busy ?? 0)].filter(Boolean).join(" · ");
    case "database":
      return [`${s.ms ?? 0} ms`, T.pool(s.pool_in_use ?? 0, s.pool_size ?? 0), formatBytes(summary.cards.disk.database_bytes),
              T.dataVersions(summary.cards.disk.data_versions)].join(" · ");
    case "notifications":
      return T.connections(s.connections ?? 0);
  }
}

function Overview({ data }: { data: HealthSummary }) {
  const { queue, interactive, errors, disk } = data.cards;
  return (
    <>
      <div className="sc-health-cards">
        <KpiCard label={T.queue} value={String(queue.queued)} tone={queue.warn ? "over" : undefined}
                 note={queue.oldest_wait_minutes === null ? T.queueEmpty : T.queueWait(queue.oldest_wait_minutes)} />
        <KpiCard label={T.interactive} value={`${interactive.running} / ${interactive.limit}`} />
        <KpiCard label={T.errors} value={String(errors.last_7_days)} tone={errors.last_7_days > errors.resolved ? "risk" : undefined}
                 note={errors.last_7_days > 0 ? T.resolved(errors.resolved) : undefined} />
        <KpiCard label={T.disk} value={`%${disk.percent}`} tone={disk.warn ? "over" : undefined}
                 note={T.diskNote(formatBytes(disk.free_bytes), disk.threshold)} />
      </div>
      <Card className="sc-service-strip">
        {data.services.map((s) => (
          <div key={s.key} data-testid={`service-${s.key}`}>
            <span className="sc-service-name">{T.services[s.key]}</span>
            <Badge tone={SERVICE_TONE[s.status] ?? "neutral"}>{s.status}</Badge>
            <span className="sc-muted sc-service-note">{serviceNote(s, data)}</span>
          </div>
        ))}
      </Card>
    </>
  );
}

/** Bildirimlerde işin adı: özet, yoksa numara (K-107). */
const jobLabel = (row: Row) => (row.Summary ? String(row.Summary) : `#${row.Id}`);

function JobMenu({ row, anchor, onClose, onChanged, onCancelOther }: {
  row: Row; anchor: HTMLElement; onClose(): void; onChanged(notice: string): void; onCancelOther(row: Row): void;
}) {
  const me = useAuth().me!;
  const queued = row.Status === QUEUED;
  const own = row.RequestedBy === me.id;
  const locked = Boolean(row.IsProtected) && me.role !== SYSTEM_OWNER;
  const state = (reason: string | null): MenuState => ({ allowed: !reason, reason });
  const cancelState = state(!queued ? T.notQueuedCancel : row.JobType === TRANSFER ? T.transferCancel : locked ? T.protectedJob : null);
  const moveState = state(!queued ? T.notQueuedMove : row.Channel === NIGHT ? T.nightMove : locked ? T.protectedJob : null);

  const run = async (work: () => Promise<unknown>, notice: string) => {
    onClose();
    try {
      await work();
      onChanged(notice);
    } catch (e) {
      emitNotice(e instanceof ApiError ? e.message : tr.users.failed);
    }
  };
  return (
    <RowPopMenu label={T.jobMenu(row.Id)} anchor={anchor} onClose={onClose}>
      <MenuItem label={T.moveUp} state={moveState} onClick={() => void run(() => systemHealthApi.prioritize(row.Id), T.movedNotice(jobLabel(row)))} />
      <MenuItem label={T.cancel} state={cancelState} onClick={() => {
        if (own) {
          void run(() => api.cancelJob(row.Id), T.cancelledNotice(jobLabel(row)));
        } else {
          onClose();
          onCancelOther(row);
        }
      }} />
    </RowPopMenu>
  );
}

function EventDialog({ id, onClose }: { id: number; onClose(): void }) {
  const [event, setEvent] = useState<EventDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const ctrl = new AbortController();
    systemHealthApi.event(id, ctrl.signal).then(setEvent).catch((e: unknown) => {
      if (!ctrl.signal.aborted) setError(e instanceof ApiError ? e.message : tr.users.failed);
    });
    return () => ctrl.abort();
  }, [id]);
  return (
    <Dialog title={T.eventTitle} onClose={onClose} onSubmit={onClose} submitLabel={tr.ui.close} noCancel wide>
      {event && (
        <dl className="sc-detail-rows">
          <dt>{T.eventMessage}</dt><dd>{event.message}</dd>
          <dt>{T.eventComponent}</dt><dd>{event.component}</dd>
          <dt>{T.eventTime}</dt><dd>{formatDateTime(new Date(event.occurred_at))}</dd>
          <dt>{T.eventResolution}</dt><dd>{event.resolution ?? ""}</dd>
          <dt>{T.eventResolved}</dt><dd>{event.is_resolved ? tr.table.yes : tr.table.no}</dd>
          {event.job_id !== null && <><dt>{T.eventJob}</dt><dd>{event.job_id}</dd></>}
          {event.trace_id && <><dt>{T.eventTrace}</dt><dd>{event.trace_id}</dd></>}
          {event.detail && <><dt>{T.eventDetail}</dt><dd>{event.detail}</dd></>}
        </dl>
      )}
      {error && <Alert tone="error">{error}</Alert>}
    </Dialog>
  );
}

type Section = "queue" | "runs" | "events";

export function SystemHealth() {
  const [data, setData] = useState<HealthSummary | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [section, setSection] = useState<Section>("queue");
  const [reloadKey, setReloadKey] = useState(0);
  const [menu, setMenu] = useState<{ row: Row; anchor: HTMLElement } | null>(null);
  const [cancelling, setCancelling] = useState<Row | null>(null);
  const [eventId, setEventId] = useState<number | null>(null);
  const lastLoad = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    lastLoad.current = Date.now();
    try {
      setData(await systemHealthApi.summary());
      setProblem(null);
      setReloadKey((n) => n + 1);  // ulaşılamazken tablo son satırlarıyla kalır
    } catch (e) {
      setProblem(e instanceof ApiError && e.code !== "database_unavailable" ? e.message
        : e instanceof ApiError ? T.databaseDown : T.serverDown);
    }
  }, []);

  useEffect(() => {
    void load();
    const poll = setInterval(() => void load(), POLL_MS);
    const onHealth = () => {
      if (timer.current) return;
      const wait = Math.max(0, THROTTLE_MS - (Date.now() - lastLoad.current));
      timer.current = setTimeout(() => {
        timer.current = null;
        void load();
      }, wait);
    };
    window.addEventListener(HEALTH_EVENT, onHealth);
    return () => {
      clearInterval(poll);
      if (timer.current) clearTimeout(timer.current);
      timer.current = null;
      window.removeEventListener(HEALTH_EVENT, onHealth);
    };
  }, [load]);

  const changed = (notice: string) => {
    emitNotice(notice);
    void load();
  };
  const jobMenu: RowMenuSpec = useMemo(() => ({
    label: (row: Row) => T.jobMenu(row.Id),
    onOpen: (row: Row, anchor: HTMLElement) => setMenu((m) => (m?.row.Id === row.Id ? null : { row, anchor })),
  }), []);
  const eventMenu: RowMenuSpec = useMemo(() => ({
    icon: Eye,
    label: () => T.eventTitle,
    onOpen: (row: Row) => setEventId(row.Id),
  }), []);

  return (
    <section className="sc-page--fill">
      <header className="sc-page-head sc-page-head--row">
        <h1>{T.title}</h1>
        {data && <p className="sc-muted sc-num">{T.serverTime(formatDateTime(new Date(data.server_time)))}</p>}
      </header>
      {problem && <Alert tone="risk">{data ? T.lastKnown(problem, formatTime(new Date(data.server_time))) : problem}</Alert>}
      {data && <Overview data={data} />}
      <div className="sc-section-switch">
        <Segment<Section> label={T.sections} hideLabel value={section} onChange={(v) => { setMenu(null); setSection(v); }}
                 options={[{ value: "queue", label: T.queueSection }, { value: "runs", label: T.runsSection }, { value: "events", label: T.eventsSection }]} />
      </div>
      {section === "queue" && <DataTable key="queue" list="job-queue" cellRender={CELLS} rowMenu={jobMenu} reloadKey={reloadKey} />}
      {section === "runs" && <DataTable key="runs" list="job-runs" cellRender={CELLS} reloadKey={reloadKey} />}
      {section === "events" && <DataTable key="events" list="system-events" rowMenu={eventMenu} reloadKey={reloadKey} />}
      {menu && (
        <JobMenu key={menu.row.Id} row={menu.row} anchor={menu.anchor} onClose={() => setMenu(null)} onChanged={changed}
                 onCancelOther={setCancelling} />
      )}
      {cancelling && (
        <CancelJobDialog jobId={cancelling.Id} onClose={() => setCancelling(null)}
                         summary={[cancelling.Summary ?? cancelling.JobType, cancelling.RequesterName,
                                   cancelling.QueuePosition ? tr.jobs.queuePosition(Number(cancelling.QueuePosition)) : null]
                           .filter(Boolean).join(" · ")}
                         onDone={() => {
                           const label = jobLabel(cancelling);
                           setCancelling(null);
                           changed(T.cancelledNotice(label));
                         }} />
      )}
      {eventId !== null && <EventDialog id={eventId} onClose={() => setEventId(null)} />}
    </section>
  );
}

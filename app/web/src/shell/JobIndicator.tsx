// İş kuyruğu göstergesi (K-69, fonksiyon 48): açılışta /api/jobs, sonra WebSocket ile canlı.
// Panel kartlardan oluşur (K-139): her iş iki satır (üstte iş ve tablo, altta durum çipi ve saat, sağda "Aç"); bir çekim ve onun
// validasyonları tek kart, tıklayınca tablo satırları açılır. Son 5 kart; "Tümünü gör" Sistem sağlığının iş listesine gider.
// Bağlantı koparsa 10 sn'de yeniden bağlanır; bu arada 30 sn'de bir sorgulanır (yedek mod).
// Excel aktarımı çalışırken çip ilerlemeyi yazar ("Excel hazırlanıyor · 120.000 / 142.000 satır"); biten aktarım
// listede indirilir (K-91). Sıradaki işte "İptal": kendi işi herkese (48), başkasının işi Admin ve System owner'a (93);
// "Herkesin işleri" seçeneği yalnız onlarda açık, diğer rollerde pasif ve ipuçlu (K-100).
import { Activity, ChevronDown, ChevronRight, LoaderCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { useNavigate } from "react-router";

import { api, emitNotice, HEALTH_EVENT, historyPath, importResultPath, JOB_CLEANUP, JOB_EVENT, JOB_DONE, JOB_EXPORT, JOB_FAILED, JOB_TRANSFER, JOB_PRECHECK, JOB_PULL, JOB_VALIDATION, pullResultPath, transferResultPath, type Job,
  validationResultPath } from "../api/client";
import { connect, type ConnectionState, socketUrl } from "../api/socket";
import { useAuth } from "../auth/AuthContext";
import { can, forbiddenReason } from "../auth/permissions";
import { formatDateTime, serverDate } from "../format";
import { tr } from "../i18n/tr";
import { CancelJobDialog } from "../screens/CancelJobDialog";
import { Checkbox } from "../ui";

export const POLL_MS = 30_000;
export const ALL_POLL_MS = 10_000;  // herkesin işleri WebSocket'le gelmez; panel açıkken sorgulanır
const RUNNING = "Çalışıyor";
const QUEUED = "Sırada";
const CANCELLED = "İptal";
const SYSTEM_OWNER = "System owner";
const SYSTEM_HEALTH = "/yonetim/sistem-sagligi";
const CROSS_SCOPE = "Tablolar arası";

/** "120.000 / 142.000 satır" → 0,845; okunamazsa null (çubuk çizilmez). */
export function progressRatio(progress: string | null | undefined): number | null {
  const m = /^([\d.]+) \/ ([\d.]+)/.exec(progress ?? "");
  if (!m) return null;
  const [done, all] = [Number(m[1].replaceAll(".", "")), Number(m[2].replaceAll(".", ""))];
  return all > 0 ? Math.min(1, done / all) : null;
}

/** İş panelinin kartı (K-139): tek iş ya da bir çekim ve onun validasyonları. */
export interface JobCard {
  job: Job;
  /** Çekim kartında grubun validasyon işleri (tablo içi, en sonda tablolar arası). */
  children?: Job[];
}

export const CARD_LIMIT = 5;

/** Kartlar: yeniden eskiye; toplu çekimin validasyonları (`validation.group` = çekim işi) çekim kartına girer. */
export function buildCards(jobs: Job[]): JobCard[] {
  const sorted = [...jobs].sort((a, b) => b.id - a.id);
  const pulls = new Set(sorted.filter((j) => j.job_type === JOB_PULL).map((j) => j.id));
  const grouped = new Map<number, Job[]>();
  const cards: JobCard[] = [];
  for (const j of sorted) {
    const group = j.job_type === JOB_VALIDATION ? j.validation?.group : null;
    if (group && pulls.has(group)) grouped.set(group, [...(grouped.get(group) ?? []), j]);
    else cards.push({ job: j });
  }
  return cards.map((c) => (c.job.job_type !== JOB_PULL ? c : {
    ...c,
    children: (grouped.get(c.job.id) ?? []).sort((a, b) => Number(a.validation?.scope === CROSS_SCOPE) - Number(b.validation?.scope === CROSS_SCOPE) || a.id - b.id),
  }));
}

const OUTCOME_TONE: Record<string, string> = { "Hatalı": "critical", "Uyarılı": "risk", "Geçti": "ok" };
const hm = (iso: string | null | undefined) => (iso ? formatDateTime(serverDate(iso)).slice(-5) : "");

/** Kartın durum çipi: bitmiş validasyonda sonuç ve sayı (kırmızı, sarı, yeşil); öteki durumlar gri (K-139). */
export function cardState(j: Job): { text: string; tone: string; running: boolean } {
  const v = j.validation;
  if (j.job_type === JOB_VALIDATION && j.status === JOB_DONE && v?.outcome) {
    const count = v.outcome === "Hatalı" ? v.error_rows : v.outcome === "Uyarılı" ? v.warning_rows : null;
    return { text: tr.validation.chip(v.outcome, count ?? null), tone: OUTCOME_TONE[v.outcome] ?? "neutral", running: false };
  }
  if (j.status === JOB_FAILED) return { text: j.status, tone: "critical", running: false };
  const extra = j.queue_position ? ` · ${tr.jobs.queuePosition(j.queue_position)}` : j.status === RUNNING && j.progress ? ` · ${j.progress}` : "";
  return { text: `${j.status}${extra}`, tone: "neutral", running: j.status === RUNNING };
}

/** Çekim kartının özeti: tabloların son sonucu ("2 Hatalı · 1 Uyarılı · 3 Geçti"); tablolar arası bittiyse onun sonucu geçerlidir. */
export function groupOutcomes(children: Job[]): { outcome: string; count: number }[] {
  const cross = children.find((c) => c.validation?.scope === CROSS_SCOPE && c.status === JOB_DONE && c.validation?.tables);
  const outcomes = cross
    ? cross.validation!.tables!.map((t) => t.outcome)
    : children.filter((c) => c.validation?.scope !== CROSS_SCOPE && c.status === JOB_DONE && c.validation?.outcome).map((c) => c.validation!.outcome!);
  return ["Hatalı", "Uyarılı", "Geçti"].map((o) => ({ outcome: o, count: outcomes.filter((x) => x === o).length })).filter((x) => x.count);
}

function StateTag({ state }: { state: { text: string; tone: string; running: boolean } }) {
  return (
    <span className={`sc-tag sc-tag--${state.tone}`}>
      {state.running && <LoaderCircle className="sc-spin" aria-hidden width={12} height={12} />}
      {state.text}
    </span>
  );
}

export function JobIndicator({ onJob }: { onJob?: (job: Job) => void }) {
  const [jobs, setJobs] = useState<Map<number, Job>>(new Map());
  const [conn, setConn] = useState<ConnectionState>("reconnecting");
  const [open, setOpen] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [everyone, setEveryone] = useState<Job[] | null>(null);  // "Herkesin işleri" seçiliyken
  const me = useAuth().me!;
  const navigate = useNavigate();
  const canSeeAll = can(me, 93, "read", false);
  const [cancelling, setCancelling] = useState<Job | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const toldCancelled = useRef(new Set<number>());
  const onJobRef = useRef(onJob);
  useEffect(() => {
    onJobRef.current = onJob;
  });

  const refresh = useCallback(async () => {
    try {
      const r = await api.jobs();
      setJobs(new Map(r.jobs.map((j) => [j.id, j])));
      r.jobs.forEach((j) => onJobRef.current?.(j));
    } catch {
      // bağlantı yok; gösterge son bilinen durumda kalır
    }
  }, []);

  useEffect(() => {
    refresh();
    const handle = connect(
      socketUrl("/api/ws"),  // oturum çerezle (K-97)
      (msg) => {
        if (msg.type === "job") {
          const job = msg.job as Job;
          setJobs((prev) => new Map(prev).set(job.id, job));
          onJobRef.current?.(job);
          window.dispatchEvent(new CustomEvent<Job>(JOB_EVENT, { detail: job }));  // ekranlar yenilenir (K-143)
          // Başkası iptal etti (mesaj yalnız sahibine gelir; kendi iptalinde neden yok, K-107)
          if (job.status === CANCELLED && job.cancel_reason && !toldCancelled.current.has(job.id)) {
            toldCancelled.current.add(job.id);
            emitNotice(tr.jobs.cancelledByOther(job.summary ?? job.job_type, job.cancel_reason));
          }
        } else if (msg.type === "health") {
          window.dispatchEvent(new Event(HEALTH_EVENT));
        }
      },
      (state) => {
        setConn(state);
        if (state === "connected") refresh();
      },
    );
    return () => handle.close();
  }, [refresh]);

  useEffect(() => {
    if (conn === "connected") return;
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [conn, refresh]);

  const showAll = everyone !== null;
  const loadAll = useCallback(async () => {
    try {
      setEveryone((await api.jobs("all")).jobs);
    } catch {
      // 403 tek yerde bildirilir; liste son bilinen hâlde kalır
    }
  }, []);
  useEffect(() => {
    if (!open || !showAll) return;
    const t = setInterval(loadAll, ALL_POLL_MS);
    return () => clearInterval(t);
  }, [open, showAll, loadAll]);

  const afterCancel = async () => {
    await refresh();
    if (showAll) await loadAll();
  };
  const cancel = async (j: Job) => {
    if (j.requested_by !== me.id) {  // başkasının işi: neden zorunlu (K-107)
      setCancelling(j);
      return;
    }
    setDownloadError(null);
    try {
      await api.cancelJob(j.id);
    } catch (e) {
      setDownloadError(e instanceof Error ? e.message : String(e));
    }
    await afterCancel();
  };
  const canCancel = (j: Job) => j.status === QUEUED && j.job_type !== JOB_TRANSFER && (j.requested_by === me.id
    || (can(me, 93, "write", false) && (!j.is_protected || me.role === SYSTEM_OWNER)));

  const all = [...jobs.values()];
  const running = all.filter((j) => j.status === RUNNING).length;
  const queued = all.filter((j) => j.status === QUEUED).length;
  const delayed = conn === "connected" ? undefined : tr.jobs.delayed;  // sorun yokken metin yok
  const cards = buildCards(everyone ?? all).slice(0, CARD_LIMIT);
  const exporting = all.find((j) => j.job_type === JOB_EXPORT && j.status === RUNNING)
    ?? all.find((j) => j.job_type === JOB_EXPORT && j.status === QUEUED);
  const ratio = exporting?.status === RUNNING ? progressRatio(exporting.progress) : null;
  const canSeeHealth = can(me, 94, "read", false);

  const download = async (j: Job) => {
    setDownloadError(null);
    try {
      await api.downloadExport(j.id, "smartchain.xlsx");
    } catch (e) {
      setDownloadError(e instanceof Error ? e.message : String(e));
    }
  };
  const go = (path: string) => {
    setOpen(false);
    navigate(path);
  };
  const mine = (j: Job) => (j.requested_by ?? me.id) === me.id;
  const ended = (j: Job) => j.status === JOB_DONE || j.status === JOB_FAILED;

  /** Kartın sağındaki "Aç" (ya da "İndir"): iş türüne göre sonuç. */
  const action = (j: Job, title: string) => {
    if (j.job_type === JOB_EXPORT && j.status === JOB_DONE && mine(j)) {
      return <button type="button" className="sc-link-btn" onClick={() => download(j)}>{tr.jobs.download}</button>;
    }
    const path = j.job_type === JOB_PRECHECK && j.status === JOB_DONE && j.import_batch_id && mine(j) ? importResultPath(j.import_batch_id)
      : j.job_type === JOB_VALIDATION && j.validation?.entity && ended(j) ? validationResultPath(j.validation.entity)
        : j.job_type === JOB_PULL && ended(j) && mine(j) ? pullResultPath(j.id)
          : j.job_type === JOB_TRANSFER && ended(j) && mine(j) ? transferResultPath(j.id)
            : j.job_type === JOB_CLEANUP && ended(j) && mine(j) ? historyPath : null;
    return path ? <button type="button" className="sc-link-btn" aria-label={tr.jobs.openOf(title)} onClick={() => go(path)}>{tr.jobs.open}</button> : null;
  };
  const meta = (j: Job) => (
    <>
      {showAll && j.requested_by !== me.id && j.requested_by_name && <span className="sc-muted">{tr.jobs.ownerOf(j.requested_by_name)}</span>}
      {j.cancel_reason && <span className="sc-muted">{j.cancel_reason}</span>}
      {canCancel(j) && (
        <button type="button" className="sc-link-btn" onClick={() => void cancel(j)} aria-label={tr.jobs.cancelOf(j.id)}>{tr.jobs.cancel}</button>
      )}
    </>
  );

  const single = (j: Job) => {
    const title = j.summary ?? j.job_type;
    return (
      <li key={j.id} className="sc-job-card">
        <div className="sc-job-card-main">
          <span className="sc-job-card-title">{title}</span>
          <span className="sc-job-card-sub"><StateTag state={cardState(j)} /><span className="sc-num sc-muted">{hm(j.created_at ?? j.updated_at)}</span>{meta(j)}</span>
        </div>
        <span className="sc-job-card-action">{action(j, title)}</span>
      </li>
    );
  };

  const group = (card: JobCard) => {
    const j = card.job;
    const kids = card.children ?? [];
    const title = `${j.summary ?? j.job_type} · ${hm(j.created_at ?? j.updated_at)}`;
    const busy = j.status === RUNNING || j.status === QUEUED || kids.some((c) => c.status === RUNNING || c.status === QUEUED);
    const parts = groupOutcomes(kids);
    const isOpen = expanded.has(j.id);
    const cross = kids.find((c) => c.validation?.scope === CROSS_SCOPE && c.status === JOB_DONE)?.validation?.tables ?? null;
    const shownState = (c: Job) => {  // tablolar arası bittiyse tablonun son sonucu onunkidir
      const t = cross?.find((x) => x.entity === c.validation?.entity);
      return t ? cardState({ ...c, validation: { ...c.validation!, outcome: t.outcome, error_rows: t.error_rows, warning_rows: t.warning_rows } }) : cardState(c);
    };
    return (
      <li key={j.id} className="sc-job-card">
        <div className="sc-job-card-main">
          <button type="button" className="sc-job-card-title sc-job-card-toggle" aria-expanded={isOpen} aria-label={tr.jobs.toggleGroup(title)}
                  onClick={() => setExpanded((s) => { const n = new Set(s); if (n.has(j.id)) n.delete(j.id); else n.add(j.id); return n; })}>
            {isOpen ? <ChevronDown aria-hidden width={14} height={14} /> : <ChevronRight aria-hidden width={14} height={14} />}
            {title}
          </button>
          <span className="sc-job-card-sub">
            {busy || !parts.length ? <StateTag state={cardState(j.status === JOB_DONE && busy ? { ...j, status: RUNNING, progress: null } : j)} /> : parts.map((p) => (
              <span key={p.outcome} className={`sc-tag sc-tag--${OUTCOME_TONE[p.outcome]}`}>{tr.jobs.stateCount(p.count, p.outcome)}</span>
            ))}
            {meta(j)}
          </span>
          {isOpen && (
            <ul className="sc-job-card-rows">
              {kids.map((c) => {
                const name = c.validation?.scope === CROSS_SCOPE ? tr.jobs.crossTables : c.validation?.name ?? c.summary ?? c.job_type;
                return (
                  <li key={c.id}>
                    <span>{name}</span>
                    <StateTag state={shownState(c)} />
                    <span className="sc-job-card-action">{c.validation?.scope === CROSS_SCOPE ? null : action(c, name)}</span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <span className="sc-job-card-action">{action(j, title)}</span>
      </li>
    );
  };

  return (
    <div className="sc-jobs">
      <button type="button" className="sc-chip sc-chip-btn" aria-haspopup="dialog" aria-expanded={open}
              onClick={() => setOpen(!open)} title={delayed} data-testid="job-indicator">
        {running ? <LoaderCircle aria-hidden="true" className="sc-spin" /> : <Activity aria-hidden="true" />}
        <span>
          {exporting
            ? exporting.status === RUNNING ? tr.jobs.exporting(exporting.progress) : tr.jobs.exportQueued
            : tr.jobs.count(running, queued)}
        </span>
        {ratio !== null && (
          <span className="sc-progress" role="progressbar" aria-valuemin={0} aria-valuemax={100}
                aria-valuenow={Math.round(ratio * 100)}>
            <span className="sc-progress-fill" style={{ width: `${ratio * 100}%` }} />
          </span>
        )}
        <span className={`sc-dot is-${conn}`} {...(delayed ? { "aria-label": delayed, role: "img" } : { "aria-hidden": true })} />
      </button>
      {open && (
        <div className="sc-popover sc-jobs-panel" role="dialog" aria-label={tr.jobs.title}>
          <div className="sc-popover-title">{tr.jobs.title}</div>
          {delayed && <p className="sc-muted">{delayed}</p>}
          <span title={canSeeAll ? undefined : forbiddenReason(93, "read")}>
            <Checkbox label={tr.jobs.allJobs} checked={showAll} disabled={!canSeeAll}
                      onChange={(on) => (on ? void loadAll() : setEveryone(null))} />
          </span>
          {cards.length === 0 ? (
            <p className="sc-muted">{tr.jobs.empty}</p>
          ) : (
            <ul className="sc-job-list">
              {cards.map((c) => (c.job.job_type === JOB_PULL && c.children?.length ? group(c) : single(c.job)))}
            </ul>
          )}
          {canSeeHealth && (
            <button type="button" className="sc-link-btn sc-jobs-all" onClick={() => go(SYSTEM_HEALTH)}>{tr.jobs.seeAll}</button>
          )}
          {downloadError && <p className="sc-field-error" role="alert">{downloadError}</p>}
        </div>
      )}
      {cancelling && (
        <CancelJobDialog jobId={cancelling.id} onClose={() => setCancelling(null)}
                         summary={[cancelling.summary ?? cancelling.job_type, cancelling.requested_by_name,
                                   cancelling.queue_position ? tr.jobs.queuePosition(cancelling.queue_position) : null]
                           .filter(Boolean).join(" · ")}
                         onDone={() => {
                           setCancelling(null);
                           void afterCancel();
                         }} />
      )}
    </div>
  );
}

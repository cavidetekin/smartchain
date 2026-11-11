// Zamanlanmış akışın durumu (K-163, docs/12): bağlam çubuğundaki çip ve akış sürerken pasif düğmeler aynı kaynaktan okur
// (GET /api/flows/status; ana sayfa 9.1'de de). Çip yalnız son akış durduğunda ya da başlamadığında görünür, kişi kapatana kadar kalır;
// yeni bir durma ilk görüldüğünde bildirim de çıkar. End user'da (01 okuma yok) sorgulanmaz.
import { TriangleAlert } from "lucide-react";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";

import { emitNotice, flowHistoryPath, JOB_EVENT } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { can } from "../auth/permissions";
import { formatDateTime, serverDate } from "../format";
import { tr } from "../i18n/tr";
import { userPrefs } from "../prefs";
import { FLOW_STOPPED, type FlowAlert, type FlowStatus, flowsApi } from "../screens/flowsApi";
import { Button } from "../ui";

export const FLOW_POLL_MS = 20_000;
const T = tr.flows;

interface FlowState {
  status: FlowStatus | null;
  refresh(): void;
}

const FlowContext = createContext<FlowState>({ status: null, refresh: () => {} });

export function FlowStatusProvider({ children }: { children: ReactNode }) {
  const me = useAuth().me!;
  const allowed = can(me, 1, "read");
  const [status, setStatus] = useState<FlowStatus | null>(null);
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((n) => n + 1), []);
  const prefs = useMemo(() => userPrefs(me.id), [me.id]);

  useEffect(() => {
    if (!allowed) return;
    const ctrl = new AbortController();
    const load = () => flowsApi.status(ctrl.signal).then(setStatus).catch(() => undefined);  // ulaşılamazsa son bilinen hâl kalır
    let soon: number | undefined;
    const onJob = () => {  // çekimde art arda gelen iş bildirimleri tek sorgu olur
      window.clearTimeout(soon);
      soon = window.setTimeout(() => void load(), 1000);
    };
    void load();
    const t = window.setInterval(() => void load(), FLOW_POLL_MS);
    window.addEventListener(JOB_EVENT, onJob);
    return () => {
      ctrl.abort();
      window.clearInterval(t);
      window.clearTimeout(soon);
      window.removeEventListener(JOB_EVENT, onJob);
    };
  }, [allowed, tick]);

  useEffect(() => {
    if (!status?.alerts.length) return;
    const seen = prefs.notifiedFlowRuns();
    const fresh = status.alerts.filter((a) => !seen.includes(a.id));
    if (!fresh.length) return;
    fresh.forEach((a) => emitNotice(alertText(a, true)));
    prefs.setNotifiedFlowRuns([...seen, ...fresh.map((a) => a.id)]);
  }, [status, prefs]);

  const value = useMemo(() => ({ status, refresh }), [status, refresh]);
  return <FlowContext.Provider value={value}>{children}</FlowContext.Provider>;
}

export const useFlowStatus = () => useContext(FlowContext);

/** Akış sürerken (bekliyor ya da çalışıyor) veri işleri ve kural kaydı pasif: ipucu metni; sürmüyorsa null. */
export function useFlowLock(): string | null {
  return useContext(FlowContext).status?.running?.message ?? null;
}

const hm = (iso: string) => formatDateTime(serverDate(iso)).slice(-5);

/** "Gece akışı durdu · 02:14 · Veri çekme" ya da "Gece akışı başlamadı · 02:00"; bildirimde akışın adı ve nedeni de. */
export function alertText(a: FlowAlert, full = false): string {
  const head = a.state === FLOW_STOPPED ? T.chipStopped(hm(a.at), a.step) : T.chipNotStarted(hm(a.scheduled_at));
  return full ? `${head} · ${a.flow_name}${a.reason ? ` · ${a.reason}` : ""}` : head;
}

export function FlowAlertChip() {
  const { status, refresh } = useFlowStatus();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const alerts = status?.alerts ?? [];
  if (!alerts.length) return null;
  const first = alerts[0];
  const dismiss = async (a: FlowAlert) => {
    await flowsApi.dismiss(a.id).catch(() => undefined);
    if (alerts.length === 1) setOpen(false);
    refresh();
  };

  return (
    <div className="sc-flow-alert" ref={ref}>
      <button type="button" className="sc-tag sc-tag--critical sc-chip-btn" aria-expanded={open} data-testid="flow-alert"
              onClick={() => setOpen((o) => !o)} onKeyDown={(e) => e.key === "Escape" && setOpen(false)}>
        <TriangleAlert aria-hidden="true" width={14} height={14} />
        {alertText(first)}{alerts.length > 1 ? ` · +${alerts.length - 1}` : ""}
      </button>
      {open && (
        <div className="sc-popover" role="dialog" aria-label={T.alertTitle}>
          <strong>{T.alertTitle}</strong>
          <ul className="sc-flow-alert-list">
            {alerts.map((a) => (
              <li key={a.id}>
                <p><strong>{a.flow_name}</strong> · {a.state} · {formatDateTime(serverDate(a.at))}{a.state === FLOW_STOPPED ? ` · ${a.step}` : ""}</p>
                {a.reason && <p className="sc-muted">{a.reason}</p>}
                <span className="sc-flow-alert-actions">
                  {status?.can_view_history && (
                    <Button size="sm" variant="neutral" onClick={() => { setOpen(false); navigate(flowHistoryPath(a.flow_id)); }}>{T.history}</Button>
                  )}
                  <Button size="sm" variant="neutral" onClick={() => void dismiss(a)}>{T.dismiss}</Button>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

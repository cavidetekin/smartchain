// Hareketsizlik (mockup m24f-0740; K-97). Yalnız kullanıcı girdisi (tuş, tıklama, tekerlek, dokunma; fare gezdirmek
// sayılmaz) etkinliktir. Girdi olunca sunucuya en çok dakikada bir "etkinlik" bildirilir; süre bu bildirimden ölçülür,
// böylece istemci ve sunucu aynı anda doldurur. Sekmeler bildirimi paylaşır (BroadcastChannel). Sınırdan
// SessionWarningMinutes önce geri sayımlı pencere açılır (önce sunucuya sorulur: başka sekmede çalışılıyorsa açılmaz);
// pencere açıkken yalnız "Devam et" süreyi uzatır. Süre dolunca giriş sayfasına dönülür.
import { useCallback, useEffect, useRef, useState } from "react";

import { tr } from "../i18n/tr";
import { Dialog } from "../ui";
import { authApi, type Me } from "./authApi";
import { type TabMessage, useAuth } from "./AuthContext";

export const PING_EVERY_MS = 60_000;
const INPUT_EVENTS = ["keydown", "mousedown", "wheel", "touchstart"] as const;

export function countdown(seconds: number): string {
  const s = Math.max(0, seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function useIdle(me: Me, channel: BroadcastChannel | null, onTimeout: () => void) {
  const limit = me.session.idle_minutes * 60_000;
  const warnBefore = me.session.warning_minutes * 60_000;
  const last = useRef(Date.now() - (limit - me.idle_seconds_left * 1000));  // son bildirilen etkinlik
  const pending = useRef(false);  // bildirilmemiş girdi var
  const checking = useRef(false);
  const warningRef = useRef(false);
  const timeoutRef = useRef(onTimeout);
  const [warning, setWarning] = useState(false);
  const [left, setLeft] = useState(Math.ceil(me.idle_seconds_left));

  useEffect(() => {
    timeoutRef.current = onTimeout;
  });

  const showWarning = useCallback((value: boolean) => {
    warningRef.current = value;
    setWarning(value);
  }, []);

  const seen = useCallback((at: number) => {
    last.current = Math.max(last.current, at);
  }, []);

  const ping = useCallback(() => {
    pending.current = false;
    const at = Date.now();
    seen(at);
    channel?.postMessage({ type: "activity", at } satisfies TabMessage);
    void authApi.activity().catch(() => undefined);  // 401'de oturum olayı giriş sayfasına döndürür
  }, [channel, seen]);

  useEffect(() => {
    const onInput = () => {
      if (warningRef.current) return;  // pencere açıkken yalnız "Devam et"
      if (Date.now() - last.current >= PING_EVERY_MS) ping();
      else pending.current = true;
    };
    INPUT_EVENTS.forEach((name) => window.addEventListener(name, onInput, { capture: true, passive: true }));
    return () => INPUT_EVENTS.forEach((name) => window.removeEventListener(name, onInput, { capture: true }));
  }, [ping]);

  useEffect(() => {
    if (!channel) return;
    const onMessage = (e: MessageEvent<TabMessage>) => {
      if (e.data.type !== "activity") return;
      seen(e.data.at);
      if (warningRef.current) showWarning(false);
    };
    channel.addEventListener("message", onMessage);
    return () => channel.removeEventListener("message", onMessage);
  }, [channel, seen, showWarning]);

  useEffect(() => {
    const tick = () => {
      const now = Date.now();
      if (pending.current && now - last.current >= PING_EVERY_MS) ping();
      const remaining = limit - (now - last.current);
      setLeft(Math.ceil(Math.max(0, remaining) / 1000));
      if (remaining <= 0) {
        showWarning(false);
        timeoutRef.current();
        return;
      }
      if (remaining <= warnBefore && !warningRef.current && !checking.current) {
        checking.current = true;
        authApi.me()
          .then((m) => {
            const server = m.idle_seconds_left * 1000;
            if (server > remaining + 5_000) seen(Date.now() - (limit - server));  // başka sekmede çalışılıyor
            else showWarning(true);
          })
          .catch(() => showWarning(true))
          .finally(() => {
            checking.current = false;
          });
      }
    };
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [limit, warnBefore, ping, seen, showWarning]);

  const stay = useCallback(() => {
    showWarning(false);
    ping();
  }, [ping, showWarning]);

  return { warning, secondsLeft: left, stay };
}

export function IdleWatch({ me }: { me: Me }) {
  const { channel, signOut } = useAuth();
  const { warning, secondsLeft, stay } = useIdle(me, channel, () => void signOut("timeout"));
  if (!warning) return null;
  const { idle_minutes: idle, warning_minutes: warn } = me.session;
  return (
    <Dialog title={tr.auth.idleTitle} subtitle={tr.auth.idleFor(idle - warn)} onSubmit={stay}
            submitLabel={tr.auth.stay} onClose={() => void signOut("logout")} cancelLabel={tr.auth.logoutNow}
            dismissible={false} blurred>
      <div className="sc-idle">
        <p className="sc-idle-count" role="timer" aria-label={tr.auth.idleCountdown}>{countdown(secondsLeft)}</p>
        <p className="sc-idle-limit">{tr.auth.idleLimit(idle)}</p>
      </div>
    </Dialog>
  );
}

// Oturum durumu (K-97): açılışta GET /api/auth/me; herhangi bir istek 401 (oturum yok ya da zaman aşımı) dönerse ya da
// WebSocket oturum bitti diye kapanırsa giriş sayfasına dönülür. Sekmeler giriş, çıkış ve etkinliği BroadcastChannel ile
// paylaşır: bir sekmede çıkılınca hepsi çıkar.
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { AUTH_EVENT, type AuthEventDetail } from "../api/client";
import { tr } from "../i18n/tr";
import { authApi, type Me } from "./authApi";

export type AuthStatus = "loading" | "anon" | "ready";
export type SignOutReason = "logout" | "timeout";

/** Sekmeler arası mesajlar */
export type TabMessage = { type: "logout"; notice: string } | { type: "login" } | { type: "activity"; at: number };

interface AuthState {
  status: AuthStatus;
  me: Me | null;
  /** Giriş sayfasının üstünde gösterilecek bilgi (ör. zaman aşımı) */
  notice: string | null;
  signIn(me: Me): void;
  signOut(reason: SignOutReason): Promise<void>;
  refresh(): Promise<void>;
  /** Sekmeler arası kanal (yoksa null; ör. eski tarayıcı) */
  channel: BroadcastChannel | null;
}

const AuthContext = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("AuthProvider yok");
  return ctx;
}

function openChannel(): BroadcastChannel | null {
  try {
    return typeof BroadcastChannel === "undefined" ? null : new BroadcastChannel("smartchain-auth");
  } catch {
    return null;
  }
}

/** initialMe: testlerde ve önceden bilinen oturumda açılış isteği atlanır (undefined: sunucuya sorulur). */
export function AuthProvider({ children, initialMe }: { children: ReactNode; initialMe?: Me | null }) {
  const [me, setMe] = useState<Me | null>(initialMe ?? null);
  const [status, setStatus] = useState<AuthStatus>(initialMe === undefined ? "loading" : initialMe ? "ready" : "anon");
  const [notice, setNotice] = useState<string | null>(null);
  const [channel] = useState(openChannel);
  const statusRef = useRef(status);
  useEffect(() => {
    statusRef.current = status;
  });

  const drop = useCallback((text: string | null) => {
    setMe(null);
    setStatus("anon");
    setNotice(text);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const next = await authApi.me();
      setMe(next);
      setStatus("ready");
    } catch {
      if (statusRef.current !== "ready") setStatus("anon");  // 401'de olay da yayılır (drop)
    }
  }, []);

  useEffect(() => {
    if (initialMe === undefined) void refresh();
  }, [initialMe, refresh]);

  useEffect(() => {
    const onAuth = (e: Event) => {
      const detail = (e as CustomEvent<AuthEventDetail>).detail;
      if (detail.kind === "check") {
        void refresh();
      } else if (statusRef.current === "ready") {
        drop(detail.code === "session_expired" ? detail.message : tr.auth.ended);
      } else {
        setStatus("anon");
      }
    };
    window.addEventListener(AUTH_EVENT, onAuth);
    return () => window.removeEventListener(AUTH_EVENT, onAuth);
  }, [drop, refresh]);

  useEffect(() => {
    if (!channel) return;
    const onMessage = (e: MessageEvent<TabMessage>) => {
      if (e.data.type === "logout" && statusRef.current === "ready") drop(e.data.notice);
      if (e.data.type === "login" && statusRef.current !== "ready") void refresh();
    };
    channel.addEventListener("message", onMessage);
    return () => {
      channel.removeEventListener("message", onMessage);
    };
  }, [channel, drop, refresh]);

  useEffect(() => () => channel?.close(), [channel]);

  const signIn = useCallback((next: Me) => {
    setMe(next);
    setStatus("ready");
    setNotice(null);
    channel?.postMessage({ type: "login" } satisfies TabMessage);
  }, [channel]);

  const signOut = useCallback(async (reason: SignOutReason) => {
    const minutes = me?.session.idle_minutes ?? 30;
    const text = reason === "timeout" ? tr.auth.timedOut(minutes) : tr.auth.loggedOut;
    // Zaman aşımında sunucudaki oturum da aynı anda dolmuştur; kapanışı ("Zaman aşımı") sunucu yazar.
    if (reason === "logout") await authApi.logout().catch(() => undefined);
    channel?.postMessage({ type: "logout", notice: text } satisfies TabMessage);
    drop(text);
  }, [channel, drop, me]);

  const value = useMemo(() => ({ status, me, notice, signIn, signOut, refresh, channel }),
                        [status, me, notice, signIn, signOut, refresh, channel]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

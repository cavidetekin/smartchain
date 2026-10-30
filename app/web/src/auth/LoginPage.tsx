// Giriş sayfası (mockup m24f-0738; fonksiyon 89). Kullanıcı adı, şifre, tek düğme. Hata mesajı geneldir (hesabın
// varlığı belli olmaz) ve kalan deneme yazılır; kilit ve kapalı hesap sunucunun mesajıyla. "Beni hatırla" yok.
import { ChartLine } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router";

import { ApiError } from "../api/client";
import { tr } from "../i18n/tr";
import { HOME } from "../screens/catalog";
import { Alert, Button, TextField } from "../ui";
import { appVersion, authApi } from "./authApi";
import { useAuth } from "./AuthContext";

/** Yalnız uygulama içi adrese dönülür (dış adrese yönlendirme yok). */
export function safeNext(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/giris") ? next : HOME.path;
}

function failure(e: unknown): string {
  if (!(e instanceof ApiError)) return tr.auth.unreachable;
  const d = e.details[0] as unknown as { remaining_attempts?: number; lock_after?: number; lock_minutes?: number } | undefined;
  if (e.code === "login_failed" && d?.remaining_attempts !== undefined) {
    return tr.auth.failed(d.remaining_attempts, d.lock_after ?? 0, d.lock_minutes ?? 0);
  }
  return e.message;
}

export function LoginPage() {
  const { status, notice, signIn } = useAuth();
  // useSearchParams değil: react-router onu derlemeye dış adresli bir uyarıyla getiriyor (internetsizlik bekçisi).
  const next = new URLSearchParams(useLocation().search).get("next");
  const [userName, setUserName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    void appVersion().then((v) => alive && setVersion(v));
    return () => {
      alive = false;
    };
  }, []);

  if (status === "ready") return <Navigate to={safeNext(next)} replace />;

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!userName.trim() || !password || busy) return;
    setBusy(true);
    setError(null);
    try {
      signIn(await authApi.login(userName.trim(), password));
    } catch (err) {
      setError(failure(err));
      setPassword("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="sc-auth-page">
      <form className="sc-auth-card" onSubmit={submit} aria-label={tr.auth.login}>
        <div className="sc-auth-brand">
          <span className="sc-logo"><ChartLine aria-hidden="true" /></span>
          <h1 className="sc-auth-title">{tr.app.name}</h1>
        </div>
        {notice && <Alert tone="info">{notice}</Alert>}
        <TextField label={tr.auth.userName} value={userName} onChange={setUserName} autoComplete="username"
                   autoFocus autoCapitalize="none" spellCheck={false} />
        <TextField label={tr.auth.password} type="password" value={password} onChange={setPassword}
                   autoComplete="current-password" error={error ?? undefined} />
        <Button type="submit" variant="primary" busy={busy} disabled={!userName.trim() || !password}
                className="sc-auth-submit">
          {tr.auth.login}
        </Button>
        <p className="sc-auth-note">{tr.auth.loginNote}</p>
      </form>
      <p className="sc-auth-footer">{tr.auth.footer(version)}</p>
    </main>
  );
}

// Oturum kapısı (K-97): oturum yoksa giriş sayfasına (dönülecek adresle), şifre değişikliği bekliyorsa atlanamaz
// şifre penceresine; ikisi de değilse kabuğa geçilir.
import { Navigate, Outlet, useLocation } from "react-router";

import { useAuth } from "./AuthContext";
import { PasswordDialog } from "./PasswordDialog";

export function AuthGate() {
  const { status, me, refresh } = useAuth();
  const location = useLocation();
  if (status === "loading") return null;
  if (status === "anon" || !me) {
    const next = location.pathname + location.search;
    return <Navigate to={`/giris?next=${encodeURIComponent(next)}`} replace />;
  }
  if (me.must_change_password) {
    return (
      <main className="sc-auth-page">
        <PasswordDialog me={me} forced onDone={() => void refresh()} />
      </main>
    );
  }
  return <Outlet />;
}

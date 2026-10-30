// Yetkisiz ekran (K-100): ekran menüde görünmez; adres çubuğundan açılırsa boş sayfa yerine neden ve kimden isteneceği.
import { ShieldX } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { useAuth } from "../auth/AuthContext";
import { can, requiredRole, SYSTEM_OWNER } from "../auth/permissions";
import { tr } from "../i18n/tr";
import { Card } from "../ui";
import { HOME } from "./catalog";

/** Ekranı görme yetkisi (fonksiyonun okuma yetkisi) yoksa açıklama sayfası. */
export function ScreenGate({ fn, children }: { fn: number; children: ReactNode }) {
  const me = useAuth().me!;
  if (can(me, fn)) return <>{children}</>;
  const role = requiredRole(fn, "read");
  return (
    <section className="sc-page">
      <header className="sc-page-head">
        <h1>{tr.authz.screenTitle}</h1>
      </header>
      <Card className="sc-placeholder">
        <ShieldX aria-hidden="true" className="sc-placeholder-icon" />
        <p>{tr.authz.screenText(role, role === SYSTEM_OWNER)}</p>
        <Link to={HOME.path} className="sc-link">{tr.screen.backHome}</Link>
      </Card>
    </section>
  );
}

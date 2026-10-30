// Yetki reddi bildirimi (K-100): sunucu 403 forbidden ya da sahiplik reddi dönerse sağ altta sunucunun mesajı
// ("Bu işlem için Admin yetkisi gerekir. Yetki için yöneticinize başvurun."). Tek yerde: api/client.ts olayı yayar.
import { ShieldX, X } from "lucide-react";
import { useEffect, useState } from "react";

import { FORBIDDEN_EVENT } from "../api/client";
import { tr } from "../i18n/tr";

const HIDE_MS = 10_000;

export function ForbiddenNotice() {
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const on = (e: Event) => setMessage((e as CustomEvent<string>).detail);
    window.addEventListener(FORBIDDEN_EVENT, on);
    return () => window.removeEventListener(FORBIDDEN_EVENT, on);
  }, []);

  useEffect(() => {
    if (!message) return;
    const t = setTimeout(() => setMessage(null), HIDE_MS);
    return () => clearTimeout(t);
  }, [message]);

  if (!message) return null;
  return (
    <div className="sc-toasts sc-toasts--notice" role="region" aria-label={tr.authz.notice}>
      <div className="sc-toast is-error" role="alert">
        <ShieldX aria-hidden="true" className="sc-toast-icon" />
        <div className="sc-toast-body">
          <p className="sc-toast-title">{message}</p>
        </div>
        <button type="button" className="sc-toast-close" onClick={() => setMessage(null)} aria-label={tr.ui.close}
                title={tr.ui.close}>
          <X aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

// Kabuk bildirimi. Yetki reddi (K-100): sunucu 403 forbidden ya da sahiplik reddi dönerse sağ altta sunucunun mesajı
// ("Bu işlem için Admin yetkisi gerekir. Yetki için yöneticinize başvurun."). Tek yerde: api/client.ts olayı yayar.
// Bilgi (2.3): rol değişti, kullanıcı oluşturuldu gibi kısa mesajlar (NOTICE_EVENT).
import { Info, ShieldX, X } from "lucide-react";
import { useEffect, useState } from "react";

import { FORBIDDEN_EVENT, NOTICE_EVENT } from "../api/client";
import { tr } from "../i18n/tr";

const HIDE_MS = 10_000;

export function ForbiddenNotice() {
  const [message, setMessage] = useState<string | null>(null);
  const [denied, setDenied] = useState(false);

  useEffect(() => {
    const show = (isDenied: boolean) => (e: Event) => {
      setDenied(isDenied);
      setMessage((e as CustomEvent<string>).detail);
    };
    const onDenied = show(true);
    const onInfo = show(false);
    window.addEventListener(FORBIDDEN_EVENT, onDenied);
    window.addEventListener(NOTICE_EVENT, onInfo);
    return () => {
      window.removeEventListener(FORBIDDEN_EVENT, onDenied);
      window.removeEventListener(NOTICE_EVENT, onInfo);
    };
  }, []);

  useEffect(() => {
    if (!message) return;
    const t = setTimeout(() => setMessage(null), HIDE_MS);
    return () => clearTimeout(t);
  }, [message]);

  if (!message) return null;
  return (
    <div className="sc-toasts sc-toasts--notice" role="region" aria-label={tr.authz.notice}>
      <div className={`sc-toast${denied ? " is-error" : ""}`} role={denied ? "alert" : "status"}>
        {denied ? <ShieldX aria-hidden="true" className="sc-toast-icon" /> : <Info aria-hidden="true" className="sc-toast-icon" />}
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

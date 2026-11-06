// Sağdan çekmece (K-134, docs/12): sayfanın üstünde durur, arkası karartılmaz; Esc ve kapatma düğmesi kapatır, odak içinde kalır.
// Pencereden farkı: sayfa bağlamı görünür kalır (ör. Veri yükleme tablosu). Genişliği pencerenin yarısı, en az 640 px.
import { X } from "lucide-react";
import { type KeyboardEvent, type ReactNode, useEffect, useId, useRef } from "react";

import { tr } from "../i18n/tr";

const FOCUSABLE = "a[href], input, select, textarea, button:not([disabled]), [tabindex]:not([tabindex='-1'])";

export function Drawer({ title, subtitle, children, actions, onClose }: {
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  /** Alttaki düğmeler (ör. Hatalı kayıtları indir, Yeniden doğrula). */
  actions?: ReactNode;
  onClose(): void;
}) {
  const titleId = useId();
  const ref = useRef<HTMLElement>(null);
  const opener = useRef<Element | null>(document.activeElement);

  useEffect(() => {
    ref.current?.querySelector<HTMLElement>(".sc-drawer-close")?.focus();
    const back = opener.current;
    return () => (back as HTMLElement | null)?.focus?.();
  }, []);

  const onKey = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      onClose();
    } else if (e.key === "Tab" && ref.current) {
      const items = [...ref.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
      if (!items.length) return;
      const [first, last] = [items[0], items[items.length - 1]];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  };

  return (
    <aside ref={ref} className="sc-drawer" role="dialog" aria-modal="false" aria-labelledby={titleId} onKeyDown={onKey}>
      <header className="sc-drawer-head">
        <div className="sc-drawer-heading">
          <h2 id={titleId} className="sc-drawer-title">{title}</h2>
          {subtitle && <p className="sc-drawer-subtitle">{subtitle}</p>}
        </div>
        <button type="button" className="sc-drawer-close" aria-label={tr.ui.close} onClick={onClose}><X aria-hidden /></button>
      </header>
      <div className="sc-drawer-body">{children}</div>
      {actions && <footer className="sc-drawer-actions">{actions}</footer>}
    </aside>
  );
}

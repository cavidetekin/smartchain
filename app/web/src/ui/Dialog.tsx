// Pencere ve onay penceresi (K-85: onay penceresi ilk kullanan ekranda; 1.4 kayıtlı görünüm). Kipli: arka plan
// örtülür, odak pencerenin içinde döner, Esc ve "Vazgeç" kapatır, açılınca ilk alan ya da birincil düğme odaklanır.
// Atlanamaz pencerede (dismissible=false; 2.1 zorunlu şifre değişikliği, zaman aşımı) Esc kapatmaz; ikincil düğme
// yalnız cancelLabel verilirse görünür.
import { type FormEvent, type KeyboardEvent, type ReactNode, useEffect, useId, useRef } from "react";

import { tr } from "../i18n/tr";
import { Button } from "./Button";

export function Dialog({ title, subtitle, children, onClose, onSubmit, submitLabel, busy, danger, submitDisabled, wide,
                         dismissible = true, cancelLabel, blurred }: {
  title: string;
  /** Başlığın altında sessiz satır (ör. kaynak ve satır sayısı). */
  subtitle?: ReactNode;
  children: ReactNode;
  onClose(): void;
  onSubmit(): void;
  submitLabel: string;
  busy?: boolean;
  /** Geri alınamaz işlem (kiremit düğme, K-85). */
  danger?: boolean;
  submitDisabled?: boolean;
  wide?: boolean;
  /** false: Esc kapatmaz, Vazgeç yok (cancelLabel verilirse o düğme onClose'u çağırır). */
  dismissible?: boolean;
  /** İkincil düğmenin metni (ör. "Şimdi çıkış yap"); verilirse ikincil düğme biçiminde. */
  cancelLabel?: string;
  /** Arka plan bulanık (sayfa etkileşimi kilitli; 2.1). */
  blurred?: boolean;
}) {
  const titleId = useId();
  const ref = useRef<HTMLFormElement>(null);
  const opener = useRef<Element | null>(document.activeElement);

  useEffect(() => {
    const el = ref.current?.querySelector<HTMLElement>("input, select, textarea") ??
      ref.current?.querySelector<HTMLElement>("button[type=submit]");
    el?.focus();
    const back = opener.current;
    return () => (back as HTMLElement | null)?.focus?.();
  }, []);

  const onKey = (e: KeyboardEvent) => {
    if (e.key === "Escape") {
      e.stopPropagation();
      if (dismissible) onClose();
    } else if (e.key === "Tab" && ref.current) {  // odak pencerede döner
      const items = [...ref.current.querySelectorAll<HTMLElement>("input, select, textarea, button:not([disabled])")];
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
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!submitDisabled && !busy) onSubmit();
  };

  return (
    <div className={`sc-dialog-backdrop${blurred ? " is-blurred" : ""}`}>
      <form ref={ref} className={`sc-dialog${wide ? " sc-dialog--wide" : ""}`} role="dialog" aria-modal="true" aria-labelledby={titleId}
            onKeyDown={onKey} onSubmit={submit}>
        <div>
          <h2 id={titleId} className="sc-dialog-title">{title}</h2>
          {subtitle && <p className="sc-dialog-subtitle">{subtitle}</p>}
        </div>
        <div className="sc-dialog-body">{children}</div>
        <div className="sc-dialog-actions">
          {(dismissible || cancelLabel) && (
            <Button variant={cancelLabel ? "secondary" : "ghost"} onClick={onClose}>{cancelLabel ?? tr.ui.cancel}</Button>
          )}
          <Button type="submit" variant={danger ? "danger" : "primary"} busy={busy} disabled={submitDisabled}>{submitLabel}</Button>
        </div>
      </form>
    </div>
  );
}

export function ConfirmDialog({ title, message, confirmLabel, onConfirm, onCancel, danger }: {
  title: string; message: ReactNode; confirmLabel: string; onConfirm(): void; onCancel(): void; danger?: boolean;
}) {
  return (
    <Dialog title={title} onClose={onCancel} onSubmit={onConfirm} submitLabel={confirmLabel} danger={danger}>
      <p className="sc-dialog-message">{message}</p>
    </Dialog>
  );
}

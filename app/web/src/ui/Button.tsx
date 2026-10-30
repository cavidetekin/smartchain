// Buton (K-85): birincil (indigo, U-4), ikincil, sessiz, geri alınamaz işlem (kiremit; yalnız onay penceresi).
// disabledReason (K-100): bağlam dışı düğme gizlenmez; pasifleşir ve nedenini araç ipucunda ve ekran okuyucuda söyler.
import type { LucideIcon } from "lucide-react";
import { LoaderCircle } from "lucide-react";
import { type ButtonHTMLAttributes, type ReactNode, type Ref, useId } from "react";

import { tr } from "../i18n/tr";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "md" | "sm";
  icon?: LucideIcon;
  busy?: boolean;
  /** Verilirse düğme pasif; metin araç ipucunda (title) ve aria-describedby ile (ör. "Bu işlem için Admin yetkisi gerekir…"). */
  disabledReason?: string | null;
  children: ReactNode;
  ref?: Ref<HTMLButtonElement>;
}

export function Button({ variant = "secondary", size = "md", icon: Icon, busy, disabled, disabledReason, children,
                         type = "button", className, ref, title, ...rest }: Props) {
  const reasonId = useId();
  return (
    <>
    <button ref={ref} type={type} className={`sc-btn sc-btn--${variant}${size === "sm" ? " sc-btn--sm" : ""}${className ? ` ${className}` : ""}`}
            disabled={disabled || busy || Boolean(disabledReason)} aria-busy={busy || undefined}
            title={disabledReason || title} aria-describedby={disabledReason ? reasonId : undefined} {...rest}>
      {busy ? <LoaderCircle aria-hidden="true" className="sc-spin" /> : Icon ? <Icon aria-hidden="true" /> : null}
      <span>{busy ? tr.ui.busy : children}</span>
    </button>
    {disabledReason && <span id={reasonId} className="sc-visually-hidden">{disabledReason}</span>}
    </>
  );
}

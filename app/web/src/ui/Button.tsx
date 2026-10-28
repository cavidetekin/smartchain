// Buton (K-85): birincil (indigo, U-4), ikincil, sessiz, geri alınamaz işlem (kiremit; yalnız onay penceresi).
import type { LucideIcon } from "lucide-react";
import { LoaderCircle } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode, Ref } from "react";

import { tr } from "../i18n/tr";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "md" | "sm";
  icon?: LucideIcon;
  busy?: boolean;
  children: ReactNode;
  ref?: Ref<HTMLButtonElement>;
}

export function Button({ variant = "secondary", size = "md", icon: Icon, busy, disabled, children, type = "button",
                         className, ref, ...rest }: Props) {
  return (
    <button ref={ref} type={type} className={`sc-btn sc-btn--${variant}${size === "sm" ? " sc-btn--sm" : ""}${className ? ` ${className}` : ""}`}
            disabled={disabled || busy} aria-busy={busy || undefined} {...rest}>
      {busy ? <LoaderCircle aria-hidden="true" className="sc-spin" /> : Icon ? <Icon aria-hidden="true" /> : null}
      <span>{busy ? tr.ui.busy : children}</span>
    </button>
  );
}

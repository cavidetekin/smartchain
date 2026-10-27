// Uyarı kutusu (mockup m24f-0539, m24f-0757): her tonun ikonu var (U-3); hata role="alert".
import { CircleCheck, CircleX, Info, TriangleAlert, X } from "lucide-react";
import type { ReactNode } from "react";

import { tr } from "../i18n/tr";

export type AlertTone = "info" | "ok" | "risk" | "error";
const ICONS = { info: Info, ok: CircleCheck, risk: TriangleAlert, error: CircleX };

export function Alert({ tone = "info", title, children, onClose }: {
  tone?: AlertTone; title?: string; children: ReactNode; onClose?: () => void;
}) {
  if (children === null || children === undefined || children === "") throw new Error("Uyarı metinsiz olamaz (U-3)");
  const Icon = ICONS[tone];
  return (
    <div className={`sc-alert sc-alert--${tone}`} role={tone === "error" ? "alert" : "status"}>
      <Icon aria-label={tr.ui.alertTone[tone]} role="img" className="sc-alert-icon" />
      <div className="sc-alert-body">
        {title && <p className="sc-alert-title">{title}</p>}
        <div>{children}</div>
      </div>
      {onClose && (
        <button type="button" className="sc-alert-close" onClick={onClose} aria-label={tr.ui.close} title={tr.ui.close}>
          <X aria-hidden="true" />
        </button>
      )}
    </div>
  );
}

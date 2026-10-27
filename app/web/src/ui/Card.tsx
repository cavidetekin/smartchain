// Kart ve KPI kartı (mockup m23-0291, m24e-0310): beyaz zemin, ince çerçeve.
import type { ReactNode } from "react";

interface CardProps {
  title?: string;
  subtitle?: string;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}

export function Card({ title, subtitle, actions, children, className }: CardProps) {
  return (
    <section className={`sc-card${className ? ` ${className}` : ""}`}>
      {(title || actions) && (
        <header className="sc-card-head">
          <div>
            {title && <h3 className="sc-card-title">{title}</h3>}
            {subtitle && <p className="sc-card-sub">{subtitle}</p>}
          </div>
          {actions && <div className="sc-card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

/** KPI değeri durum rengini yalnız durum varsa alır (U-2); not satırı durumu yazıyla da söyler (U-3). */
export function KpiCard({ label, value, note, tone }: {
  label: string; value: string; note?: string; tone?: "ok" | "risk" | "over";
}) {
  return (
    <section className="sc-card sc-kpi">
      <p className="sc-kpi-label">{label}</p>
      <p className={`sc-kpi-value${tone ? ` sc-kpi--${tone}` : ""}`}>{value}</p>
      {note && <p className="sc-kpi-note">{note}</p>}
    </section>
  );
}

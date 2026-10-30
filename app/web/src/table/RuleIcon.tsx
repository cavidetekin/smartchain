// Koşullu biçim ikonları (K-96): sabit 8 ikon, kendi renginde (seçilmezse ikonun varsayılan rengi). Excel'de aynı ikon
// biçim kodunda karakter olarak yazılır (app/api/export/formats.py ICON_CHARS; renk hücrenin yazı rengi).
// İkon değerin ters tarafında: sağa yaslı sayıda hücrenin başında, sola yaslı metin ve tarihte sonunda; değerin yeri
// ikonlu ve ikonsuz satırlarda aynı kalır.
import { ArrowDown, ArrowUp, Check, Circle, Flag, type LucideIcon, Star, Triangle, X } from "lucide-react";
import type { ReactNode } from "react";

import { iconColor } from "./rules";
import type { RuleFormat, RuleIcon } from "./types";

const ICONS: Record<RuleIcon, LucideIcon> = {
  arrow_up: ArrowUp, arrow_down: ArrowDown, dot: Circle, warning: Triangle, check: Check, cross: X, flag: Flag, star: Star,
};
/** İçi dolu çizilenler (1.6 demosu): nokta, uyarı (ünlemsiz üçgen), bayrak, yıldız. */
const FILLED: RuleIcon[] = ["dot", "warning", "flag", "star"];

export function RuleIconView({ name, color, label }: { name: RuleIcon; color?: string; label?: string }) {
  const Icon = ICONS[name];
  return (
    <Icon className={`sc-rule-icon${FILLED.includes(name) ? " is-filled" : ""}`} style={color ? { color } : undefined}
          aria-hidden={label ? undefined : true} aria-label={label} role={label ? "img" : undefined} />
  );
}

/** Hücre içeriği: ikon varsa değerin ters tarafında (sayıda başta, metin ve tarihte sonda). */
export function RuledValue({ format, numeric, children }: { format: RuleFormat | undefined; numeric: boolean; children: ReactNode }) {
  if (!format?.icon) return <>{children}</>;
  const icon = <RuleIconView name={format.icon} color={iconColor(format)} />;
  return (
    <span className={`sc-ruled${numeric ? " is-start" : " is-end"}`}>
      {numeric && icon}
      <span className="sc-ruled-value">{children}</span>
      {!numeric && icon}
    </span>
  );
}

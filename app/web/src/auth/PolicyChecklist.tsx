// Şifre politikası listesi (mockup m24f-0739): her kural yazarken anlık ✓ / ✗. Sunucuda özetle denetlenen kural
// ("son N şifreden farklı") kaydedene kadar nötrdür; sunucu reddederse ✗ olur. Durum yalnız renkle değil ikon ve
// ekran okuyucu metniyle de verilir (U-3).
import { Check, Circle, X } from "lucide-react";
import { useId } from "react";

import { tr } from "../i18n/tr";

export type RuleState = "ok" | "fail" | "pending";

export interface PolicyRule {
  key: string;
  label: string;
  state: RuleState;
}

const ICONS = { ok: Check, fail: X, pending: Circle };

export function PolicyChecklist({ rules }: { rules: PolicyRule[] }) {
  const titleId = useId();
  return (
    <div className="sc-policy">
      <div className="sc-policy-title" id={titleId}>{tr.auth.policy}</div>
      <ul aria-labelledby={titleId}>
        {rules.map((r) => {
          const Icon = ICONS[r.state];
          return (
            <li key={r.key} className={`sc-policy-item is-${r.state}`} data-rule={r.key}>
              <Icon role="img" aria-label={tr.auth.ruleState[r.state]} className="sc-policy-icon" />
              <span>{r.label}</span>
              {r.state === "pending" && <span className="sc-muted"> · {tr.auth.ruleState.pending}</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

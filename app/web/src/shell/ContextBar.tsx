// Bağlam çubuğu (U-17, docs/12): senaryo / plan versiyonu / dönem (8.1), veri versiyonu, iş göstergesi, kullanıcı.
import { Database } from "lucide-react";
import { useEffect, useState } from "react";

import { api, ApiError, type DataVersion } from "../api/client";
import { formatDateTime } from "../format";
import { tr } from "../i18n/tr";
import type { FontSize } from "../prefs";
import { JobIndicator } from "./JobIndicator";
import { UserMenu } from "./UserMenu";

const REFRESH_MS = 60_000;

interface Props {
  userId: number;
  fontSize: FontSize;
  onFontSize(size: FontSize): void;
}

export function ContextBar({ userId, fontSize, onFontSize }: Props) {
  return (
    <header className="sc-context">
      <div className="sc-context-left">
        {[tr.context.scenario, tr.context.planVersion, tr.context.bucket].map((label) => (
          <span key={label} className="sc-pill is-disabled" title={tr.context.notYet} aria-disabled="true">
            {label}: —
          </span>
        ))}
      </div>
      <div className="sc-context-right">
        <DataVersionBadge />
        <JobIndicator userId={userId} />
        <UserMenu userId={userId} fontSize={fontSize} onFontSize={onFontSize} />
      </div>
    </header>
  );
}

type DvState = { kind: "loading" } | { kind: "ok"; dv: DataVersion } | { kind: "none" } | { kind: "offline" };

export function DataVersionBadge() {
  const [state, setState] = useState<DvState>({ kind: "loading" });

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const dv = await api.currentDataVersion();
        if (alive) setState({ kind: "ok", dv });
      } catch (e) {
        if (alive) setState(e instanceof ApiError && e.code === "no_data_version" ? { kind: "none" } : { kind: "offline" });
      }
    };
    load();
    const t = setInterval(load, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const text =
    state.kind === "ok" ? tr.context.dataVersion(state.dv.id, formatDateTime(new Date(state.dv.created_at)))
    : state.kind === "none" ? tr.context.noData
    : state.kind === "offline" ? tr.context.offline
    : "…";
  return (
    <span className={`sc-badge${state.kind === "offline" ? " is-muted" : ""}`} data-testid="data-version">
      <Database aria-hidden="true" />
      <span>{text}</span>
    </span>
  );
}

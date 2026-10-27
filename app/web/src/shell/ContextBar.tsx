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

// Veri yok (404) · API veritabanına bağlanamıyor (503) · API cevap vermiyor (ağ hatası, vekil 5xx).
type DvState =
  | { kind: "loading" } | { kind: "ok"; dv: DataVersion } | { kind: "none" } | { kind: "dbDown" } | { kind: "apiDown" };

export function DataVersionBadge() {
  const [state, setState] = useState<DvState>({ kind: "loading" });

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const dv = await api.currentDataVersion();
        if (alive) setState({ kind: "ok", dv });
      } catch (e) {
        if (!alive) return;
        if (e instanceof ApiError && e.code === "no_data_version") setState({ kind: "none" });
        else if (e instanceof ApiError && e.status === 503) setState({ kind: "dbDown" });
        else setState({ kind: "apiDown" });
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
    : state.kind === "dbDown" ? tr.context.dbDown
    : state.kind === "apiDown" ? tr.context.apiDown
    : "…";
  return (
    <span className={`sc-chip${state.kind === "apiDown" || state.kind === "dbDown" ? " is-muted" : ""}`}
          data-testid="data-version">
      <Database aria-hidden="true" />
      <span>{text}</span>
    </span>
  );
}

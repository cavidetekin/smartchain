// Bağlam çubuğu (U-17, docs/12): senaryo seçici (K-177), plan versiyonu / dönem (8.2; K-204), veri versiyonu,
// iş göstergesi, zamanlanmış iş çipi (K-163), kullanıcı.
import { Check, ChevronDown, Database } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { api, ApiError, type DataVersion, JOB_TRANSFER, type Job } from "../api/client";
import { formatDateTime } from "../format";
import { tr } from "../i18n/tr";
import type { FontSize } from "../prefs";
import { FlowAlertChip } from "./FlowStatus";
import { RowPopMenu } from "../ui/PopMenu";
import { JobIndicator } from "./JobIndicator";
import { type ScenarioOption, scenarioApi } from "./scenarioApi";
import { useShell } from "./ShellContext";
import { useJobRefresh } from "./useJobRefresh";
import { UserMenu } from "./UserMenu";

const REFRESH_MS = 60_000;

interface Props {
  fontSize: FontSize;
  onFontSize(size: FontSize): void;
  /** Her iş güncellemesi (dışa aktarım bildirimi, K-91). */
  onJob?(job: Job): void;
}

export function ContextBar({ fontSize, onFontSize, onJob }: Props) {
  return (
    <header className="sc-context">
      <div className="sc-context-left">
        <ScenarioPill />
        {[tr.context.planVersion, tr.context.bucket].map((label) => (
          <span key={label} className="sc-pill is-disabled" title={tr.context.notYet} aria-disabled="true">
            {label}: —
          </span>
        ))}
      </div>
      <div className="sc-context-right">
        <DataVersionBadge />
        <JobIndicator onJob={onJob} />
        <FlowAlertChip />
        <UserMenu fontSize={fontSize} onFontSize={onFontSize} />
      </div>
    </header>
  );
}

/** Senaryo seçici (K-177): "Senaryo: <ad> ▾". Tıklanınca aktif senaryoların listesi (Baz başta, seçili işaretli; pasif senaryo yok); seçilince
 *  senaryoya bağlı açık ekran o senaryoyla yeniden yüklenir. Seçim kullanıcı bazında hatırlanır. */
function ScenarioPill() {
  const { scenario, selectScenario, scenarioTick } = useShell();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [options, setOptions] = useState<ScenarioOption[]>([]);
  useEffect(() => {
    if (!anchor) return undefined;
    const ctrl = new AbortController();
    scenarioApi.options(ctrl.signal).then(setOptions).catch(() => undefined);
    return () => ctrl.abort();
  }, [anchor, scenarioTick]);
  if (!scenario) {
    return <span className="sc-pill is-disabled" data-testid="scenario">{tr.context.scenario}: —</span>;
  }
  return (
    <>
      <button type="button" className="sc-pill sc-pill--button is-current" data-testid="scenario" aria-haspopup="menu" aria-expanded={Boolean(anchor)}
              title={scenario.isActive ? tr.context.scenarioPick : tr.context.scenarioPassive} onClick={(e) => setAnchor(anchor ? null : e.currentTarget)}>
        {tr.context.scenario}: {scenario.name} <ChevronDown aria-hidden="true" />
      </button>
      {anchor && (
        <RowPopMenu label={tr.context.scenarios} anchor={anchor} onClose={() => setAnchor(null)}>
          {options.map((o) => (
            <button key={o.id} type="button" role="menuitemradio" aria-checked={o.id === scenario.id} className="sc-popmenu-item sc-popmenu-item--check"
                    onClick={() => { setAnchor(null); void selectScenario(o.id); }}>
              <span>{o.is_base ? tr.scenarios.baseName(o.name) : o.name}</span>
              {o.id === scenario.id && <Check aria-hidden="true" />}
            </button>
          ))}
        </RowPopMenu>
      )}
    </>
  );
}

// Veri yok (404) · API veritabanına bağlanamıyor (503) · API cevap vermiyor (ağ hatası, vekil 5xx).
type DvState =
  | { kind: "loading" } | { kind: "ok"; dv: DataVersion } | { kind: "none" } | { kind: "dbDown" } | { kind: "apiDown" };

const TRANSFER_JOBS = [JOB_TRANSFER];

export function DataVersionBadge() {
  const [state, setState] = useState<DvState>({ kind: "loading" });
  const [tick, setTick] = useState(0);
  const bump = useCallback(() => setTick((n) => n + 1), []);
  useJobRefresh(TRANSFER_JOBS, bump);  // aktarım bitince yeni veri versiyonu hemen görünür (K-153)

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
  }, [tick]);

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

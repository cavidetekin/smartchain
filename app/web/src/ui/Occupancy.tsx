// Doluluk hücresi ve lejantı (K-85): her hücrede değer yazar (U-3); eşikler parametre.
import { formatNumber } from "../format";
import { tr } from "../i18n/tr";
import { DEFAULT_THRESHOLDS, LEVELS, legendLabels, occupancyLevel, type OccupancyThresholds } from "./occupancyScale";

export function OccupancyCell({ value, delta, thresholds = DEFAULT_THRESHOLDS }: {
  value: number; delta?: number; thresholds?: OccupancyThresholds;
}) {
  const level = occupancyLevel(value, thresholds);
  return (
    <span className={`sc-occ sc-occ--${level}`} data-level={level}>
      <span className="sc-occ-value">%{formatNumber(Math.round(value))}</span>
      {delta !== undefined && <span className="sc-occ-delta">{tr.ui.delta(delta)}</span>}
    </span>
  );
}

export function OccupancyLegend({ thresholds = DEFAULT_THRESHOLDS }: { thresholds?: OccupancyThresholds }) {
  const labels = legendLabels(thresholds);
  return (
    <ul className="sc-occ-legend">
      {LEVELS.map((level) => (
        <li key={level}>
          <span className={`sc-occ-swatch sc-occ--${level}`} aria-hidden="true" />
          {labels[level]}
        </li>
      ))}
    </ul>
  );
}

import { MapControlPanel } from "@/components/map";
import { COVERAGE_STATES, NO_ACTIVITY_COLOR, type CoverageActivity, COVERAGE_STATE_COLOR, COVERAGE_STATE_LABEL, type CoverageState } from "@/lib/map-api";

export function CoverageLegend({ counts }: { counts: Record<CoverageState, number> }) {
  return (
    <MapControlPanel title="Status" defaultOpen={false} testId="coverage-legend">
      <ul className="flex flex-col gap-1.5 px-3 pb-3">
        {COVERAGE_STATES.map((s) => (
          <li key={s} className="flex items-center gap-2 text-[13px] text-[var(--sd-ink)]">
            <span className="h-3 w-3 rounded-sm" style={{ background: COVERAGE_STATE_COLOR[s] }} aria-hidden />
            <span className="flex-1">{COVERAGE_STATE_LABEL[s]}</span>
            <span className="tabular-nums text-[var(--sd-muted)]">{counts[s] ?? 0}</span>
          </li>
        ))}
      </ul>
    </MapControlPanel>
  );
}

/** The legend when the map is coloured by activity: one swatch per operation in use. */
export function ActivityLegend({ items }: { items: CoverageActivity[] }) {
  return (
    <MapControlPanel title="Activity" defaultOpen testId="activity-legend">
      <ul className="flex flex-col gap-1.5 px-3 pb-3">
        {items.map((a) => (
          <li key={a.operation} className="flex items-center gap-2 text-[13px] text-[var(--sd-ink)]">
            <span className="h-3 w-3 rounded-sm" style={{ background: a.color }} aria-hidden />
            <span className="flex-1">{a.operation}</span>
          </li>
        ))}
        <li className="flex items-center gap-2 text-[13px] text-[var(--sd-muted)]">
          <span className="h-3 w-3 rounded-sm" style={{ background: NO_ACTIVITY_COLOR }} aria-hidden />
          <span className="flex-1">No activity</span>
        </li>
      </ul>
    </MapControlPanel>
  );
}

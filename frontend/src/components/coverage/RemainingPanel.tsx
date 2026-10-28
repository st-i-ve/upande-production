import { MapControlPanel } from "@/components/map";
import { COVERAGE_STATE_COLOR, COVERAGE_STATE_LABEL, formatQty, type CoverageUnit } from "@/lib/map-api";
import { cn } from "@/lib/utils";

/** "Work remaining": one row per block with work outstanding, most urgent first. */
export function RemainingPanel({
  blocks,
  selected,
  onPick,
}: {
  blocks: CoverageUnit[];
  selected: string | null;
  onPick: (name: string) => void;
}) {
  return (
    <MapControlPanel title="Work remaining" count={blocks.length} bodyClassName="max-h-[34vh] overflow-y-auto" testId="remaining-panel">
      {blocks.length === 0 ? (
        <p className="px-3 pb-3 text-[13px] text-[var(--sd-muted)]">Nothing left this week.</p>
      ) : (
        <ul className="flex flex-col pb-1">
          {blocks.map((u) => {
            const color = COVERAGE_STATE_COLOR[u.state];
            return (
              <li key={u.name}>
                <button
                  type="button"
                  data-testid="remaining-row"
                  data-block={u.name}
                  aria-pressed={selected === u.name}
                  onClick={() => onPick(u.name)}
                  className={cn(
                    "flex w-full flex-col gap-1 px-3 py-2 text-left hover:bg-[var(--sd-bg-soft)]",
                    selected === u.name && "bg-[var(--sd-bg-soft)]",
                  )}
                >
                  <span className="flex items-center gap-2 text-[13px] font-medium text-[var(--sd-ink)]">
                    <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} aria-hidden />
                    <span className="min-w-0 flex-1 truncate">{u.name}</span>
                    <span className="text-[11px] font-normal tabular-nums text-[var(--sd-muted)]">{Math.round(u.progress_pct)}%</span>
                  </span>
                  <span className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--sd-bg-soft)] ring-1 ring-border/50">
                    <span className="block h-full rounded-full" style={{ width: `${Math.min(100, u.progress_pct)}%`, background: color }} />
                  </span>
                  <span className="flex justify-between gap-2 text-[11px] text-[var(--sd-muted)]">
                    <span className="truncate">{formatQty(u.remaining_qty, COVERAGE_STATE_LABEL[u.state])}</span>
                    <span className="shrink-0">{COVERAGE_STATE_LABEL[u.state]}</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </MapControlPanel>
  );
}

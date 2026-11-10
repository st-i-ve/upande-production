import { TriangleAlert } from "lucide-react";
import { StatusPill } from "@/components/blocks/StatusPill";
import { treeAge } from "@/components/cycles/AddCycleDialog";
import { StageChip } from "@/components/varieties/StageChip";
import { ha, qty, shortDate } from "@/lib/format";

export interface RunningCycleCard {
  name: string;
  item?: string | null;
  variety?: string | null;
  current_stage?: string | null;
  status: string;
  start_date?: string | null;
  area_ha?: number | null;
  plant_count?: number | null;
  existing_cycle?: 0 | 1 | boolean;
  planting_date?: string | null;
}

/**
 * The cycles running on one block, side by side (several may run at once). When their area or trees add up
 * to more than the block has, a warning shows; nothing is refused.
 */
export function RunningCycles({
  cycles,
  blockArea,
  blockTrees,
  accent,
  yieldPerTree,
}: {
  cycles: RunningCycleCard[];
  blockArea?: number | null;
  blockTrees?: number | null;
  accent: string;
  /** variety -> expected kg per tree per year. */
  yieldPerTree?: Record<string, number>;
}) {
  const running = cycles.filter((c) => c.status === "Active" || c.status === "Harvesting");
  if (!running.length) return null;
  const area = running.reduce((t, c) => t + (c.area_ha || 0), 0);
  const trees = running.reduce((t, c) => t + (c.plant_count || 0), 0);
  const warnings: string[] = [];
  if (blockArea && area > blockArea * 1.0001) warnings.push(`Running cycles cover ${ha(area)} ha, more than the block's ${ha(blockArea)} ha.`);
  if (blockTrees && trees > blockTrees) warnings.push(`Running cycles hold ${qty(trees)} trees, more than the block's ${qty(blockTrees)}.`);
  return (
    <div className="flex flex-col gap-2" data-testid="running-cycles">
      {warnings.map((w) => (
        <div key={w} role="alert" className="flex items-start gap-2 rounded-[var(--sd-radius-md)] bg-[var(--sd-alert-warn)] px-3 py-2 text-[12.5px] text-[var(--sd-sev-high)]">
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          {w}
        </div>
      ))}
      <div className="grid gap-2 sm:grid-cols-2">
        {running.map((c) => {
          const kg = c.variety && yieldPerTree?.[c.variety] && c.plant_count ? yieldPerTree[c.variety] * c.plant_count : null;
          return (
            <div key={c.name} data-testid={`running-cycle-${c.name}`} className="flex flex-col gap-1.5 rounded-[var(--sd-radius-md)] border border-[var(--sd-line)] bg-[var(--sd-card)] p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-[14px] font-semibold text-[var(--sd-ink)]">{c.variety || c.item || c.name}</div>
                  <div className="text-[11px] tabular-nums text-[var(--sd-quiet)]">
                    {c.name}
                    {c.existing_cycle ? " · existing cycle" : ""}
                  </div>
                </div>
                <StatusPill status={c.status} />
              </div>
              <div className="flex items-center gap-2">
                <StageChip stage={c.current_stage} accent={accent} />
                {c.planting_date && <span className="text-[11.5px] text-[var(--sd-quiet)]">trees {treeAge(c.planting_date)} old</span>}
              </div>
              <dl className="grid grid-cols-3 gap-2 text-[12px]">
                <div>
                  <dt className="text-[var(--sd-quiet)]">Trees</dt>
                  <dd className="tabular-nums text-[var(--sd-ink)]">{c.plant_count ? qty(c.plant_count) : "—"}</dd>
                </div>
                <div>
                  <dt className="text-[var(--sd-quiet)]">Area (ha)</dt>
                  <dd className="tabular-nums text-[var(--sd-ink)]">{c.area_ha ? ha(c.area_ha) : "—"}</dd>
                </div>
                <div>
                  <dt className="text-[var(--sd-quiet)]">Exp. kg/year</dt>
                  <dd className="tabular-nums text-[var(--sd-ink)]">{kg ? qty(kg) : "—"}</dd>
                </div>
              </dl>
              {c.start_date && <div className="text-[11px] text-[var(--sd-quiet)]">Started {shortDate(c.start_date)}</div>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

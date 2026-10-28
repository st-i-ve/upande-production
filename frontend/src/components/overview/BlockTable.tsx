import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { StatusPill } from "@/components/blocks/StatusPill";
import { ha, kes, qty, shortDate } from "@/lib/format";
import type { OverviewBlock } from "@/lib/api";
import type { BlockExtra } from "@/lib/overview-api";
import { cn } from "@/lib/utils";

/** One row per unit: cycle, stage, open tasks, crew, season totals, last activity. */
export function BlockTable({
  blocks,
  extras,
  canSeePay,
  uom,
  unitLabel,
}: {
  blocks: OverviewBlock[];
  extras?: Map<string, BlockExtra>;
  canSeePay: boolean;
  uom: string;
  unitLabel: string;
}) {
  return (
    <ScrollTable tall>
      <table className="w-full min-w-[820px] text-[13px]">
        <thead>
          <tr className={cn(THEAD_ROW, STICKY_HEAD)}>
            <th className={TH}>{unitLabel}</th>
            <th className={THR}>Area (ha)</th>
            <th className={TH}>Cycle</th>
            <th className={TH}>Stage</th>
            <th className={THR}>Open tasks</th>
            <th className={THR}>Crew (30d)</th>
            {canSeePay && <th className={THR}>Labour this season</th>}
            <th className={THR}>Harvest{uom ? ` (${uom})` : ""}</th>
            <th className={TH}>Last activity</th>
          </tr>
        </thead>
        <tbody>
          {blocks.map((b) => {
            const x = extras?.get(b.unit);
            return (
              <tr key={b.unit} className={BODY_ROW}>
                <td className={TD}>
                  <div className="font-medium text-[var(--sd-ink)]">{b.unit}</div>
                  <div className="text-[11px] text-[var(--sd-quiet)]">
                    {b.parent ? `${b.parent} · ${b.unit_type}` : b.unit_type}
                  </div>
                </td>
                <td className={TDR}>{ha(b.area_ha)}</td>
                <td className={TD}>
                  {b.cycle ? (
                    <>
                      <div className="text-[var(--sd-ink)]">{b.item || b.cycle}</div>
                      <div className="text-[11px] text-[var(--sd-quiet)]">
                        {b.cycle}
                        {x?.cycle_day != null ? ` · day ${qty(x.cycle_day)}` : ""}
                      </div>
                    </>
                  ) : (
                    <span className="text-[var(--sd-quiet)]">No active cycle</span>
                  )}
                </td>
                <td className={TD}>
                  <StatusPill status={x?.stage} />
                </td>
                <td className={cn(TDR, b.tasks_open ? "text-[var(--sd-ink)]" : "text-[var(--sd-quiet)]")}>
                  {qty(b.tasks_open)}
                </td>
                <td className={TDR}>
                  {x && x.crew_30d ? (
                    <>
                      {qty(x.crew_30d)}
                      <span className="ml-1 text-[11px] text-[var(--sd-quiet)]">{qty(x.hours_30d)} h</span>
                    </>
                  ) : (
                    <span className="text-[var(--sd-quiet)]">—</span>
                  )}
                </td>
                {canSeePay && <td className={cn(TDR, "text-[var(--sd-muted)]")}>{kes(b.labour_cost_season)}</td>}
                <td className={TDR}>{qty(b.harvest_qty_season)}</td>
                <td className={cn(TD, "tabular-nums text-[var(--sd-muted)]")}>{shortDate(x?.last_activity)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </ScrollTable>
  );
}

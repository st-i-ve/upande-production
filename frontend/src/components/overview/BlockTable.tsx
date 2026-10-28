import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { ha, kes, qty } from "@/lib/format";
import type { OverviewBlock } from "@/lib/api";
import { cn } from "@/lib/utils";

/** One row per unit, with the parent shown beneath the name. */
export function BlockTable({
  blocks,
  canSeePay,
  uom,
  unitLabel,
}: {
  blocks: OverviewBlock[];
  canSeePay: boolean;
  uom: string;
  unitLabel: string;
}) {
  return (
    <ScrollTable tall>
      <table className="w-full min-w-[640px] text-[13px]">
        <thead>
          <tr className={cn(THEAD_ROW, STICKY_HEAD)}>
            <th className={TH}>{unitLabel}</th>
            <th className={THR}>Area (ha)</th>
            <th className={TH}>Cycle</th>
            <th className={THR}>Open tasks</th>
            {canSeePay && <th className={THR}>Labour this season</th>}
            <th className={THR}>Harvest{uom ? ` (${uom})` : ""}</th>
          </tr>
        </thead>
        <tbody>
          {blocks.map((b) => (
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
                    <div className="text-[11px] text-[var(--sd-quiet)]">{b.cycle}</div>
                  </>
                ) : (
                  <span className="text-[var(--sd-quiet)]">No active cycle</span>
                )}
              </td>
              <td className={cn(TDR, b.tasks_open ? "text-[var(--sd-ink)]" : "text-[var(--sd-quiet)]")}>
                {qty(b.tasks_open)}
              </td>
              {canSeePay && <td className={cn(TDR, "text-[var(--sd-muted)]")}>{kes(b.labour_cost_season)}</td>}
              <td className={TDR}>{qty(b.harvest_qty_season)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollTable>
  );
}

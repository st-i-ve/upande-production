import type { BlockCostRow } from "@/lib/api";
import { kes, qty } from "@/lib/format";
import { buildTree } from "@/components/costs/CostsTable";
import { cn } from "@/lib/utils";

/**
 * One row per top-level group: labour and inputs as a stacked bar (to the
 * largest group's total), harvest value as a tick, margin on the right.
 */
export function PivotRollup({ rows, accent }: { rows: BlockCostRow[]; accent: string }) {
  const roots = buildTree(rows).map((n) => ({ row: n.row, blocks: n.children.length }));
  const max = Math.max(1, ...roots.map(({ row: r }) => Math.max((r.labour || 0) + (r.inputs || 0), r.revenue || 0)));
  if (!roots.length) return null;
  return (
    <ul className="flex flex-col gap-3" data-testid="pivot-rollup">
      {roots.map(({ row: r, blocks }) => {
        const lab = ((r.labour || 0) / max) * 100;
        const inp = ((r.inputs || 0) / max) * 100;
        const rev = ((r.revenue || 0) / max) * 100;
        const loss = r.margin != null && r.margin < 0;
        return (
          <li key={r.unit} className="grid grid-cols-[minmax(0,9rem)_1fr_auto] items-center gap-3 text-[13px]">
            <div className="min-w-0">
              <div className="truncate font-medium text-[var(--sd-ink)]">{r.unit}</div>
              <div className="text-[11px] text-[var(--sd-quiet)]">
                {blocks ? `${blocks} blocks · ` : ""}
                {qty(r.area_ha, 1)} ha
              </div>
            </div>
            <div className="relative h-5 rounded-full bg-[var(--sd-bg-soft)]" title={`Labour ${kes(r.labour)}, inputs ${kes(r.inputs)}, harvest value ${kes(r.revenue)}`}>
              <div className="absolute inset-y-0 left-0 flex overflow-hidden rounded-full" style={{ width: `${lab + inp}%` }}>
                <div style={{ width: lab + inp ? `${(lab / (lab + inp)) * 100}%` : 0, background: accent }} />
                <div style={{ flex: 1, background: accent, opacity: 0.4 }} />
              </div>
              {rev > 0 && <div className="absolute -top-1 -bottom-1 w-[2px] rounded bg-[var(--sd-ink)]" style={{ left: `calc(${Math.min(rev, 100)}% - 1px)` }} />}
            </div>
            <div className={cn("w-28 text-right font-medium tabular-nums", loss ? "text-[var(--sd-sev-critical)]" : "text-[var(--sd-ink)]")}>
              {r.margin == null ? kes(r.inputs) : kes(r.margin)}
            </div>
          </li>
        );
      })}
      <li className="flex flex-wrap gap-4 text-[11.5px] text-[var(--sd-muted)]">
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: accent }} /> Labour</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: accent, opacity: 0.4 }} /> Inputs</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-3 w-[2px] bg-[var(--sd-ink)]" /> Harvest value</span>
      </li>
    </ul>
  );
}

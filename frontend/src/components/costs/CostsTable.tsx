import { useMemo, useState } from "react";
import { ChevronRight } from "lucide-react";
import type { BlockCostRow } from "@/lib/api";
import { ha, kes, qty } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface CostNode {
  row: BlockCostRow;
  children: CostNode[];
}

/** Nest rows under their group. A row whose parent is not in the set is a root. */
export function buildTree(rows: BlockCostRow[]): CostNode[] {
  const nodes = new Map<string, CostNode>();
  rows.forEach((r) => nodes.set(r.unit, { row: r, children: [] }));
  const roots: CostNode[] = [];
  nodes.forEach((n) => {
    const parent = n.row.parent ? nodes.get(n.row.parent) : undefined;
    if (parent && parent !== n) parent.children.push(n);
    else roots.push(n);
  });
  return roots;
}

const NUM = "px-3 py-2.5 text-right tabular-nums";

function Money({ v, testId }: { v: number | null; testId?: string }) {
  return (
    <td className={NUM} data-testid={testId}>
      {kes(v)}
    </td>
  );
}

/**
 * The cost table. Groups (pivots) show the totals rolled up from their blocks
 * and open to reveal them. With no pay visibility every money column is left
 * out rather than shown as dashes.
 */
export function CostsTable({
  rows,
  canSeePay,
  areaLabel = "Area (ha)",
}: {
  rows: BlockCostRow[];
  canSeePay: boolean;
  areaLabel?: string;
}) {
  const tree = useMemo(() => buildTree(rows), [rows]);
  const [open, setOpen] = useState<Set<string>>(new Set());
  const toggle = (u: string) =>
    setOpen((s) => {
      const n = new Set(s);
      if (n.has(u)) n.delete(u);
      else n.add(u);
      return n;
    });

  const totals = useMemo(() => {
    const t = { area: 0, labour: 0, inputs: 0, total: 0, harvest: 0, revenue: 0, margin: 0 };
    tree.forEach(({ row: r }) => {
      t.area += r.area_ha || 0;
      t.labour += r.labour || 0;
      t.inputs += r.inputs || 0;
      t.total += r.total_cost || 0;
      t.harvest += r.harvest_qty || 0;
      t.revenue += r.revenue || 0;
      t.margin += r.margin || 0;
    });
    return t;
  }, [tree]);

  const head = "px-3 py-2.5 font-medium";
  const hr = `${head} text-right`;

  const renderNode = (n: CostNode, depth: number): React.ReactNode[] => {
    const r = n.row;
    const isGroup = !!r.is_group;
    const expanded = open.has(r.unit);
    const negative = r.margin != null && r.margin < 0;
    const out: React.ReactNode[] = [
      <tr
        key={r.unit}
        data-testid={`cost-row-${r.unit}`}
        data-group={isGroup ? "true" : undefined}
        className={cn(
          "border-b border-[var(--sd-line-soft)] last:border-0",
          isGroup && "bg-[var(--sd-bg-soft)]/60 font-medium",
        )}
      >
        <td className="px-3 py-2.5" style={{ paddingLeft: 12 + depth * 20 }}>
          {isGroup && n.children.length > 0 ? (
            <button
              type="button"
              onClick={() => toggle(r.unit)}
              aria-expanded={expanded}
              aria-label={`${expanded ? "Collapse" : "Expand"} ${r.unit}`}
              className="inline-flex items-center gap-1.5 text-left text-[var(--sd-ink)]"
            >
              <ChevronRight
                className={cn("h-3.5 w-3.5 text-[var(--sd-quiet)] transition-transform", expanded && "rotate-90")}
              />
              <span>{r.unit}</span>
              <span className="text-[11px] font-normal text-[var(--sd-quiet)]">
                {n.children.length} {n.children.length === 1 ? "block" : "blocks"}
              </span>
            </button>
          ) : (
            <span className={cn("text-[var(--sd-ink)]", isGroup ? "" : "pl-5")}>{r.unit}</span>
          )}
        </td>
        <td className={NUM}>{ha(r.area_ha)}</td>
        {canSeePay && (
          <>
            <Money v={r.labour} />
            <Money v={r.inputs} />
            <Money v={r.total_cost} />
            <Money v={r.cost_per_ha} />
          </>
        )}
        <td className={NUM}>{qty(r.harvest_qty, 0)}</td>
        {canSeePay && (
          <>
            <Money v={r.revenue} />
            <td
              data-testid={`margin-${r.unit}`}
              data-negative={negative ? "true" : undefined}
              className={cn(
                NUM,
                "font-medium",
                negative ? "text-[var(--sd-sev-critical)]" : "text-[var(--sd-ink)]",
              )}
            >
              {kes(r.margin)}
            </td>
          </>
        )}
      </tr>,
    ];
    if (isGroup && expanded) n.children.forEach((c) => out.push(...renderNode(c, depth + 1)));
    return out;
  };

  return (
    <div className="overflow-x-auto rounded-[var(--sd-radius-lg)] border border-[var(--sd-line)]">
      <table className={cn("w-full text-[13px]", canSeePay ? "min-w-[60rem]" : "min-w-[24rem]")}>
        <thead>
          <tr className="border-b border-[var(--sd-line)] text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
            <th className={head}>Block</th>
            <th className={hr}>{areaLabel}</th>
            {canSeePay && (
              <>
                <th className={hr}>Labour</th>
                <th className={hr}>Inputs</th>
                <th className={hr}>Total</th>
                <th className={hr}>Cost / ha</th>
              </>
            )}
            <th className={hr}>Harvest qty</th>
            {canSeePay && (
              <>
                <th className={hr}>Revenue</th>
                <th className={hr}>Margin</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>{tree.flatMap((n) => renderNode(n, 0))}</tbody>
        <tfoot>
          <tr className="border-t border-[var(--sd-line)] bg-[var(--sd-bg-soft)] font-medium text-[var(--sd-ink)]">
            <td className="px-3 py-2.5">Total</td>
            <td className={NUM}>{ha(totals.area)}</td>
            {canSeePay && (
              <>
                <td className={NUM}>{kes(totals.labour)}</td>
                <td className={NUM}>{kes(totals.inputs)}</td>
                <td className={NUM}>{kes(totals.total)}</td>
                <td className={NUM}>{totals.area > 0 ? kes(totals.total / totals.area) : "—"}</td>
              </>
            )}
            <td className={NUM}>{qty(totals.harvest, 0)}</td>
            {canSeePay && (
              <>
                <td className={NUM}>{kes(totals.revenue)}</td>
                <td
                  className={cn(NUM, totals.margin < 0 && "text-[var(--sd-sev-critical)]")}
                  data-testid="margin-total"
                >
                  {kes(totals.margin)}
                </td>
              </>
            )}
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

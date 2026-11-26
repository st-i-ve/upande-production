import { useEffect, useState } from "react";
import { cycleCapitalCosts, type CycleCapitalCosts as Costs } from "@/lib/establishment-api";
import { isError } from "@/lib/frappe";
import { kes, shortDate } from "@/lib/format";

/** The capital costs charged to a cycle, by activity against the block's budget. Silent when there are none. */
export function CycleCapitalCosts({ cycle }: { cycle: string }) {
  const [costs, setCosts] = useState<Costs | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void cycleCapitalCosts(cycle).then((r) => {
      if (!live) return;
      if (isError(r)) setFailure(r.error);
      else setCosts(r);
    });
    return () => {
      live = false;
    };
  }, [cycle]);

  if (failure) return <p role="alert" className="text-[12.5px] text-[var(--sd-muted)]">{failure}</p>;
  if (!costs || costs.rows.length === 0) return null;
  return (
    <div className="flex flex-col gap-2" data-testid="cycle-capital-costs">
      <div className="flex items-baseline justify-between">
        <span className="text-[13px] font-medium text-[var(--sd-ink)]">Capital costs</span>
        <span className="text-[13px] tabular-nums text-[var(--sd-muted)]">{kes(costs.total)}</span>
      </div>
      <ul className="divide-y divide-[var(--sd-line-soft)] rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] px-3.5 shadow-[var(--sd-shadow-inset)]">
        {costs.by_operation.map((o) => (
          <li key={o.operation} className="flex items-center gap-3 py-2 text-[13px] tabular-nums">
            <span className="min-w-0 flex-1 break-words text-[var(--sd-ink)]">{o.operation}</span>
            <span>{kes(o.amount)}</span>
            <span className="text-[var(--sd-muted)]">of {kes(o.budget)}</span>
          </li>
        ))}
      </ul>
      <p className="text-[11.5px] text-[var(--sd-quiet)]">
        {costs.rows.length} cost{costs.rows.length === 1 ? "" : "s"}, latest {shortDate(costs.rows[costs.rows.length - 1].posting_date)}. A block's budget is not split between its cycles.
      </p>
    </div>
  );
}

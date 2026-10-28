import type { GradingPage } from "@/lib/fv-api";
import { fmtNum } from "./fv-format";

export function ReasonBreakdown({ reasons }: { reasons: GradingPage["reasons"] }) {
  if (!reasons.length) return <p className="px-5 pb-6 text-[13px] text-[var(--sd-quiet)]">No rejects in this period.</p>;
  const max = Math.max(...reasons.map((r) => r.kg), 1);
  return (
    <ul className="flex flex-col gap-3 px-5 pb-5" data-testid="reasons">
      {reasons.map((r) => (
        <li key={r.reason}>
          <div className="flex justify-between text-[13px]">
            <span className="font-medium">{r.reason}</span>
            <span className="tabular-nums text-[var(--sd-quiet)]">{fmtNum(r.kg)} kg · {fmtNum(r.pct, 0)}%</span>
          </div>
          <div className="mt-1 h-2 rounded-full bg-[var(--sd-line-soft)]">
            <span className="block h-full rounded-full bg-[var(--sd-data-red)] opacity-70" style={{ width: `${(r.kg / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

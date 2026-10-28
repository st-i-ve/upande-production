import { trimQty } from "@/lib/format";

/**
 * Thin progress line for a plan task: approved done qty, then this submission,
 * then what is still left of the plan. Unplanned work has no line.
 */
export function StepLine({
  planned,
  done,
  pending,
  uom,
}: {
  planned: number | null;
  done: number | null;
  pending: number;
  uom: string | null;
}) {
  if (planned == null || planned <= 0) {
    return <p className="text-[12px] text-[var(--sd-quiet)]">Unplanned work: no plan quantity to measure against.</p>;
  }
  const d = Math.max(0, done ?? 0);
  const p = Math.max(0, pending);
  const total = Math.max(planned, d + p);
  const pct = (n: number) => `${Math.min(100, (n / total) * 100)}%`;
  const u = uom ? ` ${uom}` : "";
  return (
    <div data-testid="step-line" className="space-y-1.5">
      <div
        role="img"
        aria-label={`Planned ${trimQty(planned)}, approved ${trimQty(d)}, this submission ${trimQty(p)}`}
        className="flex h-1.5 w-full overflow-hidden rounded-full bg-[rgba(10,10,10,0.07)]"
      >
        <span className="h-full bg-[var(--sd-data-green)]" style={{ width: pct(d) }} />
        <span className="h-full bg-[var(--sd-target)]" style={{ width: pct(p) }} />
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-0.5 text-[11.5px] text-[var(--sd-muted)]">
        <span>Planned <b className="font-semibold text-[var(--sd-ink)]">{trimQty(planned)}{u}</b></span>
        <span className="inline-flex items-center gap-1.5">
          <i className="h-2 w-2 rounded-full bg-[var(--sd-data-green)]" />Approved <b className="font-semibold text-[var(--sd-ink)]">{trimQty(d)}</b>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <i className="h-2 w-2 rounded-full bg-[var(--sd-target)]" />This submission <b className="font-semibold text-[var(--sd-ink)]">{trimQty(p)}</b>
        </span>
      </div>
    </div>
  );
}

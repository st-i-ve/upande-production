import { EnforcementPill } from "@/components/rules/RuleParts";
import type { ProtocolCheck } from "@/lib/varieties-api";
import { rowDate } from "@/components/plan/fmt";

/** Per-block activity rule breaches among the protocol steps due in the week. Quiet when there are none. */
export function ProtocolCheckPanel({ check }: { check: ProtocolCheck | null }) {
  if (!check) return null;
  const blocks = check.blocks.filter((b) => b.breaches.length > 0);
  if (!blocks.length) return null;
  const total = blocks.reduce((t, b) => t + b.breaches.length, 0);
  return (
    <section
      data-testid="protocol-check-breaches"
      aria-label="Protocol steps that break a rule"
      className="mb-4 rounded-[var(--sd-radius-lg)] bg-[var(--sd-amber-bg)] px-4 py-3"
    >
      <h2 className="mb-2 text-[13.5px] font-semibold text-[var(--sd-ink)]">
        {total} protocol step{total === 1 ? "" : "s"} this week break an activity rule, in {blocks.length} block{blocks.length === 1 ? "" : "s"}
      </h2>
      <ul className="flex flex-col gap-3">
        {blocks.map((b) => (
          <li key={b.cycle} data-testid={`check-block-${b.unit}`}>
            <div className="mb-1 text-[13px] font-medium text-[var(--sd-ink)]">{b.unit_name}</div>
            <ul className="flex flex-col gap-1.5">
              {b.breaches.map((x, i) => (
                <li key={`${x.rule}-${x.operation}-${x.due_date}-${i}`} className="flex flex-wrap items-start gap-2 text-[12.5px] text-[var(--sd-ink)]">
                  <EnforcementPill status={x.enforcement} className="shrink-0" />
                  <span className="font-medium">{x.operation_name}</span>
                  <span className="text-[var(--sd-muted)]">due {rowDate(String(x.due_date))}</span>
                  <span className="basis-full text-[var(--sd-muted)] sm:basis-auto">{x.message}</span>
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  );
}

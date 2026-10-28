import { BreachList, EnforcementPill } from "@/components/rules/RuleParts";
import type { RuleCheckProblem } from "@/lib/protocols-api";

/** Steps of the protocol version that would land in a forbidden stage or window for its variety. */
export function ProtocolRuleCheck({ problems }: { problems?: RuleCheckProblem[] }) {
  if (!problems?.length) return null;
  return (
    <div data-testid="protocol-rule-check" role="note" className="flex flex-col gap-2 rounded-[var(--sd-radius)] bg-[var(--sd-amber-bg)] px-3 py-2.5">
      <p className="text-[13px] font-semibold text-[var(--sd-ink)]">
        {problems.length} step{problems.length === 1 ? "" : "s"} would break an activity rule for this variety
      </p>
      <ul className="flex flex-col gap-2">
        {problems.map((p, i) => (
          <li key={`${p.operation}-${p.day}-${i}`} className="text-[12.5px]">
            <div className="mb-1 flex flex-wrap items-center gap-2 font-medium text-[var(--sd-ink)]">
              <EnforcementPill status={p.rule_status} />
              {p.operation_name}
              <span className="font-normal text-[var(--sd-muted)]">
                day {p.day}
                {p.repeat > 1 ? `, repeat ${p.repeat}` : ""}
                {p.stage ? ` · ${p.stage}` : ""}
              </span>
            </div>
            <BreachList breaches={p.breaches} />
          </li>
        ))}
      </ul>
    </div>
  );
}

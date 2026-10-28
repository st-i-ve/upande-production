import type { ProtocolDiff as Diff, ProtocolRow } from "@/lib/protocols-api";

const LABEL: Record<string, string> = {
  operation: "Activity",
  week: "Week",
  repeats: "Repeats",
  schedule: "Schedule",
  interval_weeks: "Interval (weeks)",
  establishment_period_weeks: "Establishment period (weeks)",
  pre_harvest_interval_days: "PHI (days)",
  budget_per_ha: "Budget per ha",
  planned_qty: "Planned qty",
  description: "Description",
  item: "Item",
};
const TABLE: Record<string, string> = {
  key_activities: "Key activities",
  cultural_activities: "Cultural activities",
  capital_activities: "Capital activities",
};
const show = (v: unknown) => (v === null || v === undefined || v === "" ? "none" : String(v));

function rowLine(s?: ProtocolRow) {
  if (!s) return "";
  const r = s as unknown as Record<string, unknown>;
  const parts: string[] = [];
  if (r.week != null) parts.push(`week ${r.week}${r.repeats === "First cycle only" ? ", first cycle only" : ""}`);
  if (r.schedule) {
    parts.push(r.schedule === "As needed" ? "as needed" : `every ${show(r.interval_weeks)} wk`);
    if (r.establishment_period_weeks) parts.push(`from week ${r.establishment_period_weeks}`);
    if (r.pre_harvest_interval_days) parts.push(`PHI ${r.pre_harvest_interval_days} d`);
  }
  if (r.budget_per_ha) parts.push(`budget ${r.budget_per_ha} per ha`);
  if (r.planned_qty) parts.push(`qty ${r.planned_qty}`);
  if (r.description) parts.push(String(r.description));
  return parts.join(", ");
}

/** What changed in this version against the previous one. */
export function ProtocolDiff({ diff }: { diff: Diff }) {
  const none = diff.fields.length === 0 && diff.steps.length === 0;
  return (
    <div data-testid="protocol-diff" className="flex flex-col gap-1.5 text-[12.5px]">
      {!diff.previous && <p className="text-[var(--sd-muted)]">First version: every activity is new.</p>}
      {diff.previous && none && <p className="text-[var(--sd-muted)]">No differences from {diff.previous}.</p>}
      {diff.fields.map((f) => (
        <p key={f.field}>
          <span className="font-medium text-[var(--sd-ink)]">{LABEL[f.field] ?? f.field}</span>{" "}
          <span className="text-[var(--sd-muted)] line-through">{show(f.before)}</span> {"→"}{" "}
          <span className="font-medium text-[var(--sd-ink)]">{show(f.after)}</span>
        </p>
      ))}
      {diff.steps.map((s, i) => (
        <div key={i} data-testid={`diff-step-${s.change}`} className="rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] px-3 py-2">
          <p className="font-medium text-[var(--sd-ink)]">
            <span
              className={
                s.change === "added"
                  ? "text-[var(--sd-data-green)]"
                  : s.change === "removed"
                    ? "text-[var(--sd-data-red)]"
                    : "text-[var(--sd-data-amber)]"
              }
            >
              {s.change === "added" ? "Added" : s.change === "removed" ? "Removed" : "Changed"}
            </span>{" "}
            {s.operation_name}{" "}
            {s.table && <span data-testid="diff-table" className="text-[11.5px] font-normal text-[var(--sd-quiet)]">{TABLE[s.table] ?? s.table}</span>}
          </p>
          {s.change === "changed" ? (
            <ul className="mt-0.5 text-[var(--sd-muted)]">
              {s.changes?.map((c) => (
                <li key={c.field}>
                  {LABEL[c.field] ?? c.field}: <span className="line-through">{show(c.before)}</span> {"→"}{" "}
                  <span className="font-medium text-[var(--sd-ink)]">{show(c.after)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-[var(--sd-muted)]">{rowLine(s.change === "added" ? s.after : s.before)}</p>
          )}
        </div>
      ))}
    </div>
  );
}

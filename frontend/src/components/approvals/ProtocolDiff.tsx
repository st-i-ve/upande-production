import type { ProtocolDiff as Diff, ProtocolStep } from "@/lib/protocols-api";

const LABEL: Record<string, string> = {
  operation: "Operation",
  day_offset: "Day",
  repeat_every_days: "Repeat every (days)",
  repeat_count: "Repeats",
  planned_qty: "Planned qty",
  note: "Note",
  item: "Item",
};
const show = (v: unknown) => (v === null || v === undefined || v === "" ? "none" : String(v));

function stepLine(s?: ProtocolStep) {
  if (!s) return "";
  const every = Number(s.repeat_every_days || 0);
  const times = Number(s.repeat_count || 1);
  const when = every > 0 && times > 1 ? `day ${s.day_offset ?? 0}, every ${every} d x ${times}` : `day ${s.day_offset ?? 0}`;
  return `${when}${s.planned_qty ? `, qty ${s.planned_qty}` : ""}${s.note ? `, ${s.note}` : ""}`;
}

/** What changed in this version against the previous one. */
export function ProtocolDiff({ diff }: { diff: Diff }) {
  const none = diff.fields.length === 0 && diff.steps.length === 0;
  return (
    <div data-testid="protocol-diff" className="flex flex-col gap-1.5 text-[12.5px]">
      {!diff.previous && <p className="text-[var(--sd-muted)]">First version: every step is new.</p>}
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
            {s.operation_name}
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
            <p className="text-[var(--sd-muted)]">{stepLine(s.change === "added" ? s.after : s.before)}</p>
          )}
        </div>
      ))}
    </div>
  );
}

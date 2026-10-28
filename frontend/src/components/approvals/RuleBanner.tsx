import { EnforcementPill } from "@/components/rules/RuleParts";
import { cn } from "@/lib/utils";

/**
 * What the manager must know before approving: the activity rule the work broke and the reason the
 * supervisor gave for going ahead. Shown above the keyed rows, never hidden behind a tooltip.
 */
export function RuleBanner({
  status,
  notes,
  overrideReason,
}: {
  status: string | null | undefined;
  notes?: string | null;
  overrideReason?: string | null;
}) {
  if (status !== "Warn" && status !== "Block") return null;
  return (
    <div
      role="note"
      data-testid="rule-banner"
      className={cn(
        "mx-5 mt-3 flex flex-col gap-1.5 rounded-[var(--sd-radius)] px-3 py-2.5 text-[12.5px] text-[var(--sd-ink)]",
        status === "Block" ? "bg-[var(--sd-alert-error)]" : "bg-[var(--sd-amber-bg)]",
      )}
    >
      <div className="flex items-center gap-2 font-semibold">
        <EnforcementPill status={status} /> Breaks an activity rule
      </div>
      {notes && <p className="whitespace-pre-line text-[var(--sd-muted)]">{notes}</p>}
      <p>
        <b className="font-semibold">Reason given:</b> {overrideReason ? overrideReason : <span className="text-[var(--sd-quiet)]">none recorded</span>}
      </p>
    </div>
  );
}

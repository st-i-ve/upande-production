import { cn } from "@/lib/utils";

export const STATUSES = ["Open", "In Progress", "Done", "Partly Done", "Skipped"] as const;

const PILL = "inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11.5px] font-medium";

const STATUS_TONE: Record<string, string> = {
  Open: "bg-[var(--sd-bg-soft)] text-[var(--sd-muted)]",
  "In Progress": "bg-[#e6f0fa] text-[#1d5fa8]",
  Done: "bg-[var(--sd-alert-ok)] text-[var(--sd-sev-moderate)]",
  "Partly Done": "bg-[var(--sd-amber-bg)] text-[var(--sd-amber)]",
  Skipped: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
};

export function StatusPill({ status }: { status: string }) {
  return <span className={cn(PILL, STATUS_TONE[status] ?? STATUS_TONE.Open)}>{status}</span>;
}

const DEVIATION_TONE: Record<string, string> = {
  Late: "bg-[var(--sd-amber-bg)] text-[var(--sd-amber)]",
  Partial: "bg-[#e6f0fa] text-[#1d5fa8]",
  Skipped: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
};

export function DeviationBadge({ deviation }: { deviation: string | null | undefined }) {
  if (!deviation) return null;
  return (
    <span className={cn(PILL, "ring-1 ring-inset ring-current/20", DEVIATION_TONE[deviation] ?? DEVIATION_TONE.Skipped)}>
      {deviation}
    </span>
  );
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]!.toUpperCase())
    .join("");
}

/** Overlapping initials for the people recorded on a task, then a +n. */
export function AvatarStack({ names }: { names: string[] }) {
  if (!names.length) return null;
  const shown = names.slice(0, 3);
  return (
    <span className="inline-flex items-center" title={names.join(", ")}>
      {shown.map((n, i) => (
        <span
          key={n + i}
          className="-ml-1.5 flex h-6 w-6 items-center justify-center rounded-full bg-[var(--sd-pistachio)] text-[10px] font-semibold text-[var(--sd-ink)] ring-2 ring-[var(--sd-card)] first:ml-0"
        >
          {initials(n)}
        </span>
      ))}
      {names.length > shown.length && (
        <span className="ml-1 text-[11px] tabular-nums text-[var(--sd-quiet)]">+{names.length - shown.length}</span>
      )}
    </span>
  );
}

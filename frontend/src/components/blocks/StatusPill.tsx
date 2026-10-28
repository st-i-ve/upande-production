import { cn } from "@/lib/utils";

/** Status words from the Production Unit and Crop Cycle doctypes. */
const TONES: Record<string, string> = {
  Active: "bg-[var(--sd-alert-ok)] text-[var(--sd-sev-moderate)]",
  Harvesting: "bg-[var(--sd-alert-ok)] text-[var(--sd-sev-moderate)]",
  Planned: "bg-[var(--sd-alert-info)] text-[var(--sd-muted)] ring-1 ring-[var(--sd-line)]",
  Fallow: "bg-[var(--sd-alert-warn)] text-[var(--sd-sev-high)]",
  Closed: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
  Retired: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
};

export function StatusPill({ status }: { status: string | null | undefined }) {
  if (!status) return <span className="text-[var(--sd-quiet)]">—</span>;
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-[var(--sd-radius-pill)] px-2.5 py-0.5 text-[11.5px] font-medium",
        TONES[status] ?? "bg-[var(--sd-bg-soft)] text-[var(--sd-muted)]",
      )}
    >
      {status}
    </span>
  );
}

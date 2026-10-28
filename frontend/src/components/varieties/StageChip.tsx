import { cn } from "@/lib/utils";

/** The growth stage a block or cycle is in now; nothing when it has none. */
export function StageChip({ stage, accent, className }: { stage: string | null | undefined; accent?: string; className?: string }) {
  if (!stage) return null;
  return (
    <span
      data-testid="stage-chip"
      className={cn("inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11.5px] font-medium text-[var(--sd-ink)]", className)}
      style={{ background: `color-mix(in srgb, ${accent || "#3f7d3a"} 18%, transparent)` }}
    >
      {stage}
    </span>
  );
}

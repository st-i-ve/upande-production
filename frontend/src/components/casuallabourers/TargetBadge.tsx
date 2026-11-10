import { cn } from "@/lib/utils";
import { trimQty } from "@/lib/format";

/** A person's day against their daily target: "42 / 60" with a met / not met colour. Targets are a
 *  yardstick only; pay is per unit of work and is never changed by them. */
export function TargetBadge({
  target,
  actual,
  met,
  uom,
  className,
}: {
  target?: number | null;
  actual?: number | null;
  met?: boolean | null;
  uom?: string | null;
  className?: string;
}) {
  if (!target) return <span className={cn("text-[var(--sd-quiet)]", className)}>—</span>;
  const tone =
    met == null
      ? "text-[var(--sd-muted)]"
      : met
        ? "text-[var(--sd-data-green)]"
        : "text-[var(--sd-amber)]";
  return (
    <span
      className={cn("whitespace-nowrap tabular-nums", tone, className)}
      title={`Daily target ${trimQty(target)}${uom ? ` ${uom}` : ""}${met == null ? "" : met ? " (met)" : " (not met)"}`}
    >
      {actual != null ? `${trimQty(actual)} / ` : ""}
      {trimQty(target)}
      {met != null && <span className="ml-1 text-[11px]">{met ? "met" : "not met"}</span>}
    </span>
  );
}

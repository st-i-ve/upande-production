import { cn } from "@/lib/utils";

/** Planned vs done: a solid approved segment and, when the backend reports
 *  `pending_qty`, a hatched segment for work awaiting approval. */
export function QtyBar({
  planned,
  done,
  pending = 0,
  color,
  className,
}: {
  planned: number;
  done: number;
  pending?: number;
  color?: string;
  className?: string;
}) {
  const base = Math.max(planned, done + pending, 0.0001);
  const d = Math.min(100, (Math.max(done, 0) / base) * 100);
  const p = Math.min(100 - d, (Math.max(pending, 0) / base) * 100);
  const c = color || "var(--crop-accent, var(--sd-data-green))";
  return (
    <div
      className={cn("flex h-2 w-full overflow-hidden rounded-full bg-[var(--sd-bg-soft)]", className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(d)}
    >
      <div className="h-full transition-[width] duration-500" style={{ width: `${d}%`, background: c }} />
      {p > 0 && (
        <div
          data-pending
          className="h-full transition-[width] duration-500"
          style={{
            width: `${p}%`,
            backgroundImage: `repeating-linear-gradient(135deg, ${c} 0 3px, transparent 3px 6px)`,
            opacity: 0.55,
          }}
        />
      )}
    </div>
  );
}

/** "Awaiting approval" chip. */
export function PendingChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center whitespace-nowrap rounded-full bg-[var(--sd-amber-bg)] px-2.5 py-0.5 text-[11.5px] font-medium text-[var(--sd-amber)]">
      {children}
    </span>
  );
}

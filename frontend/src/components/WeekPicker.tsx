import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { shiftWeek, type IsoWeek } from "@/lib/weeks";

/** Pill stepper: ‹ W44 2026 ›. ISO weeks, Monday start. */
export function WeekPicker({
  value,
  onChange,
  className,
}: {
  value: IsoWeek;
  onChange: (next: IsoWeek) => void;
  className?: string;
}) {
  const step = "inline-flex h-7 w-7 items-center justify-center rounded-full hover:bg-[var(--sd-bg-soft)]";
  return (
    <div
      className={cn(
        "inline-flex h-9 items-center gap-1 rounded-full bg-[var(--sd-card)] px-1.5 text-[13px] font-medium",
        "text-[var(--sd-ink)] shadow-[var(--sd-shadow-1)] ring-1 ring-border/60",
        className,
      )}
    >
      <button
        type="button"
        aria-label="Previous week"
        className={step}
        onClick={() => onChange(shiftWeek(value, -1))}
      >
        <ChevronLeft className="h-4 w-4" />
      </button>
      <span className="min-w-[5.5rem] text-center tabular-nums">
        W{String(value.week).padStart(2, "0")} {value.year}
      </span>
      <button
        type="button"
        aria-label="Next week"
        className={step}
        onClick={() => onChange(shiftWeek(value, 1))}
      >
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  );
}

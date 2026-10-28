import { DatePicker } from "@/components/DatePicker";
import { cn } from "@/lib/utils";

/** From – to, two DatePickers in one pill. Keeps from <= to. */
export function DateRangePill({
  from,
  to,
  onChange,
  className,
}: {
  from: string;
  to: string;
  onChange: (from: string, to: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("inline-flex flex-wrap items-center gap-2", className)}>
      <DatePicker
        value={from}
        max={to}
        aria-label="From date"
        onChange={(v) => onChange(v, to)}
      />
      <span className="text-[12px] text-[var(--sd-quiet)]" aria-hidden>
        to
      </span>
      <DatePicker
        value={to}
        min={from}
        aria-label="To date"
        onChange={(v) => onChange(from, v)}
      />
    </div>
  );
}

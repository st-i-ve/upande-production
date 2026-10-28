import { useId } from "react";
import { HEADER_PILL } from "@/components/header-controls";
import { cn } from "@/lib/utils";

/** A toolbar pill holding a label and a number box (crew available, days a week, pay a day). */
export function PillNumber({
  label,
  value,
  onChange,
  onCommit,
  min = 0,
  max,
  width = "w-14",
  placeholder,
  children,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  /** Enter or blur. */
  onCommit?: () => void;
  min?: number;
  max?: number;
  width?: string;
  placeholder?: string;
  children?: React.ReactNode;
}) {
  const id = useId();
  return (
    <label
      htmlFor={id}
      className={cn(HEADER_PILL, "inline-flex min-w-0 items-center justify-center gap-2 pr-2 whitespace-nowrap")}
    >
      <span className="text-[var(--sd-quiet)]">{label}</span>
      <input
        id={id}
        type="number"
        inputMode="numeric"
        min={min}
        max={max}
        aria-label={label}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onCommit}
        onKeyDown={(e) => {
          if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        }}
        className={cn(width, "bg-transparent text-right text-xs font-semibold tabular-nums outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none")}
      />
      {children}
    </label>
  );
}

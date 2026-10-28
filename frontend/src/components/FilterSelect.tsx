import { useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface FilterOption {
  value: string;
  label: string;
}

/**
 * The filter pill: a rounded trigger showing the current choice, opening a
 * list. Used for every page filter; a native <select> never appears in a
 * filter row.
 */
export function FilterSelect({
  value,
  options,
  onChange,
  placeholder = "Select",
  className,
  "aria-label": ariaLabel,
}: {
  value: string;
  options: FilterOption[];
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  "aria-label"?: string;
}) {
  const [open, setOpen] = useState(false);
  const current = options.find((o) => o.value === value);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={ariaLabel}
          aria-haspopup="listbox"
          aria-expanded={open}
          className={cn(
            "inline-flex h-9 max-w-full items-center gap-2 rounded-full bg-[var(--sd-card)] px-3.5 text-[13px] font-medium",
            "text-[var(--sd-ink)] shadow-[var(--sd-shadow-1)] ring-1 ring-border/60 transition-shadow hover:ring-2 hover:ring-border",
            !current && "text-[var(--sd-quiet)]",
            className,
          )}
        >
          <span className="truncate">{current ? current.label : placeholder}</span>
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-[var(--sd-quiet)]" />
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-auto min-w-[10rem] max-w-[20rem] p-1.5" align="start">
        <ul role="listbox" className="flex max-h-72 flex-col overflow-y-auto">
          {options.length === 0 && (
            <li className="px-3 py-2 text-[13px] text-[var(--sd-quiet)]">Nothing to choose</li>
          )}
          {options.map((o) => {
            const selected = o.value === value;
            return (
              <li key={o.value} role="option" aria-selected={selected}>
                <button
                  type="button"
                  onClick={() => {
                    onChange(o.value);
                    setOpen(false);
                  }}
                  className={cn(
                    "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-[13px] hover:bg-[var(--sd-bg-soft)]",
                    selected && "font-semibold",
                  )}
                >
                  <span className="min-w-0 flex-1 truncate">{o.label}</span>
                  {selected && <Check className="h-3.5 w-3.5 shrink-0" />}
                </button>
              </li>
            );
          })}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

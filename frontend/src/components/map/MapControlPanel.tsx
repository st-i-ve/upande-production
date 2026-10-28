/**
 * A compact floating panel on a map (bottom-right, inside MapPanelDock): where a page's
 * legend / layer toggles / list lives. Collapses to its title row. Place inside the map's
 * `relative` container.
 */
import { useState, type ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { useInMapPanelDock } from "./MapPanelDock";

export function MapControlPanel({
  title,
  count,
  children,
  defaultOpen = true,
  className,
  bodyClassName,
  testId = "map-control-panel",
}: {
  title: ReactNode;
  count?: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  /** Override width/position (undocked default is top-left under the KPI row). */
  className?: string;
  /** Override the body's scroll box (default max-h 30vh). */
  bodyClassName?: string;
  testId?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const docked = useInMapPanelDock();
  return (
    <div
      data-testid={testId}
      className={cn(
        docked ? "relative w-[min(260px,calc(100vw-1rem))]" : "absolute left-3 top-14 z-[1000] w-[min(260px,calc(100%-5rem))]",
        "rounded-2xl border bg-card/95 shadow-[var(--sd-shadow-1)] backdrop-blur",
        className,
      )}
    >
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-[0.7rem] font-semibold uppercase tracking-wide text-muted-foreground"
      >
        <span className="min-w-0 flex-1 truncate">{title}</span>
        {count != null ? <span className="font-normal tabular-nums">{count}</span> : null}
        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
      </button>
      {open ? (
        <div className={cn("max-h-[min(30vh,18rem)] overflow-auto border-t p-2", bodyClassName)}>{children}</div>
      ) : null}
    </div>
  );
}

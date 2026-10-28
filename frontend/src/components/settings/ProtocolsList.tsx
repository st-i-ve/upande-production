import { useState } from "react";
import { ChevronRight } from "lucide-react";
import type { Row } from "@/lib/api";
import { qty } from "@/lib/format";
import { cn } from "@/lib/utils";

interface Step {
  name?: string;
  operation?: string;
  day_offset?: number;
  repeat_every_days?: number;
  repeat_count?: number;
  planned_qty?: number;
  note?: string;
}

function cadence(s: Step): string {
  const every = Number(s.repeat_every_days || 0);
  const times = Number(s.repeat_count || 1);
  return every > 0 && times > 1 ? `every ${every} d, ${times} times` : "once";
}

/** Read-only protocols, each opening to its steps. `opNames` maps operation id to its name. */
export function ProtocolsList({ protocols, opNames }: { protocols: Row[]; opNames: Record<string, string> }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!protocols.length) {
    return <p className="px-1 py-6 text-center text-[13px] text-[var(--sd-muted)]">No protocols defined for this crop yet.</p>;
  }
  return (
    <ul className="flex flex-col gap-1">
      {protocols.map((p) => {
        const id = String(p.name);
        const steps = (p.steps as Step[] | undefined) ?? [];
        const expanded = open === id;
        return (
          <li key={id}>
            <button
              type="button"
              aria-expanded={expanded}
              onClick={() => setOpen(expanded ? null : id)}
              className="flex w-full items-center gap-3 rounded-[var(--sd-radius-lg)] px-3 py-2.5 text-left transition-all hover:bg-[var(--sd-bg-soft)]"
            >
              <ChevronRight className={cn("h-4 w-4 shrink-0 text-[var(--sd-quiet)] transition-transform", expanded && "rotate-90")} />
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-[13px] font-medium text-[var(--sd-ink)]">{String(p.protocol_name ?? id)}</span>
                {p.item ? <span className="text-[11.5px] text-[var(--sd-muted)]">{String(p.item)}</span> : null}
              </span>
              <span className="shrink-0 text-[11.5px] tabular-nums text-[var(--sd-quiet)]">
                {steps.length} {steps.length === 1 ? "step" : "steps"}
              </span>
            </button>
            {expanded && (
              <div className="mb-1 ml-7 overflow-x-auto rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] px-4 py-3 shadow-[var(--sd-shadow-inset)]">
                {steps.length === 0 ? (
                  <p className="text-[12px] text-[var(--sd-muted)]">This protocol has no steps.</p>
                ) : (
                  <table className="w-full min-w-[28rem] text-[12.5px]">
                    <thead>
                      <tr className="text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
                        <th className="py-1.5 pr-3 font-medium">Day</th>
                        <th className="py-1.5 pr-3 font-medium">Operation</th>
                        <th className="py-1.5 pr-3 font-medium">Repeats</th>
                        <th className="py-1.5 pr-3 text-right font-medium">Planned qty</th>
                        <th className="py-1.5 font-medium">Note</th>
                      </tr>
                    </thead>
                    <tbody>
                      {steps.map((s, i) => (
                        <tr key={s.name ?? i}>
                          <td className="py-1.5 pr-3 tabular-nums text-[var(--sd-muted)]">{s.day_offset ?? 0}</td>
                          <td className="py-1.5 pr-3 font-medium text-[var(--sd-ink)]">{(s.operation && opNames[s.operation]) || s.operation || "—"}</td>
                          <td className="py-1.5 pr-3 text-[var(--sd-muted)]">{cadence(s)}</td>
                          <td className="py-1.5 pr-3 text-right tabular-nums">{s.planned_qty ? qty(s.planned_qty, 1) : "—"}</td>
                          <td className="py-1.5 text-[var(--sd-muted)]">{s.note || ""}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

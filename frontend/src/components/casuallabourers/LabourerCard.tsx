import { Portrait } from "@/components/supervisors/Person";
import { formatUoms, kes } from "@/lib/format";
import type { RosterRow } from "@/lib/labourers-api";
import { cn } from "@/lib/utils";

function Chip({ children, tone }: { children: React.ReactNode; tone?: "warn" | "good" }) {
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[11.5px] font-medium",
        tone === "warn" && "bg-[var(--sd-amber)]/15 text-[var(--sd-amber)]",
        tone === "good" && "bg-[var(--sd-pistachio)] text-[var(--sd-ink)]",
        !tone && "bg-[var(--sd-bg-soft)] text-[var(--sd-muted)]",
      )}
    >
      {children}
    </span>
  );
}

/** One casual labourer: photo, name, crew and supervisor, and the period's KPIs as chips. Pay chips
 *  only when the user can see pay. */
export function LabourerCard({ row: r, canPay, accent, onOpen }: { row: RosterRow; canPay: boolean; accent: string; onOpen: () => void }) {
  const sub = [r.designation, r.department].filter(Boolean).join(" · ") || r.employee;
  const who = [r.crew, r.supervisor_name].filter(Boolean).join(" · ");
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "scp-card-in flex w-full flex-col gap-3 rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] p-4 text-left shadow-[var(--sd-shadow-1)]",
        "transition-shadow hover:shadow-[var(--sd-shadow-2,var(--sd-shadow-1))]",
        !r.active && "opacity-70",
      )}
    >
      <span className="flex items-center gap-3">
        <Portrait name={r.employee_name} image={r.image} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[15px] font-semibold text-[var(--sd-ink)]">{r.employee_name}</span>
          <span className="block truncate text-[12px] text-[var(--sd-quiet)]">
            {sub}
            {r.overrides > 0 ? ` · ${r.overrides} own target${r.overrides === 1 ? "" : "s"}` : ""}
          </span>
          {who && <span className="block truncate text-[12px] text-[var(--sd-muted)]">{who}</span>}
        </span>
        {!r.active && <Chip>Inactive</Chip>}
      </span>
      {r.hit_rate != null && (
        <span className="flex items-center gap-2">
          <span className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--sd-bg-soft)]">
            <span
              className="block h-full rounded-full"
              style={{ width: `${Math.min(100, r.hit_rate)}%`, background: r.hit_rate >= 50 ? accent : "var(--sd-amber)" }}
            />
          </span>
        </span>
      )}
      <span className="flex flex-wrap gap-1.5">
        <Chip>{r.days_worked} {r.days_worked === 1 ? "day" : "days"}</Chip>
        {r.hit_rate != null && <Chip tone={r.hit_rate >= 50 ? "good" : "warn"}>{r.hit_rate}% of target</Chip>}
        {r.qty_by_uom.length > 0 && <Chip>{formatUoms(r.qty_by_uom)}</Chip>}
        {canPay && !!r.pay_value && <Chip>{kes(r.pay_value)} earned</Chip>}
        {canPay && !!r.unpaid_value && <Chip tone="warn">{kes(r.unpaid_value)} unpaid</Chip>}
      </span>
    </button>
  );
}

import { Phone } from "lucide-react";
import { Portrait } from "@/components/supervisors/Person";
import type { SupervisorCard as Card } from "@/lib/supervisors-api";
import { cn } from "@/lib/utils";

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

function Chip({ children, tone }: { children: React.ReactNode; tone?: "warn" | "bad" | "good" }) {
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-[11.5px] font-medium",
        tone === "bad" && "bg-[var(--sd-data-red)]/12 text-[var(--sd-data-red)]",
        tone === "warn" && "bg-[var(--sd-amber)]/15 text-[var(--sd-amber)]",
        tone === "good" && "bg-[var(--sd-pistachio)] text-[var(--sd-ink)]",
        !tone && "bg-[var(--sd-bg-soft)] text-[var(--sd-muted)]",
      )}
    >
      {children}
    </span>
  );
}

/** One supervisor: photo, name, phone and this week's figures as chips. */
export function SupervisorCard({ card, onOpen }: { card: Card; onOpen: () => void }) {
  const { kpis } = card;
  const t = kpis.tasks;
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        "scp-card-in flex w-full flex-col gap-3 rounded-[var(--sd-radius-lg)] bg-[var(--sd-card)] p-4 text-left shadow-[var(--sd-shadow-1)]",
        "transition-shadow hover:shadow-[var(--sd-shadow-2,var(--sd-shadow-1))]",
        !card.active && "opacity-70",
      )}
    >
      <span className="flex items-center gap-3">
        <Portrait name={card.employee_name} image={card.image} />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[15px] font-semibold text-[var(--sd-ink)]">{card.employee_name}</span>
          <span className="flex items-center gap-1 text-[12px] text-[var(--sd-quiet)]">
            {card.phone ? (
              <>
                <Phone className="h-3 w-3" strokeWidth={1.75} />
                {card.phone}
              </>
            ) : (
              card.employee
            )}
          </span>
        </span>
        {!card.active && <Chip>Inactive</Chip>}
      </span>
      <span className="flex flex-wrap gap-1.5">
        <Chip>{plural(kpis.blocks, "block")}</Chip>
        <Chip tone="good">{t.done} done</Chip>
        <Chip>{t.open} open</Chip>
        {t.late > 0 && <Chip tone="bad">{t.late} late</Chip>}
        <Chip>{kpis.crew} in crew</Chip>
        {!!kpis.pending && <Chip tone="warn">{kpis.pending} to approve</Chip>}
      </span>
    </button>
  );
}

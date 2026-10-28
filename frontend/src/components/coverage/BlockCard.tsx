import { MapFloatingCard } from "@/components/map";
import { COVERAGE_STATE_COLOR, COVERAGE_STATE_LABEL, formatQty, type CoverageUnit } from "@/lib/map-api";
import { taskProgress } from "./coverage-utils";

const num = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

/** Detail card for the selected block: tasks with planned/done/pending/remaining, due dates, late flags. */
export function BlockCard({
  unit,
  accent,
  planHref,
  onClose,
}: {
  unit: CoverageUnit;
  accent: string;
  planHref: string;
  onClose: () => void;
}) {
  const color = COVERAGE_STATE_COLOR[unit.state];
  return (
    <MapFloatingCard eyebrow={unit.parent ?? unit.unit_type} title={unit.name} onClose={onClose} testId="block-card">
      <div className="flex flex-col gap-3 px-3 pb-3 text-[13px] text-[var(--sd-ink)]">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="inline-flex items-center gap-1.5 font-medium" style={{ color }}>
            <span className="h-2 w-2 rounded-full" style={{ background: color }} aria-hidden />
            {COVERAGE_STATE_LABEL[unit.state]}
          </span>
          <span className="tabular-nums text-[var(--sd-muted)]">{num(unit.area_ha)} ha</span>
          {unit.item ? <span className="text-[var(--sd-muted)]">{unit.item}</span> : null}
        </div>
        {unit.tasks.length === 0 ? (
          <p className="text-[var(--sd-muted)]">No work planned this week.</p>
        ) : (
          <ul className="flex flex-col gap-2.5 max-h-[28vh] overflow-y-auto" data-testid="block-tasks">
            {unit.tasks.map((t) => (
              <li key={t.operation} data-testid="block-task" className="flex flex-col gap-1">
                <div className="flex items-center gap-2 font-medium">
                  <span className="min-w-0 flex-1 truncate">{t.operation_name}</span>
                  {t.late ? (
                    <span className="rounded-full bg-[var(--sd-alert-bg,#fde8ea)] px-2 py-0.5 text-[10px] font-semibold uppercase text-[#e63946]">Late</span>
                  ) : null}
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-[var(--sd-bg-soft)] ring-1 ring-border/50">
                  <div className="h-full rounded-full" style={{ width: `${taskProgress(t)}%`, background: accent }} />
                </div>
                <div className="grid grid-cols-4 gap-1 text-[11px] tabular-nums text-[var(--sd-muted)]">
                  <span>Planned {num(t.planned_qty)}</span>
                  <span>Done {num(t.done_qty)}</span>
                  <span>{t.pending_qty == null ? "Pending -" : `Pending ${num(t.pending_qty)}`}</span>
                  <span>Left {num(t.remaining_qty)}</span>
                </div>
                <div className="flex justify-between text-[11px] text-[var(--sd-muted)]">
                  <span>
                    {t.uom} · {t.status}
                  </span>
                  <span className="tabular-nums">{t.due_date ? `Due ${t.due_date}` : ""}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
        <div className="flex items-center justify-between gap-2 text-[11px] text-[var(--sd-muted)]">
          <span>Left: {formatQty(unit.remaining_qty)}</span>
          <a href={planHref} className="font-medium underline-offset-2 hover:underline" style={{ color: accent }}>
            Open Weekly Plan
          </a>
        </div>
      </div>
    </MapFloatingCard>
  );
}

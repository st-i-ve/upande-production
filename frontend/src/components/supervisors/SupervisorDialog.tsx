import { useEffect, useState } from "react";
import { Pencil } from "lucide-react";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { RowsSkeleton } from "@/components/Loading";
import { Portrait } from "@/components/supervisors/Person";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { isError } from "@/lib/frappe";
import { getSupervisor, type SupervisorDetail } from "@/lib/supervisors-api";
import { cn } from "@/lib/utils";

/** One supervisor in a modal: this week's blocks and activities, task counts and the casual labourers they run. */
export function SupervisorDialog({
  employee,
  name,
  crop,
  year,
  week,
  onClose,
  onEdit,
  reloadKey = 0,
}: {
  employee: string;
  name: string;
  crop: string | null;
  year: number;
  week: number;
  onClose: () => void;
  onEdit: (d: SupervisorDetail) => void;
  reloadKey?: number;
}) {
  const [data, setData] = useState<SupervisorDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setError(null);
    void getSupervisor(employee, crop, year, week).then((r) => {
      if (!live) return;
      if (isError(r)) setError(r.error);
      else setData(r);
    });
    return () => {
      live = false;
    };
  }, [employee, crop, year, week, reloadKey]);

  const s = data?.supervisor;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl" aria-describedby="sv-desc">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <Portrait name={s?.employee_name || name} image={s?.image} className="h-14 w-14" />
            <div className="min-w-0 flex-1">
              <DialogTitle className="text-[22px] tracking-tight">{s?.employee_name || name}</DialogTitle>
              <DialogDescription id="sv-desc" className="mt-1">
                {[employee, s?.phone, s?.farm, s && !s.active ? "Inactive" : null].filter(Boolean).join(" · ")}
              </DialogDescription>
            </div>
            {data?.can_edit && (
              <Button variant="outline" size="sm" onClick={() => onEdit(data)}>
                <Pencil className="h-3.5 w-3.5" strokeWidth={1.75} />
                Edit
              </Button>
            )}
          </div>
        </DialogHeader>

        {error ? (
          <p className="text-[13px] text-[var(--sd-muted)]">{error}</p>
        ) : !data ? (
          <RowsSkeleton rows={4} />
        ) : (
          <div className="flex flex-col gap-5">
            <KpiGrid cols={4}>
              <KpiCard label="Blocks" value={data.blocks.length} hint={`week ${data.week}, ${data.year}`} />
              <KpiCard label="Done" value={data.tasks.done} hint={`of ${data.tasks.total} tasks`} tone="good" />
              <KpiCard label="Open" value={data.tasks.open} hint={data.tasks.late ? `${data.tasks.late} late` : "none late"} tone={data.tasks.late ? "warning" : "default"} />
              <KpiCard label="To approve" value={data.pending} hint="crew entries pending" tone={data.pending ? "warning" : "default"} />
            </KpiGrid>

            <section>
              <h3 className="mb-2 text-[13px] font-semibold text-[var(--sd-ink)]">Blocks this week</h3>
              {data.blocks.length === 0 ? (
                <p className="text-[13px] text-[var(--sd-muted)]">Not assigned to any block this week.</p>
              ) : (
                <ul className="divide-y divide-[var(--sd-line-soft)] rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] px-4">
                  {data.blocks.map((b) => (
                    <li key={b.unit} className="flex flex-wrap items-center gap-2 py-2 text-[13px]">
                      <span className="font-medium text-[var(--sd-ink)]">{b.unit_name}</span>
                      {b.overseer && <span className="rounded-full bg-[var(--sd-pistachio)] px-2 py-0.5 text-[11.5px]">Overseer</span>}
                      {b.categories.map((c) => (
                        <span key={c} className="rounded-full bg-[var(--sd-card)] px-2 py-0.5 text-[11.5px] text-[var(--sd-muted)]">
                          {c}
                        </span>
                      ))}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section>
              <h3 className="mb-2 text-[13px] font-semibold text-[var(--sd-ink)]">Casual labourers ({data.labourers.length})</h3>
              {data.labourers.length === 0 ? (
                <p className="text-[13px] text-[var(--sd-muted)]">No casual labourers are assigned to this supervisor.</p>
              ) : (
                <ul className="grid gap-2 sm:grid-cols-2">
                  {data.labourers.map((l) => (
                    <li key={l.employee} className={cn("flex items-center gap-2.5 rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] px-3 py-2", !l.active && "opacity-60")}>
                      <Portrait name={l.employee_name} image={l.image} className="h-8 w-8 text-[11px]" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[13px] font-medium text-[var(--sd-ink)]">{l.employee_name}</span>
                        <span className="block text-[11px] text-[var(--sd-quiet)]">{[l.crew, l.active ? null : "Inactive"].filter(Boolean).join(" · ") || l.employee}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            {s?.notes && <p className="text-[12.5px] text-[var(--sd-muted)]">{s.notes}</p>}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

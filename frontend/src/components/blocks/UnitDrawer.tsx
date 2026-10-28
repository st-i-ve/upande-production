import { useEffect, useState } from "react";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { RowsSkeleton } from "@/components/Loading";
import { useToast } from "@/components/Toast";
import { StatusPill } from "@/components/blocks/StatusPill";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { getUnit, type OverviewBlock, type Row, type Unit } from "@/lib/api";
import { isError } from "@/lib/frappe";
import { ha, kes, qty, shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const str = (v: unknown) => (v == null || v === "" ? "—" : String(v));

/** A side panel for one unit: its rotation history and its recent work. */
export function UnitDrawer({
  name,
  unitLabel,
  canSeePay,
  stats,
  uom,
  onClose,
}: {
  name: string;
  unitLabel: string;
  canSeePay: boolean;
  /** Season totals for this unit from the overview, when they have arrived. */
  stats?: OverviewBlock;
  uom?: string;
  onClose: () => void;
}) {
  const toast = useToast();
  const [data, setData] = useState<Unit | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    setLoading(true);
    void getUnit(name).then((r) => {
      if (!live) return;
      setLoading(false);
      if (isError(r)) {
        setFailed(true);
        toast(r.error, "error");
        return;
      }
      setData(r as Unit);
    });
    return () => {
      live = false;
    };
  }, [name, toast]);

  const u = data?.unit;
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        className="left-auto right-0 top-0 h-full max-h-none w-full max-w-[560px] translate-x-0 translate-y-0 content-start overflow-y-auto sm:rounded-none sm:rounded-l-[var(--sd-radius-card)]"
      >
        <DialogHeader>
          <DialogTitle className="text-[22px] tracking-tight">{name}</DialogTitle>
          <DialogDescription className="flex flex-wrap items-center gap-2">
            {u ? (
              <>
                <span>{u.parent ? `${u.unit_type} in ${u.parent}` : u.unit_type}</span>
                <StatusPill status={u.status} />
              </>
            ) : (
              <span>{unitLabel}</span>
            )}
          </DialogDescription>
        </DialogHeader>

        {loading && !data ? (
          <RowsSkeleton rows={8} />
        ) : failed || !data || !u ? (
          <p className="text-[13px] text-[var(--sd-muted)]">This {unitLabel.toLowerCase()} could not be loaded.</p>
        ) : (
          <>
            <KpiGrid cols={2}>
              <KpiCard label="Area" value={`${ha(u.area_ha)} ha`} hint={u.plant_count ? `${qty(u.plant_count)} plants` : undefined} />
              <KpiCard
                label="Plants per ha"
                value={u.plant_count && u.area_ha ? qty(u.plant_count / u.area_ha) : "—"}
              />
              {stats && <KpiCard label="Open tasks" value={qty(stats.tasks_open)} hint="this week" tone={stats.tasks_open ? "warning" : "good"} />}
              {stats && <KpiCard label="Harvest this season" value={`${qty(stats.harvest_qty_season)}${uom ? ` ${uom}` : ""}`} />}
              {stats && canSeePay && <KpiCard label="Labour this season" value={kes(stats.labour_cost_season)} />}
              <KpiCard
                label="Recent work"
                value={`${qty(data.recent_work.reduce((t, w) => t + Number(w.hours ?? 0), 0), 1)} h`}
                hint={`${data.recent_work.length} latest entries`}
              />
            </KpiGrid>
            {u.cost_center && (
              <p className="text-[12px] text-[var(--sd-quiet)]">
                Cost centre <span className="tabular-nums text-[var(--sd-muted)]">{u.cost_center}</span>
              </p>
            )}

            <section className="flex flex-col gap-2">
              <h3 className="text-[13px] font-semibold text-[var(--sd-ink)]">Rotation history</h3>
              {data.cycles.length === 0 ? (
                <p className="text-[13px] text-[var(--sd-muted)]">No cycles on this {unitLabel.toLowerCase()} yet.</p>
              ) : (
                <div className="overflow-auto">
                  <table className="w-full min-w-[460px] text-[13px]">
                    <thead>
                      <tr className={THEAD_ROW}>
                        <th className={TH}>Cycle</th>
                        <th className={TH}>Started</th>
                        <th className={TH}>Harvest window</th>
                        <th className={TH}>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.cycles.map((c) => (
                        <tr key={c.name} className={BODY_ROW}>
                          <td className={TD}>
                            <div className="font-medium text-[var(--sd-ink)]">{c.item || c.title || c.name}</div>
                            <div className="text-[11px] text-[var(--sd-quiet)]">{c.cycle_type}</div>
                          </td>
                          <td className={cn(TD, "tabular-nums")}>{shortDate(c.start_date)}</td>
                          <td className={cn(TD, "tabular-nums text-[var(--sd-muted)]")}>
                            {c.expected_harvest_start
                              ? `${shortDate(c.expected_harvest_start)} – ${shortDate(c.expected_harvest_end)}`
                              : "—"}
                          </td>
                          <td className={TD}>
                            <StatusPill status={c.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="flex flex-col gap-2">
              <h3 className="text-[13px] font-semibold text-[var(--sd-ink)]">Recent work</h3>
              {data.recent_work.length === 0 ? (
                <p className="text-[13px] text-[var(--sd-muted)]">No work recorded here yet.</p>
              ) : (
                <div className="overflow-auto">
                  <table className="w-full min-w-[460px] text-[13px]">
                    <thead>
                      <tr className={THEAD_ROW}>
                        <th className={TH}>Date</th>
                        <th className={TH}>Value adder</th>
                        <th className={TH}>Operation</th>
                        <th className={THR}>Qty</th>
                        {canSeePay && <th className={THR}>Pay</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_work.map((w: Row, i) => (
                        <tr key={str(w.name) + i} className={BODY_ROW}>
                          <td className={cn(TD, "tabular-nums")}>{shortDate(w.work_date as string)}</td>
                          <td className={TD}>{str(w.employee_name ?? w.employee)}</td>
                          <td className={TD}>{str(w.operation)}</td>
                          <td className={TDR}>
                            {qty(Number(w.qty ?? 0), 1)}
                            {w.uom ? <span className="ml-1 text-[11px] text-[var(--sd-quiet)]">{String(w.uom)}</span> : null}
                          </td>
                          {canSeePay && <td className={cn(TDR, "text-[var(--sd-muted)]")}>{kes(w.pay_value as number | null)}</td>}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

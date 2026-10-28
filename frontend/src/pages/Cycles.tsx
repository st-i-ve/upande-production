import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { FilterSelect } from "@/components/FilterSelect";
import { RowsSkeleton } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { useToast } from "@/components/Toast";
import { StatusPill } from "@/components/blocks/StatusPill";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { CYCLE_STATUSES, NewCycleDialog } from "@/components/cycles/NewCycleDialog";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeaderRow,
  CardHeading,
  CardTitle,
  CardTools,
} from "@/components/ui/card";
import { listCycles, listUnits, type Cycle, type UnitRow } from "@/lib/api";
import { pluralise, useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { ha, qty, shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const ALL = "all";

export function Cycles() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const [cycles, setCycles] = useState<Cycle[] | null>(null);
  const [units, setUnits] = useState<UnitRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState(ALL);
  const [unit, setUnit] = useState(ALL);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await listCycles(crop.name, unit === ALL ? null : unit, status === ALL ? null : status);
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setCycles((r as { cycles: Cycle[] }).cycles);
  }, [crop.name, unit, status, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  // Units feed the filter and the dialog; a failure costs those, not the list.
  useEffect(() => {
    let live = true;
    setUnit(ALL);
    void listUnits(crop.name).then((r) => {
      if (!live) return;
      if (isError(r)) toast(r.error, "error");
      else setUnits((r as { units: UnitRow[] }).units);
    });
    return () => {
      live = false;
    };
  }, [crop.name, toast]);

  const unitOptions = useMemo(
    () => [
      { value: ALL, label: `All ${pluralise(crop.unit_label).toLowerCase()}` },
      ...units.map((u) => ({ value: u.name, label: u.name })),
    ],
    [units, crop.unit_label],
  );
  const statusOptions = useMemo(
    () => [{ value: ALL, label: "All statuses" }, ...CYCLE_STATUSES.map((s) => ({ value: s, label: s }))],
    [],
  );

  const waiting = loading && !cycles;
  const filtered = status !== ALL || unit !== ALL;

  return (
    <PageShell
      title={viewLabel("cycles", crop)}
      eyebrow={crop.name}
      actions={
        <>
          <RefreshButton onClick={load} loading={loading} label="the cycles" />
          <Button className="h-9 rounded-full px-4" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" />
            New cycle
          </Button>
        </>
      }
      description={`One cycle per ${crop.unit_label.toLowerCase()} per season, newest first. A protocol on the cycle drives its weekly plan.`}
    >
      <Card>
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Cycles</CardTitle>
            <CardDescription>{cycles ? `${qty(cycles.length)} shown` : "Loading…"}</CardDescription>
          </CardHeading>
          <CardTools>
            <FilterSelect
              aria-label="Status"
              value={status}
              options={statusOptions}
              onChange={setStatus}
            />
            <FilterSelect
              aria-label={crop.unit_label}
              value={unit}
              options={unitOptions}
              onChange={setUnit}
            />
          </CardTools>
        </CardHeaderRow>
        <CardContent>
          {waiting ? (
            <RowsSkeleton rows={6} />
          ) : cycles && cycles.length === 0 ? (
            <p className="text-[13px] text-[var(--sd-muted)]">
              {filtered ? "No cycles match these filters." : `No crop cycles for ${crop.name} yet. Use New cycle to start one.`}
            </p>
          ) : (
            cycles && (
              <ScrollTable tall>
                <table className="w-full min-w-[820px] text-[13px]">
                  <thead>
                    <tr className={cn(THEAD_ROW, STICKY_HEAD)}>
                      <th className={TH}>Cycle</th>
                      <th className={TH}>{crop.unit_label}</th>
                      <th className={TH}>Type</th>
                      <th className={TH}>Started</th>
                      <th className={TH}>Harvest window</th>
                      <th className={THR}>Area (ha)</th>
                      <th className={TH}>Protocol</th>
                      <th className={TH}>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {cycles.map((c) => (
                      <tr key={c.name} className={BODY_ROW}>
                        <td className={TD}>
                          <div className="font-medium text-[var(--sd-ink)]">{c.item || c.title || c.name}</div>
                          <div className="text-[11px] tabular-nums text-[var(--sd-quiet)]">{c.name}</div>
                        </td>
                        <td className={TD}>{c.unit}</td>
                        <td className={cn(TD, "text-[var(--sd-muted)]")}>{c.cycle_type}</td>
                        <td className={cn(TD, "tabular-nums")}>{shortDate(c.start_date)}</td>
                        <td className={cn(TD, "tabular-nums text-[var(--sd-muted)]")}>
                          {c.expected_harvest_start
                            ? `${shortDate(c.expected_harvest_start)} – ${shortDate(c.expected_harvest_end)}`
                            : "—"}
                        </td>
                        <td className={TDR}>{ha(c.area_ha)}</td>
                        <td className={cn(TD, "text-[var(--sd-muted)]")}>{c.protocol || "—"}</td>
                        <td className={TD}>
                          <StatusPill status={c.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </ScrollTable>
            )
          )}
        </CardContent>
      </Card>

      <NewCycleDialog
        crop={crop}
        units={units.map((u) => ({ name: u.name, is_group: !!u.is_group }))}
        defaultUnit={unit === ALL ? undefined : unit}
        open={creating}
        onOpenChange={setCreating}
        onSaved={() => void load()}
      />
    </PageShell>
  );
}

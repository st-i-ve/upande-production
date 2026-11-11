import { useCallback, useEffect, useMemo, useState } from "react";
import { ScanLine } from "lucide-react";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { Chip, daysAgo, EmptyNote, TONE } from "@/components/apiary/ui";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { DateRangePicker, type DateRange } from "@/components/DateRangePicker";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard } from "@/components/KpiCard";
import { firstLoad, MapPageSkeleton, TableRowsSkeleton } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { ToolbarButton } from "@/components/ToolbarButton";
import { useToast } from "@/components/Toast";
import { FinishAllocationDialog } from "@/components/machines/FinishAllocationDialog";
import { MachinePositions } from "@/components/machines/MachinePositions";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { durationLabel } from "@/lib/machine-scan";
import { listAllocations, type Allocation, type AllocationList, type AllocationStatus } from "@/lib/machines-api";
import { routeHash } from "@/lib/router";
import { todayISO } from "@/lib/utils";

const STATUSES: AllocationStatus[] = ["Open", "Closed", "Posted", "Cancelled"];
const STATUS_TONE: Record<AllocationStatus, string> = { Open: TONE.warn, Closed: TONE.quiet, Posted: TONE.ok, Cancelled: TONE.bad };
const STATUS_LABEL: Record<AllocationStatus, string> = { Open: "Running", Closed: "To post", Posted: "Posted", Cancelled: "Cancelled" };
const defaultRange = (): DateRange => ({ from: daysAgo(6), to: todayISO() });
const n = (v: number | null | undefined, d = 0) =>
  v == null ? "—" : Number(v).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
const place = (lat: number | null, lng: number | null) => (lat != null && lng != null && (lat || lng) ? `${lat.toFixed(5)}, ${lng.toFixed(5)}` : null);

/** Allocations: what each machine did, for whom, for how long and on how much diesel; open ones first, and where each machine was last scanned. */
export function Allocations() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const [data, setData] = useState<AllocationList | null>(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [status, setStatus] = useState("");
  const [machine, setMachine] = useState("");
  const [target, setTarget] = useState("");
  const [finishing, setFinishing] = useState<Allocation | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await listAllocations({ from_date: range.from, to_date: range.to, status, machine, allocated_to: target });
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setData(r as AllocationList);
  }, [range, status, machine, target, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const first = firstLoad(loading, !!data);
  const k = data?.kpis;
  const dirty = !!status || !!machine || !!target || range.from !== defaultRange().from || range.to !== defaultRange().to;
  const machineOptions = useMemo(() => (data?.machines ?? []).map((m) => ({ value: m.name, label: m.machine_name })), [data]);
  const rows = data?.rows ?? [];

  return (
    <PageShell
      title={viewLabel("allocations", crop)}
      eyebrow="Machines"
      description="Running allocations are always listed; the rest by the day they started. Posting an allocation issues its diesel from the fuel warehouse, and its cost is that stock entry's value."
      actions={
        <>
          <DateRangePicker label="Period" value={range} onChange={setRange} max={todayISO()} />
          <FilterSelect label="Status" value={status} onChange={setStatus} options={STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] }))} allLabel="Any status" />
          <FilterSelect label="Machine" value={machine} onChange={setMachine} options={machineOptions} allLabel="All machines" />
          <FilterSelect label="Allocated to" value={target} onChange={setTarget} options={data?.allocated_to ?? []} allLabel="Anything" />
          <ClearFiltersPill
            active={dirty}
            onClear={() => {
              setStatus("");
              setMachine("");
              setTarget("");
              setRange(defaultRange());
            }}
          />
          <RefreshButton onClick={load} loading={loading} label="the allocations" />
          <ToolbarButton onClick={() => (window.location.hash = routeHash(crop.crop_key, "scan"))}>
            <ScanLine className="h-4 w-4" />
            Scan a machine
          </ToolbarButton>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <KpiCard loading={first} label="Running now" value={k ? String(k.open) : "—"} hint={k?.to_submit ? `${k.to_submit} closed, not posted` : "every allocation closed is posted"} tone={k?.to_submit ? "warning" : "default"} showDelta={false} />
        <KpiCard loading={first} label="Machine hours" value={k ? `${n(k.hours, 1)} h` : "—"} hint="posted, in the period" showDelta={false} />
        <KpiCard loading={first} label="Diesel" value={k ? `${n(k.diesel_litres, 0)} L` : "—"} hint="issued from stock" showDelta={false} />
        <KpiCard loading={first} label="Diesel cost" value={k ? n(k.diesel_cost, 0) : "—"} hint="stock value of the issues" showDelta={false} />
      </div>

      {first || !data ? <MapPageSkeleton /> : <MachinePositions machines={data.machines} />}

      <Card className="overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Allocations</CardTitle>
            <CardDescription>Newest first. Positions are the ones read when the machine's QR code was scanned.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? (
          <ScrollTable>
            <table className="w-full text-[13px]">
              <tbody>
                <TableRowsSkeleton cols={9} rows={5} />
              </tbody>
            </table>
          </ScrollTable>
        ) : rows.length ? (
          <ScrollTable>
            <table className="w-full text-[13px]" data-testid="allocation-table">
              <thead className={STICKY_HEAD}>
                <tr className={THEAD_ROW}>
                  <th className={TH}>Machine</th>
                  <th className={TH}>Operator</th>
                  <th className={TH}>Allocated to</th>
                  <th className={TH}>Started</th>
                  <th className={THR}>Duration</th>
                  <th className={THR}>Diesel L</th>
                  <th className={THR}>Diesel cost</th>
                  <th className={TH}>Status</th>
                  <th className={TH}>Where</th>
                  <th className={TH}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const where = place(r.end_latitude, r.end_longitude) ?? place(r.start_latitude, r.start_longitude);
                  return (
                    <tr key={r.name} className={BODY_ROW}>
                      <td className={`${TD} font-semibold`}>
                        <a className="hover:underline" href={`/app/production-asset-allocation/${encodeURIComponent(r.name)}`}>
                          {r.machine}
                        </a>
                      </td>
                      <td className={TD}>{r.operator_name ?? r.operator}</td>
                      <td className={TD}>
                        {r.allocated_to}
                        {r.reference_name ? <span className="text-[var(--sd-muted)]"> · {r.reference_name}</span> : null}
                        <div className="text-[11.5px] text-[var(--sd-quiet)]">{r.cost_center}</div>
                      </td>
                      <td className={TD}>{r.start_time.slice(0, 16)}</td>
                      <td className={TDR}>{durationLabel(r.end_time ? r.duration_hours : r.running_hours)}</td>
                      <td className={TDR}>{r.diesel_litres ? n(r.diesel_litres, 1) : "—"}</td>
                      <td className={TDR}>{r.diesel_stock_entry ? n(r.diesel_cost, 0) : "—"}</td>
                      <td className={TD}>
                        <Chip className={STATUS_TONE[r.status]}>{STATUS_LABEL[r.status]}</Chip>
                        {!r.scanned && <Chip className={`ml-1 ${TONE.quiet}`} title="Started from the desk, not by scanning the machine">typed</Chip>}
                      </td>
                      <td className={`${TD} font-mono text-[11.5px]`}>{where ?? "—"}</td>
                      <td className={`${TD} text-right`}>
                        {r.docstatus === 0 && data.can_allocate && (
                          <Button variant="outline" size="sm" onClick={() => setFinishing(r)}>
                            {r.end_time ? "Post" : "Close"}
                          </Button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </ScrollTable>
        ) : (
          <EmptyNote>{dirty ? "No allocations match these filters." : "No machine was allocated this week. Scan a machine's QR code to start."}</EmptyNote>
        )}
      </Card>

      <FinishAllocationDialog allocation={finishing} canSubmit={!!data?.can_submit} onOpenChange={(o) => !o && setFinishing(null)} onDone={load} />
    </PageShell>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import { Pencil, Plus, Printer, ScanLine } from "lucide-react";
import { BODY_ROW, TD, TH, THEAD_ROW } from "@/components/blocks/tableStyles";
import { Chip, EmptyNote, TONE } from "@/components/apiary/ui";
import { KpiCard } from "@/components/KpiCard";
import { firstLoad, TableRowsSkeleton } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { TogglePill } from "@/components/TogglePill";
import { ToolbarButton } from "@/components/ToolbarButton";
import { useToast } from "@/components/Toast";
import { LabelPrintDialog } from "@/components/machines/LabelPrintDialog";
import { MachineDialog } from "@/components/machines/MachineDialog";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { durationLabel } from "@/lib/machine-scan";
import { listMachines, type Machine, type MachineList } from "@/lib/machines-api";
import { routeHash } from "@/lib/router";

/** Machines: the farm's tractors, choppers and wagons, who has each one now, and their QR labels. */
export function Machines() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const [data, setData] = useState<MachineList | null>(null);
  const [loading, setLoading] = useState(true);
  const [showDisabled, setShowDisabled] = useState(false);
  const [editing, setEditing] = useState<Machine | null | "new">(null);
  const [printing, setPrinting] = useState<string[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    const r = await listMachines(showDisabled);
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setData(r as MachineList);
  }, [showDisabled, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const first = firstLoad(loading, !!data);
  const rows = useMemo(() => data?.machines ?? [], [data]);
  const busy = rows.filter((m) => m.open_allocation).length;
  const enabled = rows.filter((m) => !m.disabled);
  const toPrint = picked.size ? [...picked] : enabled.map((m) => m.name);
  const toggle = (name: string) =>
    setPicked((p) => {
      const next = new Set(p);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  const closePrint = useCallback((o: boolean) => !o && setPrinting(null), []);

  return (
    <PageShell
      title={viewLabel("machines", crop)}
      eyebrow="Machines"
      description="Every machine carries a QR label. Scanning it starts an allocation (who runs it, for what, where it was); scanning again closes it and its diesel is issued from stock."
      actions={
        <>
          <TogglePill pressed={showDisabled} onPressedChange={setShowDisabled}>
            Show disabled
          </TogglePill>
          <RefreshButton onClick={load} loading={loading} label="the machines" />
          <ToolbarButton onClick={() => setPrinting(toPrint)} disabled={!toPrint.length}>
            <Printer className="h-4 w-4" />
            {picked.size ? `Print ${picked.size} label${picked.size === 1 ? "" : "s"}` : "Print all labels"}
          </ToolbarButton>
          {data?.can_manage && (
            <ToolbarButton onClick={() => setEditing("new")}>
              <Plus className="h-4 w-4" />
              New machine
            </ToolbarButton>
          )}
        </>
      }
    >
      {data && !data.settings.fuel_warehouse && (
        <div role="status" className="rounded-xl bg-[var(--sd-alert-warn)] px-4 py-3 text-[13px] text-[var(--sd-sev-high)]">
          No Fuel Warehouse is set in Production Settings, so allocations with diesel cannot be submitted yet.{" "}
          <a className="underline" href="/app/production-settings">
            Set it in Production Settings
          </a>
          .
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-3">
        <KpiCard loading={first} label="Machines" value={data ? String(enabled.length) : "—"} hint="in use on the farm" showDelta={false} />
        <KpiCard loading={first} label="Allocated now" value={data ? String(busy) : "—"} hint="an open allocation" showDelta={false} />
        <KpiCard loading={first} label="Idle" value={data ? String(enabled.length - busy) : "—"} hint="free to allocate" showDelta={false} />
      </div>

      <Card className="overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Machines</CardTitle>
            <CardDescription>Tick machines to print just their labels; with none ticked, every machine's label prints.</CardDescription>
          </CardHeading>
          <Button variant="outline" size="sm" asChild>
            <a href={routeHash(crop.crop_key, "scan")}>
              <ScanLine className="h-4 w-4" />
              Scan a machine
            </a>
          </Button>
        </CardHeaderRow>
        {first || !data ? (
          <ScrollTable>
            <table className="w-full text-[13px]">
              <tbody>
                <TableRowsSkeleton cols={7} rows={4} />
              </tbody>
            </table>
          </ScrollTable>
        ) : rows.length ? (
          <ScrollTable>
            <table className="w-full text-[13px]" data-testid="machine-table">
              <thead className={STICKY_HEAD}>
                <tr className={THEAD_ROW}>
                  <th className={TH}>
                    <span className="sr-only">Pick</span>
                  </th>
                  <th className={TH}>Machine</th>
                  <th className={TH}>Type</th>
                  <th className={TH}>Now</th>
                  <th className={TH}>Fuel item</th>
                  <th className={TH}>Cost centre</th>
                  <th className={TH}>Last seen</th>
                  <th className={TH}>Label</th>
                  <th className={TH}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((m) => (
                  <tr key={m.name} className={BODY_ROW}>
                    <td className={TD}>
                      <input
                        type="checkbox"
                        aria-label={`Pick ${m.machine_name}`}
                        checked={picked.has(m.name)}
                        onChange={() => toggle(m.name)}
                        className="h-4 w-4 accent-[var(--sd-ink)]"
                      />
                    </td>
                    <td className={`${TD} font-semibold`}>
                      {m.machine_name}
                      {!!m.disabled && <Chip className={`ml-2 ${TONE.quiet}`}>disabled</Chip>}
                    </td>
                    <td className={TD}>{m.machine_type}</td>
                    <td className={TD}>
                      {m.open_allocation ? (
                        <span>
                          <Chip className={TONE.warn}>{m.open_allocation.allocated_to}</Chip>{" "}
                          <span className="text-[var(--sd-muted)]">
                            {m.open_allocation.operator_name ?? m.open_allocation.operator} · {durationLabel(m.open_allocation.running_hours)}
                          </span>
                        </span>
                      ) : (
                        <Chip className={TONE.ok}>idle</Chip>
                      )}
                    </td>
                    <td className={TD}>{m.fuel_item ?? <span className="text-[var(--sd-quiet)]">not set</span>}</td>
                    <td className={TD}>{m.default_cost_center ?? "—"}</td>
                    <td className={TD}>{m.last_seen_at ? m.last_seen_at.slice(0, 16) : "—"}</td>
                    <td className={`${TD} font-mono text-[12px] tracking-[0.08em]`}>{m.qr_code ?? "—"}</td>
                    <td className={`${TD} whitespace-nowrap text-right`}>
                      <Button variant="ghost" size="sm" onClick={() => setPrinting([m.name])} aria-label={`Print label for ${m.machine_name}`}>
                        <Printer className="h-4 w-4" />
                      </Button>
                      {data.can_manage && (
                        <Button variant="ghost" size="sm" onClick={() => setEditing(m)} aria-label={`Edit ${m.machine_name}`}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollTable>
        ) : (
          <EmptyNote>{data.can_manage ? "No machines yet. Add one with New machine, then print its label." : "No machines yet."}</EmptyNote>
        )}
      </Card>

      {data && (
        <MachineDialog
          open={editing !== null}
          onOpenChange={(o) => !o && setEditing(null)}
          machine={editing === "new" ? null : editing}
          machineTypes={data.machine_types}
          onSaved={load}
        />
      )}
      <LabelPrintDialog open={printing !== null} onOpenChange={closePrint} machines={printing ?? []} />
    </PageShell>
  );
}

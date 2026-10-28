import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard } from "@/components/KpiCard";
import { RowsSkeleton, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { SearchInput } from "@/components/SearchInput";
import { ToolbarButton } from "@/components/ToolbarButton";
import { useToast } from "@/components/Toast";
import { StatusPill } from "@/components/blocks/StatusPill";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { CycleGantt } from "@/components/cycles/CycleGantt";
import { CYCLE_STATUSES, NewCycleDialog } from "@/components/cycles/NewCycleDialog";
import { Card, CardContent, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { listCycles, listUnits, type Cycle, type UnitRow } from "@/lib/api";
import { pluralise, useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { ha, qty, shortDate } from "@/lib/format";
import { cn, matchesQuery, ymd } from "@/lib/utils";

const ALL = "";
const WEEKS = 12;

/** The Monday-start week ends of the last WEEKS weeks, oldest first. */
function weekEnds(): string[] {
  const out: string[] = [];
  const now = new Date();
  for (let i = WEEKS - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i * 7);
    out.push(ymd(d));
  }
  return out;
}

/** A cycle counts as running on `day` between its start and its harvest end (or, with none, while not Closed). */
function runningOn(c: Cycle, day: string): boolean {
  if (c.status === "Planned" && c.start_date > day) return false;
  if (c.start_date > day) return false;
  if (c.expected_harvest_end) return c.expected_harvest_end >= day;
  return c.status !== "Closed";
}

export function Cycles() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#3f7d3a";
  const [cycles, setCycles] = useState<Cycle[] | null>(null);
  const [units, setUnits] = useState<UnitRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState(ALL);
  const [unit, setUnit] = useState(ALL);
  const [q, setQ] = useState("");
  const [tab, setTab] = useState("timeline");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await listCycles(crop.name, unit || null, status || null);
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

  const unitOptions = useMemo(() => units.map((u) => u.name), [units]);
  const statusOptions = useMemo(() => CYCLE_STATUSES.map((s) => ({ value: s, label: s })), []);

  const shown = useMemo(
    () => (cycles ?? []).filter((c) => !q || matchesQuery(`${c.name} ${c.title} ${c.unit} ${c.item ?? ""} ${c.protocol ?? ""}`, q)),
    [cycles, q],
  );

  const kpis = useMemo(() => {
    const all = shown;
    const running = all.filter((c) => c.status === "Active" || c.status === "Harvesting");
    const ends = weekEnds();
    const countSeries = ends.map((d) => ({ week: d, value: all.filter((c) => runningOn(c, d)).length }));
    const areaSeries = ends.map((d) => ({ week: d, value: all.filter((c) => runningOn(c, d)).reduce((t, c) => t + (c.area_ha || 0), 0) }));
    return {
      running: running.length,
      harvesting: all.filter((c) => c.status === "Harvesting").length,
      planned: all.filter((c) => c.status === "Planned").length,
      area: running.reduce((t, c) => t + (c.area_ha || 0), 0),
      countSeries,
      areaSeries,
      noProtocol: running.filter((c) => !c.protocol).length,
    };
  }, [shown]);

  const first = firstLoad(loading, !!cycles);
  const filtered = !!status || !!unit || !!q;
  const unitWord = pluralise(crop.unit_label).toLowerCase();
  const empty = !!cycles && shown.length === 0;

  const emptyText = filtered ? "No cycles match these filters." : `No crop cycles for ${crop.name} yet. Use New cycle to start one.`;

  return (
    <Tabs value={tab} onValueChange={setTab} className="flex min-w-0 flex-1 flex-col">
      <PageShell
        title={viewLabel("cycles", crop)}
        eyebrow={crop.name}
        tabs={
          <TabsList>
            <TabsTrigger value="timeline">Timeline</TabsTrigger>
            <TabsTrigger value="list">List</TabsTrigger>
          </TabsList>
        }
        actions={
          <>
            <SearchInput size="md" value={q} onChange={setQ} placeholder="Search cycles" className="w-48" />
            <FilterSelect aria-label="Status" value={status} options={statusOptions} onChange={setStatus} allLabel="All statuses" />
            <FilterSelect aria-label={crop.unit_label} value={unit} options={unitOptions} onChange={setUnit} allLabel={`All ${unitWord}`} />
            <ClearFiltersPill
              active={filtered}
              onClear={() => {
                setStatus(ALL);
                setUnit(ALL);
                setQ("");
              }}
            />
            <RefreshButton onClick={load} loading={loading} label="the cycles" />
            <ToolbarButton onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" />
              New cycle
            </ToolbarButton>
          </>
        }
        description={`One cycle per ${crop.unit_label.toLowerCase()} per season. A protocol on the cycle drives its weekly plan.`}
      >
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <KpiCard loading={first} label="Running cycles" value={kpis.running} hint={`${kpis.planned} planned next`} series={kpis.countSeries} goodDirection="up" deltaLabel="vs 1 week ago" />
          <KpiCard loading={first} label="In harvest" value={kpis.harvesting} hint="cycles picking now" tone={kpis.harvesting ? "accent" : "default"} />
          <KpiCard loading={first} label="Area in cycle" value={`${ha(kpis.area)} ha`} hint={`across ${unitWord}`} series={kpis.areaSeries} goodDirection="up" deltaLabel="vs 1 week ago" />
          <KpiCard
            loading={first}
            label="Without protocol"
            value={kpis.noProtocol}
            hint={kpis.noProtocol ? "running cycles with no weekly plan source" : "every running cycle has one"}
            tone={kpis.noProtocol ? "warning" : "good"}
          />
        </div>

        <TabsContent value="timeline" className="mt-0">
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Stage timeline</CardTitle>
                <CardDescription>{cycles ? `${qty(shown.length)} shown, oldest start first` : "Loading…"}</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent>
              {first ? <RowsSkeleton rows={6} /> : empty ? <p className="text-[13px] text-[var(--sd-muted)]">{emptyText}</p> : <CycleGantt cycles={shown} accent={accent} unitLabel={crop.unit_label} />}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="list" className="mt-0">
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Cycles</CardTitle>
                <CardDescription>{cycles ? `${qty(shown.length)} shown, newest first` : "Loading…"}</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent>
              {first ? (
                <RowsSkeleton rows={6} />
              ) : empty ? (
                <p className="text-[13px] text-[var(--sd-muted)]">{emptyText}</p>
              ) : (
                <CycleTable cycles={shown} unitLabel={crop.unit_label} />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <NewCycleDialog
          crop={crop}
          units={units.map((u) => ({ name: u.name, is_group: !!u.is_group }))}
          defaultUnit={unit || undefined}
          open={creating}
          onOpenChange={setCreating}
          onSaved={() => void load()}
        />
      </PageShell>
    </Tabs>
  );
}

function CycleTable({ cycles, unitLabel }: { cycles: Cycle[]; unitLabel: string }) {
  return (
    <ScrollTable tall>
      <table className="w-full min-w-[820px] text-[13px]">
        <thead>
          <tr className={cn(THEAD_ROW, STICKY_HEAD)}>
            <th className={TH}>Cycle</th>
            <th className={TH}>{unitLabel}</th>
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
                {c.expected_harvest_start ? `${shortDate(c.expected_harvest_start)} – ${shortDate(c.expected_harvest_end)}` : "—"}
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
  );
}

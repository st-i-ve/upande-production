import { useCallback, useEffect, useMemo, useState } from "react";
import { Lock } from "lucide-react";
import { ChartSkeleton, RowsSkeleton, firstLoad } from "@/components/Loading";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { DateRangePicker, type DateRange } from "@/components/DateRangePicker";
import { FilterSelect } from "@/components/FilterSelect";
import { flagCurrentWeek } from "@/components/Sparkline";
import { KpiCard } from "@/components/KpiCard";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { useToast } from "@/components/Toast";
import { BlockBreakdown } from "@/components/costs/BlockBreakdown";
import { CostTreemap } from "@/components/costs/CostTreemap";
import { CostsTable, buildTree } from "@/components/costs/CostsTable";
import { MarginChart } from "@/components/costs/MarginChart";
import { PivotRollup } from "@/components/costs/PivotRollup";
import { Card, CardContent, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { blockCosts, type BlockCostRow } from "@/lib/api";
import { useVarietyFilter } from "@/lib/use-varieties";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { costTrend, type CostTrendWeek } from "@/lib/insights-api";
import { kes, qty } from "@/lib/format";
import { todayISO } from "@/lib/utils";

const ALL = "";

const defaultRange = (): DateRange => {
  const today = todayISO();
  return { from: `${today.slice(0, 4)}-01-01`, to: today };
};

/** The rows of one group's subtree (the group itself included). */
function inSubtree(rows: BlockCostRow[], root: string): BlockCostRow[] {
  const byUnit = new Map(rows.map((r) => [r.unit, r]));
  return rows.filter((r) => {
    for (let cur: BlockCostRow | undefined = r, i = 0; cur && i < 20; cur = cur.parent ? byUnit.get(cur.parent) : undefined, i++) {
      if (cur.unit === root) return true;
    }
    return false;
  });
}

/**
 * What each block cost and earned over a period, like SCP's Finances page:
 * KPI cards with weekly sparklines, a per-group roll-up, a treemap of where the
 * money goes, margin by block, then the full table.
 *
 * The period defaults to the current year to date. Pay figures are withheld by
 * the server for a viewer, so the page drops every money column and says why.
 */
export function Costs() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const canSeePay = crop.boot.can_see_pay;
  const accent = crop.accent_color || "#3f7d3a";
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [group, setGroup] = useState(ALL);
  const [variety, setVariety] = useState(ALL);
  const vf = useVarietyFilter(crop.name);
  const [allRows, setRows] = useState<BlockCostRow[] | null>(null);
  const [trend, setTrend] = useState<CostTrendWeek[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [openUnit, setOpenUnit] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const [r, t] = await Promise.all([blockCosts(crop.name, range.from, range.to), costTrend(crop.name, range.from, range.to)]);
    setLoading(false);
    // The trend only feeds the sparklines; a failure there costs those, not the page.
    setTrend(isError(t) ? [] : (t.weeks ?? []));
    if (isError(r)) {
      setFailure(r.error);
      toast(r.error, "error");
      setRows((cur) => cur ?? []);
      return;
    }
    setFailure(null);
    setRows(r.rows ?? []);
  }, [crop.name, range.from, range.to, toast]);

  useEffect(() => {
    setRows(null);
    void load();
  }, [load]);

  const groups = useMemo(() => (allRows ?? []).filter((r) => r.is_group).map((r) => r.unit), [allRows]);
  const rows = useMemo(() => {
    const scoped = allRows && group ? inSubtree(allRows, group) : allRows;
    if (!scoped || !variety) return scoped;
    // A variety is grown on blocks; show those blocks flat (a group's roll-up mixes varieties).
    return scoped.filter((r) => !r.is_group && vf.byUnit.get(r.unit) === variety).map((r) => ({ ...r, parent: null }));
  }, [allRows, group, variety, vf.byUnit]);

  const totals = useMemo(() => {
    const roots = buildTree(rows ?? []).map((n) => n.row);
    const sum = (f: (r: BlockCostRow) => number) => roots.reduce((t, r) => t + f(r), 0);
    return {
      labour: sum((r) => r.labour || 0),
      inputs: sum((r) => r.inputs || 0),
      cost: sum((r) => r.total_cost || 0),
      revenue: sum((r) => r.revenue || 0),
      margin: sum((r) => r.margin || 0),
      area: sum((r) => r.area_ha || 0),
      harvest: sum((r) => r.harvest_qty || 0),
    };
  }, [rows]);

  // Weekly series for the KPI sparklines (whole crop: the trend endpoint is not group-scoped).
  const series = useMemo(() => {
    const w = trend ?? [];
    const pts = (f: (x: CostTrendWeek) => number) => flagCurrentWeek(w.map((x) => ({ week: x.week_start, value: f(x) }))) ?? [];
    return {
      labour: pts((x) => x.labour ?? 0),
      inputs: pts((x) => x.inputs),
      revenue: pts((x) => x.revenue),
      margin: pts((x) => x.revenue - (x.labour ?? 0) - x.inputs),
      perKg: pts((x) => (x.harvest_qty > 0 ? ((x.labour ?? 0) + x.inputs) / x.harvest_qty : 0)),
      harvest: pts((x) => x.harvest_qty),
    };
  }, [trend]);
  const perHaSeries = useMemo(
    () => (totals.area > 0 ? series.labour.map((p, i) => ({ week: p.week, partial: p.partial, value: (p.value + (series.inputs[i]?.value ?? 0)) / totals.area })) : []),
    [series, totals.area],
  );

  const first = firstLoad(loading, !!allRows);
  const empty = !!allRows && allRows.length === 0;
  const unitWord = crop.unit_label || "Block";
  const dirty = !!group || !!variety || range.from !== defaultRange().from || range.to !== defaultRange().to;
  const uom = crop.yield_uom || "kg";
  const hasData = !!rows && rows.length > 0;

  return (
    <PageShell
      title={viewLabel("costs", crop)}
      eyebrow={crop.name}
      description={`Labour, inputs and harvest value for each ${unitWord.toLowerCase()}, rolled up to the ${(crop.parent_unit_label || "group").toLowerCase()}.`}
      actions={
        <>
          {groups.length > 0 && (
            <FilterSelect
              label={crop.parent_unit_label || "Group"}
              value={group}
              onChange={setGroup}
              options={groups}
              allLabel={`All ${(crop.parent_unit_label || "groups").toLowerCase()}s`}
            />
          )}
          {vf.options.length > 0 && <FilterSelect label="Variety" value={variety} onChange={setVariety} options={vf.options} allLabel="All varieties" />}
          <DateRangePicker label="Period" value={range} onChange={setRange} max={todayISO()} />
          <ClearFiltersPill
            active={dirty}
            onClear={() => {
              setGroup(ALL);
              setVariety(ALL);
              setRange(defaultRange());
            }}
          />
          <RefreshButton onClick={load} loading={loading} label="the costs" />
        </>
      }
    >
      {!canSeePay && (
        <div
          role="note"
          className="flex items-center gap-2.5 rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-info)] px-4 py-3 text-[13px] font-medium text-[var(--sd-ink)]"
        >
          <Lock className="h-4 w-4 shrink-0 text-[var(--sd-quiet)]" />
          Money figures are hidden for your role. Area and harvest quantities are shown.
        </div>
      )}

      {failure && (
        <div role="alert" className="rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-error)] px-4 py-3 text-[13px] font-medium text-[var(--sd-ink)]">
          {failure}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-3">
        {canSeePay && (
          <KpiCard loading={first} label="Labour" value={kes(totals.labour)} hint="approved work, pay value" series={series.labour} goodDirection="down" />
        )}
        {canSeePay && <KpiCard loading={first} label="Inputs" value={kes(totals.inputs)} hint="expense postings on cost centres" series={series.inputs} goodDirection="down" />}
        {canSeePay && <KpiCard loading={first} label="Harvest value" value={kes(totals.revenue)} hint={`${qty(totals.harvest)} ${uom} harvested`} series={series.revenue} goodDirection="up" />}
        {canSeePay && (
          <>
            <KpiCard
              loading={first}
              label="Margin"
              value={kes(totals.margin)}
              hint={totals.margin < 0 ? "running at a loss" : "harvest value less cost"}
              tone={totals.margin < 0 ? "critical" : "good"}
              series={series.margin}
              goodDirection="up"
            />
            <KpiCard
              loading={first}
              label="Cost per ha"
              value={totals.area > 0 ? kes(totals.cost / totals.area) : "—"}
              hint={`over ${qty(totals.area, 1)} ha`}
              series={perHaSeries}
              goodDirection="down"
            />
            <KpiCard
              loading={first}
              label={`Cost per ${uom}`}
              value={totals.harvest > 0 ? `KES ${qty(totals.cost / totals.harvest, 2)}` : "—"}
              hint="labour + inputs per unit harvested"
              series={series.perKg}
              goodDirection="down"
            />
          </>
        )}
        {!canSeePay && <KpiCard loading={first} label="Harvested" value={qty(totals.harvest)} hint={uom} series={series.harvest} goodDirection="up" />}
      </div>

      {(first || hasData) && (
        <div className="grid gap-6 xl:grid-cols-2">
          {canSeePay && <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>By {(crop.parent_unit_label || "group").toLowerCase()}</CardTitle>
                <CardDescription>{canSeePay ? "Cost stacked, harvest value as the tick, margin on the right." : "Inputs and harvest value per group."}</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent className="pt-0">{!rows ? <RowsSkeleton rows={5} /> : <PivotRollup rows={rows} accent={accent} />}</CardContent>
          </Card>}
          <Card className={canSeePay ? undefined : "xl:col-span-2"}>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Where the money goes</CardTitle>
                <CardDescription>Each box is a {unitWord.toLowerCase()}; hover for the figures.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent className="pt-0">
              {!rows ? <ChartSkeleton height={340} /> : <CostTreemap rows={rows} canSeePay={canSeePay} accent={accent} />}
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Cost and margin by {unitWord.toLowerCase()}</CardTitle>
            <CardDescription>Open a group to see the blocks it adds up; open a block for what went into it.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        <CardContent className="pt-0">
          {!rows ? (
            <RowsSkeleton rows={6} />
          ) : empty || rows.length === 0 ? (
            <p className="px-1 py-6 text-center text-[13px] text-[var(--sd-muted)]">
              {failure ? "The costs could not be loaded." : `No ${unitWord.toLowerCase()} costs for this period.`}
            </p>
          ) : (
            <CostsTable rows={rows} canSeePay={canSeePay} areaLabel="Area (ha)" onOpenUnit={setOpenUnit} />
          )}
        </CardContent>
      </Card>

      {canSeePay && (
        <Card>
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>Margin by block</CardTitle>
              <CardDescription>Revenue less labour and inputs, for each individual block.</CardDescription>
            </CardHeading>
          </CardHeaderRow>
          <CardContent className="pt-0">{!rows ? <ChartSkeleton height={220} /> : <MarginChart rows={rows} />}</CardContent>
        </Card>
      )}
      {openUnit && <BlockBreakdown unit={openUnit} from={range.from} to={range.to} canSeePay={canSeePay} onClose={() => setOpenUnit(null)} />}
    </PageShell>
  );
}

import { useCallback, useEffect, useMemo, useState } from "react";
import { FilterSelect } from "@/components/FilterSelect";
import { flagCurrentWeek } from "@/components/Sparkline";
import { KpiCard, KpiGrid } from "@/components/KpiCard";
import { RowsSkeleton, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { SearchInput } from "@/components/SearchInput";
import { useToast } from "@/components/Toast";
import { BlockTable } from "@/components/overview/BlockTable";
import { EmptyNote, Panel } from "@/components/overview/Panel";
import {
  DeviationList,
  ForecastChart,
  HarvestTrend,
  OperationsProgress,
  UpcomingList,
} from "@/components/overview/Panels";
import { cycleFlags, getOverview, type CycleFlagRow, type Overview as OverviewData } from "@/lib/api";
import { cropUsesCycles, pluralise, useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { kes, qty } from "@/lib/format";
import { getOverviewExtras, type BlockExtra, type OverviewExtras } from "@/lib/overview-api";
import { routeHash } from "@/lib/router";
import { matchesQuery } from "@/lib/utils";

/** The crop at a glance: this week's work, the season's harvest, the next
 *  four weeks of forecast, and where each unit stands. */
export function Overview() {
  const crop = useCurrentCrop();
  const { boot } = crop;
  const toast = useToast();
  const accent = crop.accent_color || "#3f7d3a";
  const [data, setData] = useState<OverviewData | null>(null);
  const [extras, setExtras] = useState<OverviewExtras | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingExtras, setLoadingExtras] = useState(true);
  const [failed, setFailed] = useState(false);
  const [offProtocol, setOffProtocol] = useState<CycleFlagRow[] | null>(null);
  const [query, setQuery] = useState("");
  const [parent, setParent] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setLoadingExtras(true);
    // The extras are garnish: a failure there never blocks the page.
    void getOverviewExtras(crop.name).then((r) => {
      setLoadingExtras(false);
      if (!isError(r)) setExtras(r as OverviewExtras);
    });
    // Manager flags are garnish too: a failure leaves the card out.
    if (cropUsesCycles(crop)) {
      void cycleFlags(crop.name).then((f) => {
        if (f && !isError(f)) setOffProtocol((f as { rows: CycleFlagRow[] }).rows);
      });
    }
    const r = await getOverview(crop.name);
    setLoading(false);
    if (isError(r)) {
      setFailed(true);
      toast(r.error, "error");
      return;
    }
    setFailed(false);
    setData(r as OverviewData);
  }, [crop, toast]);

  useEffect(() => {
    setData(null);
    setExtras(null);
    setOffProtocol(null);
    void load();
  }, [load]);

  const waiting = firstLoad(loading, !!data);
  const exLoading = firstLoad(loadingExtras, !!extras);
  const t = data?.tiles;
  const units = pluralise(crop.unit_label).toLowerCase();
  const uom = crop.yield_uom;
  const usesCycles = cropUsesCycles(crop);

  const trend = extras?.trend;
  const series = (pick: (w: NonNullable<typeof trend>[number]) => number) =>
    flagCurrentWeek(trend?.map((w) => ({ week: w.week, value: pick(w) })));
  const fw = extras?.forecast_weeks;
  const pending = extras?.pending_approvals;

  const extraByUnit = useMemo(() => new Map<string, BlockExtra>((extras?.blocks ?? []).map((b) => [b.unit, b])), [extras]);
  const parents = useMemo(
    () => [...new Set((data?.blocks ?? []).map((b) => b.parent).filter((p): p is string => !!p))].sort(),
    [data],
  );
  const shown = useMemo(
    () =>
      (data?.blocks ?? []).filter(
        (b) =>
          (!parent || b.parent === parent) &&
          matchesQuery(`${b.unit} ${b.parent ?? ""} ${b.item ?? ""} ${usesCycles ? b.cycle ?? "" : ""}`, query),
      ),
    [data, parent, query, usesCycles],
  );

  return (
    <PageShell
      title={viewLabel("overview", crop)}
      eyebrow={crop.name}
      actions={<RefreshButton onClick={load} loading={loading} label="the overview" />}
      description={`How the season stands: this week's work, harvest so far, and where each ${crop.unit_label.toLowerCase()} is.`}
    >
      <KpiGrid cols={3}>
        <KpiCard
          label="Week done"
          value={t ? `${qty(t.done_pct)}%` : "—"}
          hint={t ? `${qty(t.tasks_done)} of ${qty(t.tasks_total)} tasks` : undefined}
          series={series((w) => w.done_pct)}
          goodDirection="up"
          loading={waiting}
        />
        <KpiCard
          label="Deviations"
          value={t ? qty(t.deviations) : "—"}
          hint="late, partial, skipped or missed · last 4 weeks"
          tone={t && t.deviations > 0 ? "warning" : "default"}
          series={series((w) => w.deviations)}
          goodDirection="down"
          loading={waiting}
        />
        {boot.can_see_pay && (
          <KpiCard
            label="Labour this month"
            value={t ? kes(t.labour_cost_mtd) : "—"}
            hint="value adder pay, month to date"
            series={trend?.some((w) => w.labour != null) ? series((w) => w.labour ?? 0) : undefined}
            loading={waiting}
          />
        )}
        <KpiCard
          label="Harvest this season"
          value={t ? `${qty(t.harvest_qty_season)} ${uom}` : "—"}
          hint="current calendar year"
          series={series((w) => w.harvest)}
          goodDirection="up"
          loading={waiting}
        />
        <KpiCard
          label="Next 4 weeks"
          value={t ? `${qty(t.forecast_next4)} ${uom}` : "—"}
          hint={t ? `forecast, ${qty(t.committed_next4)} committed` : undefined}
          series={fw?.map((w) => ({ week: w.week, value: w.forecast }))}
          showDelta={false}
          loading={waiting}
        />
        <KpiCard
          label="Pending approvals"
          value={pending != null ? qty(pending) : "—"}
          hint={pending ? "submissions waiting for a manager" : "nothing waiting"}
          tone={pending ? "warning" : "accent"}
          href={routeHash(crop.crop_key, "approvals")}
          loading={exLoading}
        />
      </KpiGrid>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Panel title="This week by operation" hint="Approved work, with work awaiting approval hatched.">
          <OperationsProgress rows={extras?.operations} color={accent} loading={exLoading} />
        </Panel>
        <Panel title="Harvest by week" hint={`Last 8 weeks, ${uom}.`}>
          <HarvestTrend trend={trend} color={accent} uom={uom} loading={exLoading} />
        </Panel>
        <Panel title="Forecast vs committed" hint={`Next four weeks, ${uom}.`}>
          <ForecastChart weeks={fw} color={accent} uom={uom} loading={exLoading} />
        </Panel>
        <Panel title="Upcoming tasks" hint="Open work due soonest.">
          <UpcomingList rows={extras?.upcoming} loading={exLoading} />
        </Panel>
        <Panel title="Recent deviations" hint="Last four weeks." className="lg:col-span-2">
          <DeviationList rows={extras?.recent_deviations} loading={exLoading} />
        </Panel>
        {offProtocol && (
          <Panel title="Off protocol" hint="Cycles that flowered or were picked later than expected, or have no date recorded." className="lg:col-span-2">
            {offProtocol.length === 0 ? (
              <EmptyNote>Every cycle is on protocol.</EmptyNote>
            ) : (
              <ul className="divide-y divide-[var(--sd-line-soft)]" data-testid="off-protocol">
                {offProtocol.map((r) => (
                  <li key={r.cycle} className="flex flex-wrap items-start gap-x-3 gap-y-1 py-2.5 text-[13px]">
                    <span className="w-40 shrink-0">
                      <span className="block font-medium text-[var(--sd-ink)]">{r.unit}</span>
                      <span className="block text-[11.5px] text-[var(--sd-quiet)]">{[r.variety, r.cycle].filter(Boolean).join(" · ")}</span>
                    </span>
                    <span className="min-w-0 flex-1 text-[var(--sd-sev-high)]">
                      {r.flags.map((f) => (
                        <span key={f} className="block break-words">{f}</span>
                      ))}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        )}
      </div>

      <Panel
        className="mt-4"
        title={pluralise(crop.unit_label)}
        hint={`${usesCycles ? "Current cycle, stage, open tasks" : "Open tasks"}, crew and season totals for each ${crop.unit_label.toLowerCase()}.`}
        tools={
          <div className="flex flex-wrap items-center gap-2">
            {parents.length > 1 && (
              <FilterSelect
                label={crop.parent_unit_label || "Parent"}
                value={parent}
                onChange={setParent}
                options={parents}
                allLabel={`All ${pluralise(crop.parent_unit_label || "parent").toLowerCase()}`}
              />
            )}
            <SearchInput size="md" value={query} onChange={setQuery} placeholder={`Search ${units}`} className="w-52" />
          </div>
        }
      >
        {waiting ? (
          <RowsSkeleton rows={6} />
        ) : failed && !data ? (
          <EmptyNote>The overview could not be loaded. Use the refresh button to try again.</EmptyNote>
        ) : data && data.blocks.length === 0 ? (
          <EmptyNote>
            No {units} recorded for {crop.name} yet.
          </EmptyNote>
        ) : (
          data && (
            <BlockTable
              blocks={shown}
              extras={extraByUnit}
              canSeePay={boot.can_see_pay}
              uom={uom}
              unitLabel={crop.unit_label}
              usesCycles={usesCycles}
            />
          )
        )}
      </Panel>
    </PageShell>
  );
}

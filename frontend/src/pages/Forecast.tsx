import { useCallback, useEffect, useMemo, useState } from "react";
import { ChartSkeleton, RowsSkeleton, firstLoad } from "@/components/Loading";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { DateRangePicker, type DateRange } from "@/components/DateRangePicker";
import { flagCurrentWeek } from "@/components/Sparkline";
import { KpiCard } from "@/components/KpiCard";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { SearchInput } from "@/components/SearchInput";
import { TogglePill } from "@/components/TogglePill";
import { useToast } from "@/components/Toast";
import { AccuracyTable, errorTone, vsForecast } from "@/components/forecast/AccuracyTable";
import { CommitmentsPanel } from "@/components/forecast/CommitmentsPanel";
import { FORECAST_CHART_HEIGHT, ForecastChart } from "@/components/forecast/ForecastChart";
import { SamplesPanel } from "@/components/forecast/SamplesPanel";
import { SEASONS_CHART_HEIGHT, SeasonsChart } from "@/components/forecast/SeasonsChart";
import { Card, CardContent, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { forecastSummary, type ForecastSummary, type ForecastTotals } from "@/lib/api";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { qty } from "@/lib/format";
import { matchesQuery, todayISO, ymd } from "@/lib/utils";

const EMPTY_TOTALS: ForecastTotals = { forecast: 0, forecast_to_date: 0, actual: 0, committed: 0, error_pct: null };

function offsetDays(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return ymd(d);
}
const defaultRange = (): DateRange => ({ from: offsetDays(-56), to: offsetDays(56) });

/**
 * What is expected to be harvested, what was, and what buyers have asked for.
 *
 * Tabs as pills: Overview (KPIs, weekly chart, seasons), Accuracy (per unit),
 * Samples and Commitments (the records behind the numbers). Accuracy is judged
 * per unit over the chosen window.
 */
export function Forecast() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const [tab, setTab] = useState("overview");
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [q, setQ] = useState("");
  const [offOnly, setOffOnly] = useState(false);
  const [data, setData] = useState<ForecastSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await forecastSummary(crop.name, range.from, range.to);
    setLoading(false);
    if (isError(r)) {
      setFailure(r.error);
      toast(r.error, "error");
      setData((cur) => cur ?? { uom: crop.yield_uom || "", weeks: [], units: [], totals: EMPTY_TOTALS, seasons: [] });
      return;
    }
    setFailure(null);
    setData({ ...r, weeks: r.weeks ?? [], units: r.units ?? [], totals: r.totals ?? EMPTY_TOTALS, seasons: r.seasons ?? [] });
  }, [crop.name, crop.yield_uom, range.from, range.to, toast]);

  useEffect(() => {
    setData(null);
    void load();
  }, [load]);

  const uom = data?.uom || crop.yield_uom || "";
  const unitLabel = crop.unit_label || "Unit";
  const canEdit = crop.boot.can_plan || crop.boot.can_manage;
  const totals = data?.totals ?? EMPTY_TOTALS;
  const first = firstLoad(loading, !!data);

  const series = useMemo(() => {
    const w = data?.weeks ?? [];
    const today = todayISO();
    // `realised` series (actual, error) stop at today: weeks still to come have nothing to compare.
    const pts = (f: (x: (typeof w)[number]) => number | null, realised = false) =>
      flagCurrentWeek(
        w.flatMap((x) => {
          const v = f(x);
          return v == null || (realised && x.week_start > today) ? [] : [{ week: x.week_start, value: v }];
        }),
      ) ?? [];
    return {
      forecast: pts((x) => x.forecast),
      actual: pts((x) => x.actual, true),
      committed: pts((x) => x.committed),
      error: pts((x) => (x.error_pct == null ? null : Math.abs(x.error_pct)), true),
      cover: pts((x) => (x.forecast > 0 ? (x.committed / x.forecast) * 100 : null)),
    };
  }, [data]);

  const offTarget = useMemo(() => (data?.units ?? []).filter((u) => errorTone(u.error_pct) === "poor").length, [data]);
  const cover = totals.forecast > 0 ? (totals.committed / totals.forecast) * 100 : null;

  const units = useMemo(
    () =>
      (data?.units ?? [])
        .filter((u) => !q || matchesQuery(u.unit, q))
        .filter((u) => !offOnly || errorTone(u.error_pct) !== "good")
        .sort((a, b) => Math.abs(b.error_pct ?? 0) - Math.abs(a.error_pct ?? 0)),
    [data, q, offOnly],
  );

  const dirty = range.from !== defaultRange().from || range.to !== defaultRange().to || !!q || offOnly;
  const clear = () => {
    setRange(defaultRange());
    setQ("");
    setOffOnly(false);
  };

  return (
    <Tabs value={tab} onValueChange={setTab} className="flex min-w-0 flex-1 flex-col">
      <PageShell
        title={viewLabel("forecast", crop)}
        eyebrow={crop.name}
        tab={tab}
        description={`Expected ${uom ? uom + " " : ""}harvest by week against what came in and what buyers have committed.`}
        tabs={
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="accuracy">Accuracy</TabsTrigger>
            <TabsTrigger value="samples">Samples</TabsTrigger>
            <TabsTrigger value="commitments">Commitments</TabsTrigger>
          </TabsList>
        }
        filters={[
          { key: "q", tabs: ["accuracy"], node: <SearchInput size="md" value={q} onChange={setQ} placeholder={`Search ${unitLabel.toLowerCase()}s`} className="w-48" /> },
          {
            key: "off",
            tabs: ["accuracy"],
            node: (
              <TogglePill pressed={offOnly} onPressedChange={setOffOnly}>
                Off by more than 10%
              </TogglePill>
            ),
          },
          { key: "range", tabs: ["overview", "accuracy"], node: <DateRangePicker label="Period" value={range} onChange={setRange} /> },
        ]}
        actions={
          <>
            <ClearFiltersPill active={dirty} onClear={clear} />
            <RefreshButton onClick={load} loading={loading} label="the forecast" />
          </>
        }
      >
        {failure && (
          <div role="alert" className="rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-error)] px-4 py-3 text-[13px] font-medium text-[var(--sd-ink)]">
            {failure}
          </div>
        )}

        <TabsContent value="overview" className="mt-0 flex flex-col gap-6">
          <div className="grid grid-cols-2 gap-4 xl:grid-cols-3">
            <KpiCard loading={first} label="Forecast" value={data ? `${qty(totals.forecast)} ${uom}` : "—"} hint="in this period" series={series.forecast} />
            <KpiCard loading={first} label="Actual" value={data ? `${qty(totals.actual)} ${uom}` : "—"} hint="harvested" series={series.actual} goodDirection="up" />
            <KpiCard loading={first} label="Committed" value={data ? `${qty(totals.committed)} ${uom}` : "—"} hint="to buyers" series={series.committed} goodDirection="up" />
            <KpiCard
              loading={first}
              label="Actual vs forecast to date"
              value={data ? vsForecast(totals.error_pct) : "—"}
              tone={data ? ({ good: "accent", fair: "warning", poor: "critical", none: "default" } as const)[errorTone(totals.error_pct)] : "default"}
              hint="harvest so far against the forecast for the same weeks"
              series={series.error}
              goodDirection="down"
              deltaLabel="weekly miss"
            />
            <KpiCard
              loading={first}
              label="Buyer cover"
              value={cover == null ? "—" : `${cover.toFixed(0)}%`}
              hint="committed as a share of forecast"
              series={series.cover}
              goodDirection="up"
            />
            <KpiCard
              loading={first}
              label={`${unitLabel}s off target`}
              value={data ? offTarget : "—"}
              hint="more than 25% from forecast"
              tone={offTarget ? "warning" : "good"}
            />
          </div>

          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Weekly forecast, actual and committed</CardTitle>
                <CardDescription>Hover a week for the figures behind it. Weeks start on Monday.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent className="pt-0">
              {!data ? <ChartSkeleton height={FORECAST_CHART_HEIGHT} /> : <ForecastChart weeks={data.weeks} uom={uom} today={todayISO()} />}
            </CardContent>
          </Card>

          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Seasons</CardTitle>
                <CardDescription>Harvest per year.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent className="pt-0">
              {!data ? <ChartSkeleton height={SEASONS_CHART_HEIGHT} /> : <SeasonsChart seasons={data.seasons} uom={uom} />}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="accuracy" className="mt-0">
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Accuracy by {unitLabel.toLowerCase()}</CardTitle>
                <CardDescription>How close the forecast was to what was harvested, furthest off first.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <CardContent className="pt-0">
              {!data ? (
                <RowsSkeleton rows={5} />
              ) : data.units.length === 0 ? (
                <p className="px-1 py-6 text-center text-[13px] text-[var(--sd-muted)]">No forecasts to compare for this period.</p>
              ) : units.length === 0 ? (
                <p className="px-1 py-6 text-center text-[13px] text-[var(--sd-muted)]">Nothing matches these filters.</p>
              ) : (
                <AccuracyTable units={units} uom={uom} unitLabel={unitLabel} />
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="samples" className="mt-0">
          <Card>
            <CardContent className="pt-5">
              <SamplesPanel crop={crop.name} unitLabel={unitLabel} canEdit={canEdit} onSaved={load} />
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="commitments" className="mt-0">
          <Card>
            <CardContent className="pt-5">
              <CommitmentsPanel crop={crop.name} uom={uom} canEdit={canEdit} canSeePay={crop.boot.can_see_pay} onSaved={load} />
            </CardContent>
          </Card>
        </TabsContent>
      </PageShell>
    </Tabs>
  );
}

import { useCallback, useEffect, useState } from "react";
import { ChartSkeleton, RowsSkeleton } from "@/components/Loading";
import { Figure, FigureRow } from "@/components/Figure";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { useToast } from "@/components/Toast";
import { DateRangePill } from "@/components/costs/DateRangePill";
import { AccuracyTable } from "@/components/forecast/AccuracyTable";
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
import { todayISO, ymd } from "@/lib/utils";

const EMPTY_TOTALS: ForecastTotals = { forecast: 0, forecast_to_date: 0, actual: 0, committed: 0, error_pct: null };

function offsetDays(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return ymd(d);
}

/**
 * What is expected to be harvested, what was, and what buyers have asked for.
 *
 * Accuracy is judged per unit over the chosen window; the seasons chart is the
 * long view, one bar per calendar year.
 */
export function Forecast() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const [from, setFrom] = useState(() => offsetDays(-56));
  const [to, setTo] = useState(() => offsetDays(56));
  const [data, setData] = useState<ForecastSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await forecastSummary(crop.name, from, to);
    setLoading(false);
    if (isError(r)) {
      setFailure(r.error);
      toast(r.error, "error");
      setData((cur) => cur ?? { uom: crop.yield_uom || "", weeks: [], units: [], totals: EMPTY_TOTALS, seasons: [] });
      return;
    }
    setFailure(null);
    setData({ ...r, weeks: r.weeks ?? [], units: r.units ?? [], totals: r.totals ?? EMPTY_TOTALS, seasons: r.seasons ?? [] });
  }, [crop.name, crop.yield_uom, from, to, toast]);

  useEffect(() => {
    setData(null);
    void load();
  }, [load]);

  const uom = data?.uom || crop.yield_uom || "";
  const unitLabel = crop.unit_label || "Unit";
  const canEdit = crop.boot.can_plan || crop.boot.can_manage;

  const totals = data?.totals ?? EMPTY_TOTALS;


  return (
    <PageShell
      title={viewLabel("forecast", crop)}
      eyebrow={crop.name}
      description={`Expected ${uom ? uom + " " : ""}harvest by week against what came in and what buyers have committed.`}
      actions={
        <>
          <DateRangePill from={from} to={to} onChange={(f, t) => (setFrom(f), setTo(t))} />
          <RefreshButton onClick={load} loading={loading} label="the forecast" />
        </>
      }
    >
      {failure && (
        <div role="alert" className="rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-error)] px-4 py-3 text-[13px] font-medium text-[var(--sd-ink)]">
          {failure}
        </div>
      )}

      <FigureRow>
        <Figure loading={!data} label="Forecast" value={data ? qty(totals.forecast) : "—"} unit={uom} hint="in this period" />
        <Figure loading={!data} label="Actual" value={data ? qty(totals.actual) : "—"} unit={uom} hint="harvested" />
        <Figure loading={!data} label="Committed" value={data ? qty(totals.committed) : "—"} unit={uom} hint="to buyers" />
        <Figure
          loading={!data}
          label="Accuracy to date"
          value={data && totals.error_pct != null ? `${totals.error_pct > 0 ? "+" : ""}${totals.error_pct.toFixed(1)}%` : "—"}
          hint="actual vs forecast so far"
        />
      </FigureRow>

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

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>Accuracy by {unitLabel.toLowerCase()}</CardTitle>
              <CardDescription>How close the forecast was to what was harvested.</CardDescription>
            </CardHeading>
          </CardHeaderRow>
          <CardContent className="pt-0">
            {!data ? (
              <RowsSkeleton rows={5} />
            ) : data.units.length === 0 ? (
              <p className="px-1 py-6 text-center text-[13px] text-[var(--sd-muted)]">No forecasts to compare for this period.</p>
            ) : (
              <AccuracyTable units={data.units} uom={uom} unitLabel={unitLabel} />
            )}
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
      </div>

      <Card>
        <CardContent className="pt-5">
          <Tabs defaultValue="samples" className="flex flex-col gap-4">
            <TabsList className="self-start">
              <TabsTrigger value="samples">Samples</TabsTrigger>
              <TabsTrigger value="commitments">Commitments</TabsTrigger>
            </TabsList>
            <TabsContent value="samples">
              <SamplesPanel crop={crop.name} unitLabel={unitLabel} canEdit={canEdit} onSaved={load} />
            </TabsContent>
            <TabsContent value="commitments">
              <CommitmentsPanel crop={crop.name} uom={uom} canEdit={canEdit} canSeePay={crop.boot.can_see_pay} onSaved={load} />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </PageShell>
  );
}

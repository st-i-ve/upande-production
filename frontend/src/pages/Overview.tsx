import { useCallback, useEffect, useState } from "react";
import { Figure, FigureRow } from "@/components/Figure";
import { RowsSkeleton } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { useToast } from "@/components/Toast";
import { BlockTable } from "@/components/overview/BlockTable";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeaderRow,
  CardHeading,
  CardTitle,
  CardTools,
} from "@/components/ui/card";
import { getOverview, type Overview as OverviewData } from "@/lib/api";
import { pluralise, useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { kes, qty } from "@/lib/format";

/** The crop at a glance: this week's work, the season's harvest, the next
 *  four weeks of forecast, and where each unit stands. */
export function Overview() {
  const crop = useCurrentCrop();
  const { boot } = crop;
  const toast = useToast();
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await getOverview(crop.name);
    setLoading(false);
    if (isError(r)) {
      setFailed(true);
      toast(r.error, "error");
      return;
    }
    setFailed(false);
    setData(r as OverviewData);
  }, [crop.name, toast]);

  useEffect(() => {
    setData(null);
    void load();
  }, [load]);

  const waiting = loading && !data;
  const t = data?.tiles;
  const dash = (v: string | undefined) => (t ? (v as string) : "—");
  const units = pluralise(crop.unit_label).toLowerCase();

  return (
    <PageShell
      title={viewLabel("overview", crop)}
      eyebrow={crop.name}
      actions={<RefreshButton onClick={load} loading={loading} label="the overview" />}
      description={`How the season stands: this week's work, harvest so far, and where each ${crop.unit_label.toLowerCase()} is.`}
    >
      <FigureRow>
        <Figure
          label="Active cycles"
          value={dash(t && qty(t.active_cycles))}
          hint={`across ${units}`}
          loading={waiting}
        />
        <Figure
          label="Week done"
          value={dash(t && qty(t.done_pct))}
          unit={t ? "%" : undefined}
          hint={t ? `${qty(t.tasks_done)} of ${qty(t.tasks_total)} tasks` : undefined}
          loading={waiting}
        />
        <Figure
          label="Deviations"
          value={dash(t && qty(t.deviations))}
          hint="late, partial, skipped or missed · last 4 weeks"
          loading={waiting}
        />
        {boot.can_see_pay && (
          <Figure
            label="Labour this month"
            value={dash(t && kes(t.labour_cost_mtd))}
            hint="value adder pay, month to date"
            loading={waiting}
          />
        )}
        <Figure
          label="Harvest this season"
          value={dash(t && qty(t.harvest_qty_season))}
          unit={t ? crop.yield_uom : undefined}
          hint="current calendar year"
          loading={waiting}
        />
        <Figure
          label="Next 4 weeks"
          value={dash(t && qty(t.forecast_next4))}
          unit={t ? crop.yield_uom : undefined}
          hint={t ? `forecast, ${qty(t.committed_next4)} committed` : undefined}
          loading={waiting}
        />
      </FigureRow>

      <Card>
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>{pluralise(crop.unit_label)}</CardTitle>
            <CardDescription>
              Current cycle, open tasks and season totals for each {crop.unit_label.toLowerCase()}.
            </CardDescription>
          </CardHeading>
          <CardTools />
        </CardHeaderRow>
        <CardContent>
          {waiting ? (
            <RowsSkeleton rows={6} />
          ) : failed && !data ? (
            <p className="text-[13px] text-[var(--sd-muted)]">
              The overview could not be loaded. Use the refresh button to try again.
            </p>
          ) : data && data.blocks.length === 0 ? (
            <p className="text-[13px] text-[var(--sd-muted)]">
              No {units} recorded for {crop.name} yet.
            </p>
          ) : (
            data && (
              <BlockTable
                blocks={data.blocks}
                canSeePay={boot.can_see_pay}
                uom={crop.yield_uom}
                unitLabel={crop.unit_label}
              />
            )
          )}
        </CardContent>
      </Card>
    </PageShell>
  );
}

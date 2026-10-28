import { useCallback, useEffect, useMemo, useState } from "react";
import { Lock } from "lucide-react";
import { ChartSkeleton, RowsSkeleton } from "@/components/Loading";
import { Figure, FigureRow } from "@/components/Figure";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { useToast } from "@/components/Toast";
import { CostsTable, buildTree } from "@/components/costs/CostsTable";
import { DateRangePill } from "@/components/costs/DateRangePill";
import { MarginChart } from "@/components/costs/MarginChart";
import { Card, CardContent, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { blockCosts, type BlockCostRow } from "@/lib/api";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { kes } from "@/lib/format";
import { todayISO } from "@/lib/utils";

/**
 * What each block cost and earned over a period.
 *
 * The period defaults to the current year to date: the season is the calendar
 * year. Pay figures are withheld by the server for a viewer, so the page drops
 * every money column and says why instead of showing a column of dashes.
 */
export function Costs() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const canSeePay = crop.boot.can_see_pay;
  const today = todayISO();
  const [from, setFrom] = useState(`${today.slice(0, 4)}-01-01`);
  const [to, setTo] = useState(today);
  const [rows, setRows] = useState<BlockCostRow[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [failure, setFailure] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await blockCosts(crop.name, from, to);
    setLoading(false);
    if (isError(r)) {
      setFailure(r.error);
      toast(r.error, "error");
      setRows((cur) => cur ?? []);
      return;
    }
    setFailure(null);
    setRows(r.rows ?? []);
  }, [crop.name, from, to, toast]);

  useEffect(() => {
    setRows(null);
    void load();
  }, [load]);

  const totals = useMemo(() => {
    const roots = buildTree(rows ?? []).map((n) => n.row);
    const sum = (f: (r: BlockCostRow) => number) => roots.reduce((t, r) => t + f(r), 0);
    return {
      cost: sum((r) => r.total_cost || 0),
      revenue: sum((r) => r.revenue || 0),
      margin: sum((r) => r.margin || 0),
      area: sum((r) => r.area_ha || 0),
    };
  }, [rows]);

  const empty = !!rows && rows.length === 0;
  const unitWord = crop.unit_label || "Block";

  return (
    <PageShell
      title={viewLabel("costs", crop)}
      eyebrow={crop.name}
      description={`Labour, inputs and harvest value for each ${unitWord.toLowerCase()}, rolled up to the ${(crop.parent_unit_label || "group").toLowerCase()}.`}
      actions={
        <>
          <DateRangePill from={from} to={to} onChange={(f, t) => (setFrom(f), setTo(t))} />
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

      {canSeePay && (
        <FigureRow>
          <Figure loading={!rows} label="Total cost" value={rows ? kes(totals.cost) : "—"} hint="labour + inputs" />
          <Figure loading={!rows} label="Revenue" value={rows ? kes(totals.revenue) : "—"} hint="harvest value" />
          <Figure
            loading={!rows}
            label="Margin"
            value={rows ? kes(totals.margin) : "—"}
            hint={totals.margin < 0 ? "running at a loss" : "revenue less cost"}
          />
          <Figure
            loading={!rows}
            label="Cost per ha"
            value={rows && totals.area > 0 ? kes(totals.cost / totals.area) : "—"}
          />
        </FigureRow>
      )}

      <Card>
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Cost and margin by {unitWord.toLowerCase()}</CardTitle>
            <CardDescription>Open a group to see the blocks it adds up.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        <CardContent className="pt-0">
          {!rows ? (
            <RowsSkeleton rows={6} />
          ) : empty ? (
            <p className="px-1 py-6 text-center text-[13px] text-[var(--sd-muted)]">
              {failure ? "The costs could not be loaded." : `No ${unitWord.toLowerCase()} costs for this period.`}
            </p>
          ) : (
            <CostsTable rows={rows} canSeePay={canSeePay} areaLabel="Area (ha)" />
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
          <CardContent className="pt-0">
            {!rows ? <ChartSkeleton height={220} /> : <MarginChart rows={rows} />}
          </CardContent>
        </Card>
      )}
    </PageShell>
  );
}

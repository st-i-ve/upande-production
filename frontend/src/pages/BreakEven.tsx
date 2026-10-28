import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Lock } from "lucide-react";
import { CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ChartSkeleton, RowsSkeleton, firstLoad } from "@/components/Loading";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard } from "@/components/KpiCard";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable } from "@/components/ScrollTable";
import { useToast } from "@/components/Toast";
import { Card, CardContent, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { compact } from "@/components/forecast/chart-utils";
import { cropBreakeven, type BreakEvenBlock, type BreakEvenFarm } from "@/lib/breakeven-api";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { kes, qty, shortDate } from "@/lib/format";

const PAY_MESSAGE = "Break-even includes pay; ask a manager.";
const BASIS: Record<string, string> = {
  forecast: "from the forecast",
  trailing_12m: "from the last 12 months' net",
};
type SortKey = "unit" | "invested" | "recovered" | "balance" | "pct_recovered";

function monthLabel(ymd: string): string {
  return shortDate(ymd).replace(/^\d+ /, "");
}

/** The date a block (or the farm) breaks even: reached, or projected. */
function dateCell(b: { break_even_date?: string | null; projected_date?: string | null }) {
  if (b.break_even_date) return <span className="text-[var(--sd-data-green)]">{shortDate(b.break_even_date)}</span>;
  if (b.projected_date) return <span className="text-[var(--sd-muted)]">~{shortDate(b.projected_date)}</span>;
  return <span className="text-[var(--sd-quiet)]">—</span>;
}

function CostValueChart({ farm, accent }: { farm: BreakEvenFarm; accent: string }) {
  const cross = farm.break_even_date ? farm.points.find((p) => p.date >= (farm.break_even_date as string)) : undefined;
  return (
    <div data-testid="breakeven-chart">
      <div className="h-[300px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={farm.points} margin={{ top: 12, right: 24, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--sd-line)" />
            <XAxis dataKey="date" tickFormatter={monthLabel} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--sd-quiet)" }} minTickGap={24} />
            <YAxis width={52} tickFormatter={compact} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--sd-quiet)" }} />
            <Tooltip
              content={({ active, payload }) => {
                const p = active ? (payload?.[0]?.payload as { date: string; cost: number; value: number } | undefined) : undefined;
                if (!p) return null;
                return (
                  <div className="rounded-lg bg-foreground px-3 py-2 text-[12px] text-background shadow-[var(--sd-shadow-3)]">
                    <div className="font-semibold">{monthLabel(p.date)}</div>
                    <div>Cost {kes(p.cost)}</div>
                    <div>Value {kes(p.value)}</div>
                  </div>
                );
              }}
            />
            <Line type="monotone" dataKey="cost" name="Cumulative cost" stroke="var(--sd-data-amber)" strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="value" name="Cumulative value" stroke={accent} strokeWidth={2} dot={false} isAnimationActive={false} />
            {cross && <ReferenceDot x={cross.date} y={cross.value} r={6} fill="var(--sd-ink)" stroke="var(--sd-card)" strokeWidth={2} />}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-1 pt-2 text-[12px] text-[var(--sd-muted)]">
        <span className="flex items-center gap-2"><i className="h-0.5 w-4" style={{ background: "var(--sd-data-amber)" }} />Cumulative cost</span>
        <span className="flex items-center gap-2"><i className="h-0.5 w-4" style={{ background: accent }} />Cumulative harvest value</span>
        {cross && <span className="flex items-center gap-2"><i className="h-2.5 w-2.5 rounded-full bg-[var(--sd-ink)]" />Break-even, {monthLabel(cross.date)}</span>}
      </div>
    </div>
  );
}

/**
 * When each block pays back what it cost: setup cost, running cost and harvest value, summed per
 * block and for the farm, with the month the two lines cross (or when they are expected to).
 * It includes labour pay, so it is shown only to people who can see pay.
 */
export function BreakEven() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const canSeePay = crop.boot.can_see_pay;
  const accent = crop.accent_color || "#3f7d3a";
  const farms = crop.boot.farms ?? [];
  const [farm, setFarm] = useState("");
  const [data, setData] = useState<{ blocks: BreakEvenBlock[]; farm: BreakEvenFarm } | null>(null);
  const [loading, setLoading] = useState(canSeePay);
  const [failure, setFailure] = useState<string | null>(null);
  const [hidden, setHidden] = useState(!canSeePay);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "pct_recovered", dir: -1 });

  const load = useCallback(async () => {
    if (!canSeePay) return;
    setLoading(true);
    const r = await cropBreakeven(crop.name, farm || null);
    setLoading(false);
    if (isError(r)) {
      if (/includes pay/i.test(r.error)) return setHidden(true);
      setFailure(r.error);
      toast(r.error, "error");
      return;
    }
    setFailure(null);
    setData({ blocks: r.blocks ?? [], farm: r.farm });
  }, [crop.name, farm, canSeePay, toast]);

  useEffect(() => {
    setData(null);
    void load();
  }, [load]);

  const blocks = useMemo(() => {
    const rows = [...(data?.blocks ?? [])];
    rows.sort((a, b) => {
      const x = a[sort.key];
      const y = b[sort.key];
      return (typeof x === "string" ? x.localeCompare(y as string) : (x as number) - (y as number)) * sort.dir;
    });
    return rows;
  }, [data, sort]);

  const title = viewLabel("break-even", crop);
  if (hidden) {
    return (
      <PageShell title={title} eyebrow={crop.name}>
        <div role="note" className="flex max-w-xl items-center gap-2.5 rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-info)] px-4 py-3 text-[13px] font-medium text-[var(--sd-ink)]">
          <Lock className="h-4 w-4 shrink-0 text-[var(--sd-quiet)]" />
          {PAY_MESSAGE}
        </div>
      </PageShell>
    );
  }

  const f = data?.farm;
  const first = firstLoad(loading, !!data);
  const sortBy = (key: SortKey) => setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: key === "unit" ? 1 : -1 }));
  const head = (key: SortKey, label: string, right = true) => (
    <TableHead className={right ? "text-right" : undefined} aria-sort={sort.key === key ? (sort.dir === 1 ? "ascending" : "descending") : "none"}>
      <button type="button" className="inline-flex items-center gap-1 font-medium hover:text-foreground" onClick={() => sortBy(key)}>
        {label}
        {sort.key === key && (sort.dir === 1 ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)}
      </button>
    </TableHead>
  );

  return (
    <PageShell
      title={title}
      eyebrow={crop.name}
      description="Setup cost, running cost and harvest value added up over time. A block breaks even in the month its cumulative value reaches its cumulative cost."
      actions={
        <>
          {farms.length > 1 && <FilterSelect label="Farm" value={farm} onChange={setFarm} options={farms} allLabel="All farms" />}
          <RefreshButton onClick={load} loading={loading} label="the break-even figures" />
        </>
      }
    >
      {failure && (
        <div role="alert" className="rounded-[var(--sd-radius-toast)] bg-[var(--sd-alert-error)] px-4 py-3 text-[13px] font-medium text-[var(--sd-ink)]">
          {failure}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 xl:grid-cols-5">
        <KpiCard loading={first} label="Invested" value={kes(f?.invested)} hint="setup + running cost" />
        <KpiCard loading={first} label="Recovered" value={kes(f?.recovered)} hint="harvest value" />
        <KpiCard
          loading={first}
          label="Balance"
          value={kes(f?.balance)}
          hint={f && f.balance < 0 ? "still to recover" : "ahead of cost"}
          tone={f ? (f.balance < 0 ? "critical" : "good") : "default"}
        />
        <KpiCard loading={first} label="Share recovered" value={f ? `${qty(f.pct_recovered, 0)}%` : "—"} hint="of what was invested" />
        {f?.break_even_date ? (
          <KpiCard loading={first} label="Break-even" value={shortDate(f.break_even_date)} hint="cumulative value passed cost" tone="good" />
        ) : (
          <KpiCard
            loading={first}
            label="Projected break-even"
            value={shortDate(f?.projected_date)}
            hint={f?.projected_date ? (BASIS[f.projection_basis ?? ""] ?? "projected") : "no projection yet"}
          />
        )}
      </div>

      <Card>
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Cumulative cost and value</CardTitle>
            <CardDescription>Month by month for the {farm || "whole"} farm; the dot is where value passes cost.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        <CardContent className="pt-0">
          {!f ? (
            <ChartSkeleton height={300} />
          ) : f.points.length === 0 ? (
            <p className="px-1 py-6 text-center text-[13px] text-[var(--sd-muted)]">No costs or harvests recorded yet.</p>
          ) : (
            <CostValueChart farm={f} accent={accent} />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>By {(crop.unit_label || "block").toLowerCase()}</CardTitle>
            <CardDescription>Click a heading to sort. A date with ~ is a projection.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        <CardContent className="pt-0">
          {!data ? (
            <RowsSkeleton rows={6} />
          ) : blocks.length === 0 ? (
            <p className="px-1 py-6 text-center text-[13px] text-[var(--sd-muted)]">{failure ? "The figures could not be loaded." : "No blocks to show."}</p>
          ) : (
            <ScrollTable>
              <Table>
                <TableHeader>
                  <TableRow>
                    {head("unit", crop.unit_label || "Block", false)}
                    {head("invested", "Invested")}
                    {head("recovered", "Recovered")}
                    {head("balance", "Balance")}
                    {head("pct_recovered", "% recovered")}
                    <TableHead className="text-right">Break-even</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {blocks.map((b) => (
                    <TableRow key={b.unit} data-testid={`be-row-${b.unit}`}>
                      <TableCell className="font-medium">{b.unit}</TableCell>
                      <TableCell className="text-right tabular-nums">{kes(b.invested)}</TableCell>
                      <TableCell className="text-right tabular-nums">{kes(b.recovered)}</TableCell>
                      <TableCell className={`text-right tabular-nums ${b.balance < 0 ? "text-[var(--sd-data-red)]" : ""}`}>{kes(b.balance)}</TableCell>
                      <TableCell className="text-right tabular-nums">{qty(b.pct_recovered, 0)}%</TableCell>
                      <TableCell className="text-right tabular-nums">{dateCell(b)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </ScrollTable>
          )}
        </CardContent>
      </Card>
    </PageShell>
  );
}

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { DeviationBadge, StatusPill } from "@/components/plan/badges";
import { PendingChip, QtyBar } from "@/components/plan/QtyBar";
import { q, rowDate } from "@/components/plan/fmt";
import { EmptyNote } from "@/components/overview/Panel";
import { ChartSkeleton, RowsSkeleton } from "@/components/Loading";
import type { ForecastWeek, OperationProgress, RecentDeviation, TrendWeek, UpcomingTask } from "@/lib/overview-api";

const AXIS = { fontSize: 11, fill: "var(--sd-quiet)" };
const shortWeek = (w: string) => w.replace(/^\d{4}-/, "");

export function OperationsProgress({
  rows,
  color,
  loading,
}: {
  rows?: OperationProgress[];
  color: string;
  loading: boolean;
}) {
  if (loading) return <RowsSkeleton rows={4} />;
  if (!rows || !rows.length) return <EmptyNote>Nothing is planned for this week yet.</EmptyNote>;
  return (
    <ul className="flex flex-col gap-3.5">
      {rows.map((r) => {
        const pct = r.planned ? Math.round((r.done / r.planned) * 100) : 0;
        return (
          <li key={r.operation_name} className="flex flex-col gap-1.5">
            <div className="flex flex-wrap items-baseline gap-x-3 text-[13px]">
              <span className="min-w-0 flex-1 truncate font-medium text-[var(--sd-ink)]">{r.operation_name}</span>
              {r.pending > 0 && <PendingChip>{q(r.pending)} awaiting approval</PendingChip>}
              <span className="tabular-nums text-[var(--sd-muted)]">
                <span className="text-[var(--sd-ink)]">{q(r.done)}</span> / {q(r.planned)} {r.uom ?? ""}
              </span>
              <span className="w-10 text-right tabular-nums text-[var(--sd-quiet)]">{pct}%</span>
            </div>
            <QtyBar planned={r.planned} done={r.done} pending={r.pending} color={color} />
            <div className="text-[11.5px] text-[var(--sd-quiet)]">
              {r.tasks_done} of {r.tasks} task{r.tasks === 1 ? "" : "s"} done
            </div>
          </li>
        );
      })}
    </ul>
  );
}

export function HarvestTrend({
  trend,
  color,
  uom,
  loading,
}: {
  trend?: TrendWeek[];
  color: string;
  uom: string;
  loading: boolean;
}) {
  if (loading) return <ChartSkeleton height={220} />;
  if (!trend || !trend.some((t) => t.harvest > 0)) return <EmptyNote>No harvest recorded in the last 8 weeks.</EmptyNote>;
  const data = trend.map((t) => ({ week: shortWeek(t.week), harvest: t.harvest }));
  return (
    <div className="h-[220px] w-full" role="img" aria-label="Harvest by week">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--sd-line-soft)" />
          <XAxis dataKey="week" tick={AXIS} axisLine={false} tickLine={false} />
          <YAxis tick={AXIS} axisLine={false} tickLine={false} width={44} />
          <Tooltip
            cursor={{ fill: "var(--sd-bg-soft)" }}
            formatter={(v: number) => [`${q(v)} ${uom}`, "Harvest"]}
            contentStyle={{ borderRadius: 12, border: "none", boxShadow: "var(--sd-shadow-2)", fontSize: 12 }}
          />
          <Bar dataKey="harvest" fill={color} radius={[6, 6, 0, 0]} maxBarSize={36} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ForecastChart({
  weeks,
  color,
  uom,
  loading,
}: {
  weeks?: ForecastWeek[];
  color: string;
  uom: string;
  loading: boolean;
}) {
  if (loading) return <ChartSkeleton height={220} />;
  if (!weeks || !weeks.some((w) => w.forecast > 0 || w.committed > 0))
    return <EmptyNote>No forecast or buyer commitments for the next four weeks.</EmptyNote>;
  const data = weeks.map((w) => ({ week: shortWeek(w.week), Forecast: w.forecast, Committed: w.committed }));
  return (
    <div className="h-[220px] w-full" role="img" aria-label="Forecast against committed, next four weeks">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 4, left: 0, bottom: 0 }} barGap={4}>
          <CartesianGrid vertical={false} stroke="var(--sd-line-soft)" />
          <XAxis dataKey="week" tick={AXIS} axisLine={false} tickLine={false} />
          <YAxis tick={AXIS} axisLine={false} tickLine={false} width={44} />
          <Tooltip
            cursor={{ fill: "var(--sd-bg-soft)" }}
            formatter={(v: number, n: string) => [`${q(v)} ${uom}`, n]}
            contentStyle={{ borderRadius: 12, border: "none", boxShadow: "var(--sd-shadow-2)", fontSize: 12 }}
          />
          <Bar dataKey="Forecast" fill={color} radius={[6, 6, 0, 0]} maxBarSize={28} />
          <Bar dataKey="Committed" fill="var(--sd-ink)" opacity={0.75} radius={[6, 6, 0, 0]} maxBarSize={28} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function UpcomingList({ rows, loading }: { rows?: UpcomingTask[]; loading: boolean }) {
  if (loading) return <RowsSkeleton rows={5} />;
  if (!rows || !rows.length) return <EmptyNote>No open tasks are due.</EmptyNote>;
  return (
    <ul className="divide-y divide-[var(--sd-line-soft)]">
      {rows.map((t, i) => (
        <li key={`${t.unit}-${t.operation_name}-${i}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5 text-[13px]">
          <span className="w-24 shrink-0 tabular-nums text-[var(--sd-muted)]">{rowDate(t.due_date)}</span>
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium text-[var(--sd-ink)]">{t.operation_name}</span>
            <span className="block truncate text-[11.5px] text-[var(--sd-quiet)]">{t.unit}</span>
          </span>
          <span className="tabular-nums text-[var(--sd-muted)]">
            {q(t.done_qty)} / {q(t.planned_qty)} {t.uom ?? ""}
          </span>
          <StatusPill status={t.status} />
        </li>
      ))}
    </ul>
  );
}

export function DeviationList({ rows, loading }: { rows?: RecentDeviation[]; loading: boolean }) {
  if (loading) return <RowsSkeleton rows={5} />;
  if (!rows || !rows.length) return <EmptyNote>No deviations in the last four weeks.</EmptyNote>;
  return (
    <ul className="divide-y divide-[var(--sd-line-soft)]">
      {rows.map((d, i) => (
        <li key={`${d.unit}-${d.operation_name}-${i}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5 text-[13px]">
          <span className="w-24 shrink-0 tabular-nums text-[var(--sd-muted)]">{rowDate(d.due_date)}</span>
          <span className="min-w-0 flex-1">
            <span className="block truncate font-medium text-[var(--sd-ink)]">{d.operation_name}</span>
            <span className="block truncate text-[11.5px] text-[var(--sd-quiet)]">
              {d.unit} · {d.detail}
            </span>
          </span>
          <DeviationBadge deviation={d.kind} />
        </li>
      ))}
    </ul>
  );
}

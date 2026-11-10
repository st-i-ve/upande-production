import { useMemo } from "react";
import { CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { dayMonth } from "@/components/avocado/calendar-format";
import type { Series } from "@/lib/dmmonitor-api";
import { ymd } from "@/lib/utils";

const DAY = 86_400_000;
const ts = (d: string) => new Date(`${d}T00:00:00`).getTime();

interface Row {
  t: number;
  dm?: number | null;
  micro?: number | null;
  machine?: number | null;
  lab?: number | null;
  proj?: number | null;
}

/** One chart per selection: the average of both methods, microwave and machine apart when both were used,
 *  lab tests as points, the export target and max as reference lines and the straight-line projection to the target. */
export function MonitorChart({
  series,
  lab,
  target,
  max,
  accent,
  label,
}: {
  series: Series | undefined;
  lab?: { date: string; dm_pct: number }[];
  target: number | null;
  max: number | null;
  accent: string;
  label: string;
}) {
  const { rows, both, lo, hi, projEnd, ticks } = useMemo(() => {
    const pts = series?.points ?? [];
    const map = new Map<number, Row>();
    const row = (d: string) => {
      const t = ts(d);
      if (!map.has(t)) map.set(t, { t });
      return map.get(t)!;
    };
    for (const p of pts) Object.assign(row(p.date), { dm: p.dm_pct, micro: p.microwave_pct, machine: p.machine_pct });
    // lab tests only where the fruit was being followed (two weeks of lead), so an old test does not stretch the axis
    const from = pts.length ? ts(pts[0].date) - 14 * DAY : Infinity;
    for (const p of lab ?? []) if (ts(p.date) >= from) row(p.date).lab = p.dm_pct;
    const hasMicro = pts.some((p) => p.microwave_pct != null);
    const hasMachine = pts.some((p) => p.machine_pct != null);
    const last = pts[pts.length - 1];
    const pj = series?.projection;
    let end: number | null = null;
    if (last && last.dm_pct != null && target && pj?.state === "rising" && pj.date) {
      row(last.date).proj = last.dm_pct;
      row(pj.date).proj = target;
      end = ts(pj.date);
    }
    const all = [...map.values()].sort((a, b) => a.t - b.t);
    const vals = all.flatMap((r) => [r.dm, r.micro, r.machine, r.lab]).filter((v): v is number => v != null);
    const floor = Math.floor(Math.min(...vals, target ?? Infinity) - 2);
    const ceil = Math.ceil(Math.max(...vals, max ?? target ?? 0) + 1);
    const span = ceil - floor;
    const step = span <= 12 ? 2 : span <= 30 ? 5 : 10;
    const bottom = Math.floor((Number.isFinite(floor) ? floor : 0) / step) * step;
    const top = Math.ceil(ceil / step) * step;
    const ticks: number[] = [];
    for (let v = bottom; v <= top; v += step) ticks.push(v);
    return { rows: all, both: hasMicro && hasMachine, lo: bottom, hi: top, projEnd: end, ticks };
  }, [series, lab, target, max]);

  if (!rows.length) {
    return (
      <div className="flex h-[320px] items-center justify-center rounded-xl bg-[var(--sd-bg-soft)] text-[13px] text-[var(--sd-quiet)]" data-testid="dm-monitor-empty">
        No readings yet. Add one to start the line.
      </div>
    );
  }
  const t0 = rows[0].t - 2 * DAY;
  const t1 = Math.max(rows[rows.length - 1].t, projEnd ?? 0) + 2 * DAY;
  return (
    <div className="h-[340px] w-full" role="img" aria-label={label} data-testid="dm-monitor-chart">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 12, right: 24, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="var(--sd-line)" />
          <XAxis dataKey="t" type="number" scale="time" domain={[t0, t1]} tickFormatter={(t: number) => dayMonth(ymd(new Date(t)))} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--sd-quiet)" }} minTickGap={32} />
          <YAxis width={44} domain={[lo, hi]} ticks={ticks} tickFormatter={(v: number) => `${v}%`} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--sd-quiet)" }} />
          <Tooltip
            content={({ active, payload }) => {
              const p = active ? (payload?.[0]?.payload as Row | undefined) : undefined;
              if (!p) return null;
              const f = (v?: number | null) => (v == null ? null : `${v.toFixed(1)}%`);
              return (
                <div className="rounded-lg bg-foreground px-3 py-2 text-[12px] text-background shadow-[var(--sd-shadow-3)]">
                  <div className="font-semibold">{dayMonth(ymd(new Date(p.t)))}</div>
                  {f(p.dm) && <div>Dry matter {f(p.dm)}</div>}
                  {both && f(p.micro) && <div>Microwave {f(p.micro)}</div>}
                  {both && f(p.machine) && <div>Machine {f(p.machine)}</div>}
                  {f(p.lab) && <div>Lab test {f(p.lab)}</div>}
                </div>
              );
            }}
          />
          <Legend verticalAlign="top" height={28} iconType="plainline" wrapperStyle={{ fontSize: 12 }} />
          {target != null && <ReferenceLine y={target} stroke="var(--sd-data-green)" strokeDasharray="5 4" label={{ value: `Export target ${target}%`, position: "insideTopLeft", fontSize: 11, fill: "var(--sd-data-green)" }} />}
          {max != null && <ReferenceLine y={max} stroke="var(--sd-data-red)" strokeDasharray="5 4" label={{ value: `Max ${max}%`, position: "insideBottomLeft", fontSize: 11, fill: "var(--sd-data-red)" }} />}
          <Line dataKey="dm" name={both ? "Average of both" : "Dry matter"} stroke={accent} strokeWidth={2.5} dot={{ r: 3.5 }} connectNulls isAnimationActive={false} />
          {both && <Line dataKey="micro" name="Microwave" stroke="var(--sd-data-amber)" strokeWidth={1.5} dot={{ r: 2.5 }} connectNulls isAnimationActive={false} />}
          {both && <Line dataKey="machine" name="Machine" stroke="var(--sd-data-indigo)" strokeWidth={1.5} dot={{ r: 2.5 }} connectNulls isAnimationActive={false} />}
          {!!lab?.length && <Line dataKey="lab" name="Lab test" stroke="none" dot={{ r: 4, fill: "var(--sd-card)", stroke: "var(--sd-quiet)", strokeWidth: 1.5 }} activeDot={false} isAnimationActive={false} />}
          <Line dataKey="proj" name="Projection" stroke="var(--sd-quiet)" strokeWidth={1.5} strokeDasharray="2 4" dot={false} connectNulls isAnimationActive={false} legendType="plainline" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

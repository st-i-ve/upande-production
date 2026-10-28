import { Area, AreaChart, Bar, BarChart, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { GroupTrendPoint, HarvestWeek, InspectionWeek } from "@/lib/apiary-api";
import { dayMonth, fmt } from "./ui";

const TICK = { fontSize: 11, fill: "var(--sd-quiet)" };

function Tip({ lines }: { lines: string[] }) {
  return (
    <div className="rounded-lg bg-foreground px-3 py-2 text-[12px] text-background shadow-[var(--sd-shadow-3)]">
      {lines.map((l, i) => (
        <div key={i} className={i === 0 ? "font-semibold" : undefined}>{l}</div>
      ))}
    </div>
  );
}

/** Per-group mite load over the inspections, with the treatment threshold. Small, no axes clutter. */
export function MiteChart({ points, threshold, accent, label }: { points: GroupTrendPoint[]; threshold: number; accent: string; label: string }) {
  const data = points.filter((p) => p.mites != null).map((p) => ({ ...p, label: dayMonth(p.date) }));
  if (data.length < 1) {
    return (
      <div className="flex h-[110px] items-center justify-center rounded-xl bg-[var(--sd-bg-soft)] text-[12px] text-[var(--sd-quiet)]">
        No mite counts to draw
      </div>
    );
  }
  const max = Math.max(threshold * 1.5, ...data.map((d) => d.mites as number)) + 0.5;
  return (
    <div className="h-[110px] w-full" role="img" aria-label={label} data-testid="hg-trend">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 6, right: 6, left: -22, bottom: 0 }}>
          <XAxis dataKey="label" tickLine={false} axisLine={false} tick={TICK} interval="preserveStartEnd" />
          <YAxis domain={[0, max]} tickLine={false} axisLine={false} tick={TICK} width={36} tickFormatter={(v) => String(Math.round(v * 10) / 10)} />
          <ReferenceLine y={threshold} stroke="var(--sd-data-red)" strokeDasharray="4 3" />
          <Tooltip content={({ active, payload }) => {
            const p = active ? (payload?.[0]?.payload as (GroupTrendPoint & { label: string }) | undefined) : undefined;
            return p ? <Tip lines={[p.label, `${fmt(p.mites, 1)} mites per 100 bees`, `${fmt(p.queenright_pct, 0)}% queenright`]} /> : null;
          }} />
          <Area type="monotone" dataKey="mites" stroke={accent} strokeWidth={2} fill={accent} fillOpacity={0.12} isAnimationActive={false} dot={{ r: 2.5 }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** All hive groups: average mites per week (line) with the threshold, and queenright share (bars). */
export function HealthTrendChart({ series, threshold, accent }: { series: InspectionWeek[]; threshold: number; accent: string }) {
  const data = series.map((s) => ({ ...s, label: dayMonth(s.week) }));
  return (
    <div className="px-3 pb-3" data-testid="health-trend">
      <div className="h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--sd-line-soft)" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={TICK} interval="preserveStartEnd" />
            <YAxis yAxisId="m" width={36} tickLine={false} axisLine={false} tick={TICK} domain={[0, (max: number) => Math.max(Math.ceil(max), threshold + 1)]} />
            <YAxis yAxisId="q" orientation="right" width={40} tickLine={false} axisLine={false} tick={TICK} domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
            <ReferenceLine yAxisId="m" y={threshold} stroke="var(--sd-data-red)" strokeDasharray="4 4" label={{ value: `limit ${threshold}`, position: "insideTopLeft", fontSize: 11, fill: "var(--sd-data-red)" }} />
            <Tooltip cursor={{ fill: "rgba(10,10,10,0.04)" }} content={({ active, payload }) => {
              const p = active ? (payload?.[0]?.payload as (InspectionWeek & { label: string }) | undefined) : undefined;
              return p ? <Tip lines={[`Week of ${p.label}`, `${p.inspections} inspections · ${p.colonies} colonies`, `${fmt(p.avg_mites, 1)} mites per 100 bees`, `${fmt(p.queenright_pct, 0)}% queenright`]} /> : null;
            }} />
            <Bar yAxisId="q" dataKey="queenright_pct" fill={accent} fillOpacity={0.22} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
            <Line yAxisId="m" type="monotone" dataKey="avg_mites" stroke="var(--sd-ink)" strokeWidth={2} dot={{ r: 3 }} connectNulls isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-3 pt-2 text-[12px] text-[var(--sd-muted)]">
        <span className="flex items-center gap-2"><i className="h-0 w-4 border-t-2 border-foreground" />Average mites per 100 bees</span>
        <span className="flex items-center gap-2"><i className="h-2.5 w-2.5 rounded-sm opacity-40" style={{ background: accent }} />Colonies queenright</span>
        <span className="flex items-center gap-2"><i className="h-0 w-4 border-t-2 border-dashed" style={{ borderColor: "var(--sd-data-red)" }} />Treatment limit</span>
      </div>
    </div>
  );
}

/** Honey kg per week as bars; weeks with no harvest stay as empty slots. */
export function HoneyChart({ series, accent }: { series: HarvestWeek[]; accent: string }) {
  const data = series.map((s) => ({ ...s, label: dayMonth(s.week) }));
  return (
    <div className="px-3 pb-3" data-testid="honey-chart">
      <div className="h-[260px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--sd-line-soft)" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={TICK} interval="preserveStartEnd" minTickGap={24} />
            <YAxis width={40} tickLine={false} axisLine={false} tick={TICK} allowDecimals={false} />
            <Tooltip cursor={{ fill: "rgba(10,10,10,0.04)" }} content={({ active, payload }) => {
              const p = active ? (payload?.[0]?.payload as (HarvestWeek & { label: string }) | undefined) : undefined;
              return p ? <Tip lines={[`Week of ${p.label}`, `${fmt(p.kg, 1)} kg honey`, p.avg_moisture != null ? `${fmt(p.avg_moisture, 1)}% moisture` : "no moisture reading", p.grade_a_pct != null ? `${fmt(p.grade_a_pct, 0)}% grade A` : ""].filter(Boolean)} /> : null;
            }} />
            <Bar dataKey="kg" fill={accent} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** Moisture per week against the 20% ceiling honey must stay under to keep. */
export function MoistureChart({ series, limit, accent }: { series: HarvestWeek[]; limit: number; accent: string }) {
  const data = series.filter((s) => s.avg_moisture != null).map((s) => ({ ...s, label: dayMonth(s.week) }));
  if (!data.length) return null;
  return (
    <div className="px-3 pb-3" data-testid="moisture-chart">
      <div className="h-[200px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="var(--sd-line-soft)" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={TICK} interval="preserveStartEnd" />
            <YAxis width={40} tickLine={false} axisLine={false} tick={TICK} domain={[14, (m: number) => Math.max(Math.ceil(m), limit + 1)]} tickFormatter={(v) => `${v}%`} />
            <ReferenceLine y={limit} stroke="var(--sd-data-red)" strokeDasharray="4 4" label={{ value: `${limit}% limit`, position: "insideTopRight", fontSize: 11, fill: "var(--sd-data-red)" }} />
            <Tooltip content={({ active, payload }) => {
              const p = active ? (payload?.[0]?.payload as (HarvestWeek & { label: string }) | undefined) : undefined;
              return p ? <Tip lines={[`Week of ${p.label}`, `${fmt(p.avg_moisture, 1)}% moisture`]} /> : null;
            }} />
            <Area type="monotone" dataKey="avg_moisture" stroke={accent} strokeWidth={2} fill={accent} fillOpacity={0.12} dot={{ r: 3 }} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

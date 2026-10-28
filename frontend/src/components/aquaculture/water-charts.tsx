import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Bands, WaterPond } from "@/lib/aquaculture-api";
import { dayMonth, dayTime } from "./format";
import { AXIS, TipBox } from "./ui";

export const POND_COLORS = ["#2b6f9e", "#c2792b", "#5b8f3a", "#8a5aa8", "#b5483f", "#3b9aa0"];

type Metric = "dissolved_oxygen_mg_l" | "temperature_c";
const ms = (at: string) => new Date(at.replace(" ", "T")).getTime();

/** One row per timestamp with a column per pond, for a multi-line chart. */
export function pivot(ponds: WaterPond[], metric: Metric) {
  const rows = new Map<number, Record<string, number>>();
  for (const p of ponds)
    for (const s of p.series) {
      const v = s[metric];
      if (v == null) continue;
      const t = ms(s.at);
      rows.set(t, { ...(rows.get(t) ?? { t }), [p.unit]: v });
    }
  return [...rows.values()].sort((a, b) => a.t - b.t);
}

function WaterLines({
  ponds, metric, bands, unit, label, height = 220,
}: { ponds: WaterPond[]; metric: Metric; bands: Bands; unit: string; label: string; height?: number }) {
  const rows = pivot(ponds, metric);
  const isDo = metric === "dissolved_oxygen_mg_l";
  const lo = isDo ? bands.do_min : bands.temp_min;
  const hi = isDo ? undefined : bands.temp_max;
  if (!rows.length) {
    return (
      <div className="flex items-center justify-center rounded-xl bg-[var(--sd-bg-soft)] text-[12px] text-[var(--sd-quiet)]" style={{ height }}>
        No readings in this period
      </div>
    );
  }
  return (
    <div style={{ height }} data-testid={isDo ? "do-chart" : "temp-chart"} role="img" aria-label={label}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--sd-line-soft)" vertical={false} />
          <XAxis type="number" dataKey="t" scale="time" domain={["dataMin", "dataMax"]} tickLine={false} axisLine={false} tick={AXIS}
            tickFormatter={(t: number) => dayMonth(new Date(t).toISOString())} minTickGap={32} />
          <YAxis width={36} tickLine={false} axisLine={false} tick={AXIS} unit={unit}
            domain={isDo ? [0, (m: number) => Math.max(10, Math.ceil(m))] : [(m: number) => Math.min(22, Math.floor(m)), (m: number) => Math.max(32, Math.ceil(m))]} />
          {isDo ? (
            <ReferenceArea y1={0} y2={lo} fill="var(--sd-data-red)" fillOpacity={0.08} />
          ) : (
            <ReferenceArea y1={lo} y2={hi} fill="var(--sd-data-green)" fillOpacity={0.1} />
          )}
          <ReferenceLine y={lo} stroke={isDo ? "var(--sd-data-red)" : "var(--sd-quiet)"} strokeDasharray="4 3" label={{ value: isDo ? `min ${lo}` : `${lo}`, position: "insideBottomLeft", fontSize: 10, fill: "var(--sd-quiet)" }} />
          {hi != null && <ReferenceLine y={hi} stroke="var(--sd-quiet)" strokeDasharray="4 3" label={{ value: `${hi}`, position: "insideTopLeft", fontSize: 10, fill: "var(--sd-quiet)" }} />}
          <Tooltip
            cursor={{ stroke: "var(--sd-line)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const t = (payload[0].payload as { t: number }).t;
              const at = new Date(t - new Date(t).getTimezoneOffset() * 60000).toISOString().slice(0, 16).replace("T", " ");
              return <TipBox title={dayTime(at)} rows={payload.map((p) => [ponds.find((x) => x.unit === p.dataKey)?.label ?? String(p.dataKey), `${p.value}${unit}`])} />;
            }}
          />
          {ponds.map((p, i) => (
            <Line key={p.unit} dataKey={p.unit} name={p.label} stroke={POND_COLORS[i % POND_COLORS.length]} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export const DoChart = (p: { ponds: WaterPond[]; bands: Bands }) => (
  <WaterLines {...p} metric="dissolved_oxygen_mg_l" unit="" label="Dissolved oxygen in mg/L by pond, with the minimum safe level shaded" />
);
export const TempChart = (p: { ponds: WaterPond[]; bands: Bands }) => (
  <WaterLines {...p} metric="temperature_c" unit="°" label="Water temperature by pond, with the safe band shaded" />
);

export function PondLegend({ ponds }: { ponds: WaterPond[] }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 px-5 pb-2 text-[12px] text-[var(--sd-muted)]">
      {ponds.map((p, i) => (
        <span key={p.unit} className="inline-flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full" style={{ background: POND_COLORS[i % POND_COLORS.length] }} />
          {p.label}
        </span>
      ))}
    </div>
  );
}

/** Small DO trace for a pond card. */
export function MiniDo({ pond, bands, color }: { pond: WaterPond; bands: Bands; color: string }) {
  const rows = pond.series.filter((s) => s.dissolved_oxygen_mg_l != null).map((s) => ({ t: ms(s.at), v: s.dissolved_oxygen_mg_l as number }));
  if (rows.length < 2) return <div className="flex h-[70px] items-center justify-center rounded-xl bg-[var(--sd-bg-soft)] text-[12px] text-[var(--sd-quiet)]">Not enough readings</div>;
  return (
    <div className="h-[70px]" data-testid="mini-do" role="img" aria-label={`Dissolved oxygen trend for ${pond.label}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 4, right: 4, left: 4, bottom: 0 }}>
          <YAxis hide domain={[0, (m: number) => Math.max(10, Math.ceil(m))]} />
          <XAxis hide type="number" dataKey="t" domain={["dataMin", "dataMax"]} />
          <ReferenceArea y1={0} y2={bands.do_min} fill="var(--sd-data-red)" fillOpacity={0.1} />
          <Line dataKey="v" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

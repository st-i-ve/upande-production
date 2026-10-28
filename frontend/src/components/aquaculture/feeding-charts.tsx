import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DailyFeedMortality, FeedingMortalityPage } from "@/lib/aquaculture-api";
import { dayMonth, fmtKg, fmtNum } from "./format";
import { AXIS, TipBox } from "./ui";

export const CAUSE_COLOR: Record<string, string> = {
  "Low DO": "#b5483f",
  Disease: "#8a5aa8",
  Predation: "#c2792b",
  Handling: "#3b9aa0",
  Unknown: "#a8a69c",
};

/** Feed (bars, kg) against mortality (line, fish) by day: a spike in deaths after a feed drop is the pattern to look for. */
export function FeedMortalityChart({ daily, accent }: { daily: DailyFeedMortality[]; accent: string }) {
  return (
    <div className="h-[260px]" data-testid="feed-mortality-chart" role="img" aria-label="Daily feed in kilograms and fish deaths">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={daily} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--sd-line-soft)" vertical={false} />
          <XAxis dataKey="date" tickLine={false} axisLine={false} tick={AXIS} tickFormatter={dayMonth} minTickGap={28} />
          <YAxis yAxisId="feed" width={40} tickLine={false} axisLine={false} tick={AXIS} unit=" kg" />
          <YAxis yAxisId="dead" orientation="right" width={34} tickLine={false} axisLine={false} tick={AXIS} allowDecimals={false} />
          <Tooltip
            cursor={{ fill: "rgba(10,10,10,0.04)" }}
            content={({ active, payload }) => {
              const r = active ? (payload?.[0]?.payload as DailyFeedMortality | undefined) : undefined;
              return r ? <TipBox title={dayMonth(r.date)} rows={[["Fed", fmtKg(r.feed_kg)], ["Died", fmtNum(r.dead)]]} /> : null;
            }}
          />
          <Bar yAxisId="feed" dataKey="feed_kg" fill={accent} fillOpacity={0.85} radius={[3, 3, 0, 0]} isAnimationActive={false} />
          <Line yAxisId="dead" dataKey="dead" stroke="var(--sd-data-red)" strokeWidth={2} dot={{ r: 2.5, fill: "var(--sd-data-red)" }} isAnimationActive={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CausesChart({ causes }: { causes: FeedingMortalityPage["causes"] }) {
  return (
    <div className="h-[200px]" data-testid="causes-chart" role="img" aria-label="Deaths by cause">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={causes} layout="vertical" margin={{ top: 4, right: 24, left: 8, bottom: 0 }}>
          <XAxis type="number" hide />
          <YAxis type="category" dataKey="cause" width={70} tickLine={false} axisLine={false} tick={AXIS} />
          <Tooltip cursor={{ fill: "rgba(10,10,10,0.04)" }} formatter={(v: number) => [fmtNum(v), "Fish"]} />
          <Bar dataKey="count" radius={[0, 4, 4, 0]} isAnimationActive={false} label={{ position: "right", fontSize: 11, fill: "var(--sd-muted)" }}>
            {causes.map((c) => <Cell key={c.cause} fill={CAUSE_COLOR[c.cause] ?? "#a8a69c"} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

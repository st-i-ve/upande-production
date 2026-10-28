import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PondBatch } from "@/lib/aquaculture-api";
import { dayMonth, fmtGrams } from "./format";
import { AXIS, TipBox } from "./ui";

interface Row {
  days: number;
  date?: string;
  w?: number;
  proj?: number;
}

export function growthRows(b: Pick<PondBatch, "growth_curve" | "days_to_target" | "target_weight_g" | "status">): Row[] {
  const rows: Row[] = b.growth_curve.map((p) => ({ days: p.days, date: p.date, w: p.avg_weight_g }));
  const last = rows[rows.length - 1];
  if (last && b.status === "Growing" && b.days_to_target && b.target_weight_g) {
    last.proj = last.w;
    rows.push({ days: last.days + b.days_to_target, proj: b.target_weight_g });
  }
  return rows;
}

/** Average weight against days in water, with the target weight line and the projected finish. */
export function GrowthChart({ b, accent, height = 150 }: { b: PondBatch; accent: string; height?: number }) {
  const rows = growthRows(b);
  if (rows.length < 2) {
    return (
      <div className="flex items-center justify-center rounded-xl bg-[var(--sd-bg-soft)] text-[12px] text-[var(--sd-quiet)]" style={{ height }}>
        No samples yet
      </div>
    );
  }
  return (
    <div style={{ height }} data-testid="growth-chart" role="img" aria-label={`Growth of ${b.pond_name}: average weight against days in water`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="var(--sd-line-soft)" vertical={false} />
          <XAxis type="number" dataKey="days" domain={[0, "dataMax"]} tickLine={false} axisLine={false} tick={AXIS} unit=" d" />
          <YAxis width={40} tickLine={false} axisLine={false} tick={AXIS} domain={[0, (m: number) => Math.ceil(Math.max(m, b.target_weight_g ?? 0) / 50) * 50]} unit=" g" />
          {b.target_weight_g && (
            <ReferenceLine y={b.target_weight_g} stroke="var(--sd-target)" strokeDasharray="4 3" label={{ value: `target ${b.target_weight_g} g`, position: "insideBottomRight", fontSize: 10, fill: "var(--sd-target)" }} />
          )}
          <Tooltip
            cursor={{ stroke: "var(--sd-line)" }}
            content={({ active, payload }) => {
              const r = active ? (payload?.[0]?.payload as Row | undefined) : undefined;
              if (!r) return null;
              return <TipBox title={r.date ? dayMonth(r.date) : "Projected finish"} rows={[["Day", String(r.days)], [r.w != null ? "Average" : "Projected", fmtGrams(r.w ?? r.proj)]]} />;
            }}
          />
          <Line dataKey="proj" stroke={accent} strokeDasharray="5 4" strokeWidth={2} dot={false} isAnimationActive={false} connectNulls />
          <Line dataKey="w" stroke={accent} strokeWidth={2.5} dot={{ r: 3, fill: accent }} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

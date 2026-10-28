import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PlanWeek } from "@/lib/avocado-api";
import { dayMonth, fmtKgTonnes, fmtNum } from "./calendar-format";

export const STATUS_COLOR = {
  short: "var(--sd-data-red)",
  spare: "",
  no_crew: "#b9b5a8",
} as const;

export function weekColor(w: PlanWeek, accent: string) {
  return w.status === "short" ? STATUS_COLOR.short : w.status === "spare" ? accent : STATUS_COLOR.no_crew;
}

export function statusText(w: PlanWeek): string {
  if (w.status === "short") return `${fmtNum(w.people_short)} short`;
  if (w.status === "spare") return `${fmtNum(w.people_spare)} spare`;
  return "no crew set";
}

export function PickingChart({
  weeks,
  crew,
  selected,
  onSelect,
  accent,
}: {
  weeks: PlanWeek[];
  crew: number;
  selected: string | null;
  onSelect: (week: string) => void;
  accent: string;
}) {
  const rows = weeks.map((w) => ({ ...w, label: dayMonth(w.week) }));
  return (
    <div className="px-3 pb-3" data-testid="picking-chart">
      <div className="h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 12, right: 24, left: 0, bottom: 0 }} onClick={(s) => s?.activeLabel && onSelect(rows.find((r) => r.label === s.activeLabel)?.week ?? "")}>
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--sd-quiet)" }} interval="preserveStartEnd" />
            <YAxis width={36} domain={[0, (max: number) => Math.max(Math.ceil(max), crew)]} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--sd-quiet)" }} allowDecimals={false} />
            <Tooltip
              cursor={{ fill: "rgba(10,10,10,0.04)" }}
              content={({ active, payload }) => {
                const w = active ? (payload?.[0]?.payload as PlanWeek | undefined) : undefined;
                if (!w) return null;
                return (
                  <div className="rounded-lg bg-foreground px-3 py-2 text-[12px] text-background shadow-[var(--sd-shadow-3)]">
                    <div className="font-semibold">Week of {dayMonth(w.week)}</div>
                    <div>{fmtNum(w.pickers_needed)} pickers needed · {fmtNum(w.crew_available)} available</div>
                    <div>{fmtKgTonnes(w.kg)} · {fmtNum(w.crates)} crates</div>
                    <div className="opacity-80">{statusText(w)}</div>
                  </div>
                );
              }}
            />
            {crew > 0 && (
              <ReferenceLine
                y={crew}
                stroke="var(--sd-ink)"
                strokeDasharray="4 4"
                label={{ value: `${fmtNum(crew)} available`, position: "insideTopRight", fontSize: 11, fill: "var(--sd-ink)" }}
              />
            )}
            <Bar dataKey="pickers_needed" radius={[4, 4, 0, 0]} cursor="pointer" maxBarSize={36} isAnimationActive={false}>
              {rows.map((w) => (
                <Cell key={w.week} fill={weekColor(w, accent)} stroke={selected === w.week ? "var(--sd-ink)" : "none"} strokeWidth={2} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 px-3 pt-2 text-[12px] text-[var(--sd-muted)]">
        <span className="flex items-center gap-2"><i className="h-2.5 w-2.5 rounded-sm" style={{ background: accent }} />Covered (selected week outlined)</span>
        <span className="flex items-center gap-2"><i className="h-2.5 w-2.5 rounded-sm" style={{ background: STATUS_COLOR.short }} />Short of pickers</span>
        <span className="flex items-center gap-2"><i className="h-2.5 w-2.5 rounded-sm" style={{ background: STATUS_COLOR.no_crew }} />No crew set</span>
        <span className="flex items-center gap-2"><i className="h-0 w-4 border-t-2 border-dashed border-foreground" />Crew available</span>
      </div>
    </div>
  );
}

import type { GradingPage } from "@/lib/fv-api";
import { dayMonth, fmtNum } from "./fv-format";

const W = 640;
const H = 180;
const PAD = { l: 8, r: 8, t: 12, b: 24 };

/** Weekly kg graded as bars, with the class 1 share as a line over them. */
export function GradeTrend({ series, accent }: { series: GradingPage["series"]; accent: string }) {
  const max = Math.max(...series.map((s) => s.graded_kg), 1);
  const bw = (W - PAD.l - PAD.r) / Math.max(series.length, 1);
  const y = (v: number) => PAD.t + (1 - v / 100) * (H - PAD.t - PAD.b);
  const line = series
    .map((s, i) => `${i ? "L" : "M"}${PAD.l + bw * i + bw / 2},${y(s.class1_pct)}`)
    .join(" ");
  return (
    <div className="px-5 pb-5" data-testid="grade-trend">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Weekly kg graded and class 1 share">
        {series.map((s, i) => {
          const h = (s.graded_kg / max) * (H - PAD.t - PAD.b);
          return (
            <g key={s.week}>
              <rect x={PAD.l + bw * i + bw * 0.18} y={H - PAD.b - h} width={bw * 0.64} height={h} rx={4} fill={accent} opacity={0.28}>
                <title>{`Week of ${dayMonth(s.week)}: ${fmtNum(s.graded_kg)} kg graded, ${fmtNum(s.class1_pct, 0)}% class 1, ${fmtNum(s.reject_pct, 1)}% rejects`}</title>
              </rect>
              <text x={PAD.l + bw * i + bw / 2} y={H - 6} textAnchor="middle" fontSize={11} fill="var(--sd-quiet)">
                {dayMonth(s.week)}
              </text>
            </g>
          );
        })}
        <path d={line} fill="none" stroke={accent} strokeWidth={2} />
        {series.map((s, i) => (
          <circle key={s.week} cx={PAD.l + bw * i + bw / 2} cy={y(s.class1_pct)} r={3} fill={accent} />
        ))}
      </svg>
      <p className="mt-1 text-[12px] text-[var(--sd-quiet)]">Bars are kg graded each week; the line is the class 1 share (0 to 100%).</p>
    </div>
  );
}

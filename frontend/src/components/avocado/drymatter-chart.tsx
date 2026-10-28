import type { DryMatterBlock } from "@/lib/avocado-api";
import { dayMonth } from "./calendar-format";

const W = 300;
const H = 110;
const PAD = { l: 28, r: 8, t: 8, b: 18 };

const t = (d: string) => new Date(`${d}T00:00:00`).getTime();

/** Dry matter readings over time against the export floor. Inline SVG; one per block card. */
export function TrendChart({
  points,
  minimum,
  accent,
  label,
}: {
  points: DryMatterBlock["trend"];
  minimum: number;
  accent: string;
  label: string;
}) {
  if (!points.length) {
    return (
      <div className="flex h-[110px] items-center justify-center rounded-xl bg-[var(--sd-bg-soft)] text-[12px] text-[var(--sd-quiet)]">
        No readings to draw
      </div>
    );
  }
  const ys = points.map((p) => p.dry_matter_pct);
  const lo = Math.floor(Math.min(...ys, minimum) - 2);
  const hi = Math.ceil(Math.max(...ys, minimum) + 2);
  const t0 = t(points[0].date);
  const t1 = t(points[points.length - 1].date);
  const x = (d: string) =>
    PAD.l + (t1 === t0 ? (W - PAD.l - PAD.r) / 2 : ((t(d) - t0) / (t1 - t0)) * (W - PAD.l - PAD.r));
  const y = (v: number) => PAD.t + (1 - (v - lo) / (hi - lo)) * (H - PAD.t - PAD.b);
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(p.date).toFixed(1)},${y(p.dry_matter_pct).toFixed(1)}`).join(" ");
  const fy = y(minimum);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={label} className="h-[110px] w-full" data-testid="dm-trend">
      <rect x={PAD.l} y={fy} width={W - PAD.l - PAD.r} height={H - PAD.b - fy} fill="var(--sd-data-red)" opacity="0.06" />
      <line x1={PAD.l} x2={W - PAD.r} y1={fy} y2={fy} stroke="var(--sd-data-red)" strokeDasharray="4 3" strokeWidth="1" />
      <text x={PAD.l - 4} y={fy + 3} textAnchor="end" fontSize="9" fill="var(--sd-data-red)">{minimum}%</text>
      <text x={PAD.l - 4} y={PAD.t + 6} textAnchor="end" fontSize="9" fill="var(--sd-quiet)">{hi}</text>
      <text x={PAD.l - 4} y={H - PAD.b} textAnchor="end" fontSize="9" fill="var(--sd-quiet)">{lo}</text>
      {points.length > 1 && <path d={line} fill="none" stroke={accent} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />}
      {points.map((p) => (
        <circle key={p.date + p.dry_matter_pct} cx={x(p.date)} cy={y(p.dry_matter_pct)} r="3" fill={p.measured_on === "block" ? accent : "var(--sd-card)"} stroke={accent} strokeWidth="1.5">
          <title>{`${dayMonth(p.date)} · ${p.dry_matter_pct.toFixed(1)}% dry matter${p.measured_on === "cohort" || p.measured_on === "area" ? " (planting area)" : ""}`}</title>
        </circle>
      ))}
      <text x={PAD.l} y={H - 4} fontSize="9" fill="var(--sd-quiet)">{dayMonth(points[0].date)}</text>
      {points.length > 1 && (
        <text x={W - PAD.r} y={H - 4} textAnchor="end" fontSize="9" fill="var(--sd-quiet)">{dayMonth(points[points.length - 1].date)}</text>
      )}
    </svg>
  );
}

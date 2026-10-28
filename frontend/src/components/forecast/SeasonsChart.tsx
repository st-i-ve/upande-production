import { qty } from "@/lib/format";
import { SERIES, compact, niceTicks, useWidth } from "./chart-utils";

export const SEASONS_CHART_HEIGHT = 220;
const PAD = { top: 22, right: 16, bottom: 44, left: 62 };

/** One bar per year of harvested quantity. */
export function SeasonsChart({ seasons, uom }: { seasons: Array<{ year: number; actual: number }>; uom: string }) {
  const [ref, width] = useWidth(280, 520);
  if (!seasons.length) {
    return (
      <div className="flex h-[160px] items-center justify-center rounded-[var(--sd-radius-lg)] border border-dashed border-[var(--sd-line)] text-[13px] text-[var(--sd-quiet)]">
        No harvests recorded yet.
      </div>
    );
  }
  const plotW = Math.max(1, width - PAD.left - PAD.right);
  const plotH = SEASONS_CHART_HEIGHT - PAD.top - PAD.bottom;
  const ticks = niceTicks(0, Math.max(1, ...seasons.map((s) => s.actual)), 4);
  const top = ticks[ticks.length - 1] || 1;
  const band = plotW / seasons.length;
  const barW = Math.min(56, band * 0.6);
  const y = (v: number) => PAD.top + plotH - (v / top) * plotH;

  return (
    <div ref={ref} className="w-full overflow-x-auto">
      <svg
        width={width}
        height={SEASONS_CHART_HEIGHT}
        viewBox={`0 0 ${width} ${SEASONS_CHART_HEIGHT}`}
        role="img"
        aria-label={`Harvest ${uom} per season`}
        className="block"
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD.left} x2={PAD.left + plotW} y1={y(t)} y2={y(t)} stroke="var(--sd-line)" strokeWidth={1} />
            <text x={PAD.left - 8} y={y(t) + 4} textAnchor="end" className="fill-[var(--sd-quiet)] text-[11px] tabular-nums">
              {compact(t)}
            </text>
          </g>
        ))}
        {seasons.map((s, i) => {
          const cx = PAD.left + band * (i + 0.5);
          return (
            <g key={s.year}>
              <title>{`${s.year}: ${qty(s.actual)} ${uom}`}</title>
              <rect x={cx - barW / 2} y={y(s.actual)} width={barW} height={Math.max(0, y(0) - y(s.actual))} rx={3} fill={SERIES.actual} opacity={0.85} />
              <text x={cx} y={y(s.actual) - 5} textAnchor="middle" className="fill-[var(--sd-muted)] text-[10.5px] tabular-nums">
                {compact(s.actual)}
              </text>
              <text x={cx} y={y(0) + 16} textAnchor="middle" className="fill-[var(--sd-quiet)] text-[11px] tabular-nums">
                {s.year}
              </text>
            </g>
          );
        })}
        <line x1={PAD.left} x2={PAD.left + plotW} y1={y(0)} y2={y(0)} stroke="var(--sd-muted)" strokeWidth={1} />
        <text x={14} y={PAD.top + plotH / 2} textAnchor="middle" transform={`rotate(-90 14 ${PAD.top + plotH / 2})`} className="fill-[var(--sd-muted)] text-[11px] font-medium">
          {uom || "Quantity"}
        </text>
        <text x={PAD.left + plotW / 2} y={SEASONS_CHART_HEIGHT - 6} textAnchor="middle" className="fill-[var(--sd-muted)] text-[11px] font-medium">
          Season (year)
        </text>
      </svg>
    </div>
  );
}

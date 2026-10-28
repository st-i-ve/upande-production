import type { BlockCostRow } from "@/lib/api";
import { kes } from "@/lib/format";
import { SERIES, clip, compact, niceTicks, useWidth } from "@/components/forecast/chart-utils";

const ROW_H = 26;
const PAD = { top: 12, right: 24, bottom: 52, left: 130 };

/**
 * Margin per leaf block, as horizontal bars out from a zero line: green to the
 * right where the block earned more than it cost, red to the left where it did
 * not. Plain SVG, like the other charts.
 */
export function MarginChart({ rows }: { rows: BlockCostRow[] }) {
  const [ref, width] = useWidth();
  const data = rows
    .filter((r) => !r.is_group && r.margin != null)
    .map((r) => ({ unit: r.unit, margin: r.margin as number, revenue: r.revenue, total: r.total_cost }))
    .sort((a, b) => b.margin - a.margin);

  if (!data.length) {
    return (
      <div className="flex h-[160px] items-center justify-center rounded-[var(--sd-radius-lg)] border border-dashed border-[var(--sd-line)] text-[13px] text-[var(--sd-quiet)]">
        No block margins to draw for this period.
      </div>
    );
  }

  const height = PAD.top + PAD.bottom + data.length * ROW_H;
  const plotW = Math.max(1, width - PAD.left - PAD.right);
  const lo = Math.min(0, ...data.map((d) => d.margin));
  const hi = Math.max(0, ...data.map((d) => d.margin));
  const ticks = niceTicks(lo, hi, 5);
  const min = Math.min(lo, ticks[0]);
  const max = Math.max(hi, ticks[ticks.length - 1]);
  const x = (v: number) => PAD.left + ((v - min) / (max - min || 1)) * plotW;
  const plotBottom = PAD.top + data.length * ROW_H;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-4 text-[11.5px] text-[var(--sd-muted)]">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: SERIES.positive }} />
          Profit
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: SERIES.negative }} />
          Loss
        </span>
      </div>
      <div ref={ref} className="w-full overflow-x-auto">
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Margin in Kenyan shillings for ${data.length} blocks`}
          className="block"
        >
          {ticks.map((t) => (
            <g key={t}>
              <line x1={x(t)} x2={x(t)} y1={PAD.top} y2={plotBottom} stroke="var(--sd-line)" strokeWidth={1} />
              <text x={x(t)} y={plotBottom + 16} textAnchor="middle" className="fill-[var(--sd-quiet)] text-[11px] tabular-nums">
                {compact(t)}
              </text>
            </g>
          ))}
          <line x1={x(0)} x2={x(0)} y1={PAD.top} y2={plotBottom} stroke="var(--sd-muted)" strokeWidth={1.25} />
          {data.map((d, i) => {
            const y = PAD.top + i * ROW_H;
            const neg = d.margin < 0;
            const x0 = x(0);
            const x1 = x(d.margin);
            return (
              <g key={d.unit} data-testid={`bar-${d.unit}`} data-negative={neg ? "true" : undefined}>
                <title>{`${d.unit}: margin ${kes(d.margin)} (revenue ${kes(d.revenue)}, cost ${kes(d.total)})`}</title>
                <text x={PAD.left - 10} y={y + ROW_H / 2 + 4} textAnchor="end" className="fill-[var(--sd-muted)] text-[11.5px]">
                  {clip(d.unit, 20)}
                </text>
                <rect
                  x={Math.min(x0, x1)}
                  y={y + 4}
                  width={Math.max(1, Math.abs(x1 - x0))}
                  height={ROW_H - 8}
                  rx={3}
                  fill={neg ? SERIES.negative : SERIES.positive}
                />
              </g>
            );
          })}
          <text x={PAD.left + plotW / 2} y={height - 6} textAnchor="middle" className="fill-[var(--sd-muted)] text-[11px] font-medium">
            Margin (KES)
          </text>
        </svg>
      </div>
    </div>
  );
}

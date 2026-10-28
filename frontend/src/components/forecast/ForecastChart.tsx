import type { ForecastWeek } from "@/lib/api";
import { qty, shortDate } from "@/lib/format";
import { SERIES, compact, niceTicks, useWidth } from "./chart-utils";

export const FORECAST_CHART_HEIGHT = 320;
const PAD = { top: 16, right: 20, bottom: 58, left: 62 };

function addDays(ymd: string, n: number): string {
  const [y, m, d] = ymd.split("-").map(Number);
  const dt = new Date(y, m - 1, d + n);
  const p = (v: number) => String(v).padStart(2, "0");
  return `${dt.getFullYear()}-${p(dt.getMonth() + 1)}-${p(dt.getDate())}`;
}

/**
 * Weekly forecast (line) against what was harvested (bars) and what buyers
 * have committed to (dashed line), with a marker for today.
 */
export function ForecastChart({
  weeks,
  uom,
  today,
}: {
  weeks: ForecastWeek[];
  uom: string;
  today: string;
}) {
  const [ref, width] = useWidth();
  if (!weeks.length) {
    return (
      <div className="flex h-[220px] items-center justify-center rounded-[var(--sd-radius-lg)] border border-dashed border-[var(--sd-line)] text-[13px] text-[var(--sd-quiet)]">
        No weekly forecast for this period.
      </div>
    );
  }

  const plotW = Math.max(1, width - PAD.left - PAD.right);
  const plotH = FORECAST_CHART_HEIGHT - PAD.top - PAD.bottom;
  const n = weeks.length;
  const band = plotW / n;
  const peak = Math.max(1, ...weeks.flatMap((w) => [w.forecast, w.actual, w.committed]));
  const ticks = niceTicks(0, peak, 5);
  const top = ticks[ticks.length - 1] || peak;
  const cx = (i: number) => PAD.left + band * (i + 0.5);
  const y = (v: number) => PAD.top + plotH - (v / top) * plotH;
  const barW = Math.min(36, band * 0.6);

  const line = (pick: (w: ForecastWeek) => number) =>
    weeks.map((w, i) => `${i ? "L" : "M"}${cx(i)},${y(pick(w))}`).join(" ");

  const todayIdx = weeks.findIndex((w) => w.week_start <= today && today <= addDays(w.week_start, 6));
  const labelEvery = Math.max(1, Math.ceil(n / Math.max(1, Math.floor(plotW / 44))));

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[11.5px] text-[var(--sd-muted)]">
        <span className="inline-flex items-center gap-1.5">
          <span className="h-0.5 w-5 rounded" style={{ background: SERIES.forecast }} />
          Forecast
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: SERIES.actual }} />
          Actual
        </span>
        <span className="inline-flex items-center gap-1.5">
          <svg width="20" height="4" aria-hidden>
            <line x1="0" x2="20" y1="2" y2="2" stroke={SERIES.committed} strokeWidth="2" strokeDasharray="4 3" />
          </svg>
          Committed to buyers
        </span>
        {todayIdx >= 0 && (
          <span className="inline-flex items-center gap-1.5">
            <svg width="4" height="12" aria-hidden>
              <line x1="2" x2="2" y1="0" y2="12" stroke="var(--sd-ink)" strokeWidth="1.5" strokeDasharray="2 2" />
            </svg>
            Today
          </span>
        )}
      </div>
      <div ref={ref} className="w-full overflow-x-auto">
        <svg
          width={width}
          height={FORECAST_CHART_HEIGHT}
          viewBox={`0 0 ${width} ${FORECAST_CHART_HEIGHT}`}
          role="img"
          aria-label={`Weekly forecast, actual and committed ${uom} across ${n} weeks`}
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

          {weeks.map((w, i) => (
            <rect
              key={`b${w.week_start}`}
              x={cx(i) - barW / 2}
              y={y(w.actual)}
              width={barW}
              height={Math.max(0, y(0) - y(w.actual))}
              rx={2}
              fill={SERIES.actual}
              opacity={0.85}
            />
          ))}

          <path d={line((w) => w.committed)} fill="none" stroke={SERIES.committed} strokeWidth={2} strokeDasharray="6 4" strokeLinejoin="round" />
          <path d={line((w) => w.forecast)} fill="none" stroke={SERIES.forecast} strokeWidth={2.25} strokeLinejoin="round" strokeLinecap="round" />
          {weeks.map((w, i) => (
            <circle key={`p${w.week_start}`} cx={cx(i)} cy={y(w.forecast)} r={2.75} fill="var(--sd-card)" stroke={SERIES.forecast} strokeWidth={1.75} />
          ))}

          {todayIdx >= 0 && (
            <g data-testid="today-marker">
              <line x1={cx(todayIdx)} x2={cx(todayIdx)} y1={PAD.top} y2={y(0)} stroke="var(--sd-ink)" strokeWidth={1.25} strokeDasharray="3 3" />
              <text x={cx(todayIdx)} y={PAD.top - 4} textAnchor="middle" className="fill-[var(--sd-ink)] text-[10.5px] font-medium">
                Today
              </text>
            </g>
          )}

          <line x1={PAD.left} x2={PAD.left + plotW} y1={y(0)} y2={y(0)} stroke="var(--sd-muted)" strokeWidth={1} />

          {weeks.map((w, i) => (
            <g key={`x${w.week_start}`}>
              {i % labelEvery === 0 && (
                <>
                  <text x={cx(i)} y={y(0) + 16} textAnchor="middle" className="fill-[var(--sd-quiet)] text-[11px] tabular-nums">
                    W{String(w.iso_week).padStart(2, "0")}
                  </text>
                  <text x={cx(i)} y={y(0) + 29} textAnchor="middle" className="fill-[var(--sd-quiet)] text-[10px]">
                    {shortDate(w.week_start).replace(/ \d{4}$/, "")}
                  </text>
                </>
              )}
              {/* A full-height hit area per week so the tooltip is easy to reach. */}
              <rect x={cx(i) - band / 2} y={PAD.top} width={band} height={plotH} fill="transparent">
                <title>
                  {`Week ${w.iso_week}, ${w.iso_year} (from ${shortDate(w.week_start)})\nForecast: ${qty(w.forecast)} ${uom}\nActual: ${qty(w.actual)} ${uom}\nCommitted: ${qty(w.committed)} ${uom}${
                    w.error_pct == null ? "" : `\nError: ${w.error_pct > 0 ? "+" : ""}${w.error_pct.toFixed(1)}%`
                  }`}
                </title>
              </rect>
            </g>
          ))}

          <text x={14} y={PAD.top + plotH / 2} textAnchor="middle" transform={`rotate(-90 14 ${PAD.top + plotH / 2})`} className="fill-[var(--sd-muted)] text-[11px] font-medium">
            {uom || "Quantity"}
          </text>
          <text x={PAD.left + plotW / 2} y={FORECAST_CHART_HEIGHT - 6} textAnchor="middle" className="fill-[var(--sd-muted)] text-[11px] font-medium">
            ISO week (week starting)
          </text>
        </svg>
      </div>
    </div>
  );
}

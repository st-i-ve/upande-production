import { useMemo, useState } from "react";
import { compact, niceTicks, useWidth } from "@/components/forecast/chart-utils";
import { TogglePill } from "@/components/TogglePill";
import type { SeasonOutlook, TimelineWeek } from "@/lib/avocado-api";
import { qty } from "@/lib/format";
import { ACCENT, EmptyNote, Legend, SectionCard, dayMonth, tonnes } from "./forecast-ui";

export const TIMELINE_HEIGHT = 240;
const PAD = { top: 52, right: 14, bottom: 30, left: 46 };
/** Weeks of empty lead-in kept before the first forecast week in the trimmed view. */
export const LEAD_WEEKS = 4;
const TAIL_WEEKS = 2;

/** The slice of weeks to draw: from a few weeks before the first late-crop week to a little after the last. */
export function trimWeeks(weeks: TimelineWeek[]): TimelineWeek[] {
  const first = weeks.findIndex((w) => w.forecast_kg > 0);
  if (first < 0) return weeks;
  let last = first;
  weeks.forEach((w, i) => {
    if (w.forecast_kg > 0 || w.picked_kg > 0) last = Math.max(last, i);
  });
  return weeks.slice(Math.max(0, first - LEAD_WEEKS), Math.min(weeks.length, last + 1 + TAIL_WEEKS));
}

export function SeasonTimeline({ data }: { data: SeasonOutlook }) {
  const tl = data.timeline;
  const [whole, setWhole] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const [ref, width] = useWidth(320, 900);
  const trimmable = useMemo(() => trimWeeks(tl.weeks).length < tl.weeks.length, [tl.weeks]);
  const weeks = useMemo(() => (whole ? tl.weeks : trimWeeks(tl.weeks)), [whole, tl.weeks]);
  const hidden = tl.weeks.length - weeks.length;

  const note =
    `${tl.scheduled_kg ? `${tonnes(tl.scheduled_kg)} dated. ` : ""}` +
    (tl.calibration_factor && tl.calibration_factor !== 1
      ? `Forecasts are scaled by ${qty(tl.calibration_factor, 2)}, from delivered against estimate (${tl.calibration_basis})`
      : "Forecasts are not scaled: no delivered season to compare with yet");

  const plotW = Math.max(1, width - PAD.left - PAD.right);
  const plotH = TIMELINE_HEIGHT - PAD.top - PAD.bottom;
  const n = weeks.length;
  const band = n ? plotW / n : plotW;
  const hiKg = Math.max(1, ...weeks.map((w) => Math.max(w.picked_kg, w.forecast_kg)));
  const ticks = niceTicks(0, hiKg, 4);
  const top = ticks[ticks.length - 1] || hiKg;
  const y = (kg: number) => PAD.top + plotH - (kg / top) * plotH;
  const xOf = (week: string) => {
    const i = weeks.findIndex((w) => w.week === week);
    return i < 0 ? null : PAD.left + i * band + band / 2;
  };
  const todayX = xOf(tl.today_week);
  const peakX = tl.peak ? xOf(tl.peak.week) : null;
  const crossings = tl.crossings.map((c) => ({ ...c, x: xOf(c.week) })).filter((c) => c.x != null);
  const labelEvery = Math.max(1, Math.ceil(n / Math.max(4, Math.floor(plotW / 64))));
  const hw = hover == null ? null : weeks[hover];

  const empty = !weeks.length || weeks.every((w) => w.picked_kg === 0 && w.forecast_kg === 0);

  return (
    <SectionCard
      testId="outlook-timeline"
      title="Season timeline"
      description={`${note}. Bars are kilograms per week: picked so far, then forecast from each block's dry matter date.`}
      tools={
        trimmable || whole ? (
          <TogglePill pressed={whole} onPressedChange={setWhole}>
            Whole season
          </TogglePill>
        ) : undefined
      }
    >
      {empty ? (
        <EmptyNote big>
          {tl.unscheduled_kg
            ? `${tonnes(tl.unscheduled_kg)} undated — no week can be placed until the blocks have a current dry matter sample.`
            : "No crop on file — the orchard record is empty."}
        </EmptyNote>
      ) : (
        <>
          <div ref={ref} className="relative w-full">
            <svg width={width} height={TIMELINE_HEIGHT} role="img" aria-label="Weekly kilograms picked and forecast">
              {ticks.map((t) => (
                <g key={t}>
                  <line x1={PAD.left} x2={width - PAD.right} y1={y(t)} y2={y(t)} stroke="var(--sd-line)" />
                  <text x={PAD.left - 8} y={y(t) + 3.5} textAnchor="end" fontSize="10.5" fill="var(--sd-quiet)">
                    {compact(t / 1000)}t
                  </text>
                </g>
              ))}
              {weeks.map((w, i) => {
                const x = PAD.left + i * band + band * 0.14;
                const bw = Math.max(2, band * 0.72);
                const kg = w.picked_kg > 0 ? w.picked_kg : w.forecast_kg;
                const picked = w.picked_kg > 0;
                return (
                  <g key={w.week} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                    <rect x={PAD.left + i * band} y={PAD.top} width={band} height={plotH} fill="transparent" />
                    {kg > 0 && (
                      <rect
                        x={x}
                        y={y(kg)}
                        width={bw}
                        height={Math.max(1, PAD.top + plotH - y(kg))}
                        rx={Math.min(3, bw / 2)}
                        fill={ACCENT}
                        fillOpacity={picked ? 1 : 0.42}
                        stroke={picked ? undefined : ACCENT}
                        strokeDasharray={picked ? undefined : "3 2"}
                        data-kind={picked ? "picked" : "forecast"}
                      />
                    )}
                    {i % labelEvery === 0 && (
                      <text x={PAD.left + i * band + band / 2} y={TIMELINE_HEIGHT - 10} textAnchor="middle" fontSize="10.5" fill="var(--sd-quiet)">
                        {dayMonth(w.week)}
                      </text>
                    )}
                  </g>
                );
              })}
              {crossings.map((c) => {
                // Own row above the plot; pushed right of the today label when they would meet.
                const nearToday = todayX != null && Math.abs(c.x! - todayX) < 80;
                const lx = nearToday ? Math.max(c.x! + 4, todayX! + 30) : c.x! + 4;
                return (
                  <g key={`${c.planting_year}-${c.week}`}>
                    <line x1={c.x!} x2={c.x!} y1={16} y2={PAD.top + plotH} stroke="var(--sd-sev-critical)" strokeWidth="1.2" strokeDasharray="2 3" />
                    <text x={lx} y={12} fontSize="10" fontWeight="600" fill="var(--sd-sev-critical)">
                      {tl.minimum_pct}% · {c.planting_year ?? "unplanted"}
                    </text>
                  </g>
                );
              })}
              {todayX != null && (
                <g>
                  <line x1={todayX} x2={todayX} y1={26} y2={PAD.top + plotH} stroke="var(--sd-ink)" strokeWidth="1.3" />
                  <text x={todayX} y={36} textAnchor="middle" fontSize="10" fontWeight="600" fill="var(--sd-ink)">
                    today
                  </text>
                </g>
              )}
              {peakX != null && tl.peak && (
                <g>
                  <circle cx={peakX} cy={y(tl.peak.kg) - 6} r="3" fill="var(--sd-ink)" />
                  <text x={peakX} y={Math.max(y(tl.peak.kg) - 13, 46)} textAnchor="middle" fontSize="10.5" fontWeight="600" fill="var(--sd-ink)" stroke="var(--sd-card)" strokeWidth="3" paintOrder="stroke">
                    peak {tonnes(tl.peak.kg)}
                  </text>
                </g>
              )}
            </svg>
            {hw && (
              <div
                role="tooltip"
                className="pointer-events-none absolute right-2 top-0 rounded-lg bg-[var(--sd-ink)] px-2.5 py-1.5 text-[11.5px] text-white shadow-md"
              >
                Week of {dayMonth(hw.week)} · {hw.picked_kg > 0 ? "picked" : "forecast"} {qty((hw.picked_kg || hw.forecast_kg) / 1000, 1)} t
              </div>
            )}
          </div>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
            <Legend
              items={[
                { color: ACCENT, label: `Picked ${tonnes(tl.picked_kg)}` },
                { color: ACCENT, label: "Forecast", dashed: true },
                { color: "var(--sd-sev-critical)", label: `${tl.minimum_pct}% dry matter crossed` },
              ]}
            />
            {hidden > 0 && (
              <span className="text-[12px] text-[var(--sd-quiet)]">
                {hidden} empty {hidden === 1 ? "week" : "weeks"} hidden · use Whole season to see them
              </span>
            )}
          </div>
        </>
      )}
    </SectionCard>
  );
}

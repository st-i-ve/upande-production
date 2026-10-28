import type { ForecastUnit } from "@/lib/api";
import { qty } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Within +/-10% green, within +/-25% amber, anything worse red. */
export function errorTone(pct: number | null): "good" | "fair" | "poor" | "none" {
  if (pct == null) return "none";
  const a = Math.abs(pct);
  return a <= 10 ? "good" : a <= 25 ? "fair" : "poor";
}

const TONE_CLASS = {
  good: "text-[var(--sd-sev-moderate)]",
  fair: "text-[var(--sd-sev-high)]",
  poor: "text-[var(--sd-sev-critical)]",
  none: "text-[var(--sd-quiet)]",
} as const;

/** The error as plain words: -54 is "54% below forecast", +12 is "12% above forecast". */
export function vsForecast(pct: number | null, suffix = " forecast"): string {
  if (pct == null) return "—";
  const a = Math.abs(pct);
  if (a < 0.5) return `on${suffix}`;
  return `${a.toFixed(a < 10 ? 1 : 0)}% ${pct < 0 ? "below" : "above"}${suffix}`;
}

const BAR_COLOR = {
  good: "var(--sd-sev-moderate)",
  fair: "var(--sd-sev-high)",
  poor: "var(--sd-sev-critical)",
  none: "var(--sd-line)",
} as const;

/** Diverging bar around a centre line: under-delivery to the left, over to the right (capped at 50%). */
function BiasBar({ pct, tone }: { pct: number | null; tone: keyof typeof BAR_COLOR }) {
  if (pct == null) return null;
  const w = Math.min(50, Math.abs(pct) / 2);
  return (
    <div className="relative h-2 rounded-full bg-[var(--sd-bg-soft)]" aria-hidden>
      <div className="absolute inset-y-[-2px] left-1/2 w-px bg-[var(--sd-quiet)]" />
      <div
        className="absolute inset-y-0 rounded-full"
        style={{ background: BAR_COLOR[tone], width: `${w}%`, left: pct < 0 ? `${50 - w}%` : "50%" }}
      />
    </div>
  );
}

export function AccuracyTable({ units, uom, unitLabel }: { units: ForecastUnit[]; uom: string; unitLabel: string }) {
  return (
    <div className="overflow-x-auto rounded-[var(--sd-radius-lg)] border border-[var(--sd-line)]">
      <table className="w-full min-w-[28rem] text-[13px]">
        <thead>
          <tr className="border-b border-[var(--sd-line)] text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
            <th className="px-3 py-2.5 font-medium">{unitLabel}</th>
            <th className="px-3 py-2.5 text-right font-medium">Forecast to date ({uom})</th>
            <th className="px-3 py-2.5 text-right font-medium">Actual ({uom})</th>
            <th className="px-3 py-2.5 text-right font-medium">Actual vs forecast</th>
            <th className="w-40 px-3 py-2.5 font-medium">Bias</th>
          </tr>
        </thead>
        <tbody>
          {units.map((u) => {
            const tone = errorTone(u.error_pct);
            return (
              <tr key={u.unit} className="border-b border-[var(--sd-line-soft)] last:border-0">
                <td className="px-3 py-2.5 font-medium text-[var(--sd-ink)]">{u.unit}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{qty(u.forecast_to_date ?? u.forecast)}</td>
                <td className="px-3 py-2.5 text-right tabular-nums">{qty(u.actual)}</td>
                <td
                  data-testid={`error-${u.unit}`}
                  data-tone={tone}
                  className={cn("px-3 py-2.5 text-right font-medium tabular-nums", TONE_CLASS[tone])}
                >
                  {vsForecast(u.error_pct, "")}
                </td>
                <td className="px-3 py-2.5">
                  <BiasBar pct={u.error_pct} tone={tone} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="border-t border-[var(--sd-line-soft)] px-3 py-2 text-[11.5px] text-[var(--sd-quiet)]">
        Only weeks up to the current one count. Actual vs forecast is how far the harvest so far is from the forecast for the same weeks. Green within 10%, amber within 25%, red beyond.
      </p>
    </div>
  );
}

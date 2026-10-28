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

export function formatError(pct: number | null): string {
  if (pct == null) return "—";
  return `${pct > 0 ? "+" : ""}${pct.toFixed(1)}%`;
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
            <th className="px-3 py-2.5 text-right font-medium">Error</th>
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
                  {formatError(u.error_pct)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="border-t border-[var(--sd-line-soft)] px-3 py-2 text-[11.5px] text-[var(--sd-quiet)]">
        Only weeks up to the current one count. Error is (actual - forecast) / forecast. Green within 10%, amber within 25%, red beyond.
      </p>
    </div>
  );
}

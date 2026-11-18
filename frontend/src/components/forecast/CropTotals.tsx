import type { ForecastCrop } from "@/lib/api";
import { qty } from "@/lib/format";
import { cn } from "@/lib/utils";
import { errorTone, vsForecast } from "@/components/forecast/AccuracyTable";
import type { Bands } from "@/lib/bands";

const TONE = { good: "text-[var(--sd-sev-moderate)]", fair: "text-[var(--sd-sev-high)]", poor: "text-[var(--sd-sev-critical)]", none: "text-[var(--sd-quiet)]" } as const;

/**
 * Forecast, actual and committed for each crop of a section, in the crop's own unit. A line is one crop in one
 * unit; pieces and kilograms are never added into a total.
 */
export function CropTotals({ rows, bands }: { rows: ForecastCrop[]; bands: Bands | undefined }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]" data-testid="forecast-by-crop">
        <thead>
          <tr className="text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
            <th className="py-2 pr-3 font-medium">Crop</th>
            <th className="py-2 pr-3 font-medium">Unit</th>
            <th className="py-2 pr-3 text-right font-medium">Forecast</th>
            <th className="py-2 pr-3 text-right font-medium">Actual</th>
            <th className="py-2 pr-3 text-right font-medium">Committed</th>
            <th className="py-2 text-right font-medium">Actual vs forecast to date</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={`${r.field_crop}-${r.uom}`} className="border-t border-[var(--sd-line-soft)]">
              <td className="py-2.5 pr-3 font-medium text-[var(--sd-ink)]">{r.field_crop ?? "Other"}</td>
              <td className="py-2.5 pr-3 text-[var(--sd-muted)]">{r.uom ?? "—"}</td>
              <td className="py-2.5 pr-3 text-right tabular-nums">{qty(r.forecast)}</td>
              <td className="py-2.5 pr-3 text-right tabular-nums">{qty(r.actual)}</td>
              <td className="py-2.5 pr-3 text-right tabular-nums">{qty(r.committed)}</td>
              <td className={cn("py-2.5 text-right tabular-nums", TONE[errorTone(r.error_pct, bands)])}>{vsForecast(r.error_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

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
export function CropTotals({ rows, bands, crops }: { rows: ForecastCrop[]; bands: Bands | undefined; crops?: { name: string; crop_group?: string | null }[] }) {
  // Roll-up per (crop group, unit) in one structure: only crops in the same unit are added.
  const groupOf = new Map((crops ?? []).map((c) => [c.name, c.crop_group || "Other"]));
  const rolled = new Map<string, { group: string; uom: string | null; forecast: number; actual: number; committed: number }>();
  if (crops)
    for (const r of rows) {
      const group = (r.field_crop && groupOf.get(r.field_crop)) || "Other";
      const key = `${group}\u0000${r.uom ?? ""}`;
      const cur = rolled.get(key) ?? { group, uom: r.uom, forecast: 0, actual: 0, committed: 0 };
      cur.forecast += r.forecast;
      cur.actual += r.actual;
      cur.committed += r.committed;
      rolled.set(key, cur);
    }
  const groups = [...rolled.values()].sort((a, b) => a.group.localeCompare(b.group) || (a.uom ?? "").localeCompare(b.uom ?? ""));
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
      {groups.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1 border-t border-[var(--sd-line-soft)] pt-3 text-[12.5px]" aria-label="By crop group">
          {groups.map((g) => (
            <li key={`${g.group}-${g.uom}`} data-testid="group-total" className="flex flex-wrap gap-x-4 text-[var(--sd-muted)]">
              <span className="font-medium text-[var(--sd-ink)]">{g.group}</span>
              <span>{g.uom ?? "—"}</span>
              <span className="tabular-nums">Forecast {qty(g.forecast)}</span>
              <span className="tabular-nums">Actual {qty(g.actual)}</span>
              <span className="tabular-nums">Committed {qty(g.committed)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

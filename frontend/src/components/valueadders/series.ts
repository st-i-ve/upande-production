import { flagCurrentWeek, type SeriesPoint } from "@/components/Sparkline";
import { parseYmd, ymd } from "@/lib/utils";

/** Bucket day rows (key = YYYY-MM-DD) into weeks, oldest first, for a KPI sparkline. */
export function weeklySeries<T extends { key: string }>(rows: T[], pick: (r: T) => number): SeriesPoint[] {
  const buckets = new Map<string, number>();
  for (const r of rows) {
    const d = parseYmd(r.key);
    if (!d) continue;
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    const k = ymd(d);
    buckets.set(k, (buckets.get(k) ?? 0) + pick(r));
  }
  return flagCurrentWeek([...buckets.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([week, value]) => ({ week, value }))) ?? [];
}

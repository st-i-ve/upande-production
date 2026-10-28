/**
 * Typed client for `upande_production.api.insights` (extra series behind the Costs sparklines).
 * Same contract as lib/api.ts: resolves to an `Envelope<T>`, never throws; check `isError(r)`.
 */

import { call, type Envelope } from "@/lib/frappe";

const PREFIX = "upande_production.api.insights.";

export interface CostTrendWeek {
  week_start: string;
  iso_year: number;
  iso_week: number;
  /** null when the viewer may not see pay */
  labour: number | null;
  inputs: number;
  revenue: number;
  harvest_qty: number;
}

export const costTrend = (crop: string, fromDate: string, toDate: string): Promise<Envelope<{ weeks: CostTrendWeek[] }>> =>
  call<{ weeks: CostTrendWeek[] }>(PREFIX + "cost_trend", { crop, from_date: fromDate, to_date: toDate });

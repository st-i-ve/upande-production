/**
 * Typed client for `upande_production.api.breakeven`.
 * Same contract as lib/api.ts: resolves to an `Envelope<T>`, never throws; check `isError(r)`.
 */

import { call } from "@/lib/frappe";

const PREFIX = "upande_production.api.breakeven.";

export interface BreakEvenPoint {
  /** Month end, YYYY-MM-DD. Both figures are cumulative. */
  date: string;
  cost: number;
  value: number;
}

export interface BreakEvenSeries {
  points: BreakEvenPoint[];
  invested: number;
  recovered: number;
  balance: number;
  /** Percent, 0-100 (can pass 100). */
  pct_recovered: number;
  break_even_date: string | null;
}

export interface BreakEvenBlock extends Partial<BreakEvenSeries> {
  unit: string;
  invested: number;
  recovered: number;
  balance: number;
  pct_recovered: number;
  projected_date?: string | null;
  years_to_break_even?: number | null;
}

export interface BreakEvenFarm extends BreakEvenSeries {
  projected_date?: string | null;
  projection_basis?: "forecast" | "trailing_12m" | null;
}

export const cropBreakeven = (crop: string, farm?: string | null) =>
  call<{ blocks: BreakEvenBlock[]; farm: BreakEvenFarm }>(PREFIX + "crop_breakeven", { crop, farm: farm || null });

/**
 * Client for `upande_production.api.drymatter_monitor`: avocado tagged-fruit dry matter monitoring.
 * Resolves to an `Envelope<T>`; check `isError(r)`.
 *
 * A reading holds the microwave method (fresh / dry / dish weights, the app works out the %), the machine
 * method (the % read off the meter), or both. `dm_pct` is the average of the two when both were used, else the one that was.
 */

import { call } from "@/lib/frappe";

const PREFIX = "upande_production.api.drymatter_monitor.";

export interface FruitReading {
  name: string;
  idx: number;
  reading_date: string;
  method: "Microwave" | "Machine" | "Both";
  fresh_g: number | null;
  dish_g: number | null;
  dry_g: number | null;
  microwave_pct: number | null;
  machine_pct: number | null;
  instrument: string | null;
  dm_pct: number;
  recorded_by: string | null;
  notes: string | null;
}

export type TagStatus = "Active" | "Harvested" | "Lost";

export interface FruitTag {
  name: string;
  unit: string;
  farm: string | null;
  crop: string | null;
  cycle: string | null;
  variety: string | null;
  tree_label: string;
  fruit_tag: string;
  tagged_on: string | null;
  status: TagStatus;
  notes: string | null;
  readings: FruitReading[];
  latest_pct: number | null;
  latest_on: string | null;
  ready: boolean;
}

export interface SeriesPoint {
  date: string;
  dm_pct: number | null;
  microwave_pct: number | null;
  machine_pct: number | null;
  fruit: number;
}

/** reached: at or over the target; rising: a straight line crosses it on `date`; flat: not gaining; few: needs two
 *  readings on different days; far: more than 180 days off; none: no readings or no target. */
export type ProjectionState = "reached" | "rising" | "flat" | "few" | "far" | "none";

export interface Projection {
  state: ProjectionState;
  date: string | null;
  slope_per_week: number | null;
  points: number;
}

export interface Series {
  points: SeriesPoint[];
  projection: Projection;
  fruit?: number;
}

export interface Monitor {
  crop: string;
  target_pct: number | null;
  max_pct: number | null;
  blocks: { unit: string; farm: string | null }[];
  tags: FruitTag[];
  /** fruit: by tag name (one point per reading date). tree: by "block||tree" and block: by block (weekly averages). */
  series: { fruit: Record<string, Series>; tree: Record<string, Series>; block: Record<string, Series> };
  /** Lab maturity tests (count-size readings) per block, averaged per test date. */
  lab: Record<string, { date: string; dm_pct: number }[]>;
  drives: string;
}

export const getMonitor = (crop: string) => call<Monitor>(PREFIX + "get_monitor", { crop });

export interface ReadingInput {
  reading_date: string;
  fresh_g?: number | null;
  dish_g?: number | null;
  dry_g?: number | null;
  machine_pct?: number | null;
  instrument?: string | null;
  notes?: string | null;
}

export const saveFruitTag = (data: {
  unit: string;
  tree_label: string;
  fruit_tag: string;
  tagged_on: string;
  notes?: string;
  reading?: ReadingInput;
}) => call<FruitTag>(PREFIX + "save_tag", { data });

export const addFruitReading = (tag: string, data: ReadingInput) => call<FruitTag>(PREFIX + "add_reading", { tag, data });
export const deleteFruitReading = (tag: string, reading: string) => call<FruitTag>(PREFIX + "delete_reading", { tag, reading });
export const updateFruitTag = (tag: string, a: { status?: TagStatus; notes?: string }) => call<FruitTag>(PREFIX + "update_tag", { tag, ...a });

/** The same sums the server does, so the form shows the result as the weights are typed. */
export function microwavePct(fresh: string, dry: string, dish: string): { pct: number | null; problem: string | null } {
  const f = Number(fresh), d = Number(dry), k = Number(dish || 0);
  if (!fresh.trim() && !dry.trim()) return { pct: null, problem: null };
  if (!fresh.trim() || !dry.trim() || !Number.isFinite(f) || !Number.isFinite(d) || !Number.isFinite(k)) {
    return { pct: null, problem: "Enter both the fresh and the dry weight." };
  }
  if (k < 0) return { pct: null, problem: "The dish weight cannot be negative." };
  if (f - k <= 0) return { pct: null, problem: "The fresh weight must be more than the dish weight." };
  if (d - k <= 0) return { pct: null, problem: "The dry weight must be more than the dish weight." };
  if (d > f) return { pct: null, problem: "The dry weight cannot be more than the fresh weight." };
  return { pct: Math.round(((d - k) / (f - k)) * 10000) / 100, problem: null };
}

/** The value that drives the trend: both methods averaged, else whichever exists. */
export function combinePct(micro: number | null, machine: number | null): number | null {
  const v = [micro, machine].filter((x): x is number => x != null);
  return v.length ? Math.round((v.reduce((a, b) => a + b, 0) / v.length) * 100) / 100 : null;
}

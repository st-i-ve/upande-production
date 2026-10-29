/**
 * Typed client for `upande_production.api.fv`: the Fruits & Vegetables field logs
 * (pivot irrigation, harvest grading).
 *
 * Every function resolves to an `Envelope<T>` (data, or `{error}`); nothing throws, check
 * `isError(r)` first. Units are in the field names: `_mm` millimetres of water, `_kg`
 * kilograms, `_pct` percent (0-100). Weeks are the Monday as `YYYY-MM-DD`; datetimes are
 * `YYYY-MM-DD HH:mm:ss`.
 */

import type { Bands } from "@/lib/bands";
import { call, type Envelope } from "@/lib/frappe";

const PREFIX = "upande_production.api.fv.";
const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>(PREFIX + name, args);

function clean(args: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(args)) if (v !== undefined && v !== null && v !== "") out[k] = v;
  return out;
}

export type ISODate = string;

// -- Irrigation ---------------------------------------------------------------

export type IrrigationFault = "None" | "Tower misalignment" | "Pressure drop" | "Power" | "Stuck";

export interface IrrigationRun {
  name: string;
  unit: string;
  start_time: string;
  end_time: string;
  hours: number;
  direction: string | null;
  percent_timer: number | null;
  depth_mm: number;
  water_source: string | null;
  operator: string | null;
  operator_name: string | null;
  fault: IrrigationFault | null;
  notes: string | null;
  slices: string[];
}

export interface PivotSummary {
  name: string;
  area_ha: number;
  slices: number;
  runs: number;
  hours: number;
  faults: number;
  mm_per_slice: number;
  utilisation_pct: number;
}

export interface SliceMm {
  slice: string;
  pivot: string;
  item: string | null;
  mm: number;
  target_mm: number;
  pct_of_target: number;
}

export interface WeekIrrigation {
  week: ISODate;
  runs: number;
  hours: number;
  mm_per_slice: number;
}

export interface FaultRow {
  name: string;
  pivot: string;
  start_time: string;
  hours: number;
  fault: IrrigationFault;
  depth_mm: number;
  operator: string | null;
  notes: string | null;
}

export interface SliceFeature {
  type: "Feature";
  properties: SliceMm;
  geometry: { type: string; coordinates: unknown };
}

export interface IrrigationPage {
  from_date: ISODate;
  to_date: ISODate;
  pivot: string | null;
  pivot_names: string[];
  pivots: PivotSummary[];
  target: { weekly_mm: number; period_mm: number; weeks: number };
  bands: Bands;
  kpis: {
    runs: number;
    hours: number;
    mm_total: number;
    mm_per_slice_avg: number;
    slices_on_target: number;
    slices: number;
    faults: number;
    utilisation_pct: number;
  };
  series: WeekIrrigation[];
  slices: SliceMm[];
  runs: IrrigationRun[];
  faults: FaultRow[];
  map: { type: "FeatureCollection"; features: SliceFeature[]; bounds: [[number, number], [number, number]] | null };
  form: {
    pivots: { name: string; slices: string[] }[];
    faults: IrrigationFault[];
    directions: string[];
    water_sources: string[];
  };
}

export interface IrrigationRunInput {
  unit: string;
  start_time: string;
  end_time: string;
  depth_mm: number;
  direction?: string;
  percent_timer?: number;
  water_source?: string;
  operator?: string;
  fault?: string;
  notes?: string;
  slices: string[];
}

export const getIrrigation = (a: { from_date?: ISODate; to_date?: ISODate; pivot?: string } = {}) =>
  rpc<IrrigationPage>("irrigation", clean(a));

export const saveIrrigationRun = (data: IrrigationRunInput) =>
  rpc<{ ok: boolean; name: string; hours: number }>("save_irrigation_run", { data });

// -- Grading ------------------------------------------------------------------

export interface GradeBucket {
  key: string;
  graded_kg: number;
  rejects_kg: number;
  received_kg: number;
  grades: Record<string, number>;
  class1_pct: number;
  reject_pct: number;
}

export interface GradingLine {
  grade: string;
  kg: number;
  crates: number;
}

export interface GradingRow {
  name: string;
  unit: string;
  cycle: string | null;
  item: string | null;
  grading_date: ISODate;
  received_kg: number;
  received_crates: number | null;
  graded_kg: number;
  class1_kg: number;
  rejects_kg: number;
  reject_reason: string | null;
  graded_by: string | null;
  notes: string | null;
  lines: GradingLine[];
}

export interface GradingPage {
  from_date: ISODate;
  to_date: ISODate;
  unit: string | null;
  item: string | null;
  units: string[];
  items: string[];
  kpis: {
    graded_kg: number;
    received_kg: number;
    rejects_kg: number;
    class1_pct: number;
    reject_pct: number;
    top_reject_reason: string | null;
    top_reject_pct: number;
    logs: number;
  };
  grades: string[];
  by_item: GradeBucket[];
  by_block: GradeBucket[];
  reasons: { reason: string; kg: number; pct: number }[];
  series: { week: ISODate; graded_kg: number; class1_pct: number; reject_pct: number }[];
  rows: GradingRow[];
  form: {
    units: { name: string; parent: string | null; item: string | null; cycle: string | null }[];
    reasons: string[];
    default_grades: string[];
  };
}

export interface GradingInput {
  unit: string;
  grading_date: ISODate;
  received_kg: number;
  received_crates?: number;
  rejects_kg?: number;
  reject_reason?: string;
  graded_by?: string;
  notes?: string;
  item?: string;
  cycle?: string;
  lines: { grade: string; kg: number; crates?: number }[];
}

export const getGrading = (a: { from_date?: ISODate; to_date?: ISODate; unit?: string; item?: string } = {}) =>
  rpc<GradingPage>("grading", clean(a));

export const saveGrading = (data: GradingInput) =>
  rpc<{ ok: boolean; name: string; graded_kg: number }>("save_grading", { data });

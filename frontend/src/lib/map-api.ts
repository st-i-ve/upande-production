/**
 * Typed client for `upande_production.api.coverage` (the coverage map).
 * Same contract as lib/api.ts: resolves to an `Envelope<T>`, never throws; check `isError(r)`.
 */

import { call, type Envelope } from "@/lib/frappe";

export type CoverageState = "done" | "partial" | "not_started" | "late" | "pending_approval" | "no_work";

export const COVERAGE_STATES: CoverageState[] = ["done", "partial", "not_started", "late", "pending_approval", "no_work"];

export const COVERAGE_STATE_LABEL: Record<CoverageState, string> = {
  done: "Done",
  partial: "In progress",
  not_started: "Not started",
  late: "Late",
  pending_approval: "Awaiting approval",
  no_work: "No work planned",
};

/** Fill colours for the map, one per state. */
export const COVERAGE_STATE_COLOR: Record<CoverageState, string> = {
  done: "#3f7d3a",
  partial: "#e9a23b",
  not_started: "#9a968c",
  late: "#e63946",
  pending_approval: "#3d54b0",
  no_work: "#d6d2c8",
};

/** GeoJSON Feature (or bare geometry) as stored on Production Unit.geojson. */
export type UnitGeoJSON = {
  type: string;
  properties?: Record<string, unknown>;
  geometry?: { type: string; coordinates: unknown };
  coordinates?: unknown;
} | null;

/** Quantities keyed by unit of measure, e.g. { Bed: 120, Hectare: 6 }. */
export type QtyByUom = Record<string, number>;

export interface CoverageTask {
  operation: string;
  operation_name: string;
  planned_qty: number;
  done_qty: number;
  /** null until the approvals change adds the field. */
  pending_qty: number | null;
  /** max(planned - done, 0); 0 when Skipped. Pending quantity is NOT counted as done. */
  remaining_qty: number;
  uom: string;
  status: string;
  due_date: string;
  /** Overdue with quantity still outstanding (remaining minus pending). */
  late: boolean;
}

export interface CoverageActivity {
  operation: string;
  color: string;
}

/** Fill for a block with no activity when colouring by activity. */
export const NO_ACTIVITY_COLOR = "#d6d2c8";

export interface CoverageUnit {
  name: string;
  parent: string | null;
  unit_type: string;
  area_ha: number;
  geojson: UnitGeoJSON;
  cycle: string | null;
  item: string | null;
  variety?: string | null;
  /** Growth stage of the current cycle. */
  current_stage?: string | null;
  tasks: CoverageTask[];
  /** The activity the block is going through this week (operation and its colour), or null. */
  activity?: CoverageActivity | null;
  /** Mean of per-task completion, 0 to 100 (UOMs are not summed). */
  progress_pct: number;
  remaining_qty: QtyByUom;
  state: CoverageState;
}

export interface CoverageOutline {
  name: string;
  unit_type: string;
  area_ha: number;
  geojson: UnitGeoJSON;
}

export interface CoverageTotals {
  blocks: number;
  planned: QtyByUom;
  done: QtyByUom;
  remaining: QtyByUom;
  pending: QtyByUom;
  /** Blocks in the late state. */
  late: number;
  by_state: Record<CoverageState, number>;
  tasks: number;
}

export interface CoverageOperation {
  operation: string;
  operation_name: string;
  uom: string;
}

export interface CoverageMap {
  week_start: string;
  week_end: string;
  units: CoverageUnit[];
  /** Operations in use this week with their colours, for the "Colour by activity" legend. */
  legend?: CoverageActivity[];
  /** Group units (pivot circles) for drawing outlines under their slices. */
  outlines: CoverageOutline[];
  totals: CoverageTotals;
  /** All operations planned that week; unaffected by the operation filter. */
  operations: CoverageOperation[];
  /** [lng, lat] or null when no unit has geometry. */
  center: [number, number] | null;
  /** [[minLng, minLat], [maxLng, maxLat]] or null. */
  bounds: [[number, number], [number, number]] | null;
}

export interface CoverageArgs {
  crop: string;
  year: number;
  week: number;
  farm?: string | null;
  /** Field Activity name (OP-…) limiting the tasks counted. */
  operation?: string | null;
  /** Keep only blocks in this state. */
  status?: CoverageState | null;
}

export const coverageMap = ({ crop, year, week, farm, operation, status }: CoverageArgs): Promise<Envelope<CoverageMap>> =>
  call<CoverageMap>("upande_production.api.coverage.coverage_map", {
    crop,
    year,
    week,
    ...(farm ? { farm } : {}),
    ...(operation ? { operation } : {}),
    ...(status ? { status } : {}),
  });

/** "120 Bed · 6 Hectare" for a QtyByUom (zero entries dropped); "Nothing left" when empty. */
export function formatQty(q: QtyByUom, empty = "Nothing left"): string {
  const parts = Object.entries(q)
    .filter(([, v]) => v > 0)
    .map(([uom, v]) => `${Number.isInteger(v) ? v : v.toFixed(1)} ${uom}`);
  return parts.length ? parts.join(" · ") : empty;
}

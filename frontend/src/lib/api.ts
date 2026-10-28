/**
 * Typed wrappers for every endpoint in `upande_production.api.production`.
 *
 * The shapes below are the contract written in the plan (Task 4). Every
 * function resolves to an `Envelope<T>`: the data, or `{error}` written for a
 * farm user. Nothing here throws; check `isError(r)` first.
 *
 * Money fields (`rate`, `pay_value`, `labour…`) are `null` when the caller
 * lacks pay visibility (`boot.can_see_pay`), so they are typed nullable.
 */

import { call, type Envelope } from "@/lib/frappe";
import type { UomQty } from "@/lib/format";

const PREFIX = "upande_production.api.production.";
const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>(PREFIX + name, args);

export type Money = number | null;
export type Row = Record<string, unknown>;

// -- Bootstrap ---------------------------------------------------------------

export interface Crop {
  name: string;
  crop_key: string;
  accent_color: string;
  icon_key: string;
  unit_label: string;
  parent_unit_label: string;
  sub_unit_label: string;
  yield_uom: string;
  /** 0 for bees and fish: they run in hives and ponds, not crop cycles. */
  uses_crop_cycles?: number | boolean;
  /** Dry matter tests are switched on for this crop (avocado keeps its own page). */
  dry_matter_testing?: number | boolean;
  dry_matter_on?: "Fruit" | "Tuber" | null;
  dry_matter_target_pct?: number | null;
}

export interface Boot {
  crops: Crop[];
  farms: string[];
  can_see_pay: boolean;
  can_plan: boolean;
  can_manage: boolean;
}

export const getBootstrap = () => rpc<Boot>("get_bootstrap");

// -- Overview ----------------------------------------------------------------

export interface OverviewTiles {
  active_cycles: number;
  tasks_total: number;
  tasks_done: number;
  done_pct: number;
  deviations: number;
  labour_cost_mtd: Money;
  forecast_next4: number;
  committed_next4: number;
  harvest_qty_season: number;
}

export interface OverviewBlock {
  unit: string;
  unit_type: string;
  parent: string | null;
  area_ha: number;
  cycle: string | null;
  item: string | null;
  tasks_open: number;
  labour_cost_season: Money;
  harvest_qty_season: number;
}

export interface Overview {
  tiles: OverviewTiles;
  blocks: OverviewBlock[];
}

export const getOverview = (crop: string) => rpc<Overview>("get_overview", { crop });

// -- Units -------------------------------------------------------------------

export interface UnitRow {
  name: string;
  unit_type: string;
  parent: string | null;
  is_group: 0 | 1 | boolean;
  area_ha: number;
  plant_count: number;
  cost_center: string | null;
  status: string;
  current_cycle: string | null;
  item: string | null;
  has_geojson: 0 | 1 | boolean;
  /** Variety and growth stage of the current cycle. */
  variety?: string | null;
  current_stage?: string | null;
  /** Latest dry matter test; null when none (or the crop does not test). */
  dry_matter?: DryMatterLatest | null;
  /** Plants replaced by gap filling (approved work, uom Plant). */
  plants_replaced?: number;
  /** Off-protocol flags of the unit's current cycle. */
  flags?: string[];
}

export interface DryMatterLatest {
  pct: number;
  target: number | null;
  ready: boolean;
  date: string | null;
}

export const listUnits = (crop: string) => rpc<{ units: UnitRow[] }>("list_units", { crop });

export interface UnitDetail extends Omit<UnitRow, "has_geojson"> {
  geojson: string | null;
  [field: string]: unknown;
}

export interface Unit {
  unit: UnitDetail;
  cycles: Cycle[];
  /** At most 20 entries. */
  recent_work: Row[];
}

export const getUnit = (name: string) => rpc<Unit>("get_unit", { name });

// -- Cycles ------------------------------------------------------------------

export interface Cycle {
  name: string;
  title: string;
  unit: string;
  item: string | null;
  cycle_type: string;
  start_date: string;
  expected_harvest_start: string | null;
  expected_harvest_end: string | null;
  protocol: string | null;
  status: string;
  area_ha: number;
  previous_cycle: string | null;
  cycle_no?: number;
  expected_flowering_date?: string | null;
  actual_flowering_date?: string | null;
  actual_harvest_start?: string | null;
  actual_harvest_end?: string | null;
  /** Off-protocol flags, e.g. "Block A flowered 3 weeks late". */
  flags?: string[];
  due_for_uprooting?: 0 | 1 | boolean;
  proposed_next_cycle?: string | null;
  variety?: string | null;
  current_stage?: string | null;
  /** The variety's stages with real dates (actuals applied). */
  stage_bands?: StageBand[];
}

export interface StageBand {
  stage: string;
  start: string;
  /** Exclusive: the day the next stage begins. */
  end: string;
  is_harvest: 0 | 1 | boolean;
  /** A recorded actual date moved this stage. */
  actual: boolean;
}

export const listCycles = (crop: string, unit?: string | null, status?: string | null) =>
  rpc<{ cycles: Cycle[] }>("list_cycles", { crop, unit: unit ?? null, status: status ?? null });

/** Inserts, or updates when `data.name` is set. */
export const saveCycle = (data: Partial<Cycle> & Row) =>
  rpc<{ name: string; proposed_next_cycle?: string | null }>("save_cycle", { data });

export interface CycleFlagRow {
  cycle: string;
  unit: string;
  variety: string | null;
  flags: string[];
}

export const cycleFlags = (crop: string) => rpc<{ rows: CycleFlagRow[] }>("cycle_flags", { crop });

// -- Weekly plan -------------------------------------------------------------

export interface WorkEntry {
  name: string;
  employee: string;
  employee_name: string;
  qty: number;
  hours: number;
  pay_value: Money;
  /** Pending / Sent Back drafts are listed but do not count until a manager approves them. */
  approval_status?: "Pending" | "Approved" | "Sent Back";
  review_note?: string | null;
}

export type RuleStatus = "OK" | "Warn" | "Block";

export interface PlanTask {
  /** Absent on a row that has not been saved yet. */
  name?: string;
  unit: string;
  cycle: string | null;
  operation: string;
  operation_name: string;
  planned_qty: number;
  /** Approved quantity only. */
  done_qty: number;
  /** Keyed by the supervisor, awaiting manager approval. */
  pending_qty?: number;
  uom: string | null;
  rate: Money;
  due_date: string;
  supervisor: string | null;
  supervisor_name: string | null;
  status: string;
  deviation: string | null;
  protocol_ref: string | null;
  note: string | null;
  /** The operation's colour (Production Operation.color), for the activity dot. */
  color?: string | null;
  /** Activity rule flag: OK, Warn (allowed with a reason) or Block. */
  rule_status?: RuleStatus | null;
  rule_notes?: string | null;
  override_reason?: string | null;
  work: WorkEntry[];
  /** Set to 1 on a row passed to `savePlanTasks` to delete it. */
  _delete?: 1;
}

export interface Plan {
  plan: string | null;
  week_start: string;
  week_end: string;
  tasks: PlanTask[];
}

export const getPlan = (crop: string, farm: string, year: number, week: number) =>
  rpc<Plan>("get_plan", { crop, farm, year, week });

/** Upserts rows by `name`; rows without a name are appended; only rows with `_delete: 1` are removed. */
export const savePlanTasks = (
  crop: string,
  farm: string,
  year: number,
  week: number,
  tasks: Array<Partial<PlanTask> & Row>,
  overrideReason?: string | null,
) => rpc<{ name: string }>("save_plan_tasks", { crop, farm, year, week, tasks, override_reason: overrideReason ?? null });

/** A protocol step the activity rules refused to plan (Block). */
export interface SkippedStep {
  protocol_ref: string;
  unit: string;
  cycle: string;
  operation: string;
  due_date: string;
  message: string;
}

export const generatePlanWeek = (crop: string, farm: string, year: number, week: number) =>
  rpc<{ name: string; created: number; skipped?: SkippedStep[] }>("generate_plan_week", { crop, farm, year, week });

export interface WorkInput {
  employee: string;
  qty?: number;
  hours?: number;
  [field: string]: unknown;
}

export const recordTaskWork = (
  plan: string,
  task: string,
  status: string,
  entries: WorkInput[],
  note = "",
  workDate: string | null = null,
  overrideReason: string | null = null,
) =>
  rpc<{ task: PlanTask; work: string[] }>("record_task_work", {
    plan,
    task,
    status,
    entries,
    note,
    work_date: workDate,
    override_reason: overrideReason,
  });

// -- Value Adders ------------------------------------------------------------

export interface ValueAdder {
  name: string;
  employee_name: string;
  image: string | null;
}

export const listValueAdders = () => rpc<{ people: ValueAdder[] }>("list_value_adders");

export type GroupBy = "employee" | "day" | "unit";

export interface ValueAdderSummaryRow {
  key: string;
  label: string;
  /** Quantity per unit of measure; never added across UOMs. */
  qty_by_uom: UomQty[];
  hours: number;
  pay_value: Money;
  entries: number;
}

export const valueAdderSummary = (
  crop: string,
  fromDate: string,
  toDate: string,
  groupBy: GroupBy,
) =>
  rpc<{ rows: ValueAdderSummaryRow[]; total_pay: Money; total_qty_by_uom: UomQty[] }>("value_adder_summary", {
    crop,
    from_date: fromDate,
    to_date: toDate,
    group_by: groupBy,
  });

// -- Costs, deviations, forecast ---------------------------------------------

export interface BlockCostRow {
  unit: string;
  unit_type: string;
  parent: string | null;
  is_group: 0 | 1 | boolean;
  area_ha: number;
  labour: Money;
  inputs: number;
  total_cost: Money;
  cost_per_ha: Money;
  harvest_qty: number;
  revenue: number;
  margin: Money;
}

export const blockCosts = (crop: string, fromDate: string, toDate: string) =>
  rpc<{ rows: BlockCostRow[] }>("block_costs", { crop, from_date: fromDate, to_date: toDate });

export type DeviationKind = "Late" | "Partial" | "Skipped" | "Unplanned" | "Missed";

export interface DeviationRow {
  kind: DeviationKind;
  unit: string;
  operation_name: string;
  due_date: string;
  plan: string | null;
  detail: string;
}

export const deviations = (crop: string, fromDate: string, toDate: string) =>
  rpc<{ rows: DeviationRow[] }>("deviations", { crop, from_date: fromDate, to_date: toDate });

export interface ForecastWeek {
  iso_year: number;
  iso_week: number;
  week_start: string;
  forecast: number;
  actual: number;
  committed: number;
  /** (actual - forecast) / forecast * 100; null when forecast is 0 or the week is still ahead. */
  error_pct: number | null;
}

export interface ForecastUnit {
  unit: string;
  /** Forecast for weeks up to and including the current one. */
  forecast: number;
  forecast_to_date: number;
  actual: number;
  /** Judged on forecast_to_date only. */
  error_pct: number | null;
}

export interface ForecastTotals {
  /** Every week in the range, future ones included. */
  forecast: number;
  forecast_to_date: number;
  actual: number;
  committed: number;
  error_pct: number | null;
}

export interface ForecastSummary {
  uom: string;
  weeks: ForecastWeek[];
  units: ForecastUnit[];
  totals: ForecastTotals;
  seasons: Array<{ year: number; actual: number }>;
}

export const forecastSummary = (crop: string, fromDate: string, toDate: string) =>
  rpc<ForecastSummary>("forecast_summary", { crop, from_date: fromDate, to_date: toDate });

// -- Records: each returns {rows} or {name} ----------------------------------

export type Rows<T = Row> = { rows: T[] };
export type Saved = { name: string };

export const listSamples = (crop: string, unit?: string | null) =>
  rpc<Rows>("list_samples", { crop, unit: unit ?? null });
export const saveSample = (data: Row) => rpc<Saved>("save_sample", { data });

export const saveHarvest = (data: Row) => rpc<Saved>("save_harvest", { data });
export const listHarvests = (crop: string, fromDate: string, toDate: string) =>
  rpc<Rows>("list_harvests", { crop, from_date: fromDate, to_date: toDate });

export const listCommitments = (crop: string) => rpc<Rows>("list_commitments", { crop });
export const saveCommitment = (data: Row) => rpc<Saved>("save_commitment", { data });

export const listOperations = (crop: string) => rpc<Rows>("list_operations", { crop });
export const saveOperation = (data: Row) => rpc<Saved>("save_operation", { data });

export const listProtocols = (crop: string) => rpc<Rows>("list_protocols", { crop });

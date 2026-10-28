/**
 * Typed client for `upande_production.api.avocado`: one endpoint per avocado page.
 *
 * Every function resolves to an `Envelope<T>` (data, or `{error}`); nothing throws,
 * check `isError(r)` first. Units are in the field names: `_kg` kilograms, `_kes`
 * Kenya shillings, `_pct` percent (0-100), `_ha` hectares. Tonnes are a display
 * choice and never on the wire. Weeks are the Monday as `YYYY-MM-DD`.
 * Money tied to pay (`wage_*`, `pay_per_day_kes`) is null unless the caller may see pay.
 */

import { call, type Envelope } from "@/lib/frappe";

const PREFIX = "upande_production.api.avocado.";
const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>(PREFIX + name, args);

/** Drop undefined so the server applies its own default / saved preference. */
function clean(args: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(args)) if (v !== undefined && v !== null && v !== "") out[k] = v;
  return out;
}

export type ISODate = string;
export type ForecastMode = "manual" | "automatic";
export type CellKind = "fill" | "locked" | "no_sample" | "empty";

// -- Production Forecast ------------------------------------------------------

export interface KpiCard {
  key: string;
  label: string;
  value: number | null;
  unit: string;
  hint: string;
  of?: number;
  lost_kes?: number | null;
}

export interface BlockRow {
  block: string;
  farm: string | null;
  variety: string | null;
  planting_year: number | null;
  age: number | null;
  live_trees: number;
  bearing_trees: number;
  pct_bearing: number | null;
  kg_per_tree: number;
  basis: string;
  evidence: string | null;
  expected_kg: number;
  value_kes: number | null;
}

export interface VsBudget {
  forecast_kg: number;
  /** Already delivered this season (0 for a typed whole-season forecast). */
  delivered_kg: number;
  on_trees_kg: number;
  /** delivered + on the trees: what the budget is compared with. */
  outturn_kg: number;
  basis: string;
  diff_kg: number;
  pct_of_budget: number | null;
}

export interface ForecastView {
  kind: ForecastMode;
  total_kg: number;
  total_value_kes: number | null;
  blocks: number;
  live_trees: number;
  bearing_trees: number;
  pct_bearing: number | null;
  grade_1_share: number | null;
  grade_1_kg: number | null;
  counted_blocks: number | null;
  manual_entries: number | null;
  cards: KpiCard[];
  /** Blocks with trees or a forecast, table order. */
  block_rows: BlockRow[];
  /** Ranked bars: the 12 heaviest forecasting blocks. */
  top_blocks: BlockRow[];
  forecasting_blocks: number;
  vs_budget: VsBudget | null;
}

export interface BudgetMonth {
  month: string;
  budget_kg: number;
  budget_value: number | null;
  share_of_peak_pct: number;
  /** Harvest-log kilograms in this month of the season. */
  delivered_kg?: number;
  /** Scheduled forecast kilograms still to come in this month. */
  forecast_kg?: number;
}

export interface Budget {
  set: boolean;
  season: number;
  crop: string;
  budget_kg?: number;
  budget_price_per_kg?: number | null;
  budget_value?: number | null;
  set_by?: string | null;
  entry_date?: string | null;
  notes?: string | null;
  months: BudgetMonth[];
  months_total_kg?: number;
}

export interface EarlyScoreRow {
  block: string;
  farm: string | null;
  planting_year: number | null;
  estimated_kg: number;
  delivered_kg: number;
  pct_of_estimate: number | null;
}

export interface EstimateVsDelivered {
  season: number;
  crop: string;
  /** block = scored per block; estate = whole-estate closed-season totals; none = nothing delivered. */
  basis: "block" | "estate" | "none";
  estimated_kg: number;
  delivered_kg: number;
  diff_kg: number | null;
  diff_pct: number | null;
  performance_pct: number | null;
  blocks_estimated: number;
  blocks_delivered: number;
  best: EarlyScoreRow | null;
  weakest: EarlyScoreRow | null;
  /** Estimated but never harvested. */
  waiting: { block: string; estimated_kg: number }[];
  note: string | null;
  rows: EarlyScoreRow[];
}

export interface PlantingYearRow {
  planting_year: number | null;
  blocks: number;
  blocks_picked: number;
  estimated_kg: number;
  delivered_kg: number;
  pct_of_estimate: number | null;
  vs_best_year_pct: number | null;
}

export interface CurveRow {
  from_age: number;
  to_age: number;
  /** "2", "7-9", "10+" */
  label: string;
  kg_per_tree: number;
  /** "harvested" (measured) or "estate history". */
  basis: string;
  harvests: number;
  trees: number;
}

export interface ScheduleWeek {
  week: ISODate;
  iso_week: number;
  kg: number;
  share_of_peak_pct: number;
  value_kes: number | null;
}

export interface Unscheduled {
  block: string;
  expected_kg: number;
  reason: string;
}

export interface ScheduledBlock {
  block: string;
  expected_kg: number;
  start: ISODate;
  weeks: number;
  /** "dry matter" or "last season" */
  measured_on: string;
  basis: string;
}

export interface ScheduleView {
  weeks: ScheduleWeek[];
  scheduled_kg: number;
  unscheduled: Unscheduled[];
  unscheduled_kg: number;
  pick_weeks: number;
  scheduled_blocks: ScheduledBlock[];
  kg_by_basis: Record<string, number>;
  blocks_by_basis: Record<string, number>;
  next_6_weeks_kg: number;
}

export interface LossRow {
  block: string;
  farm: string | null;
  age: number | null;
  sick_trees: number;
  gaps: number;
  live_trees: number;
  pct_sick: number | null;
  kg_per_tree: number;
  lost_kg: number;
  lost_value_kes: number | null;
}

export interface LossView {
  rows: LossRow[];
  lost_kg: number;
  lost_value_kes: number | null;
}

export interface Calibration {
  factor: number;
  basis: string;
  seasons: number[];
  estimated_kg: number;
  actual_kg: number;
  blocks_estimated: number;
  blocks_harvested: number;
}

export interface Delivered {
  kg: number;
  blocks: number;
  crop: string | null;
  basis: string;
  harvest_from: ISODate | null;
  harvest_to: ISODate | null;
}

export interface ProductionForecast {
  farm: string | null;
  farms: string[];
  season: number;
  seasons: number[];
  /** The crop the automatic forecast is for (the one still on the trees). */
  crop: string;
  price_per_kg: number;
  /** The user's saved toggle. */
  mode: ForecastMode;
  header: {
    blocks: number;
    live_trees: number;
    bearing_trees: number;
    pct_bearing: number | null;
    biennial_factor: number;
    on_year: boolean;
  };
  views: Record<ForecastMode, ForecastView>;
  manual_note: { entries: number; blocks_total: number };
  budget: Budget;
  estimate_vs_delivered: EstimateVsDelivered;
  by_planting_year: PlantingYearRow[];
  yield_curve: CurveRow[];
  schedule: ScheduleView;
  losses: LossView;
  maturity: {
    minimum_pct: number;
    sampled: number;
    blocks: { block: string; sample_date: ISODate; dry_matter_pct: number; shortfall_pct: number; ready: boolean }[];
  };
  data_gaps: { issue: string; count: number; blocks: string[]; detail: string }[];
  calibration: Calibration;
  delivered: Delivered;
  units: Record<string, string>;
}

export const getProductionForecast = (a: {
  farm?: string;
  season?: number;
  price_per_kg?: number;
  mode?: ForecastMode;
} = {}) => rpc<ProductionForecast>("production_forecast", clean(a));

// -- Season Outlook -------------------------------------------------------------

export interface OutlookKpi {
  key:
    | "season_crop"
    | "crop_value"
    | "ready_to_pick"
    | "crew_next_week"
    | "estimate_accuracy"
    | "stale_readings";
  label: string;
  value: number | null;
  unit: string;
  note: string;
  of?: number;
  /** 0-100 fill for the small meter under the figure. */
  meter_pct?: number;
  /** crop_value: running total across blocks, heaviest first (sparkline). */
  series?: number[];
  delivered_kg?: number;
  ready_kg?: number;
  crew_available?: number;
  week?: ISODate | null;
  /** crew_next_week: needed exceeds available. */
  short?: boolean;
  calibration_factor?: number;
  estimated_kg?: number;
  actual_kg?: number;
}

export interface TimelineWeek {
  week: ISODate;
  iso_week: number;
  picked_kg: number;
  forecast_kg: number;
  is_past: boolean;
}

export interface VsCurveBand {
  /** Exclusive upper bound in percent of the age curve; null = no upper bound. */
  to_pct: number | null;
  color: string;
  dark_text: boolean;
}

export interface BandRef {
  color: string;
  dark_text: boolean;
  index: number | null;
}

export interface TreemapBlock {
  block: string;
  farm: string | null;
  expected_kg: number;
  value_kes: number | null;
  vs_curve_pct: number | null;
  band: BandRef;
  age: number | null;
  basis: string;
  bearing_trees: number;
  live_trees: number;
  planting_year: number | null;
}

export interface MapBlock {
  block: string;
  code: string;
  /** GeoJSON geometry/feature as stored on the block; render with MapLibre. */
  geojson: unknown;
  centroid_lat: number | null;
  centroid_lon: number | null;
  area_gap: { surveyed_ha: number; paper_ha: number; ratio: number } | null;
  expected_kg: number;
  vs_curve_pct: number | null;
  band: BandRef;
  farm: string | null;
  basis: string | null;
}

export interface Cohort {
  planting_year: number | null;
  blocks_n: number;
  blocks: string[];
  expected_kg: number;
  dry_matter_pct: number;
  gain_pct_per_week: number;
  weeks_to_minimum: number | null;
  open_date: ISODate | null;
  short_pct: number;
  stale_blocks: number;
}

export interface CrewWeek {
  week: ISODate;
  kg: number;
  crates: number;
  picker_days: number;
  pickers_needed: number;
  crew_available: number;
  /** Positive = people to find, negative = spare. null when no crew set. */
  shortfall: number | null;
  pct_of_crew: number | null;
  wage_cost: number | null;
  cost_per_kg: number | null;
  blocks: string[];
  pct_kg_measured: number | null;
}

export interface CrewSummary {
  weeks: number;
  total_kg?: number;
  total_crates?: number;
  total_picker_days?: number;
  peak_week?: ISODate;
  peak_pickers?: number;
  short_weeks?: number;
  worst_shortfall?: number;
  first_short_week?: ISODate | null;
  idle_weeks?: number;
  wage_cost?: number | null;
}

export interface OutlookAlert {
  weight: number;
  /** "neg" | "warn" | "" */
  kind: string;
  key: string;
  count: number;
  kg?: number;
  label: string;
  detail: string;
  first_week?: ISODate | null;
}

export interface SeasonOutlook {
  farm: string | null;
  farms: string[];
  season: number;
  price_per_kg: number;
  crew_available: number;
  crop: string;
  header: {
    blocks: number;
    total_kg: number;
    stale_readings: number;
    weeks_dated: number;
    biennial_factor: number;
    on_year: boolean;
    evidence_split: Record<string, number>;
  };
  kpis: OutlookKpi[];
  timeline: {
    /** Continuous Mondays, gaps filled with zeros. */
    weeks: TimelineWeek[];
    today_week: ISODate;
    scheduled_kg: number;
    unscheduled_kg: number;
    picked_kg: number;
    peak: { week: ISODate; kg: number } | null;
    calibration_factor: number;
    calibration_basis: string;
    /** Where each planting cohort crosses the dry matter minimum. */
    crossings: {
      planting_year: number | null;
      open_date: ISODate;
      week: ISODate;
      blocks_n: number;
      expected_kg: number;
    }[];
    minimum_pct: number;
  };
  map: { blocks: MapBlock[]; surveyed: number; without_boundary: number; area_disagrees: number };
  treemap: {
    bands: VsCurveBand[];
    /** Heaviest first. The squarified layout is the UI's job. */
    blocks: TreemapBlock[];
    with_crop: number;
    without_crop: number;
  };
  dry_matter: {
    minimum_pct: number;
    cohorts: Cohort[];
    blocks: {
      block: string;
      dry_matter_pct: number;
      sample_date: ISODate;
      samples: number;
      gain_pct_per_week: number;
      weeks_to_minimum: number | null;
      ready_date: ISODate | null;
      ready: boolean;
      stale: boolean;
    }[];
  };
  pickers: {
    crew_available: number;
    days_per_week: number;
    rows: CrewWeek[];
    summary: CrewSummary;
    next_week: CrewWeek | null;
    weeks_short: number;
  };
  losses: LossView;
  undated: {
    kg: number;
    blocks: Unscheduled[];
    stale_blocks: { block: string; sample_date: ISODate; sample_age_weeks: number; needs: string }[];
  };
  /** At most five, worst first. Empty = nothing wrong. */
  alerts: OutlookAlert[];
  delivered_by_season: { year: number; kg: number; blocks: number; on_year: boolean }[];
  calibration: Calibration;
  units: Record<string, string>;
}

export const getSeasonOutlook = (a: {
  farm?: string;
  price_per_kg?: number;
  crew_available?: number;
} = {}) => rpc<SeasonOutlook>("season_outlook", clean(a));

// -- Harvest Calendar ------------------------------------------------------------

export type BlockState = "ready" | "waiting" | "last_season" | "nodate" | "unsampled";

export interface CalendarCell {
  week: ISODate;
  kind: CellKind;
  kg: number;
  crates: number;
  /** 0 = empty, 1-5 = light to heavy. */
  shade: 0 | 1 | 2 | 3 | 4 | 5;
}

export interface CalendarBlock {
  block: string;
  farm: string;
  planting_year: number | null;
  expected_kg: number;
  state: BlockState;
  /** Set when a planting-year reading is shared, e.g. "2018 planting, not this block". */
  cohort_note: string;
  dry_matter_pct: number | null;
  dm_basis: string;
  samples: number;
  ready_date: ISODate | null;
  weeks_to_go: number | null;
  stale: boolean;
  start: ISODate | null;
  /** "dry matter" | "last season" | null */
  placed_on: string | null;
  placed_basis: string | null;
  /** Aligned with `weeks`. */
  cells: CalendarCell[];
  row_kg: number;
  row_crates: number;
  has_date: boolean;
}

export interface HarvestCalendar {
  filters: { farms: string[]; planting_years: number[] };
  selected: { farm: string | null; planting_year: number | null };
  minimum_pct: number;
  kg_per_crate: number;
  pick_weeks: number;
  summary: { blocks: number; weeks: number; total_kg: number; total_crates: number };
  kpis: {
    peak_week: { week: ISODate; iso_week: number; kg: number; crates: number } | null;
    in_window: { kg: number; crates: number; from_iso_week: number | null; to_iso_week: number | null };
    pickable_now: { blocks: number; of: number; minimum_pct: number };
    no_pick_date: { kg: number; blocks: number };
  };
  weeks: {
    week: ISODate;
    iso_week: number;
    /** "26 Oct" */
    label: string;
    kg: number;
    crates: number;
    is_peak: boolean;
    shade: number;
  }[];
  max_cell_kg: number;
  blocks: CalendarBlock[];
  no_pick_date: { block: string; farm: string; expected_kg: number; reason: "never_sampled" | "stale_sample" | "not_rising" }[];
  no_forecast: {
    block: string;
    farm: string | null;
    planting_year: number | null;
    bearing_trees: number;
    reason: "not_bearing" | "no_planting_year";
  }[];
  states: Record<BlockState, string>;
}

export const getHarvestCalendar = (a: { farm?: string; planting_year?: number } = {}) =>
  rpc<HarvestCalendar>("harvest_calendar", clean(a));

// -- Picking Plan -----------------------------------------------------------------

export interface PlanBlock {
  block: string;
  kg: number;
  crates: number;
  kg_per_picker_day: number;
  rate_basis: string;
  measured: boolean;
  picker_days: number;
  pickers_needed: number;
}

export interface PlanWeek extends CrewWeek {
  status: "short" | "spare" | "no_crew";
  people_short: number;
  people_spare: number;
  by_block: PlanBlock[];
}

export interface PickingPlan {
  farm: string | null;
  farms: string[];
  crew_available: number;
  days_per_week: number;
  pay_per_day_kes: number | null;
  can_see_pay: boolean;
  kg_per_crate: number;
  summary: CrewSummary;
  kpis: {
    peak_week: { pickers: number | undefined; week: ISODate | undefined };
    weeks_short: { weeks: number | undefined; first_week: ISODate | null | undefined; worst_shortfall_pickers: number | undefined };
    picker_days: { total: number | undefined; days_per_week: number };
    wage_bill_kes: number | null | undefined;
    cannot_staff: { kg: number; blocks: number };
  };
  weeks: PlanWeek[];
  focus_week: ISODate | null;
  week_detail: PlanWeek | null;
  rates: {
    blocks: { block: string; kg_per_picker_day: number; basis: string; events: number }[];
    estate: { kg_per_picker_day: number; basis: string; events: number } | null;
  };
  unscheduled: Unscheduled[];
  unscheduled_kg: number;
  rejected_records: { block: string; date: string; implied_rate: number; why: string }[];
}

export const getPickingPlan = (a: {
  farm?: string;
  /** Any date inside the week to open in detail. */
  week?: ISODate;
  crew_available?: number;
  days_per_week?: number;
  pay_per_day?: number;
} = {}) => rpc<PickingPlan>("picking_plan", clean(a));

// -- Dry Matter --------------------------------------------------------------------

export type DryMatterState = "ready" | "rising" | "stale" | "never_sampled";
export type WindowKind = "under" | "in" | "over";

export interface DryMatterBlock {
  block: string;
  farm: string | null;
  planting_year: number | null;
  state: DryMatterState;
  dry_matter_pct: number | null;
  short_pct: number | null;
  sample_date: ISODate | null;
  samples: number;
  gain_pct_per_week: number | null;
  gain_basis: string | null;
  weeks_to_minimum: number | null;
  ready_date: ISODate | null;
  sample_age_weeks: number | null;
  needs: string | null;
  /** "block" | "cohort" (inherited from the planting year) | null */
  measured_on: string | null;
  trend: { date: ISODate; dry_matter_pct: number; measured_on: string }[];
}

export interface DryMatterVisit {
  test_date: ISODate;
  where: string;
  measured_on: "block" | "area";
  week_number: number | null;
  sizes: { count_size: number; dry_matter_pct: number; moisture_pct: number }[];
  average_dry_matter: number;
  ready: boolean;
}

export interface DryMatterPage {
  farm: string | null;
  block: string | null;
  farms: string[];
  form: {
    blocks: { block: string; farm: string | null; planting_year: number | null }[];
    block_source: string | null;
    areas: string[];
    sizes: { count: number; min_g: number; max_g: number }[];
    min_pct: number;
    max_pct: number;
    today: ISODate;
    week_number: number;
  };
  minimum_pct: number;
  maximum_pct: number;
  blocks: DryMatterBlock[];
  summary: { blocks: number; ready: number; rising: number; stale: number; never_sampled: number };
  recent_visits: DryMatterVisit[];
  units: Record<string, string>;
}

export const getDryMatter = (a: { farm?: string; block?: string } = {}) =>
  rpc<DryMatterPage>("dry_matter", clean(a));

export interface MoistureReading {
  count_size: number;
  /** Fraction (0.77) or percentage (77); dry matter is the remainder. */
  moisture: number | string;
}

export interface DryMatterPreview {
  sizes: {
    count_size: number;
    dry_matter_pct: number | null;
    window: WindowKind | null;
    short_by_points?: number;
  }[];
  average_dry_matter_pct: number | null;
  ready_sizes: number;
  of: number;
  window: WindowKind | null;
  verdict: string | null;
  min_pct: number;
  max_pct: number;
}

/** Server-side moisture to dry matter, window and verdict. The rule is four lines, so
 *  a form may also compute it locally; this is the reference. */
export const previewDryMatter = (readings: MoistureReading[]) =>
  rpc<DryMatterPreview>("dry_matter_preview", { readings });

// -- Writes --------------------------------------------------------------------------

export interface Ok {
  ok: true;
}

export const setForecastMode = (mode: ForecastMode) =>
  rpc<Ok & { mode: ForecastMode }>("set_forecast_mode", { mode });

export const savePricePerKg = (price_per_kg: number) =>
  rpc<Ok & { price_per_kg: number }>("save_price_per_kg", { price_per_kg });

export const saveCrewAvailable = (crew_available: number) =>
  rpc<Ok & { crew_available: number }>("save_crew_available", { crew_available });

export interface SavedDryMatter extends Ok {
  saved: { name: string; count_size: number; dry_matter_pct: number; ready: boolean }[];
  skipped: { count_size: number; why: string }[];
  average_dry_matter: number;
  ready: number;
  of: number;
  verdict: string;
}

/** Record one visit. Give a block or a planting area; sizes left blank are not sent. */
export const saveDryMatter = (a: {
  readings: MoistureReading[];
  orchard_block?: string;
  planting_area?: string;
  week_number: number;
  test_date?: ISODate;
  notes?: string;
}) => rpc<SavedDryMatter>("save_dry_matter", clean({ ...a, readings: a.readings }));

export const saveManualForecast = (a: {
  orchard_block: string;
  expected_kg: number;
  season?: number;
  crop?: "Whole Season" | "Early" | "Late";
  price_per_kg?: number;
  notes?: string;
}) =>
  rpc<Ok & { name: string; created: boolean; block: string; season: number; crop: string; expected_kg: number }>(
    "save_manual_forecast",
    clean(a),
  );

export const saveSeasonBudget = (a: {
  season: number;
  /** Month names as the doctype has them: "January" ... "December". The total is their sum. */
  months: { month: string; budget_kg: number }[];
  budget_price_per_kg?: number;
  crop?: "Whole Season" | "Early" | "Late";
  notes?: string;
}) => rpc<Ok & { name: string; created: boolean; season: number; crop: string; budget_kg: number }>(
  "save_season_budget",
  clean(a),
);

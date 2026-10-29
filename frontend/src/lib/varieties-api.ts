/**
 * Typed wrappers for `upande_production.api.varieties`: varieties and their growth stages, activity
 * rules, a cycle's stage actuals and the weekly protocol check. Every function resolves to an
 * `Envelope<T>`; check `isError(r)` first.
 */

import { call, type Envelope } from "@/lib/frappe";
import type { StageBand } from "@/lib/api";
import type { Breach } from "@/lib/rules";

const PREFIX = "upande_production.api.varieties.";
const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>(PREFIX + name, args);

export interface VarietyStage {
  stage: string;
  /** Days from the anchor (planting / flowering / stocking). */
  start_day: number;
  length_days: number;
  is_harvest: 0 | 1 | boolean;
  description?: string | null;
}

export type StageAnchor = "Planting" | "Flowering" | "Stocking";

export type HarvestPattern = "Once" | "Continuous" | "Interval";
export const HARVEST_PATTERNS: HarvestPattern[] = ["Once", "Continuous", "Interval"];

/** Weeks to first harvest of a flowering variety: weeks to first flowering + weeks flowering to harvest. */
export const firstHarvestWeeks = (flowering: number | null | undefined, toHarvest: number | null | undefined): number =>
  (Number(flowering) || 0) + (Number(toHarvest) || 0);

export const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"] as const;
export type FloweringPattern = "Seasonal" | "Interval";
export const FLOWERING_PATTERNS: FloweringPattern[] = ["Seasonal", "Interval"];

/** A flowering season: it starts in `start_month`, harvest follows `weeks_flowering_to_harvest` later. */
export interface FloweringSeason {
  season_name: string;
  start_month: string;
  weeks_flowering_to_harvest: number | null;
  crop_share_pct?: number | null;
}

/** Safe water range for one parameter of a pond; DO uses min, pH and Temperature both, Ammonia and Nitrite max. */
export const WATER_PARAMETERS = ["DO", "pH", "Temperature", "Ammonia", "Nitrite"] as const;
export interface WaterBand {
  parameter: string;
  min: number | null;
  max: number | null;
  unit: string | null;
}

/** One row of a variety's yield by tree age: kg per plant from this age until the next row. */
export interface YieldAge {
  age_years: number;
  kg_per_plant: number;
}

export interface Variety {
  name: string;
  variety_name: string;
  crop: string;
  product: string | null;
  /** The variety's own stock item. */
  item: string;
  enabled: 0 | 1 | boolean;
  stage_anchor: StageAnchor | null;
  default_protocol: string | null;
  days_to_first_harvest: number | null;
  harvest_window_days: number | null;
  expected_yield_per_ha: number | null;
  expected_yield_per_plant: number | null;
  plants_per_ha: number | null;
  /** Template fields (weeks). Days and plants per ha above are derived from these. */
  lifespan_years?: number | null;
  harvest_pattern?: HarvestPattern | null;
  harvest_interval_weeks?: number | null;
  is_flowering?: 0 | 1 | boolean;
  weeks_to_maturity?: number | null;
  flowering_pattern?: FloweringPattern | null;
  flowering_seasons?: FloweringSeason[];
  /** Species or strain water ranges; empty uses the crop's. */
  water_bands?: WaterBand[];
  /** Yield model (kg per plant by age, biennial swing, late crop share). */
  yield_by_age?: YieldAge[];
  biennial_off_factor?: number | null;
  on_years?: string | null;
  late_crop_share_pct?: number | null;
  /** Weekly irrigation target in mm; empty uses the crop's. */
  irrigation_mm_week?: number | null;
  flowering_interval_weeks?: number | null;
  weeks_to_first_flowering?: number | null;
  weeks_flowering_to_harvest?: number | null;
  weeks_to_reflower_after_harvest?: number | null;
  weeks_to_first_harvest?: number | null;
  harvest_window_weeks?: number | null;
  plants_per_m2?: number | null;
  dry_matter_target_pct?: number | null;
  notes?: string | null;
  stages: VarietyStage[];
}

export const listVarieties = (crop: string) => rpc<{ varieties: Variety[] }>("list_varieties", { crop });
/** Inserts, or updates when `data.name` is set; `data.stages` replaces the stage rows. */
export const saveVariety = (data: Partial<Variety> & Record<string, unknown>) =>
  rpc<{ name: string }>("save_variety", { data });

export type RuleType =
  | "Not in stage"
  | "Only in stage"
  | "Not within days before harvest"
  | "Not within days after operation";

export const RULE_TYPES: RuleType[] = [
  "Not in stage",
  "Only in stage",
  "Not within days before harvest",
  "Not within days after operation",
];

export interface ActivityRule {
  name: string;
  crop: string;
  variety: string | null;
  stage: string | null;
  operation: string | null;
  operation_category: string | null;
  rule_type: RuleType;
  days: number | null;
  other_operation: string | null;
  other_category: string | null;
  enforcement: "Block" | "Warn";
  reason: string | null;
  enabled: 0 | 1 | boolean;
}

export const listRules = (crop: string) => rpc<{ rules: ActivityRule[] }>("list_rules", { crop });
export const saveRule = (data: Partial<ActivityRule> & Record<string, unknown>) => rpc<{ name: string }>("save_rule", { data });
/** Rules are disabled, never deleted. */
export const setRuleEnabled = (name: string, enabled: boolean) =>
  rpc<{ name: string; enabled: number }>("set_rule_enabled", { name, enabled: enabled ? 1 : 0 });

export interface CycleStage extends StageBand {
  actual_date?: string | null;
  note?: string | null;
}

export const getCycleStages = (cycle: string) =>
  rpc<{ variety: string | null; current_stage: string | null; stages: CycleStage[] }>("get_cycle_stages", { cycle });

/** Record the date a stage really began; an empty date clears it. */
export const setStageActual = (cycle: string, stage: string, actualDate: string | null, note?: string) =>
  rpc<{ name: string; current_stage: string | null; stage_bands: StageBand[] }>("set_stage_actual", {
    cycle,
    stage,
    actual_date: actualDate,
    note: note ?? null,
  });

export interface CheckStep {
  protocol_ref: string;
  operation: string;
  operation_name: string;
  due_date: string;
  status: string;
  planned_qty: number;
  done_qty: number;
  uom: string | null;
  rule_status: "OK" | "Warn" | "Block";
  breaches: Breach[];
}

export interface CheckBlock {
  unit: string;
  unit_name: string;
  cycle: string;
  protocol: string;
  steps: CheckStep[];
  /** Every breach in the block, each with its operation and due date. */
  breaches: Array<Breach & { operation: string; operation_name: string; due_date: string }>;
}

export interface ProtocolCheck {
  crop: string;
  reason: string | null;
  blocks: CheckBlock[];
}

export const protocolCheck = (crop: string, year: number, week: number, unit?: string | null) =>
  rpc<ProtocolCheck>("protocol_check", { crop, year, week, unit: unit ?? null });

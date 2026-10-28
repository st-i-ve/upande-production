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

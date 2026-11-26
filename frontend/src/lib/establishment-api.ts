/**
 * Typed client for `upande_production.api.establishment` (capital / setup costs and opening balances).
 * Same contract as lib/api.ts: resolves to an `Envelope<T>`, never throws; check `isError(r)`.
 */

import { call, type Envelope } from "@/lib/frappe";

const PREFIX = "upande_production.api.establishment.";

export interface EstablishmentCostRow {
  name: string;
  posting_date: string;
  operation: string;
  amount: number;
  supplier?: string | null;
  paid_to?: string | null;
  reference?: string | null;
  /** The leaf blocks the cost was split over. */
  blocks?: { unit: string; share_pct?: number; amount?: number }[];
}

export interface EstablishmentByActivity {
  operation: string;
  amount: number;
  budget?: number | null;
}

export interface EstablishmentByUnit {
  unit: string;
  total: number;
  area_ha?: number | null;
  /** ERPNext Budget on the block's cost centre for the current fiscal year; absent or 0 when none. */
  erp_budget?: number | null;
  /** Setup + running expense + labour this fiscal year (null when pay is hidden); compared with the ERP budget. */
  actual_this_fy?: number | null;
  by_activity: EstablishmentByActivity[];
}

export interface CapitalActivity {
  operation: string;
  color?: string | null;
  budget_per_ha?: number | null;
}

export interface OpeningBalance {
  name?: string;
  unit: string;
  as_of_date: string;
  setup_cost: number;
  running_costs_to_date: number;
  value_recovered_to_date: number;
  planted_on?: string | null;
  note?: string | null;
}

export interface SaveCostData {
  crop: string;
  farm?: string | null;
  posting_date: string;
  operation: string;
  amount: number;
  supplier?: string | null;
  paid_to?: string | null;
  reference?: string | null;
  note?: string | null;
  split_method: "By area" | "Manual";
  /** Group units may be named; the server expands them to leaf blocks. share_pct only for Manual. */
  blocks: { unit: string; share_pct?: number }[];
}

export const listCosts = (crop: string, farm?: string | null) =>
  call<{ rows: EstablishmentCostRow[]; by_unit: EstablishmentByUnit[] }>(PREFIX + "list_costs", { crop, farm: farm || null });

export const saveCost = (data: SaveCostData) => call<{ name: string }>(PREFIX + "save_cost", { data });

export const cancelCost = (name: string) => call<{ ok?: boolean }>(PREFIX + "cancel_cost", { name });

export const capitalActivities = (crop: string): Promise<Envelope<{ rows: CapitalActivity[] }>> =>
  call<{ rows: CapitalActivity[] }>(PREFIX + "capital_activities", { crop });

export const listOpeningBalances = (crop: string) =>
  call<{ rows: OpeningBalance[] }>(PREFIX + "list_opening_balances", { crop });

export const saveOpeningBalance = (data: OpeningBalance & { crop: string }) =>
  call<{ name?: string }>(PREFIX + "save_opening_balance", { data });

export interface UnitBudgetRow {
  operation: string;
  operation_name?: string;
  basis: "Per ha" | "Total";
  amount: number;
  note?: string | null;
  /** The amount for the block: amount x area when Per ha. Null for a Per ha row on a block without area. */
  effective: number | null;
  spent: number;
}

export interface UnitBudget {
  unit: string;
  area_ha: number | null;
  rows: UnitBudgetRow[];
  total_budget: number | null;
  total_spent: number;
}

export interface UnitBudgetInput {
  operation: string;
  basis: "Per ha" | "Total";
  amount: number;
  note?: string | null;
}

export const getUnitCapitalBudget = (unit: string) => call<UnitBudget>(PREFIX + "get_unit_capital_budget", { unit });

export const saveUnitCapitalBudget = (unit: string, rows: UnitBudgetInput[]) =>
  call<UnitBudget>(PREFIX + "save_unit_capital_budget", { unit, rows });

export interface CycleCapitalCosts {
  cycle: string;
  unit: string;
  rows: { cost: string; posting_date: string; operation: string; amount: number; supplier?: string | null; reference?: string | null }[];
  total: number;
  /** `budget` is the block's budget for the operation (not split between its cycles); null when none or no area. */
  by_operation: { operation: string; amount: number; budget: number | null }[];
}

export const cycleCapitalCosts = (cycle: string) => call<CycleCapitalCosts>(PREFIX + "cycle_capital_costs", { cycle });

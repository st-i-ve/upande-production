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

/**
 * Typed client for `upande_production.api.silage`: silage cycles, their cost and the pit stock.
 *
 * Every function resolves to an `Envelope<T>` (data, or `{error}`); nothing throws, check `isError(r)`.
 * Labour figures (`labour`, `casual_labour`, an activity's `day_rate` / `labour_cost`) are null when the
 * caller cannot see pay. `cost_per_kg` is null until kilos are ensiled.
 */

import { call, type Envelope } from "@/lib/frappe";

const PREFIX = "upande_production.api.silage.";
const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>(PREFIX + name, args);

export type SilageStatus = "Planned" | "Growing" | "Harvesting" | "Ensiled" | "Closed" | "Cancelled";
export type CostKind = "inputs" | "diesel" | "labour" | "casual_labour";

export interface SilageCost {
  inputs: number;
  diesel: number;
  labour: number | null;
  casual_labour: number | null;
  total: number;
}

export interface KindRow {
  kind: CostKind;
  label: string;
  amount: number | null;
  share_pct: number | null;
}

export interface SilageCycle {
  name: string;
  title: string;
  crop: string;
  production_crop: string | null;
  production_unit: string | null;
  crop_cycle: string | null;
  status: SilageStatus;
  docstatus: 0 | 1 | 2;
  start_date: string;
  closed_on: string | null;
  pit_warehouse: string | null;
  silage_item: string | null;
  ensiled_kg: number;
  cost: SilageCost;
  by_kind: KindRow[];
  cost_per_kg: number | null;
  diesel_litres: number;
  machine_hours: number;
  receipt_stock_entry: string | null;
  activities: number;
}

export interface ActivityRow {
  name: string;
  date: string;
  activity: string;
  workers: number | null;
  day_rate: number | null;
  labour_cost: number | null;
  notes: string | null;
}

export interface InputRow {
  stock_entry: string;
  posting_date: string;
  item_code: string;
  item_name: string;
  qty: number;
  uom: string;
  stock_qty: number;
  stock_uom: string;
  warehouse: string;
  amount: number;
}

export interface AllocationRow {
  allocation: string;
  machine: string;
  operator: string | null;
  operator_name: string | null;
  start_time: string | null;
  end_time: string | null;
  duration_hours: number | null;
  diesel_litres: number | null;
  diesel_cost: number | null;
  /** false while the allocation is still open (its diesel does not count yet). */
  submitted: boolean;
}

export interface SilageCycleDetail extends SilageCycle {
  notes: string | null;
  include_casual_labour: 0 | 1;
  activity_rows: ActivityRow[];
  inputs: InputRow[];
  draft_inputs: string[];
  allocations: AllocationRow[];
  allocations_available: boolean;
}

export interface PitStockRow {
  item_code: string;
  item_name: string;
  warehouse: string;
  qty: number;
  stock_uom: string | null;
  valuation_rate: number;
  stock_value: number;
}

export interface SilageTotals {
  cost: SilageCost;
  ensiled_kg: number;
  cost_per_kg: number | null;
  cycles: number;
}

export interface UnitOption {
  name: string;
  unit_name: string;
  crop: string;
}

export interface SilageOptions {
  crops: string[];
  statuses: SilageStatus[];
  activities: string[];
  production_crops: string[];
  units: UnitOption[];
  warehouses: string[];
  input_warehouse: string | null;
  pit_warehouse: string | null;
  /** The settings day rate per worker; null when the caller cannot see pay. */
  day_rate: number | null;
}

export interface SilagePage {
  cycles: SilageCycle[];
  pit_stock: PitStockRow[];
  summary: SilageTotals;
  summary_window: { from_date: string; to_date: string };
  can_see_pay: boolean;
  can_edit: boolean;
  can_close: boolean;
  allocations_available: boolean;
  options: SilageOptions;
}

export interface ItemOption {
  item_code: string;
  item_name: string;
  stock_uom: string;
}

export interface CycleInput {
  name?: string;
  title?: string;
  crop?: string;
  production_crop?: string;
  production_unit?: string;
  crop_cycle?: string;
  status?: SilageStatus;
  start_date?: string;
  pit_warehouse?: string;
  silage_item?: string;
  ensiled_kg?: number;
  include_casual_labour?: 0 | 1;
  notes?: string;
}

export const getSilagePage = (status?: string) => rpc<SilagePage>("silage_page", status ? { status } : {});
export const getSilageCycle = (name: string) => rpc<{ cycle: SilageCycleDetail }>("silage_cycle", { name });
export const searchSilageItems = (search = "") => rpc<{ items: ItemOption[] }>("silage_items", { search });
export const saveSilageCycle = (data: CycleInput) =>
  rpc<{ name: string; cycle: SilageCycleDetail }>("save_silage_cycle", { data });
export const addSilageActivity = (args: {
  cycle: string;
  date: string;
  activity: string;
  workers?: number;
  day_rate?: number;
  labour_cost?: number;
  notes?: string;
}) => rpc<{ cycle: SilageCycleDetail }>("add_silage_activity", args);
export const removeSilageActivity = (cycle: string, row: string) =>
  rpc<{ cycle: SilageCycleDetail }>("remove_silage_activity", { cycle, row });
export const issueSilageInputs = (args: {
  cycle: string;
  items: { item_code: string; qty: number; uom?: string }[];
  warehouse?: string;
  posting_date?: string;
}) => rpc<{ stock_entry: string; cycle: SilageCycleDetail }>("issue_silage_inputs", args);
export const closeSilageCycle = (args: {
  name: string;
  ensiled_kg: number;
  closed_on?: string;
  silage_item?: string;
  pit_warehouse?: string;
}) => rpc<{ stock_entry: string; cycle: SilageCycleDetail }>("close_silage_cycle", args);

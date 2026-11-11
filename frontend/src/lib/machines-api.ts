/**
 * Typed client for `upande_production.api.asset_allocation`: machines, their QR labels and
 * allocations. Every function resolves to an `Envelope<T>`; check `isError(r)` first.
 * Datetimes are `YYYY-MM-DD HH:MM:SS` (site time); hours are decimal hours; litres are in the fuel
 * item's stock UOM; costs are in the company currency, read from the posted Stock Entry.
 */

import { call, type Envelope } from "@/lib/frappe";

const PREFIX = "upande_production.api.asset_allocation.";
const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> => call<T>(PREFIX + name, args);

export interface Option {
  value: string;
  label: string;
}

export interface Rights {
  can_manage: boolean;
  can_allocate: boolean;
  can_submit: boolean;
}

export interface MachineSettings {
  fuel_warehouse: string | null;
  feedlot_cost_center: string | null;
}

export interface OpenAllocationSummary {
  name: string;
  operator: string;
  operator_name: string | null;
  allocated_to: string;
  reference_name: string | null;
  start_time: string;
  running_hours: number;
}

export interface Machine {
  name: string;
  machine_name: string;
  machine_type: string;
  asset: string | null;
  fuel_item: string | null;
  default_cost_center: string | null;
  qr_code: string | null;
  disabled: 0 | 1;
  last_latitude: number | null;
  last_longitude: number | null;
  last_seen_at: string | null;
  notes: string | null;
  has_position: boolean;
  open_allocation: OpenAllocationSummary | null;
}

export interface MachineList extends Rights {
  machines: Machine[];
  machine_types: string[];
  settings: MachineSettings;
}

export type AllocationStatus = "Open" | "Closed" | "Posted" | "Cancelled";

export interface Allocation {
  name: string;
  machine: string;
  machine_type: string | null;
  allocated_to: string;
  reference_doctype: string | null;
  reference_name: string | null;
  operator: string;
  operator_name: string | null;
  cost_center: string;
  status: AllocationStatus;
  docstatus: 0 | 1 | 2;
  start_time: string;
  end_time: string | null;
  duration_hours: number;
  running_hours: number | null;
  scanned: 0 | 1;
  start_latitude: number | null;
  start_longitude: number | null;
  start_accuracy: number | null;
  end_latitude: number | null;
  end_longitude: number | null;
  end_accuracy: number | null;
  diesel_litres: number;
  diesel_stock_entry: string | null;
  diesel_cost: number;
  fuel_item: string | null;
  notes: string | null;
}

export interface AllocationList extends Rights {
  from_date: string | null;
  to_date: string | null;
  rows: Allocation[];
  kpis: { open: number; to_submit: number; hours: number; diesel_litres: number; diesel_cost: number };
  machines: Machine[];
  allocated_to: string[];
  settings: MachineSettings;
}

export interface MachineLabel {
  machine: string;
  machine_name: string;
  machine_type: string;
  qr_code: string;
  url: string;
  image: string | null;
}

export interface AllocationForm extends Rights {
  machines: (Option & { machine_type: string; busy: boolean })[];
  employees: Option[];
  me: string | null;
  allocated_to: string[];
  reference_doctypes: Record<string, string>;
  references: Record<string, (Option & { cost_center?: string | null })[]>;
  cost_centers: Option[];
  settings: MachineSettings;
  now: string;
}

export interface ScanResult {
  machine: {
    name: string;
    machine_name: string;
    machine_type: string;
    fuel_item: string | null;
    qr_code: string;
    last_latitude: number | null;
    last_longitude: number | null;
    last_seen_at: string | null;
  };
  open_allocation: Allocation | null;
}

export const listMachines = (include_disabled = false) =>
  rpc<MachineList>("list_machines", { include_disabled: include_disabled ? 1 : 0 });

export const saveMachine = (data: Partial<Machine> & { machine_name: string; machine_type: string }) =>
  rpc<{ name: string }>("save_machine", { data });

export const machineLabels = (machines: string[]) => rpc<{ labels: MachineLabel[] }>("machine_labels", { machines });

export const allocationForm = () => rpc<AllocationForm>("allocation_form");

export const scanMachine = (code: string) => rpc<ScanResult>("scan_machine", { code });

export const startAllocation = (data: Record<string, unknown>) =>
  rpc<{ allocation: Allocation }>("start_allocation", { data });

export const closeAllocation = (data: Record<string, unknown>, allocation?: string) =>
  rpc<{ allocation: Allocation }>("close_allocation", { data, allocation });

export const submitAllocation = (allocation: string, diesel_litres?: number | null) =>
  rpc<{ allocation: Allocation }>("submit_allocation", { allocation, diesel_litres });

export const listAllocations = (args: {
  from_date?: string;
  to_date?: string;
  status?: string;
  machine?: string;
  allocated_to?: string;
}) => {
  const clean: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(args)) if (v) clean[k] = v;
  return rpc<AllocationList>("list_allocations", clean);
};

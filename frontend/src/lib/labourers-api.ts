/**
 * Casual labour roster and KPIs (`upande_production.api.labourers`).
 *
 * Pay is per unit of work; a daily target is only a yardstick (never changes pay).
 * Money fields are null when the caller cannot see pay.
 */
import { call, type Envelope } from "@/lib/frappe";
import type { UomQty } from "@/lib/format";

const PREFIX = "upande_production.api.labourers.";
const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> => call<T>(PREFIX + name, args);

type Money = number | null;

export interface RosterRow {
  name: string;
  employee: string;
  employee_name: string;
  department: string | null;
  designation: string | null;
  image: string | null;
  active: 0 | 1;
  supervisor_name: string | null;
  crew: string | null;
  /** Number of per-person target overrides. */
  overrides: number;
  days_worked: number;
  qty_by_uom: UomQty[];
  entries: number;
  target_days: number;
  met_days: number;
  /** % of target-bearing days that met the daily target; null when no day had a target. */
  hit_rate: number | null;
  pay_value: Money;
  unpaid_value: Money;
}

export interface RosterTotals {
  labourers: number;
  active: number;
  working: number;
  days_worked: number;
  qty_by_uom: UomQty[];
  hit_rate: number | null;
  target_days: number;
  pay_value: Money;
  unpaid_value: Money;
}

export interface RosterDay {
  key: string;
  labourers: number;
  pay_value: Money;
  hit_rate: number | null;
}

export interface RosterFilters {
  search?: string;
  department?: string;
  designation?: string;
  /** "1" active, "0" inactive, "" all */
  active?: string;
}

export const listLabourers = (crop: string, fromDate: string, toDate: string, f: RosterFilters = {}) =>
  rpc<{ rows: RosterRow[]; days: RosterDay[]; totals: RosterTotals }>("list_labourers", {
    crop,
    from_date: fromDate,
    to_date: toDate,
    search: f.search ?? "",
    department: f.department ?? "",
    designation: f.designation ?? "",
    active: f.active ?? "",
  });

export interface OperationKpi {
  operation: string;
  operation_name: string;
  uom: string | null;
  qty: number;
  days: number;
  avg_per_day: number | null;
  target: number | null;
  target_uom: string | null;
  override: boolean;
  target_days: number;
  met_days: number;
  hit_rate: number | null;
  /** Average per day as a % of the daily target. */
  avg_vs_target: number | null;
  pay_value: Money;
  unpaid_value: Money;
  entries: number;
}

export interface DailyPoint {
  date: string;
  operation: string;
  operation_name: string;
  uom: string | null;
  qty: number;
  target: number | null;
  met: boolean | null;
}

export interface RecentWork {
  name: string;
  work_date: string;
  unit: string;
  operation: string;
  operation_name: string;
  qty: number;
  uom: string | null;
  pay_value: Money;
  paid: "Unpaid" | "Paid";
  paid_on: string | null;
  payroll_reference: string | null;
  target: number | null;
  target_uom: string | null;
  day_qty: number;
  target_met: boolean | null;
}

export interface TargetOverride {
  operation: string;
  operation_name: string;
  target: number;
  uom: string | null;
}

export interface LabourerDetail {
  employee: string;
  employee_name: string;
  department: string | null;
  designation: string | null;
  image: string | null;
  on_roster: boolean;
  active: boolean | null;
  supervisor: string | null;
  supervisor_name: string | null;
  crew: string | null;
  kpis: {
    days_worked: number;
    entries: number;
    qty_by_uom: UomQty[];
    target_days: number;
    met_days: number;
    hit_rate: number | null;
    avg_vs_target: number | null;
    pay_value: Money;
    paid_value: Money;
    unpaid_value: Money;
  };
  by_operation: OperationKpi[];
  daily: DailyPoint[];
  recent: RecentWork[];
  pending_entries: number;
  targets: TargetOverride[];
}

export const getLabourerDetail = (crop: string, employee: string, fromDate: string, toDate: string) =>
  rpc<LabourerDetail>("labourer_detail", { crop, employee, from_date: fromDate, to_date: toDate });

export interface Candidate {
  name: string;
  employee_name: string;
  department: string | null;
  designation: string | null;
  image: string | null;
}

export const candidateEmployees = (f: { search?: string; department?: string; designation?: string } = {}) =>
  rpc<{ people: Candidate[]; departments: string[]; designations: string[] }>("candidate_employees", {
    search: f.search ?? "",
    department: f.department ?? "",
    designation: f.designation ?? "",
    limit: 300,
  });

export const addLabourers = (employees: string[], supervisor?: string | null, crew?: string | null) =>
  rpc<{ added: string[]; skipped: string[] }>("add_labourers", { employees, supervisor: supervisor || null, crew: crew || null });

export interface LabourerPatch {
  active?: boolean;
  supervisor?: string | null;
  crew?: string | null;
  targets?: { operation: string; daily_target: number; uom?: string | null }[];
}

export const saveLabourer = (employee: string, patch: LabourerPatch) =>
  rpc<{ name: string }>("save_labourer", {
    employee,
    ...(patch.active !== undefined ? { active: patch.active ? 1 : 0 } : {}),
    ...(patch.supervisor !== undefined ? { supervisor: patch.supervisor ?? "" } : {}),
    ...(patch.crew !== undefined ? { crew: patch.crew ?? "" } : {}),
    ...(patch.targets !== undefined ? { targets: patch.targets } : {}),
  });

export const removeLabourer = (employee: string) =>
  rpc<{ removed: boolean; deactivated: boolean }>("remove_labourer", { employee });

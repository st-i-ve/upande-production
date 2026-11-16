/**
 * Built-in labour pay (`upande_production.api.labourpay`): the Labour & Pay settings, rate periods,
 * attendance and pay runs. Writes need a manager, reads need the pay role.
 */
import { call, type Envelope } from "@/lib/frappe";

const PREFIX = "upande_production.api.labourpay.";
const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> => call<T>(PREFIX + name, args);

export interface LabourModeStatus {
  mode: "Automatic" | "Built-in only";
  wm_installed: boolean;
  wm_active: boolean;
}

export const labourModeStatus = () => rpc<LabourModeStatus>("labour_mode_status");

export interface LabourSettings {
  labour_mode: string;
  pay_period: string;
  pay_week_starts_on: string;
  pay_day: string;
  /** Left out for people who may not see pay. */
  daily_wage?: number | null;
  duplicate_rule: string;
  multiple_jobs_per_day: string;
  attendance_required: number;
  attendance_source: string;
  max_backdate_days: number;
  pay_reference_prefix: string;
  /** Allowed values for each Select field. */
  options: Record<string, string[]>;
  wm_installed?: boolean;
  wm_active?: boolean;
}

export const getLabourSettings = () => rpc<LabourSettings>("get_labour_settings");
export const saveLabourSettings = (values: Record<string, unknown>) => rpc<LabourSettings>("save_labour_settings", { values });

export interface RatePeriod {
  name: string;
  operation: string;
  operation_name: string;
  valid_from: string;
  valid_to: string | null;
  rate: number | null;
  daily_target: number | null;
  uom: string | null;
  note: string | null;
}

export const listRates = (operation?: string) => rpc<{ rates: RatePeriod[] }>("list_rates", operation ? { operation } : {});
export const saveRate = (r: {
  operation: string;
  valid_from: string;
  valid_to: string | null;
  rate: number | null;
  daily_target: number | null;
  note: string;
  name?: string;
}) => rpc<RatePeriod>("save_rate", r);
export const deleteRate = (name: string) => rpc<{ deleted: string }>("delete_rate", { name });

export const ATTENDANCE_STATUSES = ["Present", "Half Day", "Absent", "On Leave", "Off"] as const;
export type AttendanceStatus = (typeof ATTENDANCE_STATUSES)[number];

export interface AttendanceRow {
  name: string;
  employee: string;
  employee_name: string;
  status: AttendanceStatus;
  farm: string | null;
  note: string | null;
}

export const attendanceDay = (date: string, farm?: string) =>
  rpc<{ date: string; rows: AttendanceRow[] }>("attendance_day", farm ? { date, farm } : { date });
export const markAttendance = (employees: string[], date: string, status: AttendanceStatus, farm?: string, note?: string) =>
  rpc<{ marked: number; names: string[] }>("mark_attendance", { employees, date, status, ...(farm ? { farm } : {}), ...(note ? { note } : {}) });

export type PayRunStatus = "Draft" | "Approved" | "Paid" | "Cancelled";

export interface PayRunSummary {
  name: string;
  company: string | null;
  farm: string | null;
  from_date: string;
  to_date: string;
  status: PayRunStatus;
  docstatus: number;
  total_people: number;
  total_amount: number | null;
  payment_reference: string | null;
  paid_on: string | null;
}

export interface PayRunLine {
  employee: string;
  employee_name: string;
  days: number;
  entries: number;
  qty: number;
  amount: number | null;
  work: string[];
}

export interface PayRunDetail extends PayRunSummary {
  lines: PayRunLine[];
}

export const listPayRuns = (status?: string, limit = 50) =>
  rpc<{ runs: PayRunSummary[]; default_period: { from_date: string; to_date: string }; pay_day: string }>("list_pay_runs", {
    ...(status ? { status } : {}),
    limit,
  });
export const newPayRun = (fromDate?: string, toDate?: string, farm?: string) =>
  rpc<PayRunDetail>("new_pay_run", { ...(fromDate ? { from_date: fromDate } : {}), ...(toDate ? { to_date: toDate } : {}), ...(farm ? { farm } : {}) });
export const payRunDetail = (name: string) => rpc<PayRunDetail>("pay_run_detail", { name });
export const approvePayRun = (name: string) => rpc<PayRunDetail>("approve_pay_run", { name });
export const markPayRunPaid = (name: string, reference?: string, paidOn?: string) =>
  rpc<PayRunDetail>("mark_pay_run_paid", { name, ...(reference ? { reference } : {}), ...(paidOn ? { paid_on: paidOn } : {}) });
export const refreshPayRun = (name: string) => rpc<PayRunDetail>("refresh_pay_run", { name });
export const cancelPayRun = (name: string) => rpc<PayRunDetail | { name: string; status: "Deleted" }>("cancel_pay_run", { name });
export const payRunCsv = (name: string) => rpc<{ filename: string; csv: string }>("pay_run_csv", { name });

/** Hand a {filename, csv} answer to the browser as a download. */
export function downloadCsv(filename: string, csv: string) {
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

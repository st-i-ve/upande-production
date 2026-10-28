/**
 * Typed wrappers for `upande_production.api.approvals`.
 *
 * Supervisors key work in as drafts (`Pending`). A manager approves it (it then counts toward done qty,
 * pay and costs) or sends it back with a note (`Sent Back`); the supervisor fixes it and resubmits.
 * Every function resolves to an `Envelope<T>`; check `isError(r)` first. Pay fields are `null` when the
 * caller lacks pay visibility.
 */

import { call, type Envelope } from "@/lib/frappe";

const PREFIX = "upande_production.api.approvals.";
const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>(PREFIX + name, args);

export type ApprovalStatus = "Pending" | "Approved" | "Sent Back";
type Money = number | null;

/** One keyed row (a Value Adder Work draft or approved entry). */
export interface ApprovalEntry {
  name: string;
  employee: string;
  employee_name: string | null;
  qty: number;
  uom: string | null;
  hours: number | null;
  rate: Money;
  pay_value: Money;
  work_date: string;
  approval_status: ApprovalStatus;
  review_note: string | null;
}

/** One card: a supervisor's submission for a plan task (or an unplanned unit + operation + date). */
export interface ApprovalGroup {
  /** Stable id for the card. */
  key: string;
  status: ApprovalStatus;
  crop: string;
  unit: string;
  unit_name: string;
  operation: string;
  operation_name: string;
  plan: string | null;
  plan_year: number | null;
  plan_week: number | null;
  plan_task: string | null;
  /** Null for unplanned work. */
  task_planned_qty: number | null;
  /** Approved qty only. */
  task_done_qty: number | null;
  task_pending_qty: number | null;
  task_status: string | null;
  /** The plan task's note. */
  note: string | null;
  unplanned: 0 | 1;
  uom: string | null;
  work_date: string;
  /** User id (email) of the keying supervisor. */
  submitted_by: string;
  submitted_by_name: string;
  /** Earliest creation time of the rows. */
  created: string;
  age_days: number;
  /** Pending for at least `stale_days`. */
  stale: boolean;
  total_qty: number;
  total_pay: Money;
  review_note: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  /** Value Adder Work names in this card: pass these to approve / sendBack / resubmit. */
  names: string[];
  entries: ApprovalEntry[];
}

export interface ApprovalList {
  groups: ApprovalGroup[];
  /** Cards per status (ignoring the status filter) plus how many Pending cards are stale. */
  counts: Record<ApprovalStatus, number> & { stale: number };
  stale_days: number;
}

export interface ApprovalFilters {
  status?: ApprovalStatus;
  fromDate?: string | null;
  toDate?: string | null;
  unit?: string | null;
  operation?: string | null;
  /** User id of the keying supervisor. */
  supervisor?: string | null;
}

/** Pending is unbounded; with no `fromDate`, Approved history is limited to the last 60 days. */
export const listApprovals = (crop: string | null, f: ApprovalFilters = {}) =>
  rpc<ApprovalList>("list_approvals", {
    crop,
    status: f.status ?? "Pending",
    from_date: f.fromDate ?? null,
    to_date: f.toDate ?? null,
    unit: f.unit ?? null,
    operation: f.operation ?? null,
    supervisor: f.supervisor ?? null,
  });

/** Managers only. Submits the drafts, so they count. All-or-nothing. */
export const approve = (names: string[]) => rpc<{ approved: string[] }>("approve", { names });

/** Managers only. `note` is required. */
export const sendBack = (names: string[], note: string) =>
  rpc<{ sent_back: string[] }>("send_back", { names, note });

export interface ResubmitEdit {
  name: string;
  qty?: number;
  hours?: number | null;
  employee?: string;
}

/** Supervisors and managers. Only Sent Back entries; optional edits are applied, then back to Pending. */
export const resubmit = (names: string[], entries?: ResubmitEdit[]) =>
  rpc<{ resubmitted: string[] }>("resubmit", { names, entries: entries ?? null });

export interface ApprovalCropCount {
  crop: string;
  crop_key: string | null;
  /** Pending cards. */
  pending: number;
  stale: number;
  /** Protocol versions awaiting approval for this crop. */
  protocols_pending?: number;
}

export interface ApprovalCounts {
  crops: ApprovalCropCount[];
  total: number;
  /** All crops. */
  protocols_pending?: number;
  stale: number;
  stale_days: number;
}

export const approvalCounts = () => rpc<ApprovalCounts>("approval_counts");

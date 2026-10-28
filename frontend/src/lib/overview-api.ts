/** Client for `upande_production.api.overview` (extra Overview figures). */

import { call, type Envelope } from "@/lib/frappe";
import type { Money } from "@/lib/api";
import type { UomQty } from "@/lib/format";

export interface TrendWeek {
  week: string;
  week_start: string;
  tasks: number;
  done: number;
  done_pct: number;
  deviations: number;
  labour: Money;
  harvest: number;
}

export interface ForecastWeek {
  week: string;
  week_start: string;
  forecast: number;
  committed: number;
}

export interface OperationProgress {
  operation_name: string;
  uom: string | null;
  planned: number;
  done: number;
  pending: number;
  tasks: number;
  tasks_done: number;
}

export interface UpcomingTask {
  unit: string;
  operation_name: string;
  due_date: string;
  status: string;
  planned_qty: number;
  done_qty: number;
  uom: string | null;
}

export interface RecentDeviation {
  kind: string;
  unit: string;
  operation_name: string;
  due_date: string | null;
  detail: string;
}

export interface BlockExtra {
  unit: string;
  stage: string | null;
  cycle_day: number | null;
  last_activity: string | null;
  hours_30d: number;
  crew_30d: number;
}

export interface OverviewExtras {
  trend: TrendWeek[];
  forecast_weeks: ForecastWeek[];
  operations: OperationProgress[];
  upcoming: UpcomingTask[];
  recent_deviations: RecentDeviation[];
  blocks: BlockExtra[];
  pending_approvals: number;
}

export const getOverviewExtras = (crop: string): Promise<Envelope<OverviewExtras>> =>
  call<OverviewExtras>("upande_production.api.overview.get_overview_extras", { crop });

// -- Value adder detail --------------------------------------------------------

export interface WorkBreakdown {
  key: string;
  qty_by_uom: UomQty[];
  hours: number;
  pay_value: Money;
  entries: number;
}

export interface ValueAdderDetail {
  employee: string;
  employee_name: string;
  by_day: WorkBreakdown[];
  by_unit: WorkBreakdown[];
  by_operation: WorkBreakdown[];
  recent: {
    work_date: string;
    unit: string;
    operation: string;
    qty: number;
    uom: string | null;
    hours: number;
    pay_value: Money;
  }[];
  pending_entries: number;
}

export const getValueAdderDetail = (crop: string, employee: string, fromDate: string, toDate: string) =>
  call<ValueAdderDetail>("upande_production.api.overview.value_adder_detail", {
    crop,
    employee,
    from_date: fromDate,
    to_date: toDate,
  });

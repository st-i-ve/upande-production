/** Supervisors page (`upande_production.api.supervisors`): a card per Production Supervisor and one's detail. */
import { call, type Envelope } from "@/lib/frappe";

const PREFIX = "upande_production.api.supervisors.";
const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> => call<T>(PREFIX + name, args);

export interface TaskCounts {
  done: number;
  open: number;
  late: number;
  skipped: number;
  total: number;
}

export interface SupervisorCard {
  employee: string;
  employee_name: string;
  image: string | null;
  phone: string | null;
  user: string | null;
  farm: string | null;
  active: boolean;
  /** `pending` is null when the viewer may not see this supervisor's crew approvals. */
  kpis: { blocks: number; tasks: TaskCounts; crew: number; pending: number | null };
}

export interface SupervisorBlockRow {
  unit: string;
  unit_name: string;
  crop: string;
  categories: string[];
  overseer: boolean;
}

export interface SupervisorLabourer {
  employee: string;
  employee_name: string;
  image: string | null;
  active: 0 | 1;
  crew: string | null;
}

export interface SupervisorDetail {
  supervisor: {
    employee: string;
    employee_name: string;
    image: string | null;
    phone: string | null;
    user: string | null;
    farm: string | null;
    active: boolean;
    notes: string | null;
    crops: string[];
  };
  year: number;
  week: number;
  can_edit: boolean;
  blocks: SupervisorBlockRow[];
  tasks: TaskCounts;
  /** null when hidden from the viewer. */
  pending: number | null;
  crew_count: number;
  /** The crew list is withheld (a plain supervisor viewing another, or a viewer). */
  crew_hidden: boolean;
  labourers: SupervisorLabourer[];
}

export interface SupervisorInput {
  employee: string;
  active?: boolean;
  farm?: string | null;
  crops?: string[];
  notes?: string | null;
}

export const listSupervisors = (crop: string, year: number, week: number) =>
  rpc<SupervisorCard[]>("list_supervisors", { crop, year, week });

export const getSupervisor = (employee: string, crop: string, year: number, week: number) =>
  rpc<SupervisorDetail>("get_supervisor", { employee, crop, year, week });

export const saveSupervisor = (data: SupervisorInput) =>
  rpc<{ employee: string; employee_name: string }>("save_supervisor", { data });

export interface AssistantWithoutManager {
  user: string;
  full_name: string;
  employee: string | null;
  reports_to: string | null;
  reason: "no_employee" | "no_reports_to" | "reports_to_not_manager";
}

/** Managers only: assistant managers whose employee reports to nobody (or to someone who is not a manager). */
export const assistantsWithoutManager = () => rpc<AssistantWithoutManager[]>("assistants_without_manager");

/** Active employees for the Add supervisor picker (managers only; not limited by HR's self-service permissions). */
export const employeeOptions = (search: string, limit = 15) =>
  rpc<{ value: string; label: string }[]>("employee_options", { search, limit });

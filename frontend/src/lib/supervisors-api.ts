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
  kpis: { blocks: number; tasks: TaskCounts; crew: number; pending: number };
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
  pending: number;
  labourers: SupervisorLabourer[];
}

export interface SupervisorInput {
  employee: string;
  active?: boolean;
  farm?: string | null;
  crops?: string[];
  notes?: string | null;
}

export const listSupervisors = (crop: string | null, year: number, week: number) =>
  rpc<SupervisorCard[]>("list_supervisors", { crop, year, week });

export const getSupervisor = (employee: string, crop: string | null, year: number, week: number) =>
  rpc<SupervisorDetail>("get_supervisor", { employee, crop, year, week });

export const saveSupervisor = (data: SupervisorInput) =>
  rpc<{ employee: string; employee_name: string }>("save_supervisor", { data });

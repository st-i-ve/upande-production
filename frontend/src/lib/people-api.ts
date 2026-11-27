/** People profiles (`upande_production.api.supervisors.people_supervisors`, `...labourers.people_labourers`):
 *  the roster with each person's figures over a date range. No pay amounts. */
import { call, type Envelope } from "@/lib/frappe";

export interface PersonFlag {
  kind: string;
  label: string;
  count: number;
  detail: string;
}

export interface ShareRow {
  key: string;
  label: string;
  count: number;
  /** percent of the person's total, null when there is none */
  share: number | null;
}

export type Figures = Record<string, number | null>;

export interface SupervisorPerson {
  employee: string;
  employee_name: string;
  image: string | null;
  phone: string | null;
  user: string | null;
  farm: string | null;
  active: boolean;
  /** this week's blocks and activities */
  blocks: number;
  activities: number;
  overseer: boolean;
  crew: number;
  /** false when the viewer may not see this supervisor's crew figures (they come back null) */
  full: boolean;
  metrics: Figures;
  /** 0-100, outward is better */
  scores: Figures;
  flags: PersonFlag[];
  where: ShareRow[];
  weekly: { week: string; done: number; logs: number }[];
}

export interface SupervisorPeople {
  from: string;
  to: string;
  weeks: string[];
  people: SupervisorPerson[];
  medians: Figures;
  can_manage: boolean;
}

export interface LabourerPerson {
  employee: string;
  employee_name: string;
  image: string | null;
  active: boolean;
  supervisor: string | null;
  supervisor_name: string | null;
  crew: string | null;
  last_worked: string | null;
  /** unit of measure of the output figures (the one they record most) */
  output_uom: string | null;
  metrics: Figures;
  scores: Figures;
  flags: PersonFlag[];
  where_blocks: ShareRow[];
  where_activities: ShareRow[];
  weekly: { week: string; days: number; output: number }[];
}

export interface LabourerPeople {
  from: string;
  to: string;
  weeks: string[];
  workdays: number;
  people: LabourerPerson[];
  medians: Figures;
}

const SUP = "upande_production.api.supervisors.";
const LAB = "upande_production.api.labourers.";

export const supervisorPeople = (crop: string, from: string, to: string): Promise<Envelope<SupervisorPeople>> =>
  call<SupervisorPeople>(SUP + "people_supervisors", { crop, from_date: from, to_date: to });

export const labourerPeople = (crop: string, from: string, to: string): Promise<Envelope<LabourerPeople>> =>
  call<LabourerPeople>(LAB + "people_labourers", { crop, from_date: from, to_date: to });

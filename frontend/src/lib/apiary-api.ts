/**
 * Typed client for `upande_production.api.apiary`: the hive inspection and honey harvest pages.
 *
 * Every function resolves to an `Envelope<T>` (data, or `{error}`); nothing throws, check
 * `isError(r)` first. Units are in the field names: `_kg` kilograms, `_pct` percent (0-100);
 * `mites_per_100` is varroa mites per 100 bees. Weeks are the Monday as `YYYY-MM-DD`, oldest
 * first, empty weeks included.
 */

import type { Bands } from "@/lib/bands";
import { call, type Envelope } from "@/lib/frappe";

const PREFIX = "upande_production.api.apiary.";
const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>(PREFIX + name, args);

function clean(args: Record<string, unknown>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(args)) if (v !== undefined && v !== null && v !== "") out[k] = v;
  return out;
}

export interface Option {
  value: string;
  label: string;
}

export type MiteStatus = "ok" | "watch" | "high" | "none";
export type QueenStatus = "queenright" | "weak" | "queenless" | "none";

export interface InspectionForm {
  units: (Option & { farm: string | null })[];
  employees: Option[];
  today: string;
  brood_patterns: string[];
  temperaments: string[];
  disease_options: string[];
  /** Treat above this (mites per 100 bees); null until the manager sets it on the Apiary crop. */
  threshold: number | null;
  watch: number | null;
}

export interface InspectionKpis {
  inspections: number;
  colonies: number;
  queenright_pct: number | null;
  avg_mites: number | null;
  avg_mites_prev: number | null;
  /** Change in the average against the previous period of the same length. */
  mites_trend: number | null;
  colonies_above_threshold: number;
  groups_above_threshold: number;
  disease_flags: number;
  queen_status: QueenStatus;
}

export interface InspectionWeek {
  week: string;
  inspections: number;
  colonies: number;
  queenright_pct: number | null;
  avg_mites: number | null;
  disease_flags: number;
}

export interface GroupTrendPoint {
  date: string;
  mites: number | null;
  queenright_pct: number | null;
}

export interface HiveGroupStatus {
  unit: string;
  label: string;
  farm: string | null;
  inspections: number;
  last_date: string | null;
  days_since?: number;
  colonies?: number;
  queenright?: number;
  queenright_pct?: number | null;
  queen_status: QueenStatus;
  queen_seen?: boolean;
  eggs_seen?: boolean;
  mites_per_100?: number | null;
  mite_status: MiteStatus;
  brood_pattern?: string | null;
  temperament?: string | null;
  disease_signs?: string;
  frames_brood?: number | null;
  frames_honey?: number | null;
  frames_stores?: number | null;
  inspector?: string | null;
  trend: GroupTrendPoint[];
}

export interface InspectionRow {
  name: string;
  unit: string;
  unit_label: string;
  inspection_date: string;
  inspector: string | null;
  colonies_inspected: number;
  colonies_queenright: number;
  queen_seen: boolean;
  eggs_seen: boolean;
  brood_pattern: string | null;
  temperament: string | null;
  varroa_per_100: number | null;
  mite_status: MiteStatus;
  disease_signs: string | null;
  frames_brood: number | null;
  frames_honey: number | null;
  frames_stores: number | null;
  feeding_kg: number | null;
  actions: string | null;
}

export interface HiveInspectionsPage {
  from_date: string;
  to_date: string;
  unit: string | null;
  threshold: number | null;
  watch: number | null;
  bands: Bands;
  kpis: InspectionKpis;
  series: InspectionWeek[];
  groups: HiveGroupStatus[];
  rows: InspectionRow[];
  form: InspectionForm;
}

export interface InspectionInput {
  unit: string;
  inspection_date: string;
  inspector?: string;
  colonies_inspected: number;
  colonies_queenright: number;
  queen_seen: boolean;
  eggs_seen: boolean;
  brood_pattern?: string;
  temperament?: string;
  varroa_per_100?: number | null;
  disease_signs: string;
  frames_brood?: number;
  frames_honey?: number;
  frames_stores?: number;
  feeding_kg?: number;
  actions?: string;
}

export const getHiveInspections = (a: { from_date?: string; to_date?: string; unit?: string } = {}) =>
  rpc<HiveInspectionsPage>("hive_inspections", clean(a));

export const saveHiveInspection = (data: InspectionInput) =>
  rpc<{ ok: boolean; name: string; message: string }>("save_hive_inspection", { data: JSON.stringify(data) });

// -- Honey harvest -------------------------------------------------------------

export interface HarvestKpis {
  kg: number;
  harvests: number;
  colonies: number;
  kg_per_hive: number | null;
  avg_moisture: number | null;
  grade_a_pct: number | null;
  wax_kg: number;
}

export interface HarvestWeek {
  week: string;
  kg: number;
  avg_moisture: number | null;
  grade_a_pct: number | null;
}

export interface HarvestGroup {
  unit: string;
  label: string;
  farm: string | null;
  harvests: number;
  kg: number;
  colonies: number;
  kg_per_hive: number | null;
  avg_moisture: number | null;
  grade_a_pct: number | null;
  wax_kg: number;
  supers_removed: number;
  last_harvest: string | null;
}

export interface HarvestRow {
  name: string;
  unit: string;
  unit_label: string;
  harvest_date: string;
  supers_removed: number;
  frames_extracted: number;
  honey_kg: number;
  moisture_pct: number | null;
  grade: string | null;
  wax_kg: number | null;
  notes: string | null;
}

export interface HoneyHarvestPage {
  from_date: string;
  to_date: string;
  unit: string | null;
  bands: Bands;
  kpis: HarvestKpis;
  series: HarvestWeek[];
  groups: HarvestGroup[];
  rows: HarvestRow[];
  form: { units: Option[]; today: string; grades: string[]; moisture_limit: number | null };
}

export interface HarvestInput {
  unit: string;
  harvest_date: string;
  supers_removed?: number;
  frames_extracted?: number;
  honey_kg: number;
  moisture_pct?: number | null;
  grade: string;
  wax_kg?: number;
  notes?: string;
}

export const getHoneyHarvest = (a: { from_date?: string; to_date?: string; unit?: string } = {}) =>
  rpc<HoneyHarvestPage>("honey_harvest", clean(a));

export const saveHoneyHarvest = (data: HarvestInput) =>
  rpc<{ ok: boolean; name: string; message: string }>("save_honey_harvest", { data: JSON.stringify(data) });

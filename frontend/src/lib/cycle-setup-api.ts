import { call, type Envelope } from "@/lib/frappe";

const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>("upande_production.api.cycle_setup." + name, args);

export interface AddCycleInput {
  unit: string;
  variety: string;
  protocol?: string | null;
  cycle_type?: string;
  start_date?: string | null;
  area_ha?: number | null;
  plant_count?: number | null;
  /** A cycle that is already in production. */
  existing?: boolean;
  planting_date?: string | null;
  current_stage?: string | null;
  last_flowering_date?: string | null;
  last_harvest_date?: string | null;
  /** kg per year (season). */
  last_season_yield_kg?: number | null;
}

/** Warnings (a block over its area or trees) come back with the saved cycle: they never refuse it. */
export const addCycle = (data: AddCycleInput) => rpc<{ name: string; warnings: string[] }>("add_cycle", { data });

export const importTemplate = () => rpc<{ filename: string; columns: string[]; content: string }>("import_template");

export interface ImportRow {
  row: number;
  raw: Record<string, string>;
  values: {
    unit: string | null;
    variety: string | null;
    planting_date: string | null;
    plant_count: number | null;
    area_ha: number | null;
    current_stage: string;
    last_season_yield_kg: number | null;
  };
  errors: string[];
  warnings: string[];
}

export const previewImport = (crop: string, filename: string, content: string) =>
  rpc<{ rows: ImportRow[]; ok: number; bad: number }>("preview_import", { crop, filename, content });

export interface ImportResult {
  row: number;
  ok: boolean;
  name?: string;
  error?: string;
  warnings?: string[];
}

export const importCycles = (crop: string, rows: Record<string, string>[]) =>
  rpc<{ results: ImportResult[]; created: number }>("import_cycles", { crop, rows });

/** The Add crop cycle dialog is for avocado blocks for now, and for whoever may manage production. */
export const canAddCycle = (crop: { crop_key: string; boot: { can_manage?: boolean; can_plan?: boolean } }) =>
  crop.crop_key === "avocado" && !!(crop.boot.can_manage ?? crop.boot.can_plan);

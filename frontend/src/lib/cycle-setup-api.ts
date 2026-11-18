import { cropUsesCycles, isFlowerCrop, type CurrentCrop } from "@/lib/crops";
import { call, type Envelope } from "@/lib/frappe";

const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>("upande_production.api.cycle_setup." + name, args);

export interface AddCycleInput {
  unit: string;
  /** Sections with named crops: the crop first, then a variety of it. */
  field_crop?: string | null;
  variety?: string | null;
  protocol?: string | null;
  cycle_type?: string;
  start_date?: string | null;
  area_ha?: number | null;
  plant_count?: number | null;
  /** A cycle that is already in production. */
  existing?: boolean;
  planting_date?: string | null;
  current_stage?: string | null;
  /** Crops whose cycle has no variety name an item. */
  item?: string | null;
  /** Another crop's cycle that is already picking, with or without a stage to say so. */
  already_harvesting?: boolean;
  last_flowering_date?: string | null;
  last_harvest_date?: string | null;
  /** kg per year (season). */
  last_season_yield_kg?: number | null;
}

/** Warnings (a block over its area or trees) come back with the saved cycle: they never refuse it. */
export const addCycle = (data: AddCycleInput) => rpc<{ name: string; warnings: string[] }>("add_cycle", { data });

/** The template follows the crop: avocado keeps its tree columns, other crops get item, protocol and start date. */
export const importTemplate = (crop?: string) =>
  rpc<{ filename: string; columns: string[]; content: string }>("import_template", crop ? { crop } : {});

export interface ImportRow {
  row: number;
  raw: Record<string, string>;
  values: {
    unit: string | null;
    variety: string | null;
    field_crop?: string | null;
    item?: string | null;
    protocol?: string | null;
    already_harvesting?: number;
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

export interface CycleEdit {
  name: string;
  unit: string;
  crop: string;
  field_crop?: string | null;
  variety: string | null;
  item: string | null;
  protocol: string | null;
  start_date: string;
  planting_date: string | null;
  area_ha: number | null;
  plant_count: number | null;
  expected_harvest_start: string | null;
  expected_harvest_end: string | null;
  status: string;
  notes: string | null;
  existing_cycle: 0 | 1 | boolean;
  /** Once a cycle has tasks its block is fixed. */
  has_tasks: boolean;
}

export const getCycleForEdit = (name: string) => rpc<CycleEdit>("get_cycle_for_edit", { name });

export interface UpdateCycleInput {
  unit?: string;
  variety?: string | null;
  protocol?: string | null;
  start_date?: string | null;
  planting_date?: string | null;
  area_ha?: number | null;
  plant_count?: number | null;
  expected_harvest_start?: string | null;
  expected_harvest_end?: string | null;
  status?: string;
  notes?: string | null;
}

/** `notes` say what the change did to planning (a running cycle re-plans from today); `warnings` are capacity. */
export const updateCycle = (name: string, data: UpdateCycleInput) =>
  rpc<{ name: string; warnings: string[]; notes: string[] }>("update_cycle", { name, data });

type CropRef = CurrentCrop;

/** Whoever may manage production can add, import and edit cycles. */
export const canManageCycles = (crop: Pick<CurrentCrop, "boot">) => !!(crop.boot.can_manage ?? crop.boot.can_plan);

/**
 * The Add crop cycle dialog (existing cycles and bulk import, and new ones too for avocado) covers every crop that
 * runs in cycles. Flower crops keep their own greenhouse screens; bees and fish have no cycles.
 */
export const canAddCycle = (crop: CropRef) => cropUsesCycles(crop) && !isFlowerCrop(crop) && canManageCycles(crop);

/** Avocado has the full dialog, new cycles included; other crops add a new cycle in their own form. */
export const hasNewCycleTab = (crop: Pick<CurrentCrop, "crop_key">) => crop.crop_key === "avocado";

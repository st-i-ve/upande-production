import { cropUsesCycles, isFlowerCrop, type CurrentCrop } from "@/lib/crops";
import { call, type Envelope } from "@/lib/frappe";

const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>("upande_production.api.cycle_setup." + name, args);

export interface AddCycleInput {
  unit: string;
  /** Sections with named crops: the crop first, then a variety of it. */
  field_crop?: string | null;
  sub_crop?: string | null;
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
  sub_crop?: string | null;
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
  /** A change already waiting for a manager: nothing else can be sent until it is decided. */
  pending_request?: PendingRequest | null;
}

export type ChangeAction = "Edit" | "Delete";
export type ChangeStatus = "Pending" | "Approved" | "Rejected" | "Sent Back";

/** The fields of a request that changed: what they were and what they would become. */
export type FieldChanges = Record<string, { old: string | number | null; new: string | number | null }>;

/** What a cycle row and its edit form carry about the open request. */
export interface PendingRequest {
  name: string;
  requested_by: string;
  action: ChangeAction;
  changes: FieldChanges;
}

export interface CycleChangeRequest {
  name: string;
  cycle: string;
  action: ChangeAction;
  status: ChangeStatus;
  reason: string | null;
  changes: FieldChanges;
  requested_by: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  /** Set once approved over a newer value on the cycle. */
  stale: 0 | 1 | boolean;
  creation: string;
  crop: string | null;
  unit: string | null;
  cycle_title: string | null;
}

export const getCycleForEdit = (name: string) => rpc<CycleEdit>("get_cycle_for_edit", { name });

export interface UpdateCycleInput {
  unit?: string;
  sub_crop?: string | null;
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
  /** A person who may not change setup directly says why; it goes with the request. */
  reason?: string;
}

/** `notes` say what the change did to planning (a running cycle re-plans from today); `warnings` are capacity. */
export const updateCycle = (name: string, data: UpdateCycleInput) =>
  rpc<{ name: string; warnings: string[]; notes: string[] } | { request: string; pending: true }>("update_cycle", { name, data });

/** A manager deletes at once ({deleted}); anyone else sends a request with a reason ({request, pending}). */
export const deleteCycle = (name: string, reason?: string) =>
  rpc<{ deleted: string } | { request: string; pending: true }>("delete_cycle", { name, reason });

export const listCycleChanges = (status?: ChangeStatus | null, crop?: string | null) =>
  rpc<{ rows: CycleChangeRequest[] }>("list_cycle_changes", { ...(status ? { status } : {}), ...(crop ? { crop } : {}) });

/** A request made over a value that has since changed is refused until `applyAnyway` is 1. */
export const approveCycleChange = (name: string, applyAnyway: 0 | 1 = 0) =>
  rpc<{ request: string }>("approve_cycle_change", { name, apply_anyway: applyAnyway });

export const sendBackCycleChange = (name: string, note: string) => rpc<{ request: string }>("send_back_cycle_change", { name, note });
export const rejectCycleChange = (name: string, note: string) => rpc<{ request: string }>("reject_cycle_change", { name, note });
export const resubmitCycleChange = (name: string, data: UpdateCycleInput, reason?: string) =>
  rpc<{ request: string; pending: true }>("resubmit_cycle_change", { name, data, ...(reason !== undefined ? { reason } : {}) });
export const withdrawCycleChange = (name: string) => rpc<{ request: string }>("withdraw_cycle_change", { name });

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

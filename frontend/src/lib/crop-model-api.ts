/**
 * Settings, Crop model: a crop's model parameters. The server describes the editor from the Production Crop
 * doctype (groups, fields, child tables) and holds the values; the UI keeps no parameter of its own.
 */

import { call } from "@/lib/frappe";

export interface ModelField {
  fieldname: string;
  label: string;
  fieldtype: "Data" | "Int" | "Float" | "Currency" | "Percent" | "Check" | "Select" | "Small Text";
  options: string | null;
  description: string | null;
  /** Another field of the crop that must be on for this one to show. */
  depends_on: string | null;
  value: string | number | null;
}

export interface ModelColumn {
  fieldname: string;
  label: string;
  fieldtype: string;
  options: string | null;
}

export interface ModelTable {
  fieldname: string;
  label: string;
  description: string | null;
  columns: ModelColumn[];
  rows: Record<string, string | number | null>[];
}

export interface ModelGroup {
  label: string;
  fields: ModelField[];
  tables: ModelTable[];
}

export interface CropModel {
  crop: string;
  crop_key: string;
  can_edit?: boolean;
  groups: ModelGroup[];
}

const PREFIX = "upande_production.api.cropmodel.";

export const getCropModel = (crop: string) => call<CropModel>(PREFIX + "get_crop_model", { crop });

export const saveCropModel = (crop: string, data: Record<string, unknown>) =>
  call<CropModel>(PREFIX + "save_crop_model", { crop, data: JSON.stringify(data) });

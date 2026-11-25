/**
 * Typed wrappers for `upande_production.api.field_crops`: the named crops inside a farm section
 * (Cabbage, Maize, Onion ... inside Fruits & Vegetables), each with its product item and harvest unit.
 * Every function resolves to an `Envelope<T>`; check `isError(r)` first.
 */

import { call, type Envelope } from "@/lib/frappe";

const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>("upande_production.api.field_crops." + name, args);

export interface CropGroup {
  name: string;
  parent: string | null;
  sort_order: number;
}

export interface SubCrop {
  name: string;
  sub_crop_name?: string;
  harvest_uom: string;
  product?: string | null;
  enabled?: 0 | 1 | boolean;
}

export interface FieldCrop {
  name: string;
  crop_name: string;
  crop_group: string | null;
  scientific_name?: string | null;
  sub_crops?: SubCrop[];
  product: string | null;
  product_name?: string | null;
  harvest_uom: string;
  color: string | null;
  enabled: 0 | 1 | boolean;
  /** How many varieties belong to it (list_field_crops only). */
  varieties?: number;
}

export const listFieldCrops = (crop: string) => rpc<{ field_crops: FieldCrop[] }>("list_field_crops", { crop });

export interface FieldCropInput {
  /** Set to edit; the name of a crop in use is fixed. */
  name?: string;
  crop_name?: string;
  crop_group?: string | null;
  scientific_name?: string | null;
  product?: string | null;
  harvest_uom?: string;
  color?: string | null;
  enabled?: 0 | 1;
}

export const saveFieldCrop = (data: FieldCropInput) => rpc<{ name: string }>("save_field_crop", { data });

/** Every group and every crop, whatever the section (the Crops tab). */
export const getCropTree = () => rpc<{ groups: CropGroup[]; crops: FieldCrop[] }>("get_crop_tree");

export interface CropGroupInput {
  name?: string;
  group_name?: string;
  parent?: string | null;
  sort_order?: number;
}

export const saveCropGroup = (data: CropGroupInput) => rpc<{ name: string }>("save_crop_group", { data });

export interface SubCropInput {
  name?: string;
  sub_crop_name?: string;
  field_crop?: string;
  product?: string | null;
  harvest_uom?: string;
  enabled?: 0 | 1;
}

export const saveSubCrop = (data: SubCropInput) => rpc<{ name: string }>("save_sub_crop", { data });

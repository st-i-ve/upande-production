/**
 * Typed wrappers for `upande_production.api.field_crops`: the named crops inside a farm section
 * (Cabbage, Maize, Onion ... inside Fruits & Vegetables), each with its product item and harvest unit.
 * Every function resolves to an `Envelope<T>`; check `isError(r)` first.
 */

import { call, type Envelope } from "@/lib/frappe";

const rpc = <T>(name: string, args: Record<string, unknown> = {}): Promise<Envelope<T>> =>
  call<T>("upande_production.api.field_crops." + name, args);

export interface FieldCrop {
  name: string;
  crop_name: string;
  production_crop: string;
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
  /** Set to edit; the name and section of a crop in use are fixed. */
  name?: string;
  crop_name?: string;
  production_crop?: string;
  product?: string | null;
  harvest_uom?: string;
  color?: string | null;
  enabled?: 0 | 1;
}

export const saveFieldCrop = (data: FieldCropInput) => rpc<{ name: string }>("save_field_crop", { data });

/**
 * Data for the flower-crop screens (greenhouse -> bed). The same endpoints the legacy Crop Production
 * desk screens use: `frappe.client.get_list` for the doctype lists and the Crop Cycle Dashboard block,
 * and `farm_map.map_payload` for the Farm Map. Same contract as lib/api.ts: never throws, check `isError`.
 */

import { call, isError, type Envelope } from "@/lib/frappe";

export type Row = Record<string, unknown>;

export async function getList(
  doctype: string,
  fields: string[],
  opts: { filters?: unknown; order_by?: string; limit?: number } = {},
): Promise<Envelope<{ rows: Row[] }>> {
  const r = await call<Row[]>("frappe.client.get_list", {
    doctype,
    fields,
    filters: opts.filters,
    order_by: opts.order_by,
    limit_page_length: opts.limit ?? 0,
  });
  if (isError(r)) return r;
  return { rows: Array.isArray(r) ? (r as Row[]) : [] };
}

export interface MapPlanting {
  cycle: string;
  variety: string;
  area: number;
  plants: number;
  stage: string;
  age_weeks: number | null;
  week_stems: number;
  ahead_stems: number;
}

export interface MapHouse {
  name: string;
  label: string;
  plantings: MapPlanting[];
  area: number;
  plants: number;
  week_stems: number;
  ahead_stems: number;
  surge: number | null;
  beds: number;
  varieties: string[];
  /** GeoJSON Polygon coordinates ([ring, ...]) for each polygon of the house. */
  polygons: number[][][][];
  has_geometry: boolean;
  empty?: boolean;
}

export interface MapPayload {
  greenhouses: MapHouse[];
  totals: { houses: number; empty: number; area: number; plants: number; week_stems: number; annual: number };
  bounds?: [[number, number], [number, number]] | null;
  now_week: number;
  year: number;
  geometry_source: string;
}

export const farmMap = () => call<MapPayload>("upande_production.farm_map.map_payload");

/** The legacy desk route for a doctype: /desk/<slug>. */
export const classicList = (doctype: string) => `/desk/${doctype.toLowerCase().replace(/ /g, "-")}`;
export const classicDoc = (doctype: string, name: string) => `${classicList(doctype)}/${encodeURIComponent(name)}`;

// -- Blocks, beds and cycles in one form (greenhouse- or block-based) ---------------------------

export interface FlowerUnit {
  name: string;
  label: string;
  farm: string | null;
  beds: number;
  plants: number;
  area_planted: number;
  gross_area: number;
  varieties: number;
  cycles: number;
}

export interface FlowerCycle {
  name: string;
  unit: string | null;
  unit_kind: "block" | "greenhouse" | null;
  farm: string | null;
  /** The item code; `variety_name` is its item_name, which is what is shown. */
  variety: string | null;
  variety_name: string | null;
  product: string | null;
  status: string | null;
  planting_date: string | null;
  plants: number;
  area: number;
  beds: number;
}

export interface FlowerData {
  mode: "block" | "greenhouse";
  units: FlowerUnit[];
  cycles: FlowerCycle[];
  farms: { farm: string; units: number; beds: number; plants: number; area: number }[];
  totals: {
    units: number; beds: number; plants: number; area_planted: number; gross_area: number;
    cycles: number; active: number; varieties: number;
  };
}

export const flowerData = (crop: string) => call<FlowerData>("upande_production.api.flowers.flower_data", { crop });

/** {item code: item_name}: the lists that carry only codes (protocols) show the names. */
export async function itemNames(codes: string[]): Promise<Record<string, string>> {
  if (!codes.length) return {};
  const r = await call<Record<string, string>>("upande_production.api.flowers.item_names", { codes: JSON.stringify(codes) });
  return isError(r) ? {} : (r as Record<string, string>);
}

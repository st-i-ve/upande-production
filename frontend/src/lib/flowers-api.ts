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

export interface GreenhouseRow {
  name: string;
  farm: string | null;
  number_of_beds: number | null;
  number_of_plants: number | null;
  area_planted: number | null;
  gross_area: number | null;
  varieties: number | null;
}

export interface CycleRow {
  name: string;
  greenhouse: string | null;
  farm: string | null;
  variety: string | null;
  status: string | null;
  qty_planted: number | null;
  plants_standing: number | null;
  planted_area: number | null;
}

export async function getDashboardData(): Promise<Envelope<{ greenhouses: GreenhouseRow[]; cycles: CycleRow[] }>> {
  const [g, c] = await Promise.all([
    getList("Greenhouse", ["name", "farm", "number_of_beds", "number_of_plants", "area_planted", "gross_area", "varieties"]),
    getList("Crop Cycle", ["name", "greenhouse", "farm", "variety", "status", "qty_planted", "plants_standing", "planted_area"]),
  ]);
  if (isError(g)) return g;
  if (isError(c)) return c;
  return { greenhouses: g.rows as unknown as GreenhouseRow[], cycles: c.rows as unknown as CycleRow[] };
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

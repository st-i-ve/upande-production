/**
 * Typed client for the block cost breakdown (`api.blockcost`) and the block links check
 * (`api.production.block_links`).
 * Same contract as lib/api.ts: resolves to an `Envelope<T>`, never throws; check `isError(r)`.
 */

import { call } from "@/lib/frappe";

export interface BreakdownLabour {
  operation: string;
  qty_by_uom: { uom: string; qty: number }[];
  workers: number;
  /** Withheld (null) when the viewer cannot see pay. */
  pay: number | null;
}

export interface BreakdownInput {
  item_code: string;
  item_name?: string | null;
  item_group?: string | null;
  qty: number;
  uom: string;
  amount: number;
  per_ha?: number | null;
  /** Protocol quantity for the same item, when the operation's item is known. */
  planned_qty?: number | null;
}

export interface BreakdownOther {
  account: string;
  amount: number;
}

export interface BlockBreakdown {
  unit: string;
  area_ha?: number | null;
  labour: BreakdownLabour[];
  inputs: BreakdownInput[];
  other: BreakdownOther[];
  totals: { labour: number | null; inputs: number; other: number; total: number | null; per_ha?: number | null };
  budget: { erp_budget: number | null; actual_this_fy: number | null };
}

export interface BlockLink {
  unit: string;
  cost_center?: string | null;
  warehouse?: string | null;
  ok: boolean;
  problems: string[];
}

export const blockBreakdown = (unit: string, from_date?: string | null, to_date?: string | null) =>
  call<BlockBreakdown>("upande_production.api.blockcost.block_breakdown", { unit, from_date: from_date || null, to_date: to_date || null });

export const blockLinks = (crop: string) => call<{ rows: BlockLink[] }>("upande_production.api.production.block_links", { crop });

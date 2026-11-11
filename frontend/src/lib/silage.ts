/**
 * Pure helpers for the Silage page. No fetching, no React: tested on their own.
 *
 * The figures themselves come from the server (cost by kind, cost per kg, pit stock); these only
 * preview what the server will compute from what an operator is typing, check a form before it is
 * sent, and add up rows the page already holds.
 */

import type { InputRow, PitStockRow, SilageCycle, SilageStatus } from "@/lib/silage-api";

/** The statuses a draft cycle can be moved through by hand. Closed is what closing sets. */
export const OPEN_STATUSES: SilageStatus[] = ["Planned", "Growing", "Harvesting", "Ensiled"];

export function isOpen(c: Pick<SilageCycle, "docstatus">): boolean {
  return c.docstatus === 0;
}

function n(v: unknown): number | null {
  if (v === "" || v == null) return null;
  const x = typeof v === "number" ? v : Number(String(v).replace(/,/g, "").trim());
  return Number.isFinite(x) ? x : null;
}

/** Same rule as the server: workers x day rate when both are above zero, else the typed amount. */
export function activityLabour(workers: unknown, dayRate: unknown, typed: unknown): number {
  const w = n(workers) ?? 0;
  const r = n(dayRate) ?? 0;
  if (w > 0 && r > 0) return Math.round(w * r * 100) / 100;
  return Math.max(n(typed) ?? 0, 0);
}

/** total / kg, or null when nothing is ensiled. */
export function costPerKg(total: number | null | undefined, kg: unknown): number | null {
  const k = n(kg);
  if (total == null || k == null || k <= 0) return null;
  return total / k;
}

/** A rate for a label: two decimals under 100, whole shillings above. KES 4.26/kg */
export function perUnitLabel(v: number | null | undefined, unit = "kg"): string {
  if (v == null || !Number.isFinite(v)) return "—";
  const d = v < 100 ? 2 : 0;
  return `KES ${v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })}/${unit}`;
}

export function perKgLabel(v: number | null | undefined): string {
  return perUnitLabel(v, "kg");
}

export interface InputLine {
  item_code: string;
  qty: string;
}

/** Problems with an input issue before it is sent; empty when it can go. */
export function inputProblems(lines: InputLine[], warehouse: string): string[] {
  const out: string[] = [];
  if (!warehouse) out.push("Choose the store the inputs come out of.");
  const used = lines.filter((l) => l.item_code || l.qty);
  if (!used.length) out.push("Add at least one item.");
  const seen = new Set<string>();
  used.forEach((l, i) => {
    if (!l.item_code) out.push(`Line ${i + 1}: choose the item.`);
    const q = n(l.qty);
    if (q == null || q <= 0) out.push(`Line ${i + 1}: quantity must be above zero.`);
    if (l.item_code && seen.has(l.item_code)) out.push(`Line ${i + 1}: ${l.item_code} is already on another line.`);
    if (l.item_code) seen.add(l.item_code);
  });
  return out;
}

/** The lines the server should get: chosen items with a quantity, as numbers. */
export function inputPayload(lines: InputLine[]): { item_code: string; qty: number }[] {
  return lines
    .filter((l) => l.item_code && (n(l.qty) ?? 0) > 0)
    .map((l) => ({ item_code: l.item_code, qty: n(l.qty) as number }));
}

/** Problems with closing a cycle; empty when it can be closed. */
export function closeProblems(args: {
  ensiledKg: unknown;
  silageItem: string;
  pitWarehouse: string;
  draftInputs: string[];
  openAllocations: string[];
}): string[] {
  const out: string[] = [];
  const kg = n(args.ensiledKg);
  if (kg == null || kg <= 0) out.push("Enter the kilos ensiled.");
  if (!args.silageItem) out.push("Choose the silage item livestock will draw.");
  if (!args.pitWarehouse) out.push("Choose the pit the silage goes into.");
  if (args.draftInputs.length) out.push(`Submit or delete the draft input issues first: ${args.draftInputs.join(", ")}.`);
  if (args.openAllocations.length) out.push(`Close the open machine allocations first: ${args.openAllocations.join(", ")}.`);
  return out;
}

/** Inputs grouped by item: quantity and value issued, largest value first. */
export function inputsByItem(rows: InputRow[]): { item_code: string; item_name: string; qty: number; uom: string; amount: number }[] {
  const map = new Map<string, { item_code: string; item_name: string; qty: number; uom: string; amount: number }>();
  for (const r of rows) {
    const cur = map.get(r.item_code) ?? { item_code: r.item_code, item_name: r.item_name, qty: 0, uom: r.stock_uom, amount: 0 };
    cur.qty += Number(r.stock_qty) || 0;
    cur.amount += Number(r.amount) || 0;
    map.set(r.item_code, cur);
  }
  return [...map.values()].sort((a, b) => b.amount - a.amount);
}

/** Pit stock totals: kilos (Kg rows only, other units are not added to kilos) and value. */
export function pitTotals(rows: PitStockRow[]): { kg: number; value: number; pits: number } {
  let kg = 0;
  let value = 0;
  const pits = new Set<string>();
  for (const r of rows) {
    if (r.qty > 0) pits.add(r.warehouse);
    if ((r.stock_uom ?? "Kg") === "Kg") kg += r.qty;
    value += r.stock_value;
  }
  return { kg, value, pits: pits.size };
}

/** Cycles still running (not closed, not cancelled). */
export function openCount(cycles: Pick<SilageCycle, "docstatus">[]): number {
  return cycles.filter(isOpen).length;
}

export type Tone = "ok" | "warn" | "quiet" | "info";

export function statusTone(s: SilageStatus): Tone {
  if (s === "Closed") return "ok";
  if (s === "Cancelled") return "quiet";
  if (s === "Ensiled" || s === "Harvesting") return "warn";
  return "info";
}

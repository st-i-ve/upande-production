import type { Crop } from "@/lib/api";

/** Does this section have named crops inside it (Fruits & Vegetables)? Avocado and the rest: no. */
export const hasFieldCrops = (crop?: Pick<Crop, "has_field_crops" | "field_crops"> | null): boolean =>
  !!crop && (!!Number(crop.has_field_crops ?? 0) || (crop.field_crops?.length ?? 0) > 0);

/** "Rose · Spray rose (Red Naomi)": a cycle or task as the screens name it; whichever parts are missing are left out. */
export function cropLabel(fieldCrop?: string | null, variety?: string | null, label?: string | null, subCrop?: string | null): string {
  if (label) return label;
  const crop = fieldCrop && subCrop ? `${fieldCrop} · ${subCrop}` : fieldCrop;
  if (crop && variety) return `${crop} (${variety})`;
  return crop || variety || "";
}

/** The sub-crops of one crop in a list of crops (empty when it has none). */
export const subCropsOf = (crops: { name: string; sub_crops?: { name: string; harvest_uom: string }[] }[] | undefined, crop: string) =>
  crops?.find((c) => c.name === crop)?.sub_crops ?? [];

/** Crop picker options, headed by their crop group; disabled crops are left out unless asked for. */
export function cropPickerOptions(
  crops: { name: string; crop_name: string; crop_group?: string | null; enabled?: 0 | 1 | boolean }[] | undefined,
  { includeDisabled = false }: { includeDisabled?: boolean } = {},
): { value: string; label: string; group?: string }[] {
  return (crops ?? [])
    .filter((c) => includeDisabled || c.enabled === undefined || !!Number(c.enabled))
    .map((c) => ({ value: c.name, label: c.crop_name, ...(c.crop_group ? { group: c.crop_group } : {}) }));
}

/**
 * Per-group roll-up of per-crop rows: one line per (group, unit), sorted by group then unit. Crops with different
 * units never add together; a crop with no group rolls up under "Other".
 */
export function groupTotals(
  rows: { field_crop: string | null; uom: string | null; qty: number }[],
  crops: { name: string; crop_group?: string | null }[] | undefined,
): { group: string; uom: string | null; qty: number }[] {
  const groupOf = new Map((crops ?? []).map((c) => [c.name, c.crop_group || "Other"]));
  const sums = new Map<string, { group: string; uom: string | null; qty: number }>();
  for (const r of rows) {
    const group = (r.field_crop && groupOf.get(r.field_crop)) || "Other";
    const key = `${group}\u0000${r.uom ?? ""}`;
    const cur = sums.get(key) ?? { group, uom: r.uom, qty: 0 };
    cur.qty += r.qty;
    sums.set(key, cur);
  }
  return [...sums.values()].sort((a, b) => a.group.localeCompare(b.group) || (a.uom ?? "").localeCompare(b.uom ?? ""));
}

/** One line per (crop, unit): "Cabbage 1,200 Pieces | Potato 3,400 Kg". Units are never added together. */
export function cropTotalsText(rows: { field_crop: string | null; uom: string | null; qty: number }[], fmt: (n: number) => string): string {
  return rows
    .filter((r) => r.qty)
    .map((r) => `${r.field_crop ?? "Other"} ${fmt(r.qty)}${r.uom ? ` ${r.uom}` : ""}`)
    .join(" | ");
}

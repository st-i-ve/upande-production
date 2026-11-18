import type { Crop } from "@/lib/api";

/** Does this section have named crops inside it (Fruits & Vegetables)? Avocado and the rest: no. */
export const hasFieldCrops = (crop?: Pick<Crop, "has_field_crops" | "field_crops"> | null): boolean =>
  !!crop && (!!Number(crop.has_field_crops ?? 0) || (crop.field_crops?.length ?? 0) > 0);

/** "Cabbage (Gloria F1)": a cycle or task as the screens name it; the variety alone, or the crop alone, when the other is missing. */
export function cropLabel(fieldCrop?: string | null, variety?: string | null, label?: string | null): string {
  if (label) return label;
  if (fieldCrop && variety) return `${fieldCrop} (${variety})`;
  return fieldCrop || variety || "";
}

/** One line per (crop, unit): "Cabbage 1,200 Pieces | Potato 3,400 Kg". Units are never added together. */
export function cropTotalsText(rows: { field_crop: string | null; uom: string | null; qty: number }[], fmt: (n: number) => string): string {
  return rows
    .filter((r) => r.qty)
    .map((r) => `${r.field_crop ?? "Other"} ${fmt(r.qty)}${r.uom ? ` ${r.uom}` : ""}`)
    .join(" | ");
}

import type { FieldChanges } from "@/lib/cycle-setup-api";

export const FIELD_LABELS: Record<string, string> = {
  unit: "Block",
  crop: "Crop",
  field_crop: "Crop",
  sub_crop: "Sub-crop",
  variety: "Variety",
  item: "Item",
  protocol: "Protocol",
  start_date: "Start date",
  planting_date: "Planting date",
  area_ha: "Area (ha)",
  plant_count: "Plant count",
  expected_harvest_start: "Harvest from",
  expected_harvest_end: "Harvest until",
  status: "Status",
  notes: "Notes",
};

const show = (v: string | number | null | undefined) => (v === null || v === undefined || v === "" ? "none" : String(v));

/** One line per changed field: "Area (ha): 10 → 12". */
export function changeLines(changes: FieldChanges | null | undefined): { field: string; label: string; old: string; next: string }[] {
  return Object.entries(changes ?? {}).map(([field, c]) => ({ field, label: FIELD_LABELS[field] ?? field, old: show(c.old), next: show(c.new) }));
}

export const changeSummary = (changes: FieldChanges | null | undefined) =>
  changeLines(changes).map((l) => `${l.label}: ${l.old} → ${l.next}`).join("\n");

import { groupTotals } from "@/lib/field-crops";
import { qty } from "@/lib/format";

/** One line per (crop group, unit) from per-crop rows; crops in different units are never added together. */
export function GroupRollup({
  rows,
  crops,
  label = "By crop group",
}: {
  rows: { field_crop: string | null; uom: string | null; qty: number }[];
  crops?: { name: string; crop_group?: string | null }[];
  label?: string;
}) {
  if (!crops?.some((c) => c.crop_group)) return null;
  const lines = groupTotals(rows, crops).filter((g) => g.qty);
  if (!lines.length) return null;
  return (
    <ul className="mt-3 flex flex-col gap-1 border-t border-[var(--sd-line-soft)] pt-3 text-[12.5px]" aria-label={label}>
      {lines.map((g) => (
        <li key={`${g.group}-${g.uom}`} data-testid="group-rollup" className="flex gap-3 text-[var(--sd-muted)]">
          <span className="flex-1 font-medium text-[var(--sd-ink)]">{g.group}</span>
          <span className="tabular-nums">{qty(g.qty)} {g.uom ?? ""}</span>
        </li>
      ))}
    </ul>
  );
}

import { useMemo } from "react";
import { useWidth } from "@/components/forecast/chart-utils";
import type { SeasonOutlook, TreemapBlock, VsCurveBand } from "@/lib/avocado-api";
import { kes, qty } from "@/lib/format";
import { cn } from "@/lib/utils";
import { EmptyNote, SectionCard, tonnes } from "./forecast-ui";

export interface Rect<T> { item: T; x: number; y: number; w: number; h: number }

/** Squarified treemap (Bruls et al.): areas proportional to `value`, aspect ratios kept near 1. */
export function squarify<T>(items: T[], value: (t: T) => number, W: number, H: number): Rect<T>[] {
  const list = items.filter((i) => value(i) > 0).sort((a, b) => value(b) - value(a));
  const total = list.reduce((s, i) => s + value(i), 0);
  if (!list.length || total <= 0 || W <= 0 || H <= 0) return [];
  const scale = (W * H) / total;
  const out: Rect<T>[] = [];
  let x = 0, y = 0, w = W, h = H;
  let row: T[] = [];
  const area = (t: T) => value(t) * scale;
  const worst = (r: T[], side: number) => {
    const s = r.reduce((a, t) => a + area(t), 0);
    const mx = Math.max(...r.map(area)), mn = Math.min(...r.map(area));
    return Math.max((side * side * mx) / (s * s), (s * s) / (side * side * mn));
  };
  const flush = () => {
    if (!row.length) return;
    const s = row.reduce((a, t) => a + area(t), 0);
    if (w >= h) {
      const rw = s / h;
      let cy = y;
      for (const t of row) { const ih = area(t) / rw; out.push({ item: t, x, y: cy, w: rw, h: ih }); cy += ih; }
      x += rw; w -= rw;
    } else {
      const rh = s / w;
      let cx = x;
      for (const t of row) { const iw = area(t) / rh; out.push({ item: t, x: cx, y, w: iw, h: rh }); cx += iw; }
      y += rh; h -= rh;
    }
    row = [];
  };
  for (const t of list) {
    const side = Math.min(w, h);
    if (!row.length || worst([...row, t], side) <= worst(row, side)) row.push(t);
    else { flush(); row.push(t); }
  }
  flush();
  return out;
}

export const bandLabel = (bands: VsCurveBand[], i: number) =>
  i === 0 ? `under ${bands[0].to_pct}%` : bands[i].to_pct == null ? `${bands[i - 1].to_pct}%+` : `${bands[i - 1].to_pct}–${bands[i].to_pct}%`;

export function BandLegend({ bands }: { bands: VsCurveBand[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-[var(--sd-quiet)]" aria-label="Shade legend">
      <span>Kg per tree against the age curve:</span>
      {bands.map((b, i) => (
        <span key={i} className="inline-flex items-center gap-1.5">
          <i className="inline-block h-3 w-5 rounded-[4px] border border-black/5" style={{ background: b.color }} />
          {bandLabel(bands, i)}
        </span>
      ))}
    </div>
  );
}

const H = 300;

export function BlocksTreemap({
  data,
  selected,
  onSelect,
}: {
  data: SeasonOutlook;
  selected: string | null;
  onSelect: (block: string | null) => void;
}) {
  const [ref, width] = useWidth(300, 900);
  const tm = data.treemap;
  const rects = useMemo(() => squarify<TreemapBlock>(tm.blocks, (b) => b.expected_kg, width, H), [tm.blocks, width]);
  const sel = tm.blocks.find((b) => b.block === selected) ?? null;

  return (
    <SectionCard
      testId="outlook-treemap"
      title="Blocks"
      description="Area is forecast tonnage. Shade is the block's own kilograms per tree against what the estate curve expects at that age — a counted block sitting far above its age band is the one to re-walk."
      tools={
        selected ? (
          <button
            type="button"
            onClick={() => onSelect(null)}
            className="rounded-full bg-[var(--sd-ink)]/[0.06] px-3 py-1 text-[12px] font-medium hover:bg-[var(--sd-ink)]/10"
          >
            {selected} ×
          </button>
        ) : undefined
      }
    >
      {!tm.blocks.length ? (
        <EmptyNote big>
          {tm.without_crop
            ? `No block carries a crop — ${tm.without_crop} blocks, none bearing.`
            : "No blocks on file — the orchard record is empty."}
        </EmptyNote>
      ) : (
        <div className="flex flex-col gap-3">
          <div ref={ref} className="relative w-full" style={{ height: H }}>
            {rects.map(({ item: b, x, y, w, h }) => (
              <button
                key={b.block}
                type="button"
                onClick={() => onSelect(selected === b.block ? null : b.block)}
                aria-pressed={selected === b.block}
                title={`${b.block}${b.farm ? ` · ${b.farm}` : ""}\n${tonnes(b.expected_kg)}${b.vs_curve_pct != null ? ` · ${b.vs_curve_pct}% of curve` : ""}\n${b.basis}`}
                className={cn(
                  "absolute overflow-hidden rounded-[10px] border-2 border-[var(--sd-card)] p-2 text-left transition-[filter,box-shadow] hover:brightness-95",
                  selected === b.block && "ring-2 ring-[var(--sd-ink)] ring-offset-0",
                  selected && selected !== b.block && "opacity-60",
                )}
                style={{
                  left: x, top: y, width: w, height: h,
                  background: b.band.color,
                  color: b.band.dark_text ? "var(--sd-ink)" : "#fff",
                }}
              >
                {w > 56 && h > 34 && (
                  <>
                    <div className="truncate text-[13px] font-semibold leading-tight">{b.block}</div>
                    <div className="text-[12px] leading-tight opacity-80 tabular-nums">{tonnes(b.expected_kg)}</div>
                  </>
                )}
              </button>
            ))}
          </div>
          <BandLegend bands={tm.bands} />
          {sel && (
            <div className="rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] px-4 py-3 text-[13px] text-[var(--sd-text)]" data-testid="block-detail">
              <b>{sel.block}</b>
              {sel.farm ? ` · ${sel.farm}` : ""} — {tonnes(sel.expected_kg)} ({kes(sel.value_kes)}), {qty(sel.bearing_trees)} bearing of {qty(sel.live_trees)} trees
              {sel.age != null ? `, age ${sel.age}` : ""}
              {sel.vs_curve_pct != null ? `, ${sel.vs_curve_pct}% of the age curve` : ""}. <span className="text-[var(--sd-quiet)]">{sel.basis}</span>
            </div>
          )}
        </div>
      )}
    </SectionCard>
  );
}

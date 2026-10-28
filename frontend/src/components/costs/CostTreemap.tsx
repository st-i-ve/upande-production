import { useMemo } from "react";
import type { BlockCostRow } from "@/lib/api";
import { kes, qty } from "@/lib/format";
import { useWidth } from "@/components/forecast/chart-utils";
import { buildTree } from "@/components/costs/CostsTable";
import { squarify, type TreeItem } from "@/components/costs/treemap";

const HEIGHT = 340;
const GAP = 2;
const RED = "#c1272d";

/** Blend a colour toward white: t = 0 white ... 1 full colour. */
function tint(hex: string, t: number): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.length === 4 ? "#" + [...hex.slice(1)].map((c) => c + c).join("") : hex);
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  const mix = (c: number) => Math.round(255 + (c - 255) * t);
  return `rgb(${mix(n >> 16)}, ${mix((n >> 8) & 255)}, ${mix(n & 255)})`;
}

/**
 * Treemap of where the money goes, like SCP's chemical stock map: one box per
 * group sized by cost, blocks inside it. Colour is margin: crop accent where a
 * block earned more than it cost, red where it did not; deeper = further from
 * break-even. Without pay access, size falls back to harvest quantity and the
 * colour is neutral.
 */
export function CostTreemap({ rows, canSeePay, accent }: { rows: BlockCostRow[]; canSeePay: boolean; accent: string }) {
  const [ref, width] = useWidth();
  const metric = (r: BlockCostRow) => (canSeePay ? r.total_cost || 0 : r.harvest_qty || 0);

  const groups = useMemo(() => {
    const tree = buildTree(rows);
    return tree
      .map((n) => {
        const kids = n.children.length ? n.children.map((c) => c.row) : [n.row];
        return { row: n.row, kids };
      })
      .filter((g) => metric(g.row) > 0 || g.kids.some((k) => metric(k) > 0));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, canSeePay]);

  if (!groups.length) {
    return (
      <div className="flex h-[160px] items-center justify-center rounded-[var(--sd-radius-lg)] border border-dashed border-[var(--sd-line)] text-[13px] text-[var(--sd-quiet)]">
        Nothing to size yet for this period.
      </div>
    );
  }

  const top: TreeItem<(typeof groups)[number]>[] = groups.map((g) => ({
    value: g.kids.reduce((t, k) => t + metric(k), 0) || metric(g.row),
    data: g,
  }));
  const tiles = squarify(top, 0, 0, width, HEIGHT);
  const maxAbs = Math.max(1, ...rows.filter((r) => r.margin != null).map((r) => Math.abs(r.margin as number)));

  const colour = (r: BlockCostRow) => {
    if (!canSeePay || r.margin == null) return tint(accent, 0.35);
    const k = Math.min(1, Math.abs(r.margin) / maxAbs);
    return tint(r.margin < 0 ? RED : accent, 0.25 + 0.65 * Math.sqrt(k));
  };

  return (
    <div ref={ref} className="w-full">
      <div className="relative w-full overflow-hidden rounded-[var(--sd-radius-lg)]" style={{ height: HEIGHT }} data-testid="cost-treemap">
        {tiles.map((t) => {
          const g = t.item.data;
          const inner = squarify(
            g.kids.map((k) => ({ value: metric(k), data: k })),
            0,
            0,
            Math.max(0, t.w - GAP * 2),
            Math.max(0, t.h - GAP * 2 - 18),
          );
          return (
            <div
              key={g.row.unit}
              className="absolute overflow-hidden bg-[var(--sd-card)]"
              style={{ left: t.x, top: t.y, width: t.w, height: t.h, padding: GAP }}
            >
              {t.w > 60 && t.h > 30 && (
                <div className="h-[18px] truncate px-1 text-[10.5px] font-medium uppercase tracking-[0.08em] text-[var(--sd-quiet)]">
                  {g.row.unit}
                </div>
              )}
              <div className="relative" style={{ width: t.w - GAP * 2, height: Math.max(0, t.h - GAP * 2 - 18) }}>
                {inner.map((b) => {
                  const r = b.item.data;
                  return (
                    <div
                      key={r.unit}
                      data-testid={`tile-${r.unit}`}
                      title={`${r.unit}: ${canSeePay ? `cost ${kes(r.total_cost)}, margin ${kes(r.margin)}` : `${qty(r.harvest_qty)} harvested`}`}
                      className="absolute overflow-hidden rounded-[6px] p-1.5 text-[11px] leading-tight text-[var(--sd-ink)]"
                      style={{ left: b.x, top: b.y, width: Math.max(0, b.w - 1.5), height: Math.max(0, b.h - 1.5), background: colour(r) }}
                    >
                      {b.w > 54 && b.h > 28 && (
                        <>
                          <div className="truncate font-medium">{r.unit}</div>
                          {b.h > 44 && (
                            <div className="truncate tabular-nums opacity-70">
                              {canSeePay ? kes(r.total_cost) : `${qty(r.harvest_qty)} kg`}
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-4 text-[11.5px] text-[var(--sd-muted)]">
        <span>{canSeePay ? "Size = total cost" : "Size = harvest quantity"}</span>
        {canSeePay && (
          <>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: tint(accent, 0.8) }} /> Profit
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: tint(RED, 0.8) }} /> Loss
            </span>
          </>
        )}
      </div>
    </div>
  );
}

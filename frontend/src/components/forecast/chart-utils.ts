import { useEffect, useRef, useState } from "react";

/** Track the width of a chart's container so the SVG is drawn at 1:1. */
export function useWidth(min = 320, initial = 880) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(initial);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const set = () => setWidth(Math.max(min, el.clientWidth || initial));
    set();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", set);
      return () => window.removeEventListener("resize", set);
    }
    const ro = new ResizeObserver(set);
    ro.observe(el);
    return () => ro.disconnect();
  }, [min, initial]);
  return [ref, width] as const;
}

/** Round tick values spanning [lo, hi], always including 0 when it is in range. */
export function niceTicks(lo: number, hi: number, target = 5): number[] {
  if (!(hi > lo)) {
    hi = lo + 1;
  }
  const rough = (hi - lo) / Math.max(1, target);
  const mag = Math.pow(10, Math.floor(Math.log10(rough)));
  const norm = rough / mag;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;
  const start = Math.floor(lo / step) * step;
  const out: number[] = [];
  for (let v = start; v <= hi + step * 0.5; v += step) out.push(Math.round(v / step) * step);
  return out;
}

/** 1,200,000 -> 1.2M, 45,000 -> 45K, for axis labels. */
export function compact(n: number): string {
  const a = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  const trim = (v: number) => String(Math.round(v * 10) / 10);
  if (a >= 1e9) return `${sign}${trim(a / 1e9)}B`;
  if (a >= 1e6) return `${sign}${trim(a / 1e6)}M`;
  if (a >= 1e3) return `${sign}${trim(a / 1e3)}K`;
  return `${sign}${trim(a)}`;
}

export function clip(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}

/** A coloured key for a chart: swatch + label. */
export const SERIES = {
  forecast: "var(--sd-data-indigo)",
  actual: "var(--sd-data-green)",
  committed: "var(--sd-data-amber)",
  positive: "var(--sd-sev-moderate)",
  negative: "var(--sd-sev-critical)",
} as const;

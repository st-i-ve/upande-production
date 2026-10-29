/**
 * KPI colour bands. The server owns them (Production Settings > Bands, `api.production.get_bands`) and
 * sends them in each page's payload as `bands`; the UI only matches a value against the rows it was sent
 * and never keeps a threshold of its own. A row covers `min <= value < max`; `max: null` has no upper limit.
 */

import { useEffect, useState } from "react";
import { call, isError } from "@/lib/frappe";

export type Severity = "Good" | "Watch" | "Critical";

export interface Band {
  band_set: string;
  label: string;
  metric: string;
  min: number;
  max: number | null;
  severity: Severity;
}

export type Bands = Record<string, Band[]>;

/** The row `value` falls in, or null (no value, no bands, or a gap). */
export function bandFor(bands: Bands | undefined | null, set: string, value: number | null | undefined): Band | null {
  if (value == null || !Number.isFinite(value)) return null;
  for (const b of bands?.[set] ?? []) if (value >= b.min && (b.max == null || value < b.max)) return b;
  return null;
}

/** KpiCard tone for a value; "default" when there is no band for it. */
export function bandTone(bands: Bands | undefined | null, set: string, value: number | null | undefined): "good" | "warning" | "critical" | "default" {
  const b = bandFor(bands, set, value);
  return !b ? "default" : b.severity === "Good" ? "good" : b.severity === "Watch" ? "warning" : "critical";
}

export const getBands = () => call<Bands>("upande_production.api.production.get_bands", {});

export const saveBands = (rows: Omit<Band, "label" | "metric">[] | Band[]) =>
  call<Bands>("upande_production.api.production.save_bands", { rows: JSON.stringify(rows) });

let cached: Promise<Bands | null> | null = null;

/** The bands for a component whose page payload does not carry them (fetched once, then shared).
 *  `undefined` until they arrive or when the call fails; callers treat that as "no colour". */
export function useBands(): Bands | undefined {
  const [bands, setBands] = useState<Bands | undefined>();
  useEffect(() => {
    let live = true;
    cached ??= getBands().then((r) => (isError(r) ? null : (r as Bands)));
    void cached.then((b) => {
      if (!b) cached = null;
      else if (live) setBands(b);
    });
    return () => {
      live = false;
    };
  }, []);
  return bands;
}

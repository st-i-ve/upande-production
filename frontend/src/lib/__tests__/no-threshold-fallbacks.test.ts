import { describe, expect, it } from "vitest";

const files = import.meta.glob("/src/**/*.{ts,tsx}", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
const src = (p: string) => files[`/src/${p}`] ?? "";

/** Thresholds live in the backend and arrive with each page; the UI keeps no copy or fallback. */
const FORBIDDEN: [string, RegExp][] = [
  ["pages/apiary/HiveInspections.tsx", /\?\? ?3\b/],
  ["pages/apiary/HiveInspections.tsx", /queenright_pct < ?90/],
  ["pages/apiary/HoneyHarvest.tsx", /\?\? ?20\b/],
  ["pages/apiary/HoneyHarvest.tsx", /grade_a_pct < ?60/],
  ["components/apiary/InspectionDialog.tsx", /\* ?0\.67/],
  ["pages/aquaculture/PondBatches.tsx", /< ?90/],
  ["components/aquaculture/batch-card.tsx", /survival_pct < ?90|sample_age_days > ?10/],
  ["pages/aquaculture/WaterQuality.tsx", /\?\? ?4\b|\(tilapia\)/],
  ["components/fv/fv-format.ts", /pct < ?(50|90)|pct <= ?125|MM_LEGEND/],
  ["components/forecast/AccuracyTable.tsx", /a <= ?(10|25)/],
  ["pages/Forecast.tsx", /more than 25%|more than 10%/],
  ["components/avocado/outlook-cards.tsx", /k\.value (>=|<) ?90/],
];

describe("no business thresholds in the desk", () => {
  it.each(FORBIDDEN)("%s has no %s", (file, pattern) => {
    expect(src(file).length).toBeGreaterThan(0);
    expect(src(file)).not.toMatch(pattern);
  });
});

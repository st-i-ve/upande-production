import { describe, expect, it } from "vitest";

/**
 * The avocado model (price, crew, crate weight, dry matter window, stale-sample weeks) comes from the server.
 * The desk keeps no copy of it and no `?? 24` style fallback: a missing figure is shown as missing.
 */
const sources = {
  ...import.meta.glob("../../pages/avocado/*.tsx", { query: "?raw", import: "default", eager: true }),
  ...import.meta.glob("../../components/avocado/*.{ts,tsx}", { query: "?raw", import: "default", eager: true }),
  ...import.meta.glob("../../components/settings/CropModelPanel.tsx", { query: "?raw", import: "default", eager: true }),
} as Record<string, string>;

const FORBIDDEN: [string, RegExp][] = [
  ["minimum_pct with a stand-in", /minimum_pct \?\? ?\d/],
  ["a hard-coded export floor", /crosses \d+%|under \d+% dry matter|the \d+% floor/],
  ["a hard-coded stale age", /older than (six|\d+) weeks/],
  ["a saved crew", /saveCrewAvailable|save_crew_available/],
  ["a per-user price default", /avocado_price_per_kg|avocado_crew_available/],
  ["a stand-in crate weight", /kg_per_crate \?\? ?\d|KG_PER_CRATE/],
  ["a stand-in price or crew", /(price_per_kg|crew_available|days_per_week) \?\? ?[1-9]/],
];

describe("no avocado model figures in the desk", () => {
  it("reads the avocado sources", () => {
    expect(Object.keys(sources).length).toBeGreaterThan(10);
  });

  it.each(FORBIDDEN)("has no %s", (_why, pattern) => {
    for (const [file, text] of Object.entries(sources)) {
      expect(text, file).not.toMatch(pattern);
    }
  });
});

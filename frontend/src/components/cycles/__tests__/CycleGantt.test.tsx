import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CycleGantt } from "@/components/cycles/CycleGantt";
import type { Cycle } from "@/lib/api";

const cycle: Cycle = {
  name: "CY-1", title: "t", unit: "Block A", item: "Potatoes - Shangi", cycle_type: "Season", start_date: "2026-08-01",
  expected_harvest_start: "2026-11-01", expected_harvest_end: "2026-11-15", protocol: null, status: "Active", area_ha: 1, previous_cycle: null,
  variety: "Shangi", current_stage: "Tuber initiation",
  stage_bands: [
    { stage: "Vegetative", start: "2026-08-01", end: "2026-09-01", is_harvest: 0, actual: false },
    { stage: "Tuber initiation", start: "2026-09-01", end: "2026-11-01", is_harvest: 0, actual: true },
    { stage: "Harvest", start: "2026-11-01", end: "2026-11-15", is_harvest: 1, actual: false },
  ],
};

describe("CycleGantt stage bands", () => {
  it("splits the bar into stage bands, shades the pre-harvest window and shows the stage chip", () => {
    render(<CycleGantt cycles={[cycle]} accent="#2a7" unitLabel="Block" preHarvestDays={() => 14} />);
    expect(screen.getByTestId("gantt-band-CY-1-Vegetative")).toBeInTheDocument();
    expect(screen.getByTestId("gantt-band-CY-1-Harvest")).toBeInTheDocument();
    expect(screen.getByTestId("gantt-preharvest-CY-1")).toBeInTheDocument();
    expect(screen.getByTestId("gantt-today")).toBeInTheDocument();
    expect(screen.getByTestId("stage-chip")).toHaveTextContent("Tuber initiation");
  });

  it("falls back to the plain bar without a variety and shades nothing", () => {
    render(<CycleGantt cycles={[{ ...cycle, variety: null, current_stage: null, stage_bands: [] }]} accent="#2a7" unitLabel="Block" />);
    expect(screen.queryByTestId("gantt-band-CY-1-Harvest")).toBeNull();
    expect(screen.queryByTestId("gantt-preharvest-CY-1")).toBeNull();
  });
});

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

  it("marks late flowering, shows the cycle number, flags and uprooting pill", () => {
    const flowered: Cycle = {
      ...cycle, cycle_no: 2, expected_flowering_date: "2026-09-01", actual_flowering_date: "2026-09-22",
      flags: ["Block A flowered 3 weeks late"], due_for_uprooting: 1,
    };
    render(<CycleGantt cycles={[flowered]} accent="#2a7" unitLabel="Block" />);
    expect(screen.getByTestId("gantt-flower-expected-CY-1")).toBeInTheDocument();
    expect(screen.getByTestId("gantt-flower-actual-CY-1")).toHaveAttribute("data-late", "true");
    expect(screen.getByTestId("gantt-flags-CY-1")).toHaveTextContent("1 flag");
    expect(screen.getByText("Block A flowered 3 weeks late")).toBeInTheDocument();
    expect(screen.getByTestId("gantt-cycleno-CY-1")).toHaveTextContent("Cycle 2");
    expect(screen.getByTestId("gantt-uproot-CY-1")).toHaveTextContent("Due for uprooting");
  });

  it("does not mark flowering that came on time", () => {
    render(<CycleGantt cycles={[{ ...cycle, expected_flowering_date: "2026-09-01", actual_flowering_date: "2026-09-01" }]} accent="#2a7" unitLabel="Block" />);
    expect(screen.getByTestId("gantt-flower-actual-CY-1")).not.toHaveAttribute("data-late");
    expect(screen.queryByTestId("gantt-flags-CY-1")).toBeNull();
  });

  it("shows season and juvenile", () => {
    render(<CycleGantt cycles={[{ ...cycle, flowering_season: "Main", juvenile: 1 }]} accent="#2a7" unitLabel="Block" />);
    expect(screen.getByTestId("gantt-season-CY-1")).toHaveTextContent("Main");
    expect(screen.getByTestId("gantt-juvenile-CY-1")).toHaveTextContent("Juvenile");
  });

  it("shows neither season nor juvenile when absent", () => {
    render(<CycleGantt cycles={[cycle]} accent="#2a7" unitLabel="Block" />);
    expect(screen.queryByTestId("gantt-season-CY-1")).toBeNull();
    expect(screen.queryByTestId("gantt-juvenile-CY-1")).toBeNull();
  });

  it("draws an open-ended continuous harvest to the chart's right edge", () => {
    const cont: Cycle = {
      ...cycle, harvest_pattern: "Continuous", expected_harvest_end: null, expected_harvest_start: "2026-11-01",
      stage_bands: [
        { stage: "Growing", start: "2026-08-01", end: "2026-11-01", is_harvest: 0, actual: false },
        { stage: "Harvest", start: "2026-11-01", end: "2026-11-08", is_harvest: 1, actual: false },
      ],
    };
    render(<CycleGantt cycles={[cont]} accent="#2a7" unitLabel="Block" />);
    const band = screen.getByTestId("gantt-band-CY-1-Harvest");
    expect(band).toHaveAttribute("data-open-ended", "true");
    const bar = band.parentElement as HTMLElement;
    const left = parseFloat(bar.style.left);
    const width = parseFloat(bar.style.width);
    expect(left + width).toBeCloseTo(100, 5);
    const bandEnd = parseFloat(band.style.left) + parseFloat(band.style.width);
    expect(bandEnd).toBeCloseTo(100, 5);
  });

  it("keeps a bounded continuous cycle and a plain open window as they were", () => {
    render(<CycleGantt cycles={[{ ...cycle, harvest_pattern: "Continuous", expected_harvest_end: "2027-01-01" }]} accent="#2a7" unitLabel="Block" />);
    expect(screen.getByTestId("gantt-band-CY-1-Harvest")).not.toHaveAttribute("data-open-ended");
  });
});

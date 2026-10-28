import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Blocks } from "@/pages/Blocks";
import * as api from "@/lib/api";
import { AQUA, renderPage } from "./testkit";

vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof api>()),
  listUnits: vi.fn(),
  getUnit: vi.fn(),
  getOverview: vi.fn().mockResolvedValue({ error: "no" }),
}));
const listUnits = vi.mocked(api.listUnits);
const getUnit = vi.mocked(api.getUnit);

const unit = (over: Partial<api.UnitRow>): api.UnitRow => ({
  name: "U",
  unit_type: "Orchard Block",
  parent: null,
  is_group: 0,
  area_ha: 0,
  plant_count: 0,
  cost_center: null,
  status: "Active",
  current_cycle: null,
  item: null,
  has_geojson: 0,
  ...over,
});

describe("Blocks", () => {
  beforeEach(() => {
    listUnits.mockReset();
    getUnit.mockReset();
  });

  it("shows an empty state", async () => {
    listUnits.mockResolvedValue({ units: [] });
    renderPage(<Blocks />);
    expect(await screen.findByText(/No orchard blocks recorded for Avocado yet/i)).toBeTruthy();
  });

  it("nests blocks under their group and opens the drawer", async () => {
    listUnits.mockResolvedValue({
      units: [
        unit({ name: "Farm North", unit_type: "Pivot", is_group: 1, area_ha: 30 }),
        unit({ name: "Block B2", parent: "Farm North", area_ha: 15.25, current_cycle: "CYC-1", item: "Hass" }),
      ],
    });
    getUnit.mockResolvedValue({
      unit: { ...unit({ name: "Block B2", parent: "Farm North", area_ha: 15.25 }), geojson: null },
      cycles: [
        {
          name: "CYC-1",
          title: "Hass 2026",
          unit: "Block B2",
          item: "Hass",
          cycle_type: "Season",
          start_date: "2026-01-05",
          expected_harvest_start: null,
          expected_harvest_end: null,
          protocol: null,
          status: "Active",
          area_ha: 15.25,
          previous_cycle: null,
        },
      ],
      recent_work: [],
    });
    renderPage(<Blocks />);
    expect(await screen.findByText("Farm North")).toBeTruthy();
    expect(screen.getByText("15.3")).toBeTruthy();
    fireEvent.click(screen.getByText("Block B2"));
    expect(await screen.findByText("Rotation history")).toBeTruthy();
    expect(screen.getByText("5 Jan 2026")).toBeTruthy();
    expect(getUnit).toHaveBeenCalledWith("Block B2");
  });

  it("shows no cycle UI for a crop without cycles", async () => {
    listUnits.mockResolvedValue({ units: [unit({ name: "Pond 1", unit_type: "Pond", area_ha: 0.1 })] });
    getUnit.mockResolvedValue({
      unit: { ...unit({ name: "Pond 1", unit_type: "Pond" }), geojson: null },
      cycles: [],
      recent_work: [],
    });
    renderPage(<Blocks />, true, AQUA);
    expect(await screen.findByText("Pond 1")).toBeTruthy();
    expect(screen.queryByText("Current cycle")).toBeNull();
    expect(screen.queryByText(/With active cycle/i)).toBeNull();
    fireEvent.click(screen.getByText("Pond 1"));
    await screen.findByRole("dialog");
    expect(screen.queryByText("Rotation history")).toBeNull();
  });
});

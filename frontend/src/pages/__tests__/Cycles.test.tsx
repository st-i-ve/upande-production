import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Cycles } from "@/pages/Cycles";
import * as api from "@/lib/api";
import { CROP, renderPage } from "./testkit";

vi.mock("@/lib/api", async (orig) => ({
  ...(await orig<typeof api>()),
  listCycles: vi.fn(),
  listUnits: vi.fn(),
  listProtocols: vi.fn(),
  saveCycle: vi.fn(),
}));
const listCycles = vi.mocked(api.listCycles);
const listUnits = vi.mocked(api.listUnits);
const listProtocols = vi.mocked(api.listProtocols);

describe("Cycles", () => {
  beforeEach(() => {
    listCycles.mockReset();
    listUnits.mockReset().mockResolvedValue({ units: [] });
    listProtocols.mockReset().mockResolvedValue({ rows: [] });
  });

  it("shows an empty state", async () => {
    listCycles.mockResolvedValue({ cycles: [] });
    renderPage(<Cycles />);
    expect(await screen.findByText(/No crop cycles for Avocado yet/i)).toBeTruthy();
  });

  it("lists cycles and opens the add-crop-cycle dialog", async () => {
    listCycles.mockResolvedValue({
      cycles: [
        {
          name: "CYC-2026-0007",
          title: "Hass 2026",
          unit: "Block A1",
          item: "Hass",
          cycle_type: "Season",
          start_date: "2026-02-01",
          expected_harvest_start: "2026-08-01",
          expected_harvest_end: "2026-10-31",
          protocol: "Hass standard",
          status: "Harvesting",
          area_ha: 8,
          previous_cycle: null,
        },
      ],
    });
    renderPage(<Cycles />);
    expect(await screen.findByText("CYC-2026-0007")).toBeTruthy();
    expect(screen.getByText("Harvesting")).toBeTruthy();
    expect(screen.getByTestId("gantt-CYC-2026-0007")).toBeTruthy();
    fireEvent.mouseDown(screen.getByRole("tab", { name: "List" }));
    expect(await screen.findByText("8.0")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Add crop cycle/i }));
    expect(await screen.findByText("Add crop cycle", { selector: "h2" })).toBeTruthy();
  });

  it("toasts the server's error text unchanged", async () => {
    listCycles.mockResolvedValue({ error: "No permission for Crop Cycle." });
    renderPage(<Cycles />);
    expect(await screen.findByText("No permission for Crop Cycle.")).toBeTruthy();
  });

  it("records actual dates and toasts the proposed next cycle", async () => {
    listCycles.mockResolvedValue({
      cycles: [
        {
          name: "CYC-5", title: "Hass", unit: "Block A1", item: "Hass", cycle_type: "Season", start_date: "2026-02-01",
          expected_harvest_start: "2026-08-01", expected_harvest_end: "2026-10-31", protocol: null, status: "Harvesting",
          area_ha: 8, previous_cycle: null, cycle_no: 2, expected_flowering_date: "2026-05-01",
          flags: ["Block A1 flowered 3 weeks late"], due_for_uprooting: 0,
        },
      ],
    });
    vi.mocked(api.saveCycle).mockResolvedValue({ name: "CYC-5", proposed_next_cycle: "CYC-6" });
    renderPage(<Cycles />);
    await screen.findByTestId("gantt-CYC-5");
    fireEvent.mouseDown(screen.getByRole("tab", { name: "List" }));
    expect(await screen.findByText("Block A1 flowered 3 weeks late", { selector: "div.text-\\[11px\\]" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Record dates for CYC-5" }));
    fireEvent.click(await screen.findByRole("button", { name: "Save and close cycle" }));
    expect(await screen.findByText("Next cycle proposed: CYC-6")).toBeTruthy();
    expect(api.saveCycle).toHaveBeenCalledWith(expect.objectContaining({ name: "CYC-5", status: "Closed" }));
  });

  it("for fruits and vegetables keeps New cycle and adds Add existing cycle, with existing and import only", async () => {
    const FV = { ...CROP, name: "Fruits & Vegetables", crop_key: "fruits-vegetables", unit_label: "Block" };
    listCycles.mockResolvedValue({ cycles: [] });
    renderPage(<Cycles />, true, FV);
    await screen.findByText(/No crop cycles for Fruits/i);
    expect(screen.getByRole("button", { name: /New cycle/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Add existing cycle/ }));
    expect(await screen.findByText("Add crop cycle", { selector: "h2" })).toBeTruthy();
    expect(screen.queryByRole("tab", { name: "New cycle" })).toBeNull();
    expect(screen.getByRole("tab", { name: "Bulk import" })).toBeTruthy();
  });

  it("offers Edit from a cycle's dialog to managers only", async () => {
    listCycles.mockResolvedValue({
      cycles: [{ name: "CYC-9", title: "Hass", unit: "Block A1", item: "Hass", cycle_type: "Season", start_date: "2026-02-01", expected_harvest_start: null,
        expected_harvest_end: null, protocol: null, status: "Active", area_ha: 8, previous_cycle: null, variety: "Hass", current_stage: "Flowering" }],
    });
    renderPage(<Cycles />);
    await screen.findByTestId("gantt-CYC-9");
    fireEvent.mouseDown(screen.getByRole("tab", { name: "List" }));
    fireEvent.click(await screen.findByRole("button", { name: "Stages of CYC-9" }));
    expect(await screen.findByRole("button", { name: "Edit" })).toBeTruthy();
  });

  it("marks a cycle with a change pending, with who asked and old to new on hover", async () => {
    listCycles.mockResolvedValue({
      cycles: [
        {
          name: "CYC-8", title: "Hass", unit: "Block A1", item: "Hass", cycle_type: "Season", start_date: "2026-02-01",
          expected_harvest_start: null, expected_harvest_end: null, protocol: null, status: "Active", area_ha: 8, previous_cycle: null,
          pending_request: { name: "CCR-1", requested_by: "sup@x.com", action: "Edit", changes: { area_ha: { old: 8, new: 9 } } },
        },
      ],
    });
    renderPage(<Cycles />);
    fireEvent.mouseDown(await screen.findByRole("tab", { name: "List" }));
    const chip = await screen.findByTestId("pending-chip-CYC-8");
    expect(chip.textContent).toContain("sup@x.com");
    expect(chip.getAttribute("title")).toContain("Area (ha): 8 → 9");
  });
});

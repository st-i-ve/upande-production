import { fireEvent, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Cycles } from "@/pages/Cycles";
import * as api from "@/lib/api";
import { renderPage } from "./testkit";

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

  it("lists cycles and opens the new-cycle dialog", async () => {
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
    fireEvent.click(screen.getByRole("button", { name: /New cycle/i }));
    expect(await screen.findByText("New crop cycle")).toBeTruthy();
  });

  it("toasts the server's error text unchanged", async () => {
    listCycles.mockResolvedValue({ error: "No permission for Crop Cycle." });
    renderPage(<Cycles />);
    expect(await screen.findByText("No permission for Crop Cycle.")).toBeTruthy();
  });
});

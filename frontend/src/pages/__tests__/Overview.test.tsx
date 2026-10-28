import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Overview } from "@/pages/Overview";
import * as api from "@/lib/api";
import { renderPage } from "./testkit";

vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof api>()), getOverview: vi.fn() }));
const getOverview = vi.mocked(api.getOverview);

const tiles = {
  active_cycles: 7,
  tasks_total: 40,
  tasks_done: 30,
  done_pct: 75,
  deviations: 3,
  labour_cost_mtd: 1234567,
  forecast_next4: 52000,
  committed_next4: 18000,
  harvest_qty_season: 910000,
};

describe("Overview", () => {
  beforeEach(() => getOverview.mockReset());

  it("says so when the crop has no units", async () => {
    getOverview.mockResolvedValue({ tiles: { ...tiles, active_cycles: 0 }, blocks: [] });
    renderPage(<Overview />);
    expect(await screen.findByText(/No orchard blocks recorded for Avocado yet/i)).toBeTruthy();
  });

  it("shows the key figures and a block row, with money formatted", async () => {
    getOverview.mockResolvedValue({
      tiles,
      blocks: [
        {
          unit: "Block A1",
          unit_type: "Orchard Block",
          parent: "Farm 1",
          area_ha: 12.34,
          cycle: "CYC-2026-0001",
          item: "Hass",
          tasks_open: 4,
          labour_cost_season: 98000,
          harvest_qty_season: 5000,
        },
      ],
    });
    renderPage(<Overview />);
    expect(await screen.findByText("KES 1,234,567")).toBeTruthy();
    expect(screen.getByText("910,000")).toBeTruthy();
    expect(screen.getByText("Block A1")).toBeTruthy();
    expect(screen.getByText("12.3")).toBeTruthy();
    expect(screen.getByText("KES 98,000")).toBeTruthy();
  });

  it("hides money when pay is not visible", async () => {
    getOverview.mockResolvedValue({
      tiles: { ...tiles, labour_cost_mtd: null },
      blocks: [],
    });
    renderPage(<Overview />, false);
    await waitFor(() => expect(getOverview).toHaveBeenCalled());
    await screen.findByText(/No orchard blocks/i);
    expect(screen.queryByText(/Labour this month/i)).toBeNull();
  });

  it("toasts the server's error text unchanged", async () => {
    getOverview.mockResolvedValue({ error: "You may not see this crop." });
    renderPage(<Overview />);
    expect(await screen.findByText("You may not see this crop.")).toBeTruthy();
  });
});

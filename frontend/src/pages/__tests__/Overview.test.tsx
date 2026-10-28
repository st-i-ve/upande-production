import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Overview } from "@/pages/Overview";
import * as api from "@/lib/api";
import { renderPage } from "./testkit";

vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof api>()), getOverview: vi.fn() }));
vi.mock("@/lib/overview-api", () => ({ getOverviewExtras: vi.fn().mockResolvedValue({ error: "no extras" }) }));
import * as oapi from "@/lib/overview-api";
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
    expect(screen.getByText(/910,000/)).toBeTruthy();
    expect(screen.getByText("Block A1")).toBeTruthy();
    expect(screen.getByText("12.3")).toBeTruthy();
    expect(screen.getByText("KES 98,000")).toBeTruthy();
  });

  it("counts pending approvals as submissions and links to the Approvals page", async () => {
    getOverview.mockResolvedValue({ tiles, blocks: [] });
    vi.mocked(oapi.getOverviewExtras).mockResolvedValue({
      trend: [], forecast_weeks: [], operations: [], upcoming: [], recent_deviations: [], blocks: [], pending_approvals: 4,
    } as never);
    renderPage(<Overview />);
    const hint = await screen.findByText("submissions waiting for a manager");
    expect(hint.closest("a")?.getAttribute("href")).toBe("#/avocado/approvals");
    expect(screen.queryByText(/entries waiting/i)).toBeNull();
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

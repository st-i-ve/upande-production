import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/api", () => ({ blockCosts: vi.fn() }));
vi.mock("@/lib/blockcost-api", () => ({ blockBreakdown: vi.fn() }));
vi.mock("@/lib/insights-api", () => ({ costTrend: vi.fn() }));
import { blockCosts } from "@/lib/api";
import { blockBreakdown } from "@/lib/blockcost-api";
import { costTrend } from "@/lib/insights-api";
import { Costs } from "@/pages/Costs";

const mocked = vi.mocked(blockCosts);
const base = { unit_type: "Pivot Block", is_group: 0, area_ha: 2, harvest_qty: 100, cost_per_ha: 0 };

describe("Costs", () => {
  beforeEach(() => {
    mocked.mockReset();
    vi.mocked(costTrend).mockReset().mockResolvedValue({ weeks: [] });
  });

  it("shows an empty state", async () => {
    mocked.mockResolvedValue({ rows: [] });
    renderPage(<Costs />);
    expect(await screen.findByText(/No block costs for this period/i)).toBeInTheDocument();
  });

  it("rolls a group up, expands to blocks, and paints a negative margin red", async () => {
    mocked.mockResolvedValue({
      rows: [
        { ...base, unit: "Pivot 1", parent: null, is_group: 1, area_ha: 5, labour: 1500000, inputs: 500000, total_cost: 2000000, cost_per_ha: 400000, harvest_qty: 300, revenue: 1000000, margin: -1000000 },
        { ...base, unit: "Block A", parent: "Pivot 1", labour: 1000000, inputs: 100000, total_cost: 1100000, revenue: 1200000, margin: 100000 },
        { ...base, unit: "Block B", parent: "Pivot 1", labour: 500000, inputs: 400000, total_cost: 900000, revenue: 0, margin: -900000 },
      ],
    } as never);
    renderPage(<Costs />);
    const group = await screen.findByTestId("cost-row-Pivot 1");
    expect(group).toHaveTextContent("KES 2,000,000");
    expect(screen.getByTestId("margin-Pivot 1").className).toMatch(/sev-critical/);
    expect(screen.queryByTestId("cost-row-Block B")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Expand Pivot 1/ }));
    expect(screen.getByTestId("cost-row-Block B")).toBeInTheDocument();
    expect(screen.getByTestId("margin-Block B").className).toMatch(/sev-critical/);
    expect(screen.getByTestId("margin-Block A").className).not.toMatch(/sev-critical/);
    // chart draws leaf blocks only, the loss in red
    expect(screen.getByTestId("bar-Block B")).toHaveAttribute("data-negative", "true");
    expect(screen.queryByTestId("bar-Pivot 1")).toBeNull();
  });

  it("hides money when pay is not visible", async () => {
    mocked.mockResolvedValue({
      rows: [{ ...base, unit: "Block A", parent: null, labour: null, inputs: 10, total_cost: null, cost_per_ha: null, revenue: 5, margin: null }],
    } as never);
    renderPage(<Costs />, { can_see_pay: false });
    await waitFor(() => expect(screen.getByTestId("cost-row-Block A")).toBeInTheDocument());
    expect(screen.getByText(/Money figures are hidden/i)).toBeInTheDocument();
    expect(screen.queryByText("Labour")).toBeNull();
    expect(screen.queryByText(/KES/)).toBeNull();
  });

  it("breakdown lists inputs per ha", async () => {
    mocked.mockResolvedValue({ rows: [{ ...base, unit: "Block A", parent: null, labour: 100, inputs: 50, total_cost: 150, revenue: 0, margin: -150 }] } as never);
    vi.mocked(blockBreakdown).mockReset().mockResolvedValue({
      unit: "Block A",
      area_ha: 2,
      labour: [{ operation: "Pruning", qty_by_uom: [{ uom: "Tree", qty: 40 }], workers: 3, pay: 100 }],
      inputs: [{ item_code: "NPK", item_name: "NPK 17", item_group: "Fertiliser", qty: 100, uom: "Kg", amount: 50, per_ha: 50, planned_qty: 120 }],
      other: [{ account: "Repairs - MUT", amount: 20 }],
      totals: { labour: 100, inputs: 50, other: 20, total: 170, per_ha: 85 },
      budget: { erp_budget: 150, actual_this_fy: 170 },
    } as never);
    renderPage(<Costs />);
    fireEvent.click(await screen.findByRole("button", { name: /cost breakdown for Block A/i }));
    const row = await screen.findByTestId("input-NPK");
    expect(row).toHaveTextContent("NPK 17");
    expect(row).toHaveTextContent("100.00 Kg");
    expect(screen.getByTestId("per-ha-NPK")).toHaveTextContent("50.00 Kg/ha");
    expect(row).toHaveTextContent("120.00 Kg");
    expect(screen.getByTestId("breakdown-labour")).toHaveTextContent("Pruning");
    expect(screen.getByTestId("breakdown-other")).toHaveTextContent("Repairs - MUT");
    expect(screen.getByTestId("breakdown-totals")).toHaveTextContent("KES 170");
    expect(screen.getByText(/over budget/i)).toBeInTheDocument();
    expect(blockBreakdown).toHaveBeenCalledWith("Block A", expect.any(String), expect.any(String));
  });
});

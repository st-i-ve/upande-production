import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/api", () => ({ listUnits: vi.fn() }));
vi.mock("@/lib/establishment-api", () => ({
  listCosts: vi.fn(),
  saveCost: vi.fn(),
  cancelCost: vi.fn(),
  capitalActivities: vi.fn(),
  listOpeningBalances: vi.fn(),
  saveOpeningBalance: vi.fn(),
}));
import { listUnits } from "@/lib/api";
import * as est from "@/lib/establishment-api";
import { Establishment } from "@/pages/Establishment";

const unit = (name: string, extra: Record<string, unknown> = {}) => ({
  name, unit_type: "Block", parent: null, is_group: 0, area_ha: 1, plant_count: 0, cost_center: null, status: "Active", current_cycle: null, item: null, has_geojson: 0, ...extra,
});

beforeEach(() => {
  vi.mocked(listUnits).mockReset().mockResolvedValue({
    units: [unit("Pivot 1", { is_group: 1, area_ha: 4 }), unit("Block A", { parent: "Pivot 1", area_ha: 3 }), unit("Block B", { parent: "Pivot 1", area_ha: 1 })],
  } as never);
  vi.mocked(est.listCosts).mockReset().mockResolvedValue({
    rows: [],
    by_unit: [{ unit: "Block A", total: 3000, by_activity: [{ operation: "Trellis", amount: 3000, budget: 2000 }] }],
  } as never);
  vi.mocked(est.capitalActivities).mockReset().mockResolvedValue({ rows: [{ operation: "Trellis", color: "#888", budget_per_ha: 1000 }] } as never);
  vi.mocked(est.listOpeningBalances).mockReset().mockResolvedValue({
    rows: [{ unit: "Block A", as_of_date: "2026-01-01", setup_cost: 100, running_costs_to_date: 0, value_recovered_to_date: 0 }],
  } as never);
  vi.mocked(est.saveOpeningBalance).mockReset().mockResolvedValue({ name: "OB-1" } as never);
  vi.mocked(est.saveCost).mockReset().mockResolvedValue({ name: "BEC-1" } as never);
});

describe("Establishment", () => {
  it("shows totals, per ha and budget vs actual", async () => {
    renderPage(<Establishment />);
    expect(await screen.findByTestId("unit-Block A")).toHaveTextContent("KES 3,000");
    expect(screen.getByText("KES 3,000 of KES 2,000")).toBeInTheDocument();
  });

  it("split preview by area", async () => {
    renderPage(<Establishment />);
    await screen.findByTestId("unit-Block A");
    fireEvent.click(screen.getByRole("button", { name: /Add cost/ }));
    fireEvent.change(await screen.findByLabelText("Amount (KES)"), { target: { value: "1000" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Pivot 1" }));
    const preview = await screen.findByTestId("split-preview");
    expect(preview).toBeInTheDocument();
    expect(screen.getByTestId("split-Block A")).toHaveTextContent("75.0%");
    expect(screen.getByTestId("split-Block A")).toHaveTextContent("KES 750");
    expect(screen.getByTestId("split-Block B")).toHaveTextContent("KES 250");
  });

  it("opening balance tab saves", async () => {
    renderPage(<Establishment />);
    await screen.findByTestId("unit-Block A");
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Opening balances" }), { button: 0 });
    fireEvent.click(screen.getByRole("tab", { name: "Opening balances" }));
    const setup = await screen.findByLabelText("Setup cost Block A");
    fireEvent.change(setup, { target: { value: "5000" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Block A" }));
    await waitFor(() =>
      expect(est.saveOpeningBalance).toHaveBeenCalledWith(expect.objectContaining({ unit: "Block A", crop: "Test Crop", as_of_date: "2026-01-01", setup_cost: 5000 })),
    );
  });

  it("manual split with a group sends the leaf rows", async () => {
    renderPage(<Establishment />);
    await screen.findByTestId("unit-Block A");
    fireEvent.click(screen.getByRole("button", { name: /Add cost/ }));
    fireEvent.change(await screen.findByLabelText("Amount (KES)"), { target: { value: "1000" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Pivot 1" }));
    fireEvent.click(screen.getByRole("button", { name: "Split manually" }));
    fireEvent.change(await screen.findByLabelText("Share Block A"), { target: { value: "60" } });
    fireEvent.change(screen.getByLabelText("Share Block B"), { target: { value: "40" } });
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Activity" }));
    fireEvent.click(await screen.findByRole("option", { name: /Trellis/ }));
    fireEvent.click(screen.getByRole("button", { name: /^Save/ }));
    await waitFor(() => expect(est.saveCost).toHaveBeenCalled());
    expect(vi.mocked(est.saveCost).mock.calls[0][0]).toEqual(
      expect.objectContaining({
        split_method: "Manual",
        blocks: [
          { unit: "Block A", share_pct: 60 },
          { unit: "Block B", share_pct: 40 },
        ],
      }),
    );
  });

  it("erp budget shown", async () => {
    vi.mocked(est.listCosts).mockResolvedValue({
      rows: [],
      by_unit: [{ unit: "Block A", total: 3000, erp_budget: 2500, by_activity: [{ operation: "Trellis", amount: 3000 }] }],
    } as never);
    renderPage(<Establishment />);
    expect(await screen.findByTestId("erp-budget-Block A")).toHaveTextContent("KES 2,500");
  });

  it("erp budget compares this fiscal year's spend, not all-time setup", async () => {
    vi.mocked(est.listCosts).mockResolvedValue({
      rows: [],
      by_unit: [
        { unit: "Block A", total: 3000, erp_budget: 2500, actual_this_fy: 900, by_activity: [{ operation: "Trellis", amount: 3000 }] },
        { unit: "Block B", total: 100, erp_budget: 500, actual_this_fy: 800, by_activity: [{ operation: "Trellis", amount: 100 }] },
      ],
    } as never);
    renderPage(<Establishment />);
    expect((await screen.findByTestId("erp-budget-Block A")).className).not.toMatch(/data-red/);
    expect(screen.getByTestId("erp-budget-Block B").className).toMatch(/data-red/);
  });
});

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";

vi.mock("@/lib/establishment-api", () => ({
  getUnitCapitalBudget: vi.fn(),
  saveUnitCapitalBudget: vi.fn(),
  cycleCapitalCosts: vi.fn(),
}));
import * as est from "@/lib/establishment-api";
import { CapitalBudgetDialog } from "@/components/establishment/CapitalBudgetDialog";
import { CycleCapitalCosts } from "@/components/cycles/CycleCapitalCosts";

const budget = {
  unit: "Block A",
  area_ha: null,
  rows: [
    { operation: "Trellis", operation_name: "Trellis", basis: "Per ha", amount: 1000, note: null, effective: null, spent: 0 },
    { operation: "Drip", operation_name: "Drip lines", basis: "Total", amount: 500, note: null, effective: 500, spent: 200 },
  ],
  total_budget: 500,
  total_spent: 200,
};

function open(canWrite: boolean) {
  return render(
    <TooltipProvider>
      <CapitalBudgetDialog unit="Block A" operations={["Trellis", "Drip", "Clearing"]} canWrite={canWrite} onClose={() => {}} />
    </TooltipProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.mocked(est.getUnitCapitalBudget).mockReset().mockResolvedValue(budget as never);
  vi.mocked(est.saveUnitCapitalBudget).mockReset().mockResolvedValue(budget as never);
  vi.mocked(est.cycleCapitalCosts).mockReset();
});

describe("CapitalBudgetDialog", () => {
  it("read only shows rows and a dash for a Per ha row without area", async () => {
    open(false);
    const row = await screen.findByTestId("budget-Trellis");
    expect(row).toHaveTextContent("Per ha");
    expect(row).toHaveTextContent("—");
    expect(screen.getByTestId("budget-Drip")).toHaveTextContent("KES 500");
    expect(screen.queryByRole("button", { name: "Save budget" })).toBeNull();
  });

  it("saves the edited rows", async () => {
    open(true);
    fireEvent.change(await screen.findByLabelText("Amount 1"), { target: { value: "1200" } });
    fireEvent.click(screen.getByRole("button", { name: "Save budget" }));
    await waitFor(() =>
      expect(est.saveUnitCapitalBudget).toHaveBeenCalledWith("Block A", [
        { operation: "Trellis", basis: "Per ha", amount: 1200, note: null },
        { operation: "Drip", basis: "Total", amount: 500, note: null },
      ]),
    );
  });

  it("shows the server's refusal inline", async () => {
    vi.mocked(est.saveUnitCapitalBudget).mockResolvedValue({ error: "A group cannot carry a budget." } as never);
    open(true);
    await screen.findByLabelText("Amount 1");
    fireEvent.click(screen.getByRole("button", { name: "Save budget" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("A group cannot carry a budget.");
  });

  it("a new row can be added and removed", async () => {
    open(true);
    await screen.findByLabelText("Amount 1");
    fireEvent.click(screen.getByRole("button", { name: /Add activity/ }));
    expect(screen.getByLabelText("Amount 3")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove activity 3" }));
    expect(screen.queryByLabelText("Amount 3")).toBeNull();
  });
});

describe("CycleCapitalCosts", () => {
  it("lists operations against the budget and dashes a null budget", async () => {
    vi.mocked(est.cycleCapitalCosts).mockResolvedValue({
      cycle: "C-1", unit: "Block A", total: 700,
      rows: [{ cost: "BEC-1", posting_date: "2026-03-01", operation: "Trellis", amount: 700 }],
      by_operation: [{ operation: "Trellis", amount: 700, budget: null }],
    } as never);
    render(<CycleCapitalCosts cycle="C-1" />);
    const box = await screen.findByTestId("cycle-capital-costs");
    expect(box).toHaveTextContent("Trellis");
    expect(box).toHaveTextContent("KES 700");
    expect(box).toHaveTextContent("of —");
  });

  it("renders nothing when the cycle has no capital costs", async () => {
    vi.mocked(est.cycleCapitalCosts).mockResolvedValue({ cycle: "C-1", unit: "Block A", total: 0, rows: [], by_operation: [] } as never);
    const { container } = render(<CycleCapitalCosts cycle="C-1" />);
    await waitFor(() => expect(est.cycleCapitalCosts).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });
});

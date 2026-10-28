import { fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/breakeven-api", () => ({ cropBreakeven: vi.fn() }));
import { cropBreakeven } from "@/lib/breakeven-api";
import { BreakEven } from "@/pages/BreakEven";

const mocked = vi.mocked(cropBreakeven);
const farm = {
  points: [
    { date: "2026-01-31", cost: 1000, value: 0 },
    { date: "2026-02-28", cost: 1200, value: 400 },
  ],
  invested: 1200, recovered: 400, balance: -800, pct_recovered: 33, break_even_date: null, projected_date: "2027-03-15", projection_basis: "trailing_12m",
};

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  mocked.mockReset();
});

describe("BreakEven", () => {
  it("shows projected date and basis", async () => {
    mocked.mockResolvedValue({ blocks: [], farm } as never);
    renderPage(<BreakEven />);
    expect(await screen.findByText("15 Mar 2027")).toBeInTheDocument();
    expect(screen.getByText("from the last 12 months' net")).toBeInTheDocument();
    expect(screen.getByText("Projected break-even")).toBeInTheDocument();
  });

  it("sorts blocks by % recovered", async () => {
    const b = (unit: string, pct: number) => ({ unit, invested: 100, recovered: pct, balance: pct - 100, pct_recovered: pct });
    mocked.mockResolvedValue({ blocks: [b("Block A", 20), b("Block B", 90)], farm } as never);
    renderPage(<BreakEven />);
    const order = async () => (await screen.findAllByTestId(/be-row-/)).map((r) => r.getAttribute("data-testid"));
    expect(await order()).toEqual(["be-row-Block B", "be-row-Block A"]);
    fireEvent.click(within(screen.getByRole("columnheader", { name: /% recovered/ })).getByRole("button"));
    expect(await order()).toEqual(["be-row-Block A", "be-row-Block B"]);
  });

  it("break-even hidden message without pay", async () => {
    mocked.mockResolvedValue({ error: "Break-even includes pay; ask a manager." });
    renderPage(<BreakEven />);
    expect(await screen.findByText("Break-even includes pay; ask a manager.")).toBeInTheDocument();
    expect(screen.queryByText("Invested")).toBeNull();
  });

  it("does not ask the server when the viewer cannot see pay", async () => {
    renderPage(<BreakEven />, { can_see_pay: false });
    expect(await screen.findByText("Break-even includes pay; ask a manager.")).toBeInTheDocument();
    expect(mocked).not.toHaveBeenCalled();
  });
});

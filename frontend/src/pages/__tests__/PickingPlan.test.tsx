import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/avocado-api", () => ({ getPickingPlan: vi.fn() }));
import { getPickingPlan } from "@/lib/avocado-api";
import { PickingPlan } from "@/pages/avocado/PickingPlan";

const plan = vi.mocked(getPickingPlan);

const wk = (week: string, status: string, needed: number) => ({
  week, kg: 9000, crates: 500, picker_days: needed * 5, pickers_needed: needed, crew_available: 20, shortfall: needed - 20, pct_of_crew: 90,
  wage_cost: 55000, cost_per_kg: 6.1, blocks: ["Block A"], pct_kg_measured: 60, status,
  people_short: status === "short" ? needed - 20 : 0, people_spare: status === "spare" ? 20 - needed : 0,
  by_block: [{ block: "Block A", kg: 9000, crates: 500, kg_per_picker_day: 95, rate_basis: "measured", measured: true, picker_days: needed * 5, pickers_needed: needed }],
});
const payload = (extra: object = {}) => ({
  farm: null, farms: ["Mutara"], crew_available: 20, days_per_week: 5, pay_per_day_kes: 700, can_see_pay: true, kg_per_crate: 18,
  summary: { weeks: 2 },
  kpis: {
    peak_week: { pickers: 26, week: "2026-11-09" },
    weeks_short: { weeks: 1, first_week: "2026-11-09", worst_shortfall_pickers: 6 },
    picker_days: { total: 230, days_per_week: 5 },
    wage_bill_kes: 161000,
    cannot_staff: { kg: 1200, blocks: 1 },
  },
  weeks: [wk("2026-11-02", "spare", 14), wk("2026-11-09", "short", 26)],
  focus_week: "2026-11-09", week_detail: null,
  rates: { blocks: [{ block: "Block A", kg_per_picker_day: 95, basis: "measured", events: 4 }], estate: { kg_per_picker_day: 90, basis: "estate history", events: 40 } },
  unscheduled: [{ block: "Block C", expected_kg: 1200, reason: "No dry matter sample" }],
  unscheduled_kg: 1200,
  rejected_records: [{ block: "Block A", date: "2026-09-01", implied_rate: 900, why: "more than one person could pick" }],
  ...extra,
});

describe("PickingPlan", () => {
  beforeEach(() => {
    // recharts' ResponsiveContainer needs it; jsdom has none.
    vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
    plan.mockReset().mockResolvedValue(payload() as never);
  });

  it("shows the focus week detail, rates, unscheduled and rejected records", async () => {
    renderPage(<PickingPlan />);
    const detail = await screen.findByTestId("week-detail");
    expect(detail).toHaveTextContent("6 short");
    expect(detail).toHaveTextContent("Block A");
    expect(screen.getByText("Estate")).toBeInTheDocument();
    expect(screen.getByText("No dry matter sample")).toBeInTheDocument();
    expect(screen.getByText("more than one person could pick")).toBeInTheDocument();
    expect(screen.getByLabelText("Pay a day (KES)")).toBeInTheDocument();
  });

  it("tries a crew for this view only: re-reads the plan with it and saves nothing", async () => {
    renderPage(<PickingPlan />);
    const crew = await screen.findByLabelText("Crew available");
    expect(plan).toHaveBeenLastCalledWith(expect.objectContaining({ crew_available: undefined }));
    fireEvent.change(crew, { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Try" }));
    await waitFor(() => expect(plan).toHaveBeenLastCalledWith(expect.objectContaining({ crew_available: 30 })));
  });

  it("refuses a crew that is not a whole number without calling the API", async () => {
    renderPage(<PickingPlan />);
    const crew = await screen.findByLabelText("Crew available");
    fireEvent.change(crew, { target: { value: "2.5" } });
    fireEvent.click(screen.getByRole("button", { name: "Try" }));
    expect(await screen.findByText(/whole number of people/)).toBeInTheDocument();
    expect(plan).toHaveBeenCalledTimes(1);
  });

  it("hides pay when the viewer cannot see it", async () => {
    plan.mockResolvedValue(payload({ can_see_pay: false, pay_per_day_kes: null }) as never);
    renderPage(<PickingPlan />);
    await screen.findByTestId("week-detail");
    expect(screen.queryByLabelText("Pay a day (KES)")).toBeNull();
    expect(screen.queryByText(/KES/)).toBeNull();
  });
});

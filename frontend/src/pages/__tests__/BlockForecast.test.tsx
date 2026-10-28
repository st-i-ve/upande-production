import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BlockForecast } from "@/pages/avocado/BlockForecast";
import * as api from "@/lib/avocado-api";
import { forecastFixture } from "./avocado-fixtures";
import { renderPage } from "./testkit";

vi.mock("@/lib/avocado-api", async (orig) => ({
  ...(await orig<typeof api>()),
  getProductionForecast: vi.fn(),
  setForecastMode: vi.fn(),
  savePricePerKg: vi.fn(),
  saveManualForecast: vi.fn(),
  saveSeasonBudget: vi.fn(),
}));
const getForecast = vi.mocked(api.getProductionForecast);
const setMode = vi.mocked(api.setForecastMode);
const savePrice = vi.mocked(api.savePricePerKg);
const saveManual = vi.mocked(api.saveManualForecast);
const saveBudget = vi.mocked(api.saveSeasonBudget);

describe("BlockForecast", () => {
  beforeEach(() => {
    getForecast.mockReset().mockImplementation(async () => structuredClone(forecastFixture));
    setMode.mockReset().mockImplementation(async (mode) => ({ ok: true, mode }));
    savePrice.mockReset().mockResolvedValue({ ok: true, price_per_kg: 100 });
    saveManual.mockReset().mockResolvedValue({ ok: true, name: "APF-1", created: false, block: "A", season: 2026, crop: "Whole Season", expected_kg: 90000 });
    saveBudget.mockReset().mockResolvedValue({ ok: true, name: "APB-1", created: false, season: 2026, crop: "Whole Season", budget_kg: 1 });
  });

  it("renders the KPI cards and every section", async () => {
    renderPage(<BlockForecast />);
    expect(await screen.findByText("Season budget")).toBeTruthy();
    for (const k of ["Forecast", "Grade 1", "Value", "Bearing", "Counted blocks", "Next 6 weeks", "Losing"]) {
      expect(screen.getAllByText(k).length).toBeGreaterThan(0);
    }
    for (const s of ["Estimate vs delivered", "By planting year", "Yield curve", "Blocks", "Pick schedule", "Losses", "Maturity", "Data gaps"]) {
      expect(screen.getAllByText(s).length).toBeGreaterThan(0);
    }
    expect(screen.getByText(/system-calculated/)).toBeTruthy();
    // budget months with share of peak, estimate-vs-delivered figures, schedule, maturity verdicts
    const budget = screen.getByTestId("forecast-budget");
    expect(within(budget).getByText("October")).toBeTruthy();
    expect(within(budget).getByText("100.0%")).toBeTruthy();
    // whole-season budget against delivered + still on the trees, not the late crop alone
    expect(within(budget).getByText("Delivered so far")).toBeTruthy();
    expect(within(budget).getByText("Still on the trees")).toBeTruthy();
    expect(within(budget).getByText("Season outturn")).toBeTruthy();
    expect(within(budget).getByText("-24.0 t")).toBeTruthy(); // 137.7 + 150.3 against 312
    expect(within(screen.getByTestId("forecast-estimate")).getByText("Best block")).toBeTruthy();
    expect(within(screen.getByTestId("forecast-maturity")).getByText("Pickable")).toBeTruthy();
    expect(within(screen.getByTestId("forecast-maturity")).getByText("Not yet")).toBeTruthy();
    expect(screen.getByText(/Nothing missing/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Edit forecast for A/ })).toBeNull(); // automatic: no inline edit
  });

  it("switches Manual/Automatic without refetching and remembers the choice", async () => {
    renderPage(<BlockForecast />);
    const kpi = async () => (await screen.findAllByText(/^(150\.3|140\.5) t$/)).map((n) => n.textContent);
    expect(await kpi()).toContain("150.3 t");
    fireEvent.click(screen.getByRole("button", { name: "Manual" }));
    await waitFor(() => expect(setMode).toHaveBeenCalledWith("manual"));
    expect(await screen.findByText(/block forecasts of 2 orchard blocks/)).toBeTruthy();
    expect(await kpi()).toContain("140.5 t");
    expect(screen.getByRole("button", { name: "Manual" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Automatic" }));
    await waitFor(() => expect(setMode).toHaveBeenCalledWith("automatic"));
    expect(screen.getByText(/system-calculated/)).toBeTruthy();
    expect(getForecast).toHaveBeenCalledTimes(1);
  });

  it("edits a manual forecast inline and saves it", async () => {
    renderPage(<BlockForecast />);
    fireEvent.click(await screen.findByRole("button", { name: "Manual" }));
    fireEvent.click(await screen.findByRole("button", { name: /Edit forecast for A/ }));
    const input = await screen.findByLabelText(/Forecast kg for A/);
    fireEvent.change(input, { target: { value: "90000" } });
    fireEvent.keyDown(input, { key: "Enter" });
    await waitFor(() => expect(saveManual).toHaveBeenCalledWith({ orchard_block: "A", expected_kg: 90000, season: 2026 }));
    await waitFor(() => expect(getForecast).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Forecast for A saved.")).toBeTruthy();
  });

  it("saves the price from its pill", async () => {
    renderPage(<BlockForecast />);
    fireEvent.click(await screen.findByRole("button", { name: /Price \/ kg: KES 95/ }));
    fireEvent.change(await screen.findByLabelText(/Price \/ kg \(KES\)/), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(savePrice).toHaveBeenCalledWith(100));
    await waitFor(() => expect(getForecast).toHaveBeenCalledTimes(2));
  });

  it("edits the season budget in a dialog", async () => {
    renderPage(<BlockForecast />);
    fireEvent.click(await screen.findByRole("button", { name: "Edit budget" }));
    expect(await screen.findByText("Season budget 2026")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("July"), { target: { value: "12000" } });
    fireEvent.click(screen.getByRole("button", { name: "Save budget" }));
    await waitFor(() => expect(saveBudget).toHaveBeenCalled());
    const arg = saveBudget.mock.calls[0][0];
    expect(arg.season).toBe(2026);
    expect(arg.months).toContainEqual({ month: "July", budget_kg: 12000 });
    expect(arg.months).toContainEqual({ month: "May", budget_kg: 52000 });
    expect(arg.budget_price_per_kg).toBe(105);
  });

  it("explains empty sections in the original's words", async () => {
    const d = structuredClone(forecastFixture);
    d.budget = { set: false, season: 2026, crop: "Whole Season", months: [] };
    d.estimate_vs_delivered = { ...d.estimate_vs_delivered, basis: "none", delivered_kg: 0, rows: [], best: null, weakest: null };
    d.schedule = { ...d.schedule, weeks: [], scheduled_blocks: [] };
    d.maturity = { ...d.maturity, blocks: [] };
    d.by_planting_year = [];
    d.data_gaps = [{ issue: "No planting year", count: 1, blocks: ["Z"], detail: "Age cannot be worked out." }];
    getForecast.mockResolvedValue(d);
    renderPage(<BlockForecast />);
    expect(await screen.findByText(/No budget has been set for 2026 yet/)).toBeTruthy();
    expect(screen.getByText(/No harvest has been recorded against these estimates yet/)).toBeTruthy();
    expect(screen.getByText(/Nothing dated — a pick week needs one dry matter sample/)).toBeTruthy();
    expect(screen.getByText(/No dry matter samples yet/)).toBeTruthy();
    expect(screen.getByText(/Nothing to group/)).toBeTruthy();
    expect(screen.getByText("No planting year")).toBeTruthy();
  });
});

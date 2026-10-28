import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CROP, renderPage } from "./helpers";

vi.mock("@/lib/api", () => ({
  forecastSummary: vi.fn(),
  listSamples: vi.fn(),
  listCommitments: vi.fn(),
  listUnits: vi.fn(),
  saveSample: vi.fn(),
  saveCommitment: vi.fn(),
}));
import { forecastSummary, listCommitments, listSamples } from "@/lib/api";
import { Forecast } from "@/pages/Forecast";

const fc = vi.mocked(forecastSummary);

describe("Forecast", () => {
  beforeEach(() => {
    vi.mocked(listSamples).mockResolvedValue({ rows: [] });
    vi.mocked(listCommitments).mockResolvedValue({ rows: [] });
  });

  it("shows empty states", async () => {
    fc.mockResolvedValue({ uom: "Kg", weeks: [], units: [], totals: { forecast: 0, forecast_to_date: 0, actual: 0, committed: 0, error_pct: null }, seasons: [] });
    renderPage(<Forecast />);
    expect(await screen.findByText(/No weekly forecast for this period/i)).toBeInTheDocument();
    expect(screen.getByText(/No forecasts to compare/i)).toBeInTheDocument();
    expect(await screen.findByText(/No yield samples recorded yet/i)).toBeInTheDocument();
  });

  it("totals, colours accuracy and shows a today marker", async () => {
    const d = new Date();
    const p = (n: number) => String(n).padStart(2, "0");
    const today = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
    fc.mockResolvedValue({
      uom: "Kg",
      weeks: [{ iso_year: 2026, iso_week: 1, week_start: today, forecast: 1000, actual: 800, committed: 500, error_pct: -20 }],
      units: [
        { unit: "Block A", forecast: 100, forecast_to_date: 100, actual: 105, error_pct: 5 },
        { unit: "Block B", forecast: 100, forecast_to_date: 100, actual: 80, error_pct: -20 },
        { unit: "Block C", forecast: 100, forecast_to_date: 100, actual: 40, error_pct: -60 },
        { unit: "Block D", forecast: 0, forecast_to_date: 0, actual: 10, error_pct: null },
      ],
      totals: { forecast: 1000, forecast_to_date: 1000, actual: 800, committed: 500, error_pct: -20 },
      seasons: [{ year: 2025, actual: 12000 }],
    });
    renderPage(<Forecast />);
    await waitFor(() => expect(screen.getByTestId("error-Block A")).toBeInTheDocument());
    expect(screen.getByTestId("error-Block A").className).toMatch(/sev-moderate/);
    expect(screen.getByTestId("error-Block B").className).toMatch(/sev-high/);
    expect(screen.getByTestId("error-Block C").className).toMatch(/sev-critical/);
    expect(screen.getByTestId("error-Block D")).toHaveTextContent("—");
    expect(screen.getByTestId("today-marker")).toBeInTheDocument();
    expect(screen.getAllByText("1,000").length).toBeGreaterThan(0);
    expect(screen.getByText("Accuracy to date")).toBeInTheDocument();
    expect(screen.getAllByText("-20.0%").length).toBeGreaterThan(1);
    expect(screen.getByRole("button", { name: /New sample/ })).toBeInTheDocument();
  });

  it("shows external links only for crops that list them", async () => {
    fc.mockResolvedValue({ uom: "Kg", weeks: [], units: [], totals: { forecast: 0, forecast_to_date: 0, actual: 0, committed: 0, error_pct: null }, seasons: [] });
    const { unmount } = renderPage(<Forecast />);
    await screen.findByText(/No weekly forecast/i);
    expect(screen.queryByText("Outlook")).toBeNull();
    unmount();
    renderPage(<Forecast />, {}, { ...CROP, crop_key: "avocado" });
    expect(await screen.findByRole("link", { name: /Outlook/ })).toHaveAttribute("href", "/avocado-outlook");
  });
});

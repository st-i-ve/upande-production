import { BANDS } from "./bands-fixtures";
import { fireEvent, screen, waitFor } from "@testing-library/react";
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
    fc.mockResolvedValue({ uom: "Kg", weeks: [], units: [], totals: { forecast: 0, forecast_to_date: 0, actual: 0, committed: 0, error_pct: null }, seasons: [], bands: BANDS });
    renderPage(<Forecast />);
    expect(await screen.findByText(/No weekly forecast for this period/i)).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Accuracy" }));
    expect(await screen.findByText(/No forecasts to compare/i)).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Samples" }));
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
      bands: BANDS,
    });
    renderPage(<Forecast />);
    expect(await screen.findByTestId("today-marker")).toBeInTheDocument();
    // The error is shown as how far actual is from forecast, in words: never a signed "accuracy".
    expect(screen.getByText("Actual vs forecast to date")).toBeInTheDocument();
    expect(screen.getAllByText("20% below forecast").length).toBeGreaterThan(0);
    expect(screen.queryByText("Accuracy to date")).toBeNull();
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Accuracy" }));
    await waitFor(() => expect(screen.getByTestId("error-Block A")).toBeInTheDocument());
    expect(screen.getByTestId("error-Block A").className).toMatch(/sev-moderate/);
    expect(screen.getByTestId("error-Block B").className).toMatch(/sev-high/);
    expect(screen.getByTestId("error-Block C").className).toMatch(/sev-critical/);
    expect(screen.getByTestId("error-Block D")).toHaveTextContent("—");
    expect(screen.getByTestId("error-Block A")).toHaveTextContent("5.0% above");
    expect(screen.getByTestId("error-Block C")).toHaveTextContent("60% below");
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Samples" }));
    expect(await screen.findByRole("button", { name: /New sample/ })).toBeInTheDocument();
  });

  it("splits a section with crops by crop, each in its own unit, with no grand total", async () => {
    const FV = { ...CROP, name: "Fruits & Vegetables", crop_key: "fruits-vegetables", has_field_crops: 1, field_crops: [] };
    fc.mockResolvedValue({
      uom: "Kg", weeks: [], units: [], totals: { forecast: 5500, forecast_to_date: 4200, actual: 4600, committed: 2800, error_pct: 9.5 }, seasons: [], bands: BANDS,
      by_crop: [
        { field_crop: "Cabbage", uom: "Pieces", forecast: 1500, forecast_to_date: 1200, actual: 1200, committed: 800, error_pct: 0 },
        { field_crop: "Potato", uom: "Kg", forecast: 4000, forecast_to_date: 3000, actual: 3400, committed: 2000, error_pct: 13.3 },
      ],
    });
    renderPage(<Forecast />, {}, FV);
    const t = await screen.findByTestId("forecast-by-crop");
    expect(t).toHaveTextContent("Cabbage");
    expect(t).toHaveTextContent("Pieces");
    expect(t).toHaveTextContent("Potato");
    expect(screen.queryByText("Buyer cover")).toBeNull();
  });

  it("keeps the single-crop layout for a section whose one crop is listed (Avocado)", async () => {
    const AV = { ...CROP, name: "Avocado", crop_key: "avocado", has_field_crops: 0, field_crops: [{ name: "Avocado", crop_name: "Avocado", harvest_uom: "Kg" }] } as never;
    fc.mockResolvedValue({
      uom: "Kg", weeks: [], units: [], totals: { forecast: 5500, forecast_to_date: 4200, actual: 4600, committed: 2800, error_pct: 9.5 }, seasons: [], bands: BANDS,
      by_crop: [{ field_crop: "Avocado", uom: "Kg", forecast: 5500, forecast_to_date: 4200, actual: 4600, committed: 2800, error_pct: 9.5 }],
    });
    renderPage(<Forecast />, {}, AV);
    await screen.findByText(/No weekly forecast/i);
    expect(screen.queryByTestId("forecast-by-crop")).toBeNull();
  });

  it("never links out to the standalone avocado pages", async () => {
    fc.mockResolvedValue({ uom: "Kg", weeks: [], units: [], totals: { forecast: 0, forecast_to_date: 0, actual: 0, committed: 0, error_pct: null }, seasons: [], bands: BANDS });
    renderPage(<Forecast />, {}, { ...CROP, crop_key: "avocado" });
    await screen.findByText(/No weekly forecast/i);
    expect(document.querySelector('a[href^="/avocado-"]')).toBeNull();
  });
});

import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CropTotals } from "@/components/forecast/CropTotals";
import { renderPage } from "@/pages/__tests__/testkit";

describe("CropTotals", () => {
  it("shows one line per crop in its own unit, with no grand total", () => {
    renderPage(
      <CropTotals
        bands={{}}
        rows={[
          { field_crop: "Cabbage", uom: "Pieces", forecast: 1500, forecast_to_date: 1200, actual: 1200, committed: 800, error_pct: 0 },
          { field_crop: "Potato", uom: "Kg", forecast: 4000, forecast_to_date: 3000, actual: 3400, committed: 2000, error_pct: 13.3 },
        ]}
      />,
    );
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(3);
    expect(rows[1].textContent).toContain("Pieces");
    expect(rows[2].textContent).toContain("Kg");
    expect(screen.queryByText(/total/i)).toBeNull();
  });

  it("adds a roll-up line per group and unit, keeping Kg and Pieces apart", () => {
    renderPage(
      <CropTotals
        bands={{}}
        crops={[
          { name: "Cabbage", crop_group: "Vegetable Crops" },
          { name: "Potato", crop_group: "Vegetable Crops" },
          { name: "Onion", crop_group: "Vegetable Crops" },
        ]}
        rows={[
          { field_crop: "Cabbage", uom: "Pieces", forecast: 1500, forecast_to_date: 1200, actual: 1200, committed: 800, error_pct: 0 },
          { field_crop: "Potato", uom: "Kg", forecast: 4000, forecast_to_date: 3000, actual: 3400, committed: 2000, error_pct: 13.3 },
          { field_crop: "Onion", uom: "Kg", forecast: 1000, forecast_to_date: 500, actual: 600, committed: 0, error_pct: 0 },
        ]}
      />,
    );
    const lines = screen.getAllByTestId("group-total");
    expect(lines).toHaveLength(2);
    expect(lines[0].textContent).toContain("Vegetable Crops");
    expect(lines[0].textContent).toContain("Kg");
    expect(lines[0].textContent).toContain("5,000");
    expect(lines[1].textContent).toContain("Pieces");
    expect(lines[1].textContent).toContain("1,500");
  });

  it("keeps forecast, actual and committed of one group and unit together, whatever the row order", () => {
    renderPage(
      <CropTotals
        bands={{}}
        crops={[
          { name: "Cabbage", crop_group: "Vegetable Crops" },
          { name: "Rose", crop_group: "Floriculture" },
          { name: "Potato", crop_group: "Vegetable Crops" },
        ]}
        rows={[
          { field_crop: "Potato", uom: "Kg", forecast: 100, forecast_to_date: 0, actual: 10, committed: 1, error_pct: null },
          { field_crop: "Rose", uom: "Stem", forecast: 500, forecast_to_date: 0, actual: 50, committed: 5, error_pct: null },
          { field_crop: "Cabbage", uom: "Pieces", forecast: 200, forecast_to_date: 0, actual: 20, committed: 2, error_pct: null },
          { field_crop: "Potato", uom: "Kg", forecast: 300, forecast_to_date: 0, actual: 30, committed: 3, error_pct: null },
        ]}
      />,
    );
    const lines = screen.getAllByTestId("group-total").map((l) => l.textContent);
    expect(lines).toHaveLength(3);
    expect(lines[0]).toMatch(/Floriculture.*Stem.*Forecast 500.*Actual 50.*Committed 5/);
    expect(lines[1]).toMatch(/Vegetable Crops.*Kg.*Forecast 400.*Actual 40.*Committed 4/);
    expect(lines[2]).toMatch(/Vegetable Crops.*Pieces.*Forecast 200.*Actual 20.*Committed 2/);
  });
});

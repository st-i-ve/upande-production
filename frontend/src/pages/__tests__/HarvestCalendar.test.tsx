import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/avocado-api", () => ({ getHarvestCalendar: vi.fn() }));
import { getHarvestCalendar } from "@/lib/avocado-api";
import { HarvestCalendar } from "@/pages/avocado/HarvestCalendar";

const mocked = vi.mocked(getHarvestCalendar);

const weeks = ["2026-10-26", "2026-11-02", "2026-11-09"].map((week, i) => ({
  week, iso_week: 44 + i, label: ["26 Oct", "2 Nov", "9 Nov"][i], kg: [0, 1800, 3600][i], crates: [0, 100, 200][i], is_peak: i === 2, shade: i * 2,
}));
const cell = (i: number, kind: string, kg = 0, shade = 0) => ({ week: weeks[i].week, kind, kg, crates: kg / 18, shade });
const base = {
  farm: "Mutara", planting_year: 2018, expected_kg: 5400, dm_basis: "", samples: 2, stale: false, start: null, placed_on: null, placed_basis: null,
  weeks_to_go: null, ready_date: null, cohort_note: "", has_date: true,
};

const payload = {
  filters: { farms: ["Mutara"], planting_years: [2018] },
  selected: { farm: null, planting_year: null },
  minimum_pct: 24, kg_per_crate: 18, pick_weeks: 3,
  summary: { blocks: 3, weeks: 3, total_kg: 5400, total_crates: 300 },
  kpis: {
    peak_week: { week: weeks[2].week, iso_week: 46, kg: 3600, crates: 200 },
    in_window: { kg: 5400, crates: 300, from_iso_week: 45, to_iso_week: 46 },
    pickable_now: { blocks: 1, of: 3, minimum_pct: 24 },
    no_pick_date: { kg: 900, blocks: 1 },
  },
  weeks, max_cell_kg: 3600,
  blocks: [
    { ...base, block: "Block A", state: "ready", dry_matter_pct: 26.1, row_kg: 5400, row_crates: 300,
      cells: [cell(0, "empty"), cell(1, "fill", 1800, 2), cell(2, "fill", 3600, 5)] },
    { ...base, block: "Block B", state: "waiting", dry_matter_pct: 21.5, ready_date: "2026-11-10", weeks_to_go: 2, row_kg: 0, row_crates: 0,
      cells: [cell(0, "locked"), cell(1, "locked"), cell(2, "locked")] },
    { ...base, block: "Block C", state: "unsampled", dry_matter_pct: null, row_kg: 0, row_crates: 0, has_date: false,
      cells: [cell(0, "no_sample"), cell(1, "no_sample"), cell(2, "no_sample")] },
  ],
  no_pick_date: [{ block: "Block C", farm: "Mutara", expected_kg: 900, reason: "never_sampled" }],
  no_forecast: [{ block: "Block Y", farm: "Mutara", planting_year: null, bearing_trees: 0, reason: "no_planting_year" }],
  states: { ready: "Ready", waiting: "Waiting", last_season: "Last season", nodate: "No date", unsampled: "Never sampled" },
};

describe("HarvestCalendar", () => {
  beforeEach(() => {
    mocked.mockReset().mockResolvedValue(payload as never);
  });

  it("draws the heat grid, locked and unsampled cells, totals and the tables", async () => {
    renderPage(<HarvestCalendar />);
    const row = await screen.findByTestId("calendar-row-Block A");
    expect(within(row).getAllByTestId("calendar-cell")).toHaveLength(2);
    expect(within(row).getAllByTestId("calendar-cell")[1]).toHaveAttribute("data-peak", "true");
    expect(within(screen.getByTestId("calendar-row-Block B")).getAllByTestId("calendar-cell-locked")).toHaveLength(3);
    expect(within(screen.getByTestId("calendar-row-Block C")).getAllByTestId("calendar-cell-no_sample")).toHaveLength(3);
    expect(screen.getByTestId("calendar-week-total-peak")).toHaveTextContent("3.60");
    expect(screen.getByText("Wk 46")).toBeInTheDocument();
    expect(screen.getByText("Never sampled", { selector: "span[title]" })).toBeInTheDocument();
    expect(screen.getByText("No planting year")).toBeInTheDocument();
  });

  it("switches the cells between tonnes, crates and kg", async () => {
    renderPage(<HarvestCalendar />);
    const row = await screen.findByTestId("calendar-row-Block A");
    expect(within(row).getAllByTestId("calendar-cell")[1]).toHaveTextContent("3.60");
    fireEvent.click(screen.getByRole("button", { name: "Crates" }));
    expect(within(row).getAllByTestId("calendar-cell")[1]).toHaveTextContent("200");
    fireEvent.click(screen.getByRole("button", { name: "Kg" }));
    expect(within(row).getAllByTestId("calendar-cell")[1]).toHaveTextContent("3,600");
  });

  it("shows the empty sentence when no weeks can be placed", async () => {
    mocked.mockResolvedValue({ ...payload, blocks: [], weeks: [] } as never);
    renderPage(<HarvestCalendar />);
    await waitFor(() => expect(screen.getByText(/A block needs a forecast in kilograms and a dry matter reading/)).toBeInTheDocument());
  });
});

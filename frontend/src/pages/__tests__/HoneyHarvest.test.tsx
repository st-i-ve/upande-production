import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/apiary-api", () => ({ getHoneyHarvest: vi.fn(), saveHoneyHarvest: vi.fn() }));
import { getHoneyHarvest, saveHoneyHarvest } from "@/lib/apiary-api";
import { HoneyHarvest } from "@/pages/apiary/HoneyHarvest";

const get = vi.mocked(getHoneyHarvest);
const save = vi.mocked(saveHoneyHarvest);

const row = (name: string, unit: string, kg: number, moisture: number, grade: string) => ({
  name, unit, unit_label: unit, harvest_date: "2026-10-13", supers_removed: 6, frames_extracted: 48, honey_kg: kg, moisture_pct: moisture, grade, wax_kg: 2.2, notes: "Spring flow",
});
const payload = () => ({
  from_date: "2025-10-30", to_date: "2026-10-28", unit: null,
  kpis: { kg: 210.5, harvests: 2, colonies: 22, kg_per_hive: 9.57, avg_moisture: 19.2, grade_a_pct: 55.5, wax_kg: 4.4 },
  series: [{ week: "2026-10-12", kg: 210.5, avg_moisture: 19.2, grade_a_pct: 55.5 }],
  groups: [
    { unit: "Hive Group North", label: "Hive Group North", farm: "Mutara", harvests: 1, kg: 118, colonies: 12, kg_per_hive: 9.83, avg_moisture: 17.8, grade_a_pct: 100, wax_kg: 3.1, supers_removed: 8, last_harvest: "2026-10-13" },
    { unit: "Hive Group South", label: "Hive Group South", farm: "Mutara", harvests: 1, kg: 92.5, colonies: 10, kg_per_hive: 9.25, avg_moisture: 20.9, grade_a_pct: 0, wax_kg: 1.3, supers_removed: 5, last_harvest: "2026-10-13" },
  ],
  rows: [row("HHL-1", "Hive Group North", 118, 17.8, "A"), row("HHL-2", "Hive Group South", 92.5, 20.9, "C")],
  form: { units: [{ value: "Hive Group North", label: "Hive Group North" }, { value: "Hive Group South", label: "Hive Group South" }], today: "2026-10-28", grades: ["A", "B", "C"], moisture_limit: 20 },
});

describe("HoneyHarvest", () => {
  beforeEach(() => {
    // recharts' ResponsiveContainer needs it; jsdom has none.
    vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
    get.mockReset().mockResolvedValue(payload() as never);
    save.mockReset().mockResolvedValue({ ok: true, name: "HHL-3", message: "ok" } as never);
  });

  it("draws KPIs, the per-group table and the log with wet honey flagged", async () => {
    renderPage(<HoneyHarvest />);
    const groups = await screen.findByTestId("group-table");
    expect(groups).toHaveTextContent("Hive Group North");
    expect(groups).toHaveTextContent("9.83");
    expect(screen.getByText("Per hive")).toBeInTheDocument();
    expect(screen.getByText("210.5 kg")).toBeInTheDocument();
    const log = screen.getByTestId("harvest-table");
    expect(log).toHaveTextContent("Spring flow");
    expect(log).toHaveTextContent("wet");
    expect(log).toHaveTextContent("Grade C");
  });

  it("shows an empty state with no harvests", async () => {
    get.mockResolvedValue({ ...payload(), rows: [], series: [], kpis: { kg: 0, harvests: 0, colonies: 0, kg_per_hive: null, avg_moisture: null, grade_a_pct: null, wax_kg: 0 } } as never);
    renderPage(<HoneyHarvest />);
    expect(await screen.findByText(/No honey recorded yet/)).toBeInTheDocument();
  });

  it("validates then saves a harvest and refreshes", async () => {
    renderPage(<HoneyHarvest />);
    await screen.findByTestId("group-table");
    fireEvent.click(screen.getByRole("button", { name: /Record harvest/ }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Save harvest" }));
    expect(await within(dialog).findByText("Choose the hive group.")).toBeInTheDocument();
    expect(within(dialog).getByText("Honey kg must be more than zero.")).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole("combobox", { name: "Hive group" }));
    fireEvent.click(await screen.findByRole("option", { name: "Hive Group South" }));
    fireEvent.change(within(dialog).getByLabelText("Honey (kg)"), { target: { value: "45.5" } });
    fireEvent.change(within(dialog).getByLabelText("Moisture %"), { target: { value: "18.4" } });
    const calls = get.mock.calls.length;
    fireEvent.click(within(dialog).getByRole("button", { name: "Save harvest" }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ unit: "Hive Group South", honey_kg: 45.5, moisture_pct: 18.4, grade: "A", harvest_date: "2026-10-28" }));
    await waitFor(() => expect(get.mock.calls.length).toBeGreaterThan(calls));
    expect(await screen.findByText("Harvest saved.")).toBeInTheDocument();
  });

  it("rejects moisture out of range", async () => {
    renderPage(<HoneyHarvest />);
    await screen.findByTestId("group-table");
    fireEvent.click(screen.getByRole("button", { name: /Record harvest/ }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Honey (kg)"), { target: { value: "5" } });
    fireEvent.change(within(dialog).getByLabelText("Moisture %"), { target: { value: "60" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save harvest" }));
    expect(await within(dialog).findByText(/Moisture must be between 5 and 40%/)).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();
  });
});

import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/fv-api", () => ({ getIrrigation: vi.fn(), saveIrrigationRun: vi.fn(), getGrading: vi.fn(), saveGrading: vi.fn() }));
vi.mock("@/components/fv/PivotMap", () => ({ PivotMap: () => <div data-testid="pivot-map" /> }));
import { getIrrigation, saveIrrigationRun } from "@/lib/fv-api";
import { Irrigation } from "@/pages/fruits-vegetables/Irrigation";

const get = vi.mocked(getIrrigation);
const save = vi.mocked(saveIrrigationRun);

const run = (name: string, unit: string, start: string, end: string, fault: string) => ({
  name, unit, start_time: start, end_time: end, hours: 10, direction: "Forward", percent_timer: 70, depth_mm: 12, water_source: "Borehole 2",
  operator: null, operator_name: null, fault, notes: null, slices: [`${unit}-1`],
});
const payload = () => ({
  from_date: "2026-09-21", to_date: "2026-10-28", pivot: null, pivot_names: ["Pivot 1", "Pivot 3"],
  pivots: [
    { name: "Pivot 1", area_ha: 24, slices: 4, runs: 2, hours: 20, faults: 0, mm_per_slice: 130, utilisation_pct: 18 },
    { name: "Pivot 3", area_ha: 21, slices: 4, runs: 1, hours: 4, faults: 1, mm_per_slice: 60, utilisation_pct: 4 },
  ],
  target: { weekly_mm: 25, period_mm: 137, weeks: 5.5 },
  kpis: { runs: 3, hours: 24, mm_total: 36, mm_per_slice_avg: 95, slices_on_target: 4, slices: 8, faults: 1, utilisation_pct: 12 },
  series: [{ week: "2026-10-12", runs: 1, hours: 10, mm_per_slice: 12 }, { week: "2026-10-19", runs: 2, hours: 14, mm_per_slice: 20 }],
  slices: [{ slice: "Pivot 1-1", pivot: "Pivot 1", item: "Potatoes", mm: 130, target_mm: 137, pct_of_target: 95 }],
  runs: [
    run("PIR-1", "Pivot 1", "2026-10-13 06:00:00", "2026-10-13 16:00:00", "None"),
    run("PIR-2", "Pivot 1", "2026-10-20 06:00:00", "2026-10-20 16:00:00", "None"),
    run("PIR-3", "Pivot 3", "2026-10-21 06:00:00", "2026-10-21 10:00:00", "Tower misalignment"),
  ],
  faults: [{ name: "PIR-3", pivot: "Pivot 3", start_time: "2026-10-21 06:00:00", hours: 4, fault: "Tower misalignment", depth_mm: 4, operator: null, notes: "Tower 7 out of line." }],
  map: { type: "FeatureCollection", features: [], bounds: [[36.7, 0], [36.8, 0.1]] },
  form: { pivots: [{ name: "Pivot 1", slices: ["Pivot 1-1", "Pivot 1-2"] }, { name: "Pivot 3", slices: ["Pivot 3-1"] }], faults: ["None", "Tower misalignment"], directions: ["Forward", "Reverse"], water_sources: ["Borehole 2"] },
});

describe("Irrigation", () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue(payload() as never);
    save.mockReset().mockResolvedValue({ ok: true, name: "PIR-9", hours: 8 } as never);
  });

  it("draws KPIs, a lane and bar per run, the map and the fault list", async () => {
    renderPage(<Irrigation />);
    const lane = await screen.findByTestId("lane-Pivot 1");
    expect(within(lane).getAllByTestId("run-bar")).toHaveLength(2);
    expect(within(screen.getByTestId("lane-Pivot 3")).getAllByTestId("run-bar")).toHaveLength(1);
    expect(screen.getByText("95 mm")).toBeInTheDocument();
    expect(screen.getByTestId("pivot-map")).toBeInTheDocument();
    expect(screen.getByTestId("fault-list")).toHaveTextContent("Tower misalignment");
    expect(screen.getByTestId("fault-list")).toHaveTextContent("Tower 7 out of line.");
    expect(screen.getByTestId("pivot-Pivot 3")).toHaveTextContent("1 fault");
  });

  it("shows an empty state when no runs fall in the period", async () => {
    get.mockResolvedValue({ ...payload(), runs: [], faults: [], pivots: [] } as never);
    renderPage(<Irrigation />);
    expect(await screen.findByTestId("no-runs")).toBeInTheDocument();
    expect(screen.getByTestId("no-faults")).toBeInTheDocument();
  });

  it("validates the dialog before saving", async () => {
    renderPage(<Irrigation />);
    await screen.findByTestId("lane-Pivot 1");
    fireEvent.click(screen.getByRole("button", { name: /Record run/ }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Save run" }));
    expect(await within(dialog).findByText(/Enter the depth applied in mm/)).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();
    fireEvent.change(within(dialog).getByLabelText("Depth applied (mm)"), { target: { value: "150" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save run" }));
    expect(await within(dialog).findByText(/looks like a typo/)).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();
  });

  it("saves a run with every slice of the first pivot, then refreshes", async () => {
    renderPage(<Irrigation />);
    await screen.findByTestId("lane-Pivot 1");
    fireEvent.click(screen.getByRole("button", { name: /Record run/ }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByTestId("ir-hours")).toHaveTextContent("8.0 hours");
    fireEvent.change(within(dialog).getByLabelText("Depth applied (mm)"), { target: { value: "12" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save run" }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    expect(save).toHaveBeenCalledWith(expect.objectContaining({ unit: "Pivot 1", depth_mm: 12, slices: ["Pivot 1-1", "Pivot 1-2"], fault: "None" }));
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
  });

  it("reports an error from the server without closing", async () => {
    save.mockResolvedValue({ error: "The run must end after it starts." } as never);
    renderPage(<Irrigation />);
    await screen.findByTestId("lane-Pivot 1");
    fireEvent.click(screen.getByRole("button", { name: /Record run/ }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Depth applied (mm)"), { target: { value: "12" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save run" }));
    expect(await screen.findByText("The run must end after it starts.")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});

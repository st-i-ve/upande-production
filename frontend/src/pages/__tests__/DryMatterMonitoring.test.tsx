import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/dmmonitor-api", async (orig) => ({
  ...(await orig<typeof import("@/lib/dmmonitor-api")>()),
  getMonitor: vi.fn(),
  saveFruitTag: vi.fn(),
  addFruitReading: vi.fn(),
  deleteFruitReading: vi.fn(),
  updateFruitTag: vi.fn(),
}));
import { addFruitReading, combinePct, getMonitor, microwavePct, saveFruitTag } from "@/lib/dmmonitor-api";
import { DryMatterMonitoring, projectionText } from "@/pages/avocado/DryMatterMonitoring";

const get = vi.mocked(getMonitor);

const reading = (name: string, date: string, mw: number | null, mc: number | null) => ({
  name, idx: 1, reading_date: date, method: mw && mc ? "Both" : mw ? "Microwave" : "Machine", fresh_g: null, dish_g: null, dry_g: null,
  microwave_pct: mw, machine_pct: mc, instrument: null, dm_pct: mw && mc ? (mw + mc) / 2 : (mw ?? mc) as number, recorded_by: "a@b.c", notes: null,
});
const tag = (name: string, unit: string, tree: string, fruit: string, latest: number | null, readings = [] as ReturnType<typeof reading>[]) => ({
  name, unit, farm: "Mutara", crop: "Test Crop", cycle: null, variety: "Hass", tree_label: tree, fruit_tag: fruit, tagged_on: "2026-10-01",
  status: "Active" as const, notes: null, readings, latest_pct: latest, latest_on: latest ? "2026-10-19" : null, ready: latest != null && latest >= 24,
});
const payload = () => {
  const r1 = [reading("r1", "2026-10-05", 20, null), reading("r2", "2026-10-12", 21, 21), reading("r3", "2026-10-19", 23, 22)];
  const pts = r1.map((r) => ({ date: r.reading_date, dm_pct: r.dm_pct, microwave_pct: r.microwave_pct, machine_pct: r.machine_pct, fruit: 1 }));
  const proj = { state: "rising" as const, date: "2026-11-01", slope_per_week: 1.2, points: 3 };
  return {
    crop: "Test Crop", target_pct: 24, max_pct: 34,
    blocks: [{ unit: "Block A", farm: "Mutara" }, { unit: "Block B", farm: "Mutara" }],
    tags: [tag("DMF-1", "Block A", "R12-T7", "1", 22.5, r1), tag("DMF-2", "Block A", "R12-T8", "2", 26, [reading("r4", "2026-10-19", null, 26)])],
    series: {
      fruit: { "DMF-1": { points: pts, projection: proj }, "DMF-2": { points: [], projection: { state: "none", date: null, slope_per_week: null, points: 0 } } },
      tree: { "Block A||R12-T7": { points: pts, projection: proj, fruit: 1 } },
      block: { "Block A": { points: pts, projection: proj, fruit: 2 } },
    },
    lab: { "Block A": [{ date: "2026-10-10", dm_pct: 21.5 }] },
    drives: "",
  };
};

describe("dry matter monitoring maths", () => {
  it("works the microwave percentage out, with and without a dish", () => {
    expect(microwavePct("50", "12.5", "")).toEqual({ pct: 25, problem: null });
    expect(microwavePct("24.5", "14.5", "4.5").pct).toBe(50);
    expect(microwavePct("20", "25", "").problem).toMatch(/more than the fresh/);
    expect(microwavePct("20", "", "").problem).toMatch(/both/);
    expect(microwavePct("", "", "").pct).toBeNull();
  });
  it("averages the two methods, else uses the one that exists", () => {
    expect(combinePct(24, 26)).toBe(25);
    expect(combinePct(null, 26.5)).toBe(26.5);
    expect(combinePct(null, null)).toBeNull();
  });
  it("words the projection", () => {
    expect(projectionText({ state: "flat", date: null, slope_per_week: -1, points: 3 }, 24).value).toBe("Not gaining");
    expect(projectionText(undefined, null).hint).toMatch(/no export target/);
  });
});

describe("DryMatterMonitoring", () => {
  beforeEach(() => {
    vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
    get.mockReset().mockResolvedValue(payload() as never);
    vi.mocked(saveFruitTag).mockReset().mockResolvedValue(tag("DMF-3", "Block A", "R1-T1", "9", null) as never);
    vi.mocked(addFruitReading).mockReset().mockResolvedValue(tag("DMF-1", "Block A", "R12-T7", "1", 25) as never);
  });

  it("lists the tagged fruit and draws the block line with the target", async () => {
    renderPage(<DryMatterMonitoring />);
    const rows = await screen.findByTestId("dm-tags");
    expect(within(rows).getByText("R12-T7")).toBeInTheDocument();
    expect(within(rows).getByText("At target")).toBeInTheDocument();
    expect(screen.getByTestId("dm-monitor-chart")).toBeInTheDocument();
    expect(screen.getByText("Reaches target")).toBeInTheDocument();
    expect(screen.getByText(/~1 Nov/)).toBeInTheDocument();
  });

  it("shows a fruit's readings with both methods when a row is chosen", async () => {
    renderPage(<DryMatterMonitoring />);
    const rows = await screen.findByTestId("dm-tags");
    fireEvent.click(within(rows).getByText("R12-T7"));
    const panel = await screen.findByTestId("dm-fruit-panel");
    expect(panel).toHaveTextContent("Both");
    expect(panel).toHaveTextContent("22.5%");
  });

  it("works out the reading in the modal as weights are typed, and saves it", async () => {
    renderPage(<DryMatterMonitoring />);
    await screen.findByTestId("dm-tags");
    fireEvent.click(screen.getByRole("button", { name: /Add a reading/ }));
    const dlg = await screen.findByRole("dialog");
    fireEvent.change(within(dlg).getByLabelText("Fresh weight (g)"), { target: { value: "50" } });
    fireEvent.change(within(dlg).getByLabelText("Dry weight (g)"), { target: { value: "12.5" } });
    expect(within(dlg).getByTestId("dmr-micro")).toHaveTextContent("25.0%");
    fireEvent.change(within(dlg).getByLabelText(/Meter reading/), { target: { value: "27" } });
    expect(within(dlg).getByTestId("dmr-result")).toHaveTextContent("26.0% dry matter (average of microwave 25.0% and machine 27.0%)");
    // no fruit chosen yet: refused with a reason
    fireEvent.click(within(dlg).getByRole("button", { name: "Save reading" }));
    expect(await within(dlg).findByRole("alert")).toHaveTextContent("Choose the fruit.");
    expect(addFruitReading).not.toHaveBeenCalled();
  });

  it("refuses a tag number already used on the tree", async () => {
    renderPage(<DryMatterMonitoring />);
    await screen.findByTestId("dm-tags");
    fireEvent.click(screen.getByRole("button", { name: /Tag a fruit/ }));
    const dlg = await screen.findByRole("dialog");
    fireEvent.change(within(dlg).getByLabelText("Tree"), { target: { value: "R1-T1" } });
    fireEvent.click(within(dlg).getByRole("button", { name: "Tag fruit" }));
    await waitFor(() => expect(within(dlg).getByRole("alert")).toHaveTextContent("Choose the block."));
    expect(within(dlg).getByRole("alert")).toHaveTextContent("Give the fruit its tag number.");
    expect(saveFruitTag).not.toHaveBeenCalled();
  });
});

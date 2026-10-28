import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("maplibre-gl", () => ({
  default: { Marker: class { setLngLat() { return this; } addTo() { return this; } remove() {} } },
}));
const fake = { on: vi.fn(), off: vi.fn(), fitBounds: vi.fn(), getZoom: () => 10, getCanvas: () => ({ style: {} }) };
vi.mock("@/components/map", async () => {
  const actual = await vi.importActual<typeof import("@/components/map")>("@/components/map/index");
  const { useEffect } = await import("react");
  return {
    ...actual,
    MapBase: ({ onReady }: { onReady: (m: unknown) => void }) => {
      useEffect(() => onReady(fake), []); // eslint-disable-line react-hooks/exhaustive-deps
      return <div data-testid="mapbase" />;
    },
    setCoverageData: vi.fn(),
    setCoverageSelected: vi.fn(),
  };
});
vi.mock("@/lib/map-api", async () => ({ ...(await vi.importActual<object>("@/lib/map-api")), coverageMap: vi.fn() }));
import { coverageMap } from "@/lib/map-api";
import { CoverageMap } from "@/pages/CoverageMap";

const mocked = vi.mocked(coverageMap);
const gj = { type: "Feature", geometry: { type: "Polygon", coordinates: [[[36.7, 0], [36.71, 0], [36.71, 0.01], [36.7, 0]]] } };
const task = (o: object) => ({ operation: "OP-1", operation_name: "Pruning", planned_qty: 10, done_qty: 4, pending_qty: null, remaining_qty: 6, uom: "Bed", status: "In Progress", due_date: "2026-10-27", late: true, ...o });
const unit = (o: object) => ({ parent: "Pivot 1", unit_type: "Block", area_ha: 2, geojson: gj, cycle: null, item: "Hass", tasks: [task({})], progress_pct: 40, remaining_qty: { Bed: 6 }, state: "late", ...o });
const payload = {
  week_start: "2026-10-26",
  week_end: "2026-11-01",
  units: [
    unit({ name: "B-notstarted", state: "not_started", progress_pct: 0, tasks: [task({ late: false, done_qty: 0, remaining_qty: 10 })], remaining_qty: { Bed: 10 } }),
    unit({ name: "B-done", state: "done", progress_pct: 100, remaining_qty: {}, tasks: [] }),
    unit({ name: "B-late" }),
  ],
  outlines: [],
  totals: { blocks: 3, planned: {}, done: {}, remaining: {}, pending: {}, late: 1, tasks: 3, by_state: { done: 1, partial: 0, not_started: 1, late: 1, pending_approval: 0, no_work: 0 } },
  operations: [{ operation: "OP-1", operation_name: "Pruning", uom: "Bed" }],
  center: [36.7, 0],
  bounds: [[36.7, 0], [36.71, 0.01]],
};

describe("CoverageMap", () => {
  beforeEach(() => {
    fake.on.mockClear();
    fake.fitBounds.mockClear();
    mocked.mockReset().mockResolvedValue(payload as never);
  });

  it("renders KPIs from the totals", async () => {
    renderPage(<CoverageMap />);
    const k = await screen.findByTestId("coverage-kpis");
    expect(k).toHaveTextContent("3 blocks");
    expect(k).toHaveTextContent("1 done");
    expect(k).toHaveTextContent("2 remaining");
    expect(k).toHaveTextContent("1 late");
    expect(screen.getByText("Coverage Map")).toBeInTheDocument();
  });

  it("lists remaining work most urgent first, without finished blocks", async () => {
    renderPage(<CoverageMap />);
    const rows = await screen.findAllByTestId("remaining-row");
    expect(rows.map((r) => r.getAttribute("data-block"))).toEqual(["B-late", "B-notstarted"]);
  });

  it("selecting a block shows its card with a plan link", async () => {
    renderPage(<CoverageMap />);
    fireEvent.click((await screen.findAllByTestId("remaining-row"))[0]);
    const card = await screen.findByTestId("block-card");
    expect(card).toHaveTextContent("B-late");
    expect(card).toHaveTextContent("Pruning");
    expect(card).toHaveTextContent("Late");
    expect(screen.getByRole("link", { name: /Weekly Plan/ })).toHaveAttribute("href", "#/test-crop/plan");
    expect(fake.fitBounds).toHaveBeenCalled();
  });

  it("clicking a block on the map selects it", async () => {
    renderPage(<CoverageMap />);
    await screen.findByTestId("coverage-kpis");
    const click = fake.on.mock.calls.filter((c) => c[0] === "click").at(-1)![2];
    act(() => click({ features: [{ properties: { name: "B-notstarted" } }] }));
    expect(await screen.findByTestId("block-card")).toHaveTextContent("B-notstarted");
  });

  it("filters change the request", async () => {
    renderPage(<CoverageMap />, { farms: ["Mutara"] });
    await screen.findByTestId("coverage-kpis");
    expect(mocked.mock.calls[0][0]).toMatchObject({ crop: "Test Crop", farm: null, status: null });
    fireEvent.click(screen.getByRole("button", { name: "Next week" }));
    await waitFor(() => expect(mocked.mock.calls.length).toBeGreaterThan(1));
    const first = mocked.mock.calls[0][0];
    const last = mocked.mock.calls.at(-1)![0];
    expect(last.week !== first.week || last.year !== first.year).toBe(true);
  });

  it("shows an empty state when no unit has geometry", async () => {
    mocked.mockResolvedValue({ ...payload, bounds: null, center: null } as never);
    renderPage(<CoverageMap />);
    expect(await screen.findByText(/has a boundary drawn/i)).toBeInTheDocument();
  });

  it("toasts on error", async () => {
    mocked.mockResolvedValue({ error: "Boom" } as never);
    renderPage(<CoverageMap />);
    expect(await screen.findByText("Boom")).toBeInTheDocument();
  });
});

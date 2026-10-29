import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Outlook } from "@/pages/avocado/Outlook";
import * as api from "@/lib/avocado-api";
import { outlookFixture } from "./avocado-fixtures";
import { renderPage } from "./testkit";

vi.mock("maplibre-gl", () => ({ default: {} }));
vi.mock("@/components/map", async () => {
  const actual = await vi.importActual<typeof import("@/components/map")>("@/components/map/index");
  return { ...actual, MapBase: () => <div data-testid="mapbase" /> };
});
vi.mock("@/lib/avocado-api", async (orig) => ({
  ...(await orig<typeof api>()),
  getSeasonOutlook: vi.fn(),
  savePricePerKg: vi.fn(),
}));
const getOutlook = vi.mocked(api.getSeasonOutlook);
const savePrice = vi.mocked(api.savePricePerKg);

describe("Outlook", () => {
  beforeEach(() => {
    getOutlook.mockReset().mockResolvedValue(structuredClone(outlookFixture));
    savePrice.mockReset().mockResolvedValue({ ok: true, price_per_kg: 100 });
  });

  it("renders every section from the payload", async () => {
    renderPage(<Outlook />);
    expect(await screen.findByText("Season timeline")).toBeTruthy();
    for (const label of ["Season crop", "Crop value", "Ready to pick", "Crew next week", "Estimate accuracy", "Stale readings"]) {
      expect(screen.getByText(label)).toBeTruthy();
    }
    expect(screen.getByTestId("kpi-season_crop").textContent).toContain("135.3 t");
    expect(screen.getByTestId("kpi-crop_value").textContent).toContain("KES 12.9M");
    for (const t of ["Orchard", "Blocks", "Dry matter", "Pickers", "Lost to sick trees", "Needs attention", "Delivered by season"]) {
      expect(screen.getAllByText(t).length).toBeGreaterThan(0);
    }
    // orchard map (polygons present), treemap cells, delivered seasons, an alert
    expect(screen.getByTestId("mapbase")).toBeTruthy();
    expect(within(screen.getByTestId("outlook-treemap")).getByRole("button", { name: /A/ })).toBeTruthy();
    expect(screen.getByText("2024")).toBeTruthy();
    expect(screen.getByText(/blocks losing fruit to sick trees and gaps/)).toBeTruthy();
    expect(screen.getByText(/2018 planting/)).toBeTruthy();
    expect(screen.queryByTestId("outlook-undated")).toBeNull();
  });

  it("trims the empty stretch and brings it back with Whole season", async () => {
    renderPage(<Outlook />);
    expect(await screen.findByText(/empty weeks hidden/)).toBeTruthy();
    const timeline = screen.getByTestId("outlook-timeline");
    const bars = () => timeline.querySelectorAll("rect[data-kind]").length;
    const trimmed = bars();
    expect(trimmed).toBe(8); // the eight forecast weeks; the picked May-June weeks are trimmed away
    fireEvent.click(screen.getByRole("button", { name: /Whole season/ }));
    expect(screen.queryByText(/empty weeks hidden/)).toBeNull();
    expect(bars()).toBeGreaterThan(trimmed);
  });

  it("says why there is no map when no block has a boundary", async () => {
    const d = structuredClone(outlookFixture);
    d.map = { blocks: [], surveyed: 0, without_boundary: 2, area_disagrees: 0 };
    getOutlook.mockResolvedValue(d);
    renderPage(<Outlook />);
    expect(await screen.findByText("No boundaries")).toBeTruthy();
    expect(screen.queryByTestId("mapbase")).toBeNull();
  });

  it("tries a price and a crew for this view without saving them", async () => {
    renderPage(<Outlook />);
    fireEvent.click(await screen.findByRole("button", { name: /Price \/ kg: KES 95/ }));
    fireEvent.change(await screen.findByLabelText(/Price \/ kg \(KES\)/), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: "Try here" }));
    await waitFor(() => expect(getOutlook).toHaveBeenLastCalledWith(expect.objectContaining({ price_per_kg: 100 })));
    expect(savePrice).not.toHaveBeenCalled();

    fireEvent.click(await screen.findByRole("button", { name: /Crew available: 14/ }));
    fireEvent.change(await screen.findByLabelText(/Crew available \(pickers\)/), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(getOutlook).toHaveBeenLastCalledWith(expect.objectContaining({ price_per_kg: 100, crew_available: 20 })));
  });

  it("lets a manager save the price for everyone, and toasts the server's error", async () => {
    renderPage(<Outlook />);
    fireEvent.click(await screen.findByRole("button", { name: /Price \/ kg: KES 95/ }));
    fireEvent.change(await screen.findByLabelText(/Price \/ kg \(KES\)/), { target: { value: "100" } });
    fireEvent.click(screen.getByRole("button", { name: "Save for everyone" }));
    await waitFor(() => expect(savePrice).toHaveBeenCalledWith(100));
    expect(await screen.findByText("Estate price saved.")).toBeTruthy();

    savePrice.mockResolvedValue({ error: "Price must be a number." });
    fireEvent.click(await screen.findByRole("button", { name: /Price \/ kg: KES/ }));
    fireEvent.change(await screen.findByLabelText(/Price \/ kg \(KES\)/), { target: { value: "100" } });
    fireEvent.click(await screen.findByRole("button", { name: "Save for everyone" }));
    expect(await screen.findByText("Price must be a number.")).toBeTruthy();
  });

  it("says plainly when no season has been delivered, instead of showing a stand-in", async () => {
    const d = structuredClone(outlookFixture);
    const k = d.kpis.find((x) => x.key === "estimate_accuracy")!;
    Object.assign(k, { value: null, note: "no delivered season yet", none_yet: true, calibration_factor: 1, meter_pct: 0 });
    getOutlook.mockResolvedValue(d);
    renderPage(<Outlook />);
    const card = await screen.findByTestId("kpi-estimate_accuracy");
    expect(card.textContent).toContain("None yet");
    expect(card.textContent).toContain("no delivered season yet");
  });

  it("shows the undated chip and empty states", async () => {
    const d = structuredClone(outlookFixture);
    d.undated = { kg: 21000, blocks: [{ block: "E", expected_kg: 21000, reason: "stale sample" }], stale_blocks: [] };
    d.alerts = [];
    d.losses = { rows: [], lost_kg: 0, lost_value_kes: null };
    d.dry_matter.cohorts = [];
    d.dry_matter.blocks = [];
    getOutlook.mockResolvedValue(d);
    renderPage(<Outlook />);
    expect(await screen.findByTestId("outlook-undated")).toBeTruthy();
    expect(screen.getByText("21.0 t undated")).toBeTruthy();
    expect(screen.getByText("Nothing wrong")).toBeTruthy();
    expect(screen.getByText(/no sick trees or gaps recorded/)).toBeTruthy();
    expect(screen.getByText("No samples")).toBeTruthy();
  });
});

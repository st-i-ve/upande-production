import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AddCycleDialog, capacityWarnings, treeAge } from "@/components/cycles/AddCycleDialog";
import * as api from "@/lib/api";
import * as setup from "@/lib/cycle-setup-api";
import * as varieties from "@/lib/varieties-api";
import { CROP, renderPage } from "@/pages/__tests__/testkit";

vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof api>()), listProtocols: vi.fn() }));
vi.mock("@/lib/varieties-api", async (orig) => ({ ...(await orig<typeof varieties>()), listVarieties: vi.fn() }));
vi.mock("@/lib/cycle-setup-api", async (orig) => ({
  ...(await orig<typeof setup>()),
  addCycle: vi.fn(),
  importTemplate: vi.fn(),
  previewImport: vi.fn(),
  importCycles: vi.fn(),
}));

const unit = (over: Partial<api.UnitRow> = {}): api.UnitRow => ({
  name: "PH1-B1",
  unit_type: "Orchard Block",
  parent: null,
  is_group: 0,
  area_ha: 10,
  plant_count: 1500,
  cost_center: null,
  status: "Active",
  current_cycle: null,
  item: null,
  has_geojson: 0,
  cycles: [],
  ...over,
});

describe("canAddCycle", () => {
  const boot = { can_manage: true, can_plan: true };
  it("covers every crop that runs in cycles, for managers, but not bees, fish or flowers", () => {
    expect(setup.canAddCycle({ ...CROP, boot } as never)).toBe(true);
    expect(setup.canAddCycle({ ...CROP, crop_key: "fruits-vegetables", boot } as never)).toBe(true);
    expect(setup.canAddCycle({ ...CROP, crop_key: "aquaculture", uses_crop_cycles: 0, boot } as never)).toBe(false);
    expect(setup.canAddCycle({ ...CROP, desk_launcher: "Crop Production desk", boot } as never)).toBe(false);
    expect(setup.canAddCycle({ ...CROP, boot: { can_manage: false, can_plan: true } } as never)).toBe(false);
  });
});

describe("capacityWarnings", () => {
  it("is quiet while the cycles fit the block", () => {
    expect(capacityWarnings(unit(), 10, 1500)).toEqual([]);
  });

  it("warns on area and on trees, counting the cycles already running", () => {
    const u = unit({ cycles: [{ name: "C1", unit: "PH1-B1", item: null, variety: "Hass", current_stage: null, status: "Active", start_date: "2026-01-01", area_ha: 6, plant_count: 900 }] });
    const w = capacityWarnings(u, 6, 900);
    expect(w).toHaveLength(2);
    expect(w[0]).toMatch(/12\.0 ha.*10\.0 ha/);
  });
});

describe("treeAge", () => {
  it("is derived from the planting date", () => {
    expect(treeAge("2020-01-01", "2026-01-01")).toBe("6.0 years");
    expect(treeAge("2025-10-01", "2026-01-01")).toBe("3 months");
    expect(treeAge("")).toBe("—");
  });
});

describe("AddCycleDialog", () => {
  beforeEach(() => {
    vi.mocked(api.listProtocols).mockReset().mockResolvedValue({ rows: [{ name: "P1", protocol_name: "Hass season", version: 2, variety: "Hass" }] });
    vi.mocked(varieties.listVarieties).mockReset().mockResolvedValue({
      varieties: [{ name: "Hass", variety_name: "Hass", enabled: 1, default_protocol: "P1", plants_per_ha: 156, expected_yield_per_plant: 75, stages: [{ stage: "Flowering" }, { stage: "Fruit set" }] }],
    } as never);
    vi.mocked(setup.addCycle).mockReset().mockResolvedValue({ name: "CYC-1", warnings: [] });
  });

  it("offers the three ways in and the existing-cycle fields", async () => {
    renderPage(<AddCycleDialog crop={CROP} units={[unit()]} defaultUnit="PH1-B1" open onOpenChange={() => {}} onSaved={() => {}} />);
    expect(await screen.findByText("Add crop cycle")).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Bulk import" })).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: /Existing cycle/ }));
    expect(await screen.findByText("Current stage")).toBeTruthy();
    expect(screen.getByText("Planting date")).toBeTruthy();
    expect(screen.getByText(/Last season yield \(kg per year/)).toBeTruthy();
  });

  it("warns, and still lets the cycle be added, when the block is over capacity", async () => {
    const u = unit({ cycles: [{ name: "C1", unit: "PH1-B1", item: null, variety: "Fuerte", current_stage: null, status: "Active", start_date: "2026-01-01", area_ha: 6, plant_count: 900 }] });
    const onSaved = vi.fn();
    renderPage(<AddCycleDialog crop={CROP} units={[u]} defaultUnit="PH1-B1" open onOpenChange={() => {}} onSaved={onSaved} />);
    expect((await screen.findAllByRole("alert")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("combobox", { name: "Variety" }));
    fireEvent.click(await screen.findByRole("option", { name: "Hass" }));
    const create = await screen.findByRole("button", { name: "Create cycle" });
    await waitFor(() => expect((create as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(create);
    await waitFor(() => expect(setup.addCycle).toHaveBeenCalled());
    expect(vi.mocked(setup.addCycle).mock.calls[0][0]).toMatchObject({ unit: "PH1-B1", variety: "Hass", protocol: "P1", existing: false });
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("for another crop asks the date it was started, an optional stage and says it picks up from today", async () => {
    const FV = { ...CROP, name: "Fruits & Vegetables", crop_key: "fruits-vegetables", unit_label: "Block" };
    renderPage(<AddCycleDialog crop={FV} units={[unit()]} defaultUnit="PH1-B1" open onOpenChange={() => {}} onSaved={() => {}} />);
    // no "New cycle" tab: those crops keep their own form for a new cycle
    expect(screen.queryByRole("tab", { name: "New cycle" })).toBeNull();
    expect(await screen.findByText("Planted / started on")).toBeTruthy();
    expect(screen.getByText("Picks up from today: nothing before today is planned.")).toBeTruthy();
    expect(screen.getByText("Already harvesting")).toBeTruthy();
    expect(screen.queryByText("Last flowering date (optional)")).toBeNull();
  });

  it("for another crop without stages offers an item and Already harvesting, and no stage", async () => {
    vi.mocked(varieties.listVarieties).mockResolvedValue({ varieties: [] } as never);
    const FV = { ...CROP, name: "Fruits & Vegetables", crop_key: "fruits-vegetables", unit_label: "Block" };
    renderPage(<AddCycleDialog crop={FV} units={[unit()]} defaultUnit="PH1-B1" open onOpenChange={() => {}} onSaved={() => {}} />);
    const add = await screen.findByRole("button", { name: "Add existing cycle" });
    expect((add as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(await screen.findByLabelText("Item"), { target: { value: "Tomato" } });
    fireEvent.click(screen.getByLabelText("Already harvesting"));
    expect((screen.getByLabelText("Already harvesting") as HTMLInputElement).checked).toBe(true);
    expect(screen.queryByText("Current stage")).toBeNull();
  });
});

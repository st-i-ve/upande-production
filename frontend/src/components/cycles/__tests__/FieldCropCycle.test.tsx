import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AddCycleDialog } from "@/components/cycles/AddCycleDialog";
import * as api from "@/lib/api";
import * as setup from "@/lib/cycle-setup-api";
import * as varieties from "@/lib/varieties-api";
import { CROP, renderPage } from "@/pages/__tests__/testkit";

vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof api>()), listProtocols: vi.fn() }));
vi.mock("@/lib/varieties-api", async (orig) => ({ ...(await orig<typeof varieties>()), listVarieties: vi.fn() }));
vi.mock("@/lib/cycle-setup-api", async (orig) => ({ ...(await orig<typeof setup>()), addCycle: vi.fn(), importTemplate: vi.fn(), previewImport: vi.fn(), importCycles: vi.fn() }));

const FV: api.Crop = {
  ...CROP,
  name: "Fruits & Vegetables",
  crop_key: "fruits-vegetables",
  has_field_crops: 1,
  field_crops: [
    { name: "Cabbage", crop_name: "Cabbage", production_crop: "Fruits & Vegetables", product: "Cabbage", harvest_uom: "Pieces", color: null, enabled: 1 },
    { name: "Potato", crop_name: "Potato", production_crop: "Fruits & Vegetables", product: "Potatoes", harvest_uom: "Kg", color: null, enabled: 1 },
  ],
};
const block: api.UnitRow = { name: "P1-B3", unit_type: "Pivot Block", parent: null, is_group: 0, area_ha: 2, plant_count: 0, cost_center: null, status: "Active", current_cycle: null, item: null, has_geojson: 0, cycles: [] };

describe("AddCycleDialog for a section with crops", () => {
  beforeEach(() => {
    vi.mocked(api.listProtocols).mockReset().mockResolvedValue({ rows: [] });
    vi.mocked(varieties.listVarieties).mockReset().mockResolvedValue({
      varieties: [
        { name: "Gloria F1", variety_name: "Gloria F1", field_crop: "Cabbage", enabled: 1, stages: [] },
        { name: "Shangi", variety_name: "Shangi", field_crop: "Potato", enabled: 1, stages: [] },
      ],
    } as never);
    vi.mocked(setup.addCycle).mockReset().mockResolvedValue({ name: "CYC-1", warnings: [] });
  });

  it("picks the crop first, then only that crop's varieties, and sends both", async () => {
    renderPage(<AddCycleDialog crop={FV} units={[block]} defaultUnit="P1-B3" modes={["new"]} open onOpenChange={() => {}} onSaved={() => {}} />, true, FV);
    expect(await screen.findByRole("combobox", { name: "Crop" })).toBeTruthy();
    expect((screen.getByRole("combobox", { name: "Variety" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("combobox", { name: "Crop" }));
    fireEvent.click(await screen.findByRole("option", { name: "Cabbage" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Variety" }));
    expect(await screen.findByRole("option", { name: "Gloria F1" })).toBeTruthy();
    expect(screen.queryByRole("option", { name: "Shangi" })).toBeNull();
    fireEvent.click(screen.getByRole("option", { name: "Gloria F1" }));
    const create = await screen.findByRole("button", { name: "Create cycle" });
    await waitFor(() => expect((create as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(create);
    await waitFor(() => expect(setup.addCycle).toHaveBeenCalled());
    expect(vi.mocked(setup.addCycle).mock.calls[0][0]).toMatchObject({ unit: "P1-B3", field_crop: "Cabbage", variety: "Gloria F1" });
  });

  it("does not offer a crop picker for a section without crops", async () => {
    renderPage(<AddCycleDialog crop={{ ...FV, has_field_crops: 0, field_crops: [] }} units={[block]} defaultUnit="P1-B3" open onOpenChange={() => {}} onSaved={() => {}} />, true, FV);
    await screen.findByText("Add crop cycle");
    expect(screen.queryByRole("combobox", { name: "Crop" })).toBeNull();
    await waitFor(() => expect(varieties.listVarieties).toHaveBeenCalled());
  });
});

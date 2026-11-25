import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { EditCycleDialog } from "@/components/cycles/EditCycleDialog";
import * as api from "@/lib/api";
import * as setup from "@/lib/cycle-setup-api";
import * as varieties from "@/lib/varieties-api";
import { CROP, renderPage } from "@/pages/__tests__/testkit";

vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof api>()), listProtocols: vi.fn() }));
vi.mock("@/lib/varieties-api", async (orig) => ({ ...(await orig<typeof varieties>()), listVarieties: vi.fn() }));
vi.mock("@/lib/cycle-setup-api", async (orig) => ({ ...(await orig<typeof setup>()), getCycleForEdit: vi.fn(), updateCycle: vi.fn() }));

const cycle = { name: "CYC-1", unit: "PH1-B1", variety: "Hass", item: null, status: "Active" } as api.Cycle;
const edit = (over: Partial<setup.CycleEdit> = {}): setup.CycleEdit => ({
  name: "CYC-1", unit: "PH1-B1", crop: "Avocado", variety: "Hass", item: null, protocol: "P1", start_date: "2026-01-01", planting_date: null,
  area_ha: 10, plant_count: 1500, expected_harvest_start: null, expected_harvest_end: null, status: "Active", notes: null, existing_cycle: 1, has_tasks: false, ...over,
});
const units = [{ name: "PH1-B1", is_group: 0, status: "Active" }, { name: "PH1-B2", is_group: 0, status: "Active" }] as api.UnitRow[];

describe("EditCycleDialog", () => {
  beforeEach(() => {
    vi.mocked(api.listProtocols).mockReset().mockResolvedValue({ rows: [{ name: "P1", protocol_name: "Hass season", version: 1, variety: "Hass" }] });
    vi.mocked(varieties.listVarieties).mockReset().mockResolvedValue({ varieties: [{ name: "Hass", variety_name: "Hass", enabled: 1 }] } as never);
    vi.mocked(setup.getCycleForEdit).mockReset().mockResolvedValue(edit());
    vi.mocked(setup.updateCycle).mockReset().mockResolvedValue({ name: "CYC-1", warnings: [], notes: [] });
  });

  it("fixes the block once the cycle has tasks", async () => {
    vi.mocked(setup.getCycleForEdit).mockResolvedValue(edit({ has_tasks: true }));
    renderPage(<EditCycleDialog cycle={cycle} crop={CROP} units={units} onClose={() => {}} onSaved={() => {}} />);
    expect(await screen.findByText("Fixed: this cycle already has tasks.")).toBeTruthy();
    expect((screen.getByLabelText("Orchard Block") as HTMLInputElement).readOnly).toBe(true);
  });

  it("saves the edited notes without a confirm", async () => {
    const onSaved = vi.fn();
    renderPage(<EditCycleDialog cycle={cycle} crop={CROP} units={units} onClose={() => {}} onSaved={onSaved} />);
    fireEvent.change(await screen.findByLabelText("Notes"), { target: { value: "Moved over" } });
    fireEvent.click(screen.getByRole("button", { name: "Save cycle" }));
    await waitFor(() => expect(setup.updateCycle).toHaveBeenCalled());
    expect(vi.mocked(setup.updateCycle).mock.calls[0][1]).toMatchObject({ unit: "PH1-B1", variety: "Hass", protocol: "P1", status: "Active", notes: "Moved over" });
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("asks in a themed dialog before closing a cycle", async () => {
    renderPage(<EditCycleDialog cycle={cycle} crop={CROP} units={units} onClose={() => {}} onSaved={() => {}} />);
    await screen.findByLabelText("Notes");
    fireEvent.click(screen.getByRole("combobox", { name: "Status" }));
    fireEvent.click(await screen.findByRole("option", { name: "Closed" }));
    fireEvent.click(screen.getByRole("button", { name: "Save cycle" }));
    expect(await screen.findByText("Close cycle CYC-1?")).toBeTruthy();
    expect(setup.updateCycle).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Close cycle" }));
    await waitFor(() => expect(setup.updateCycle).toHaveBeenCalled());
    expect(vi.mocked(setup.updateCycle).mock.calls[0][1]).toMatchObject({ status: "Closed" });
  });

  it("shows the sub-crop of a crop that has sub-crops and sends it on save", async () => {
    const FL = {
      ...CROP,
      has_field_crops: 1,
      field_crops: [
        { name: "Rose", crop_name: "Rose", crop_group: "Floriculture", product: null, harvest_uom: "Stem", color: null, enabled: 1, sub_crops: [{ name: "Standard rose", harvest_uom: "Stem" }, { name: "Spray rose", harvest_uom: "Stem" }] },
        { name: "Cabbage", crop_name: "Cabbage", crop_group: "Vegetable Crops", product: null, harvest_uom: "Pieces", color: null, enabled: 1 },
      ],
    } as api.Crop;
    vi.mocked(setup.getCycleForEdit).mockResolvedValue(edit({ field_crop: "Rose", sub_crop: "Standard rose" } as never));
    renderPage(<EditCycleDialog cycle={cycle} crop={FL} units={units} onClose={() => {}} onSaved={() => {}} />);
    const sc = await screen.findByRole("combobox", { name: "Sub-crop" });
    await waitFor(() => expect(sc.textContent).toContain("Standard rose"));
    fireEvent.click(sc);
    fireEvent.click(await screen.findByRole("option", { name: "Spray rose" }));
    fireEvent.click(screen.getByRole("button", { name: "Save cycle" }));
    await waitFor(() => expect(setup.updateCycle).toHaveBeenCalled());
    expect(vi.mocked(setup.updateCycle).mock.calls[0][1]).toMatchObject({ sub_crop: "Spray rose" });
  });
});

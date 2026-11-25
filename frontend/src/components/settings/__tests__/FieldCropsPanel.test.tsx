import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FieldCropsPanel, fieldCropProblem } from "@/components/settings/FieldCropsPanel";
import * as fc from "@/lib/field-crops-api";
import { renderPage } from "@/pages/__tests__/testkit";

vi.mock("@/lib/field-crops-api", async (orig) => ({
  ...(await orig<typeof fc>()),
  getCropTree: vi.fn(),
  saveFieldCrop: vi.fn(),
  saveCropGroup: vi.fn(),
  saveSubCrop: vi.fn(),
}));

const tree = {
  groups: [
    { name: "Floriculture", parent: null, sort_order: 1 },
    { name: "Summer Flowers", parent: "Floriculture", sort_order: 1 },
    { name: "Vegetable Crops", parent: null, sort_order: 2 },
  ],
  crops: [
    { name: "Rose", crop_name: "Rose", crop_group: "Floriculture", product: null, harvest_uom: "Stem", color: null, enabled: 1, sub_crops: [{ name: "Spray rose", harvest_uom: "Stem" }] },
    { name: "Gypsophila", crop_name: "Gypsophila", crop_group: "Summer Flowers", product: null, harvest_uom: "Bunch", color: null, enabled: 1, sub_crops: [] },
    { name: "Cabbage", crop_name: "Cabbage", crop_group: "Vegetable Crops", product: "Cabbage", product_name: "Cabbage", harvest_uom: "Pieces", color: null, enabled: 1, sub_crops: [] },
    { name: "Potato", crop_name: "Potato", crop_group: "Vegetable Crops", product: "Potatoes", product_name: "Potatoes", harvest_uom: "Kg", color: null, enabled: 1, sub_crops: [] },
  ],
} as { groups: fc.CropGroup[]; crops: fc.FieldCrop[] };

describe("fieldCropProblem", () => {
  it("needs a name and a unit", () => {
    expect(fieldCropProblem({ crop_name: " ", harvest_uom: "Kg" })).toMatch(/name/);
    expect(fieldCropProblem({ crop_name: "Maize", harvest_uom: "" })).toMatch(/unit/);
    expect(fieldCropProblem({ crop_name: "Maize", harvest_uom: "Kg" })).toBeNull();
  });
});

describe("FieldCropsPanel", () => {
  beforeEach(() => {
    vi.mocked(fc.getCropTree).mockReset().mockResolvedValue(tree);
    vi.mocked(fc.saveFieldCrop).mockReset().mockResolvedValue({ name: "Maize" });
    vi.mocked(fc.saveCropGroup).mockReset().mockResolvedValue({ name: "Fodder Crops" });
    vi.mocked(fc.saveSubCrop).mockReset().mockResolvedValue({ name: "Standard rose" });
  });

  it("shows the group tree with Summer Flowers under Floriculture", async () => {
    renderPage(<FieldCropsPanel canEdit />);
    const floriculture = await screen.findByRole("button", { name: "Floriculture" });
    const summer = screen.getByRole("button", { name: "Summer Flowers" });
    expect(summer.closest("li")?.parentElement?.closest("li")?.contains(floriculture)).toBe(true);
    expect(screen.getByText("Rose")).toBeTruthy();
    expect(screen.getByText("Spray rose")).toBeTruthy();
  });

  it("lists the crops of the selected group with unit and product", async () => {
    renderPage(<FieldCropsPanel canEdit />);
    fireEvent.click(await screen.findByRole("button", { name: "Vegetable Crops" }));
    expect(await screen.findByText("Potato")).toBeTruthy();
    expect(screen.getByText("Pieces")).toBeTruthy();
    expect(screen.queryByText("Rose")).toBeNull();
    expect(screen.getByRole("button", { name: "Edit Cabbage" })).toBeTruthy();
  });

  it("adds a crop in the selected group with its unit", async () => {
    renderPage(<FieldCropsPanel canEdit />);
    fireEvent.click(await screen.findByRole("button", { name: "Vegetable Crops" }));
    fireEvent.click(await screen.findByRole("button", { name: /New crop/ }));
    fireEvent.change(await screen.findByLabelText("Crop name"), { target: { value: "Maize" } });
    fireEvent.click(screen.getByRole("button", { name: "Save crop" }));
    await waitFor(() => expect(fc.saveFieldCrop).toHaveBeenCalled());
    expect(vi.mocked(fc.saveFieldCrop).mock.calls[0][0]).toMatchObject({ crop_name: "Maize", crop_group: "Vegetable Crops", harvest_uom: "Kg" });
  });

  it("adds a sub-crop to a crop", async () => {
    renderPage(<FieldCropsPanel canEdit />);
    fireEvent.click(await screen.findByRole("button", { name: "Add sub-crop to Rose" }));
    fireEvent.change(await screen.findByLabelText("Sub-crop name"), { target: { value: "Standard rose" } });
    fireEvent.click(screen.getByRole("button", { name: "Save sub-crop" }));
    await waitFor(() => expect(fc.saveSubCrop).toHaveBeenCalled());
    expect(vi.mocked(fc.saveSubCrop).mock.calls[0][0]).toMatchObject({ sub_crop_name: "Standard rose", field_crop: "Rose" });
  });

  it("adds a group", async () => {
    renderPage(<FieldCropsPanel canEdit />);
    fireEvent.click(await screen.findByRole("button", { name: /New group/ }));
    fireEvent.change(await screen.findByLabelText("Group name"), { target: { value: "Fodder Crops" } });
    fireEvent.click(screen.getByRole("button", { name: "Save group" }));
    await waitFor(() => expect(fc.saveCropGroup).toHaveBeenCalled());
    expect(vi.mocked(fc.saveCropGroup).mock.calls[0][0]).toMatchObject({ group_name: "Fodder Crops" });
  });

  it("is read-only without edit rights", async () => {
    renderPage(<FieldCropsPanel canEdit={false} />);
    await screen.findByRole("button", { name: "Floriculture" });
    expect(screen.queryByRole("button", { name: /New crop/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /New group/ })).toBeNull();
    expect(screen.queryByRole("button", { name: /Edit Rose/ })).toBeNull();
  });
});

import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FieldCropsPanel, fieldCropProblem } from "@/components/settings/FieldCropsPanel";
import * as fc from "@/lib/field-crops-api";
import { renderPage } from "@/pages/__tests__/testkit";

vi.mock("@/lib/field-crops-api", async (orig) => ({ ...(await orig<typeof fc>()), listFieldCrops: vi.fn(), saveFieldCrop: vi.fn() }));

const rows: fc.FieldCrop[] = [
  { name: "Cabbage", crop_name: "Cabbage", production_crop: "Fruits & Vegetables", product: "Cabbage", product_name: "Cabbage", harvest_uom: "Pieces", color: null, enabled: 1, varieties: 2 },
  { name: "Potato", crop_name: "Potato", production_crop: "Fruits & Vegetables", product: "Potatoes", product_name: "Potatoes", harvest_uom: "Kg", color: null, enabled: 1, varieties: 3 },
];

describe("fieldCropProblem", () => {
  it("needs a name and a unit", () => {
    expect(fieldCropProblem({ crop_name: " ", harvest_uom: "Kg" })).toMatch(/name/);
    expect(fieldCropProblem({ crop_name: "Maize", harvest_uom: "" })).toMatch(/unit/);
    expect(fieldCropProblem({ crop_name: "Maize", harvest_uom: "Kg" })).toBeNull();
  });
});

describe("FieldCropsPanel", () => {
  beforeEach(() => {
    vi.mocked(fc.listFieldCrops).mockReset().mockResolvedValue({ field_crops: rows });
    vi.mocked(fc.saveFieldCrop).mockReset().mockResolvedValue({ name: "Maize" });
  });

  it("lists each crop with its product, unit and varieties", async () => {
    renderPage(<FieldCropsPanel crop="Fruits & Vegetables" canEdit />);
    expect(await screen.findByText("Potato")).toBeTruthy();
    expect(screen.getByText("Pieces")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Edit Cabbage" })).toBeTruthy();
  });

  it("adds a crop in the section with its unit", async () => {
    renderPage(<FieldCropsPanel crop="Fruits & Vegetables" canEdit />);
    fireEvent.click(await screen.findByRole("button", { name: /New crop/ }));
    fireEvent.change(await screen.findByLabelText("Crop name"), { target: { value: "Maize" } });
    fireEvent.click(screen.getByRole("button", { name: "Save crop" }));
    await waitFor(() => expect(fc.saveFieldCrop).toHaveBeenCalled());
    expect(vi.mocked(fc.saveFieldCrop).mock.calls[0][0]).toMatchObject({ crop_name: "Maize", production_crop: "Fruits & Vegetables", harvest_uom: "Kg" });
  });

  it("is read-only without edit rights", async () => {
    renderPage(<FieldCropsPanel crop="Fruits & Vegetables" canEdit={false} />);
    await screen.findByText("Potato");
    expect(screen.queryByRole("button", { name: /New crop/ })).toBeNull();
  });
});

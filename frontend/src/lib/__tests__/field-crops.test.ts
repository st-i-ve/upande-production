import { describe, expect, it } from "vitest";
import { cropLabel, cropPickerOptions, cropTotalsText, groupTotals, hasFieldCrops, subCropsOf } from "@/lib/field-crops";

describe("field crops", () => {
  it("a section has crops when the server says so or lists them", () => {
    expect(hasFieldCrops(null)).toBe(false);
    expect(hasFieldCrops({})).toBe(false);
    expect(hasFieldCrops({ has_field_crops: 1 })).toBe(true);
    expect(hasFieldCrops({ field_crops: [{ name: "Cabbage" } as never] })).toBe(true);
  });

  it("names a cycle or task as crop and variety", () => {
    expect(cropLabel("Cabbage", "Gloria F1")).toBe("Cabbage (Gloria F1)");
    expect(cropLabel("Cabbage", null)).toBe("Cabbage");
    expect(cropLabel(null, "Hass")).toBe("Hass");
    expect(cropLabel("Cabbage", "Gloria F1", "Server label")).toBe("Server label");
  });

  it("keeps pieces and kg apart", () => {
    const text = cropTotalsText(
      [
        { field_crop: "Cabbage", uom: "Pieces", qty: 1200 },
        { field_crop: "Potato", uom: "Kg", qty: 3400 },
        { field_crop: "Maize", uom: "Kg", qty: 0 },
      ],
      (n) => n.toLocaleString("en"),
    );
    expect(text).toBe("Cabbage 1,200 Pieces | Potato 3,400 Kg");
  });

  it("names a sub-crop between the crop and the variety", () => {
    expect(cropLabel("Rose", "Red Naomi", null, "Spray rose")).toBe("Rose · Spray rose (Red Naomi)");
    expect(cropLabel("Rose", null, null, "Spray rose")).toBe("Rose · Spray rose");
  });

  const crops = [
    { name: "Cabbage", crop_group: "Vegetable Crops", sub_crops: [] },
    { name: "Potato", crop_group: "Vegetable Crops" },
    { name: "Onion", crop_group: "Vegetable Crops" },
    { name: "Rose", crop_group: "Floriculture", sub_crops: [{ name: "Spray rose", harvest_uom: "Stem" }] },
  ];

  it("rolls totals up per group and never adds different units", () => {
    const out = groupTotals(
      [
        { field_crop: "Cabbage", uom: "Pieces", qty: 1200 },
        { field_crop: "Potato", uom: "Kg", qty: 3400 },
        { field_crop: "Onion", uom: "Kg", qty: 600 },
        { field_crop: "Rose", uom: "Stem", qty: 50 },
        { field_crop: "Cabbage", uom: "Pieces", qty: 300 },
      ],
      crops,
    );
    expect(out).toEqual([
      { group: "Floriculture", uom: "Stem", qty: 50 },
      { group: "Vegetable Crops", uom: "Kg", qty: 4000 },
      { group: "Vegetable Crops", uom: "Pieces", qty: 1500 },
    ]);
  });

  it("lists a crop's sub-crops and groups picker options", () => {
    expect(subCropsOf(crops, "Rose").map((s) => s.name)).toEqual(["Spray rose"]);
    expect(subCropsOf(crops, "Potato")).toEqual([]);
    const opts = cropPickerOptions([{ name: "Rose", crop_name: "Rose", crop_group: "Floriculture", enabled: 1 }, { name: "Old", crop_name: "Old", crop_group: null, enabled: 0 }]);
    expect(opts).toEqual([{ value: "Rose", label: "Rose", group: "Floriculture" }]);
  });
});

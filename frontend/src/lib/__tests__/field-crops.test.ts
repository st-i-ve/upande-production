import { describe, expect, it } from "vitest";
import { cropLabel, cropTotalsText, hasFieldCrops } from "@/lib/field-crops";

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
});

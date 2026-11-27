import { describe, expect, it } from "vitest";
import type { Crop } from "@/lib/api";
import { navForCrop, viewAllowed } from "@/lib/nav";

const avocado: Crop = {
  name: "Avocado", crop_key: "avocado", accent_color: "#3f8f4f", icon_key: "avocado", unit_label: "Block",
  parent_unit_label: "Pivot", sub_unit_label: "Block", yield_uom: "kg", dry_matter_testing: 0,
};

describe("labour pay navigation", () => {
  it("lists Attendance under Field work, after Casual Labourers", () => {
    const field = navForCrop(avocado).find((g) => g.label === "Field work")!;
    const labels = field.items.map((i) => i.label);
    expect(labels.indexOf("Attendance")).toBe(labels.indexOf("Casual Labourers") + 1);
  });

  it("is allowed for ordinary crops and not for flower crops", () => {
    expect(viewAllowed("attendance", "avocado", avocado)).toBe(true);
    const roses = { ...avocado, crop_key: "roses", unit_label: "Greenhouse", parent_unit_label: "Farm", sub_unit_label: "Bed" };
    expect(viewAllowed("attendance", "roses", roses)).toBe(false);
  });
});

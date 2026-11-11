import { describe, expect, it } from "vitest";
import {
  activityLabour,
  closeProblems,
  costPerKg,
  inputPayload,
  inputProblems,
  inputsByItem,
  openCount,
  perKgLabel,
  perUnitLabel,
  pitTotals,
  statusTone,
} from "@/lib/silage";
import type { InputRow, PitStockRow } from "@/lib/silage-api";

describe("activityLabour", () => {
  it("is workers x day rate when both are given", () => {
    expect(activityLabour(6, 400, 999)).toBe(2400);
    expect(activityLabour("3", "350.5", "")).toBe(1051.5);
  });
  it("falls back to the typed amount", () => {
    expect(activityLabour("", 400, 1500)).toBe(1500);
    expect(activityLabour(5, null, "700")).toBe(700);
    expect(activityLabour(null, null, -10)).toBe(0);
    expect(activityLabour(null, null, "abc")).toBe(0);
  });
});

describe("costPerKg / perKgLabel", () => {
  it("divides only when kilos are ensiled", () => {
    expect(costPerKg(60000, 200000)).toBeCloseTo(0.3);
    expect(costPerKg(1000, 0)).toBeNull();
    expect(costPerKg(1000, "")).toBeNull();
    expect(costPerKg(null, 10)).toBeNull();
    expect(costPerKg(1000, "1,000")).toBe(1);
  });
  it("labels small rates with cents and large ones whole", () => {
    expect(perKgLabel(4.256)).toBe("KES 4.26/kg");
    expect(perKgLabel(1234.5)).toBe("KES 1,235/kg");
    expect(perKgLabel(null)).toBe("—");
    expect(perUnitLabel(12.5, "Tonne")).toBe("KES 12.50/Tonne");
  });
});

describe("inputProblems / inputPayload", () => {
  it("needs a store, an item and a positive quantity per line", () => {
    expect(inputProblems([{ item_code: "", qty: "" }], "")).toEqual([
      "Choose the store the inputs come out of.",
      "Add at least one item.",
    ]);
    expect(inputProblems([{ item_code: "Seed", qty: "0" }, { item_code: "", qty: "2" }], "Store")).toEqual([
      "Line 1: quantity must be above zero.",
      "Line 2: choose the item.",
    ]);
    expect(inputProblems([{ item_code: "Seed", qty: "2" }, { item_code: "Seed", qty: "1" }], "Store")).toEqual([
      "Line 2: Seed is already on another line.",
    ]);
    expect(inputProblems([{ item_code: "Seed", qty: "25" }, { item_code: "", qty: "" }], "Store")).toEqual([]);
  });
  it("sends only complete lines, as numbers", () => {
    expect(inputPayload([{ item_code: "Seed", qty: "25" }, { item_code: "", qty: "" }, { item_code: "DAP", qty: "1,200" }])).toEqual([
      { item_code: "Seed", qty: 25 },
      { item_code: "DAP", qty: 1200 },
    ]);
  });
});

describe("closeProblems", () => {
  it("lists everything that blocks closing", () => {
    expect(closeProblems({ ensiledKg: "", silageItem: "", pitWarehouse: "", draftInputs: ["MAT-1"], openAllocations: ["PAA-1"] })).toHaveLength(5);
    expect(closeProblems({ ensiledKg: "250000", silageItem: "Maize Silage", pitWarehouse: "Pit 1", draftInputs: [], openAllocations: [] })).toEqual([]);
  });
});

describe("inputsByItem", () => {
  it("groups by item, largest value first", () => {
    const row = (item_code: string, stock_qty: number, amount: number): InputRow => ({
      stock_entry: "SE", posting_date: "2026-11-01", item_code, item_name: item_code, qty: stock_qty, uom: "Kg",
      stock_qty, stock_uom: "Kg", warehouse: "Store", amount,
    });
    expect(inputsByItem([row("Seed", 10, 500), row("DAP", 50, 4000), row("Seed", 5, 250)])).toEqual([
      { item_code: "DAP", item_name: "DAP", qty: 50, uom: "Kg", amount: 4000 },
      { item_code: "Seed", item_name: "Seed", qty: 15, uom: "Kg", amount: 750 },
    ]);
  });
});

describe("pitTotals / openCount / statusTone", () => {
  it("adds kilos of Kg rows only, and every row's value", () => {
    const row = (warehouse: string, qty: number, stock_uom: string, stock_value: number): PitStockRow => ({
      item_code: "Maize Silage", item_name: "Maize Silage", warehouse, qty, stock_uom, valuation_rate: 0, stock_value,
    });
    expect(pitTotals([row("Pit 1", 1000, "Kg", 4000), row("Pit 2", 0, "Kg", 0), row("Pit 3", 2, "Tonne", 9000)])).toEqual({
      kg: 1000, value: 13000, pits: 2,
    });
  });
  it("counts draft cycles as open", () => {
    expect(openCount([{ docstatus: 0 }, { docstatus: 1 }, { docstatus: 0 }])).toBe(2);
  });
  it("tones statuses", () => {
    expect(statusTone("Closed")).toBe("ok");
    expect(statusTone("Planned")).toBe("info");
    expect(statusTone("Ensiled")).toBe("warn");
    expect(statusTone("Cancelled")).toBe("quiet");
  });
});

describe("Silage view gate", () => {
  it("shows only for crops grown for silage, never for flower crops", async () => {
    const { viewAllowed } = await import("@/lib/nav");
    expect(viewAllowed("silage", "maize", { dry_matter_testing: 0, grown_for_silage: 1 })).toBe(true);
    expect(viewAllowed("silage", "avocado", { dry_matter_testing: 0, grown_for_silage: 0 })).toBe(false);
    expect(viewAllowed("silage", "maize", { dry_matter_testing: 0 })).toBe(false);
    expect(viewAllowed("silage", "standard-roses", { dry_matter_testing: 0, grown_for_silage: 1, desk_launcher: "Crop Production desk" })).toBe(false);
  });
});

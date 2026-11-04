import "@testing-library/jest-dom/vitest";
import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FlowerOverview } from "@/pages/flowers/FlowerOverview";
import { Harvesting } from "@/pages/flowers/FlowerLists";
import { Greenhouses } from "@/pages/flowers/FlowerUnits";
import * as flowers from "@/lib/flowers-api";
import { isFlowerCrop } from "@/lib/crops";
import { navForCrop, viewAllowed } from "@/lib/nav";
import { CROP, renderPage } from "./testkit";

vi.mock("@/lib/flowers-api", async (orig) => ({
  ...(await orig<typeof flowers>()),
  getList: vi.fn(),
  flowerData: vi.fn(),
  itemNames: vi.fn(),
}));

const ROSES = {
  ...CROP, name: "Standard Roses", crop_key: "standard-roses", unit_label: "Greenhouse", sub_unit_label: "Bed",
  desk_launcher: "Crop Production desk",
};

describe("flower crops", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // recharts' ResponsiveContainer measures with a ResizeObserver, which jsdom lacks
    vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
  });

  it("is read from desk_launcher, falling back to the Greenhouse unit", () => {
    expect(isFlowerCrop(ROSES)).toBe(true);
    expect(isFlowerCrop({ unit_label: "Greenhouse" })).toBe(true);
    expect(isFlowerCrop({ unit_label: "Block", desk_launcher: "Production App" })).toBe(false);
    expect(isFlowerCrop(CROP)).toBe(false);
  });

  it("gives flower crops only their own screens, and the others none of them", () => {
    expect(viewAllowed("farm-map", "standard-roses", ROSES)).toBe(true);
    expect(viewAllowed("overview", "standard-roses", ROSES)).toBe(false);
    expect(viewAllowed("farm-map", "avocado", CROP)).toBe(false);
    expect(viewAllowed("overview", "avocado", CROP)).toBe(true);
    const items = navForCrop(ROSES).flatMap((g) => g.items.map((i) => i.label));
    expect(items).toEqual(["Overview", "Crop Protocols", "Cut Stages", "Greenhouses", "Crop Cycles", "Farm Map", "Weekly Plan", "Harvesting"]);
  });

  const BLOCKS = {
    mode: "block" as const,
    units: [{ name: "Kariki Thika - Block 9B", label: "Block 9B", farm: "Kariki Thika", beds: 79, plants: 70863, area_planted: 3544, gross_area: 4449, varieties: 1, cycles: 1 }],
    cycles: [{ name: "CC-Kariki Thika - Block 9B-2025W39", unit: "Kariki Thika - Block 9B", unit_kind: "block" as const, farm: "Kariki Thika", variety: "110402",
      variety_name: "Solidago Carzan Glory", product: "Solidago", status: "Active", planting_date: "2025-09-22", plants: 70863, area: 3544, beds: 79 }],
    farms: [{ farm: "Kariki Thika", units: 1, beds: 79, plants: 70863, area: 3544 }],
    totals: { units: 1, beds: 79, plants: 70863, area_planted: 3544, gross_area: 4449, cycles: 1, active: 1, varieties: 1 },
  };

  it("rebuilds the Crop Cycle Dashboard for block-based cycles, with names not codes", async () => {
    vi.mocked(flowers.flowerData).mockResolvedValue(BLOCKS);
    renderPage(<FlowerOverview />, true, ROSES);
    expect(await screen.findByText("Plants standing")).toBeInTheDocument();
    expect(await screen.findByText("Block 9B")).toBeInTheDocument();
    expect(screen.getAllByText("Blocks").length).toBeGreaterThan(0);
    expect(screen.getByText("Crop cycles by status")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Classic view/ })).toHaveAttribute("href", "/desk/greenhouse");
  });

  it("lists blocks and beds", async () => {
    vi.mocked(flowers.flowerData).mockResolvedValue(BLOCKS);
    renderPage(<Greenhouses />, true, ROSES);
    expect(await screen.findByRole("link", { name: "Block 9B" })).toHaveAttribute("href", "/desk/block/Kariki%20Thika%20-%20Block%209B");
    expect(screen.getByText("Blocks & Beds", { selector: "h1" })).toBeInTheDocument();
  });

  it("asks for Harvesting stock entries only", async () => {
    vi.mocked(flowers.getList).mockResolvedValue({ rows: [] });
    vi.mocked(flowers.itemNames).mockResolvedValue({});
    renderPage(<Harvesting />, true, ROSES);
    expect(await screen.findByText(/No harvesting yet/)).toBeInTheDocument();
    expect(vi.mocked(flowers.getList).mock.calls[0][2]?.filters).toEqual([["Stock Entry", "stock_entry_type", "=", "Harvesting"]]);
  });
});

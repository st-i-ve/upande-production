import "@testing-library/jest-dom/vitest";
import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { FlowerOverview } from "@/pages/flowers/FlowerOverview";
import { Greenhouses, Harvesting } from "@/pages/flowers/FlowerLists";
import * as flowers from "@/lib/flowers-api";
import { isFlowerCrop } from "@/lib/crops";
import { navForCrop, viewAllowed } from "@/lib/nav";
import { CROP, renderPage } from "./testkit";

vi.mock("@/lib/flowers-api", async (orig) => ({
  ...(await orig<typeof flowers>()),
  getList: vi.fn(),
  getDashboardData: vi.fn(),
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

  it("rebuilds the Crop Cycle Dashboard", async () => {
    vi.mocked(flowers.getDashboardData).mockResolvedValue({
      greenhouses: [{ name: "GH 1", farm: "Simotwo", number_of_beds: 10, number_of_plants: 1200, area_planted: 80, gross_area: 100, varieties: 1 }],
      cycles: [{ name: "C1", greenhouse: "GH 1", farm: "Simotwo", variety: "Candid", status: "Active", qty_planted: 1200, plants_standing: 1180, planted_area: 80 }],
    });
    renderPage(<FlowerOverview />, true, ROSES);
    expect(await screen.findByText("Plants standing")).toBeInTheDocument();
    expect(await screen.findByText("GH 1")).toBeInTheDocument();
    expect(screen.getByText("Crop cycles by status")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Classic view/ })).toHaveAttribute("href", "/desk/greenhouse");
  });

  it("lists greenhouses with a link to the classic form", async () => {
    vi.mocked(flowers.getList).mockResolvedValue({ rows: [{ name: "GH 1", farm: "Simotwo", number_of_beds: 10, number_of_plants: 1200 }] });
    renderPage(<Greenhouses />, true, ROSES);
    expect(await screen.findByRole("link", { name: "GH 1" })).toHaveAttribute("href", "/desk/greenhouse/GH%201");
  });

  it("asks for Harvesting stock entries only", async () => {
    vi.mocked(flowers.getList).mockResolvedValue({ rows: [] });
    renderPage(<Harvesting />, true, ROSES);
    expect(await screen.findByText(/No harvesting yet/)).toBeInTheDocument();
    expect(vi.mocked(flowers.getList).mock.calls[0][2]?.filters).toEqual([["Stock Entry", "stock_entry_type", "=", "Harvesting"]]);
  });
});

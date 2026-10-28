import { fireEvent, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Boot, Crop } from "@/lib/api";

vi.mock("@/lib/api", () => ({ valueAdderSummary: vi.fn() }));

vi.mock("@/lib/overview-api", () => ({ getValueAdderDetail: vi.fn().mockResolvedValue({ error: "x" }) }));

import * as api from "@/lib/api";
import { CropProvider } from "@/lib/crops";
import { ValueAdders } from "@/pages/ValueAdders";

const crop: Crop = {
  name: "Avocado",
  crop_key: "avocado",
  accent_color: "#3f8f4f",
  icon_key: "avocado",
  unit_label: "Block",
  parent_unit_label: "Pivot",
  sub_unit_label: "Block",
  yield_uom: "kg",
};
const boot = (can_see_pay: boolean): Boot => ({ crops: [crop], farms: ["Mutara"], can_see_pay, can_plan: true, can_manage: false });
const renderIt = (pay: boolean) =>
  render(
    <TooltipProvider>
      <CropProvider crop={crop} boot={boot(pay)}>
        <ValueAdders />
      </CropProvider>
    </TooltipProvider>,
  );

beforeEach(() => {
  vi.mocked(api.valueAdderSummary).mockResolvedValue({
    rows: [
      { key: "E1", label: "Jane Wanjiru", qty_by_uom: [{ uom: "Tree", qty: 24 }, { uom: "Hectare", qty: 6 }], hours: 12, pay_value: 1500, entries: 3 },
      { key: "E2", label: "Peter Otieno", qty_by_uom: [{ uom: "Tree", qty: 20 }], hours: 8, pay_value: 1000, entries: 2 },
    ],
    total_pay: 2500,
    total_qty_by_uom: [{ uom: "Tree", qty: 44 }, { uom: "Hectare", qty: 6 }],
  });
});

describe("ValueAdders", () => {
  it("shows rows and the total pay", async () => {
    renderIt(true);
    expect(await screen.findByText("Jane Wanjiru")).toBeTruthy();
    expect(screen.getAllByText("KES 2,500").length).toBeTruthy();
    expect(screen.getByText("Pay")).toBeTruthy();
    expect(screen.getByText("Total")).toBeTruthy();
    expect(screen.queryByText("Qty")).toBeNull();
    expect(screen.getByText("Work done and pay figures for casual value adders.")).toBeTruthy();
  });

  it("never adds quantities across units of measure", async () => {
    renderIt(true);
    await screen.findByText("Jane Wanjiru");
    // Per UOM in the KPI, the rows and the footer; 6 + 24 + 20 = 50 appears nowhere.
    expect(screen.getAllByText("44 Tree · 6 Hectare").length).toBeGreaterThan(0);
    expect(screen.getByText("24 Tree · 6 Hectare")).toBeTruthy();
    expect(screen.queryByText("50")).toBeNull();
    expect(screen.queryByText(/^50 /)).toBeNull();
  });

  it("opens a person's detail panel", async () => {
    renderIt(true);
    fireEvent.click(await screen.findByText("Jane Wanjiru"));
    expect(await screen.findByText(/could not be loaded/i)).toBeTruthy();
  });

  it("hides pay when the user cannot see it", async () => {
    renderIt(false);
    expect(await screen.findByText("Jane Wanjiru")).toBeTruthy();
    expect(screen.queryByText("KES 2,500")).toBeNull();
    expect(screen.queryByText("Pay")).toBeNull();
  });
});

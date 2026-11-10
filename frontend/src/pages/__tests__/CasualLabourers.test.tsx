import { fireEvent, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Boot, Crop } from "@/lib/api";

vi.mock("@/lib/api", () => ({ casualLabourerSummary: vi.fn(), listOperations: vi.fn().mockResolvedValue({ error: "x" }) }));

vi.mock("@/lib/labourers-api", () => ({
  listLabourers: vi.fn(),
  getLabourerDetail: vi.fn().mockResolvedValue({ error: "x" }),
  candidateEmployees: vi.fn().mockResolvedValue({ people: [], departments: [], designations: [] }),
  addLabourers: vi.fn(),
  saveLabourer: vi.fn(),
  removeLabourer: vi.fn(),
}));
vi.mock("@/lib/frappe", async (orig) => ({ ...(await orig<typeof import("@/lib/frappe")>()), searchLink: vi.fn().mockResolvedValue([]) }));

import * as api from "@/lib/api";
import * as lab from "@/lib/labourers-api";
import { CropProvider } from "@/lib/crops";
import { CasualLabourers } from "@/pages/CasualLabourers";

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
const renderIt = async (pay: boolean) => {
  render(
    <TooltipProvider>
      <CropProvider crop={crop} boot={boot(pay)}>
        <CasualLabourers />
      </CropProvider>
    </TooltipProvider>,
  );
  // The Work tab holds the by-person / by-day / by-block figures.
  fireEvent.mouseDown(await screen.findByRole("tab", { name: "Work" }), { button: 0 });
  fireEvent.click(screen.getByRole("tab", { name: "Work" }));
};

beforeEach(() => {
  vi.mocked(lab.listLabourers).mockResolvedValue({ rows: [], days: [], totals: { labourers: 0, active: 0, working: 0, days_worked: 0, qty_by_uom: [], hit_rate: null, target_days: 0, pay_value: 0, unpaid_value: 0 } });
  vi.mocked(api.casualLabourerSummary).mockResolvedValue({
    rows: [
      { key: "E1", label: "Jane Wanjiru", qty_by_uom: [{ uom: "Tree", qty: 24 }, { uom: "Hectare", qty: 6 }], days: 5, pay_value: 1500, entries: 3 },
      { key: "E2", label: "Peter Otieno", qty_by_uom: [{ uom: "Tree", qty: 20 }], days: 3, pay_value: 1000, entries: 2 },
    ],
    total_pay: 2500,
    total_qty_by_uom: [{ uom: "Tree", qty: 44 }, { uom: "Hectare", qty: 6 }],
  });
});

describe("CasualLabourers", () => {
  it("shows rows and the total pay", async () => {
    await renderIt(true);
    expect(await screen.findByText("Jane Wanjiru")).toBeTruthy();
    expect(screen.getAllByText("KES 2,500").length).toBeTruthy();
    expect(screen.getByText("Pay")).toBeTruthy();
    expect(screen.getByText("Total")).toBeTruthy();
    expect(screen.queryByText("Qty")).toBeNull();
    expect(screen.getByText(/Work done and pay figures for casual labourers/)).toBeTruthy();
    expect(screen.queryByText(/hours/i)).toBeNull();
  });

  it("never adds quantities across units of measure", async () => {
    await renderIt(true);
    await screen.findByText("Jane Wanjiru");
    // Per UOM in the KPI, the rows and the footer; 6 + 24 + 20 = 50 appears nowhere.
    expect(screen.getAllByText("44 Tree · 6 Hectare").length).toBeGreaterThan(0);
    expect(screen.getByText("24 Tree · 6 Hectare")).toBeTruthy();
    expect(screen.queryByText("50")).toBeNull();
    expect(screen.queryByText(/^50 /)).toBeNull();
  });

  it("opens a person's detail panel", async () => {
    await renderIt(true);
    fireEvent.click(await screen.findByText("Jane Wanjiru"));
    expect(await screen.findByText(/could not be loaded/i)).toBeTruthy();
  });

  it("hides pay when the user cannot see it", async () => {
    await renderIt(false);
    expect(await screen.findByText("Jane Wanjiru")).toBeTruthy();
    expect(screen.queryByText("KES 2,500")).toBeNull();
    expect(screen.queryByText("Pay")).toBeNull();
  });
});

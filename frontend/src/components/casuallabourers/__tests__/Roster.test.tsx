import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/components/Toast";
import type { Boot, Crop } from "@/lib/api";

vi.mock("@/lib/api", () => ({ casualLabourerSummary: vi.fn(), listOperations: vi.fn().mockResolvedValue({ rows: [] }) }));
vi.mock("@/lib/labourers-api", () => ({
  listLabourers: vi.fn(),
  getLabourerDetail: vi.fn(),
  candidateEmployees: vi.fn(),
  addLabourers: vi.fn(),
  saveLabourer: vi.fn(),
  removeLabourer: vi.fn(),
}));
vi.mock("@/lib/frappe", async (orig) => ({ ...(await orig<typeof import("@/lib/frappe")>()), searchLink: vi.fn().mockResolvedValue([]) }));

import * as lab from "@/lib/labourers-api";
import { CropProvider } from "@/lib/crops";
import { CasualLabourers } from "@/pages/CasualLabourers";

const crop: Crop = {
  name: "Avocado", crop_key: "avocado", accent_color: "#3f8f4f", icon_key: "avocado", unit_label: "Block",
  parent_unit_label: "Pivot", sub_unit_label: "Block", yield_uom: "kg",
};
const boot = (pay: boolean): Boot => ({ crops: [crop], farms: ["Mutara"], can_see_pay: pay, can_plan: true, can_manage: true });
const row = (o: Partial<lab.RosterRow>): lab.RosterRow => ({
  name: "E1", employee: "E1", employee_name: "Jane Wanjiru", department: "Field", designation: "Casual Labourer", image: null,
  active: 1, supervisor_name: "Grace W", crew: "Pruning A", overrides: 1, days_worked: 5, qty_by_uom: [{ uom: "Tree", qty: 240 }],
  entries: 5, target_days: 5, met_days: 4, hit_rate: 80, pay_value: 1200, unpaid_value: 600, ...o,
});
const renderIt = (pay = true) =>
  render(
    <TooltipProvider>
      <ToastProvider>
        <CropProvider crop={crop} boot={boot(pay)}>
          <CasualLabourers />
        </CropProvider>
      </ToastProvider>
    </TooltipProvider>,
  );

beforeEach(() => {
  vi.mocked(lab.listLabourers).mockResolvedValue({
    rows: [row({}), row({ name: "E2", employee: "E2", employee_name: "Peter Otieno", active: 0, hit_rate: null, days_worked: 0, qty_by_uom: [], pay_value: 0, unpaid_value: 0 })],
    days: [],
    totals: { labourers: 2, active: 1, working: 1, days_worked: 5, qty_by_uom: [{ uom: "Tree", qty: 240 }], hit_rate: 80, target_days: 5, pay_value: 1200, unpaid_value: 600 },
  });
  vi.mocked(lab.candidateEmployees).mockResolvedValue({
    people: [
      { name: "E3", employee_name: "Achieng Awino", department: null, designation: "Casual Labourer", image: null },
      { name: "E4", employee_name: "Barasa Wekesa", department: null, designation: "Casual Labourer", image: null },
    ],
    departments: [],
    designations: ["Casual Labourer"],
  });
  vi.mocked(lab.addLabourers).mockResolvedValue({ added: ["E3", "E4"], skipped: [] });
});

describe("Casual labourer roster", () => {
  it("lists active labourers with hit rate and unpaid pay, and no hours", async () => {
    renderIt();
    expect(await screen.findByText("Jane Wanjiru")).toBeTruthy();
    expect(screen.queryByText("Peter Otieno")).toBeNull(); // inactive hidden by default
    expect(screen.getByText("80%", { selector: "td span" })).toBeTruthy();
    expect(screen.getAllByText("KES 600").length).toBeGreaterThan(0);
    expect(screen.getByText("Unpaid", { selector: "th" })).toBeTruthy();
    expect(screen.queryByText(/hours/i)).toBeNull();
  });

  it("hides pay columns without pay access", async () => {
    renderIt(false);
    await screen.findByText("Jane Wanjiru");
    expect(screen.queryByText("Unpaid", { selector: "th" })).toBeNull();
    expect(screen.queryByText("KES 600")).toBeNull();
  });

  it("adds several employees at once", async () => {
    renderIt();
    await screen.findByText("Jane Wanjiru");
    fireEvent.click(screen.getByRole("button", { name: /Add labourers/ }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("Achieng Awino");
    fireEvent.click(within(dialog).getByLabelText("Select all shown"));
    fireEvent.click(within(dialog).getByRole("button", { name: /Add 2 to roster/ }));
    await waitFor(() => expect(lab.addLabourers).toHaveBeenCalledWith(["E3", "E4"], null, null));
    expect(vi.mocked(lab.candidateEmployees).mock.calls[0][0]).toMatchObject({ designation: "Casual Labourer" });
  });
});

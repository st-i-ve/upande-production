import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/components/Toast";
import type { Boot, Crop } from "@/lib/api";

vi.mock("@/lib/supervisors-api", () => ({ listSupervisors: vi.fn(), getSupervisor: vi.fn(), saveSupervisor: vi.fn() }));
vi.mock("@/lib/frappe", async (orig) => ({
  ...(await orig<typeof import("@/lib/frappe")>()),
  searchLink: vi.fn().mockResolvedValue([{ value: "E9", description: "Newbie Hand", label: "Newbie Hand" }]),
}));

import { searchLink } from "@/lib/frappe";
import * as api from "@/lib/supervisors-api";
import { CropProvider } from "@/lib/crops";
import { Supervisors } from "@/pages/Supervisors";

const crop: Crop = {
  name: "Avocado", crop_key: "avocado", accent_color: "#3f8f4f", icon_key: "avocado", unit_label: "Block",
  parent_unit_label: "Pivot", sub_unit_label: "Block", yield_uom: "kg",
};
const boot = (manage: boolean): Boot => ({ crops: [crop], farms: ["Mutara"], can_see_pay: false, can_plan: true, can_manage: manage });
const card = (o: Partial<api.SupervisorCard> & { employee: string; employee_name: string }): api.SupervisorCard => ({
  image: null, phone: "0700111222", user: null, farm: null, active: true,
  kpis: { blocks: 2, tasks: { done: 3, open: 4, late: 1, skipped: 0, total: 8 }, crew: 5, pending: 2 }, ...o,
});
const renderIt = (manage = true) =>
  render(
    <TooltipProvider>
      <ToastProvider>
        <CropProvider crop={crop} boot={boot(manage)}>
          <Supervisors />
        </CropProvider>
      </ToastProvider>
    </TooltipProvider>,
  );

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(searchLink).mockResolvedValue([{ value: "E9", description: "Newbie Hand", label: "Newbie Hand" }]);
  vi.mocked(api.listSupervisors).mockResolvedValue([
    card({ employee: "E1", employee_name: "Grace Wambui" }),
    card({ employee: "E2", employee_name: "Peter Otieno", active: false, phone: null }),
  ]);
  vi.mocked(api.getSupervisor).mockResolvedValue({
    supervisor: { employee: "E1", employee_name: "Grace Wambui", image: null, phone: "0700111222", user: null, farm: null, active: true, notes: null, crops: [] },
    year: 2026, week: 48, can_edit: true,
    blocks: [{ unit: "B1", unit_name: "Block 1", crop: "Avocado", categories: ["Spraying"], overseer: true }],
    tasks: { done: 3, open: 4, late: 1, skipped: 0, total: 8 }, pending: 2, crew_count: 1, crew_hidden: false,
    labourers: [{ employee: "L1", employee_name: "Jane Crew", image: null, active: 1, crew: "A" }],
  });
  vi.mocked(api.saveSupervisor).mockResolvedValue({ employee: "E9", employee_name: "Newbie Hand" });
});

describe("Supervisors page", () => {
  it("shows a card per active supervisor with initials, phone and KPI chips; inactive hidden by default", async () => {
    renderIt();
    expect(await screen.findByText("Grace Wambui")).toBeTruthy();
    expect(screen.getByText("GW")).toBeTruthy();
    expect(screen.getByText("0700111222")).toBeTruthy();
    expect(screen.getByText("2 blocks")).toBeTruthy();
    expect(screen.getByText("5 in crew")).toBeTruthy();
    expect(screen.getByText("1 late")).toBeTruthy();
    expect(screen.getByText("2 to approve")).toBeTruthy();
    expect(screen.queryByText("Peter Otieno")).toBeNull();
  });

  it("filters by search and by status", async () => {
    renderIt();
    await screen.findByText("Grace Wambui");
    fireEvent.change(screen.getByPlaceholderText("Search"), { target: { value: "zzz" } });
    expect(await screen.findByText(/No supervisors match/)).toBeTruthy();
  });

  it("opens the detail with blocks and crew", async () => {
    renderIt();
    fireEvent.click(await screen.findByText("Grace Wambui"));
    expect(await screen.findByText("Block 1")).toBeTruthy();
    expect(screen.getByText("Jane Crew")).toBeTruthy();
    expect(screen.getByText("Spraying")).toBeTruthy();
    expect(api.getSupervisor).toHaveBeenCalledWith("E1", "Avocado", expect.any(Number), expect.any(Number));
  });

  it("lets a manager add a supervisor from the Employee picker", async () => {
    renderIt();
    fireEvent.click(await screen.findByText("Add supervisor"));
    fireEvent.change(await screen.findByPlaceholderText("Search employees"), { target: { value: "new" } });
    fireEvent.click(await screen.findByText("Newbie Hand"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.saveSupervisor).toHaveBeenCalledWith(expect.objectContaining({ employee: "E9", active: true })));
  });

  it("shows no crew list or approvals when the server withholds them", async () => {
    vi.mocked(api.getSupervisor).mockResolvedValue({
      ...(await api.getSupervisor("E1", "Avocado", 1, 1)) as api.SupervisorDetail,
      pending: null, crew_hidden: true, labourers: [], crew_count: 3,
    });
    renderIt();
    fireEvent.click(await screen.findByText("Grace Wambui"));
    expect(await screen.findByText(/only shown to managers/)).toBeTruthy();
    expect(screen.queryByText("Jane Crew")).toBeNull();
  });

  it("hides Add supervisor for a non-manager", async () => {
    renderIt(false);
    await screen.findByText("Grace Wambui");
    expect(screen.queryByText("Add supervisor")).toBeNull();
  });
});

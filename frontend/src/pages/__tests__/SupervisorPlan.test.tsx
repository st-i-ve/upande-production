import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Boot, Crop, SupervisorPlan } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getPlan: vi.fn(),
  generatePlanWeek: vi.fn(),
  listUnits: vi.fn(),
  listOperations: vi.fn(),
  listCasualLabourers: vi.fn(),
  recordTaskWork: vi.fn(),
  savePlanTasks: vi.fn(),
  getSupervisorPlan: vi.fn(),
  saveSupervisorPlan: vi.fn(),
  copySupervisorPlan: vi.fn(),
}));

import * as api from "@/lib/api";
import { CropProvider } from "@/lib/crops";
import { Plan } from "@/pages/Plan";

const crop: Crop = {
  name: "Avocado", crop_key: "avocado", accent_color: "#3f8f4f", icon_key: "avocado",
  unit_label: "Block", parent_unit_label: "Pivot", sub_unit_label: "Block", yield_uom: "kg",
};
const boot = (over: Partial<Boot> = {}): Boot => ({
  crops: [crop], farms: ["Mutara"], can_see_pay: true, can_plan: true, can_manage: true, ...over,
});
const mocked = vi.mocked(api);

const asg = (unit: string, supervisor: string, name: string) => ({ name: `A-${unit}`, unit, supervisor, supervisor_name: name });
const sp = (over: Partial<SupervisorPlan> = {}): SupervisorPlan => ({
  week_start: "2026-11-16", week_end: "2026-11-22", can_edit: true,
  units: [
    { name: "PH1-B1", unit_name: "PH1-B1", area_ha: 4, farm: "Mutara" },
    { name: "PH1-B2", unit_name: "PH1-B2", area_ha: 3, farm: "Mutara" },
  ],
  supervisors: [
    { name: "EMP-1", employee_name: "Stephene", user: "s@x" },
    { name: "EMP-2", employee_name: "Supervisor Test", user: "t@x" },
  ],
  assignments: [], last_week: [], last_week_label: { year: 2026, week: 46 }, warnings: [], ...over,
});

async function openSupervisors(b: Boot = boot()) {
  render(
    <CropProvider crop={crop} boot={b}>
      <Plan />
    </CropProvider>,
  );
  fireEvent.mouseDown(await screen.findByRole("tab", { name: "Supervisors" }), { button: 0 });
  fireEvent.click(screen.getByRole("tab", { name: "Supervisors" }));
}

beforeEach(() => {
  vi.resetAllMocks();
  mocked.listUnits.mockResolvedValue({ units: [] });
  mocked.listOperations.mockResolvedValue({ rows: [] });
  mocked.listCasualLabourers.mockResolvedValue({ people: [] });
  mocked.getPlan.mockResolvedValue({ plan: null, week_start: "2026-11-16", week_end: "2026-11-22", tasks: [] });
});

describe("Plan supervisors view", () => {
  it("lists the blocks with each one's supervisor and last week's", async () => {
    mocked.getSupervisorPlan.mockResolvedValue(
      sp({ assignments: [asg("PH1-B1", "EMP-1", "Stephene")], last_week: [asg("PH1-B2", "EMP-2", "Supervisor Test")] }),
    );
    await openSupervisors();
    const table = await screen.findByRole("region", { name: "Supervisors by block" });
    expect(within(table).getByText("PH1-B1")).toBeTruthy();
    expect(within(table).getByText("PH1-B2")).toBeTruthy();
    expect(within(table).getByRole("button", { name: "Supervisor for PH1-B1" }).textContent).toContain("Stephene");
    expect(within(table).getByText("Supervisor Test")).toBeTruthy(); // last week's column
    expect(mocked.getSupervisorPlan).toHaveBeenCalledWith("Avocado", "Mutara", expect.any(Number), expect.any(Number));
  });

  it("is read-only for a non-manager", async () => {
    mocked.getSupervisorPlan.mockResolvedValue(sp({ can_edit: false, assignments: [asg("PH1-B1", "EMP-1", "Stephene")] }));
    await openSupervisors(boot({ can_manage: false }));
    await screen.findByRole("region", { name: "Supervisors by block" });
    expect(screen.queryByRole("button", { name: /Supervisor for/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Copy last week/ })).toBeNull();
    expect(screen.getByText("Stephene")).toBeTruthy();
  });

  it("copies last week into an empty week", async () => {
    const last = [asg("PH1-B1", "EMP-1", "Stephene")];
    mocked.getSupervisorPlan.mockResolvedValue(sp({ last_week: last }));
    mocked.copySupervisorPlan.mockResolvedValue({ ...sp({ last_week: last, assignments: last }), copied: 1 });
    await openSupervisors();
    fireEvent.click(await screen.findByRole("button", { name: /Copy last week/ }));
    await waitFor(() => expect(mocked.copySupervisorPlan).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Supervisor for PH1-B1" }).textContent).toContain("Stephene"),
    );
  });

  it("keeps Copy last week off when the week already has supervisors", async () => {
    mocked.getSupervisorPlan.mockResolvedValue(
      sp({ assignments: [asg("PH1-B1", "EMP-1", "Stephene")], last_week: [asg("PH1-B1", "EMP-2", "Supervisor Test")] }),
    );
    await openSupervisors();
    const btn = await screen.findByRole("button", { name: /Copy last week/ });
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it("saves a pick, then shows the leave warning the server returns", async () => {
    mocked.getSupervisorPlan.mockResolvedValue(sp());
    mocked.saveSupervisorPlan.mockResolvedValue({
      ...sp({ assignments: [asg("PH1-B1", "EMP-1", "Stephene")] }),
      saved: 1, tasks_updated: 2,
      warnings: [{ unit: "PH1-B1", supervisor: "EMP-1", supervisor_name: "Stephene", message: "Stephene is on approved leave from 2026-11-16 to 2026-11-20." }],
    });
    await openSupervisors();
    const save = await screen.findByRole("button", { name: "Save" });
    expect((save as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Supervisor for PH1-B1" }));
    fireEvent.click(await screen.findByRole("option", { name: "Stephene" }));
    expect((screen.getByRole("button", { name: "Save" }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(mocked.saveSupervisorPlan).toHaveBeenCalledWith("Avocado", "Mutara", expect.any(Number), expect.any(Number), [
        { unit: "PH1-B1", supervisor: "EMP-1" },
      ]),
    );
    expect(await screen.findByTestId("supervisor-warnings")).toBeTruthy();
    expect(screen.getByText(/approved leave/)).toBeTruthy();
  });

  it("shows the supervisor of each task in the task list", async () => {
    mocked.getPlan.mockResolvedValue({
      plan: "PLAN-1", week_start: "2026-11-16", week_end: "2026-11-22",
      tasks: [{
        name: "T1", unit: "PH1-B1", cycle: null, operation: "OP-1", operation_name: "Pruning", planned_qty: 1, done_qty: 0,
        uom: "Tree", rate: 1, due_date: "2026-11-17", supervisor: "EMP-1", supervisor_name: "Stephene", status: "Open",
        deviation: null, protocol_ref: null, note: null, work: [],
      }],
    });
    render(
      <CropProvider crop={crop} boot={boot()}>
        <Plan />
      </CropProvider>,
    );
    expect(await screen.findByText("Stephene")).toBeTruthy();
  });
});

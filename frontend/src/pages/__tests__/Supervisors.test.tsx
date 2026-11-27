import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/components/Toast";
import type { Boot, Crop } from "@/lib/api";

vi.mock("@/lib/people-api", () => ({ supervisorPeople: vi.fn(), labourerPeople: vi.fn() }));
vi.mock("@/lib/supervisors-api", () => ({ listSupervisors: vi.fn(), getSupervisor: vi.fn(), saveSupervisor: vi.fn(), assistantsWithoutManager: vi.fn(), employeeOptions: vi.fn() }));
vi.mock("@/lib/frappe", async (orig) => ({
  ...(await orig<typeof import("@/lib/frappe")>()),
  searchLink: vi.fn().mockResolvedValue([{ value: "E9", description: "Newbie Hand", label: "Newbie Hand" }]),
}));

import { searchLink } from "@/lib/frappe";
import * as people from "@/lib/people-api";
import * as api from "@/lib/supervisors-api";
import { CropProvider } from "@/lib/crops";
import { Supervisors } from "@/pages/Supervisors";

const crop: Crop = {
  name: "Avocado", crop_key: "avocado", accent_color: "#3f8f4f", icon_key: "avocado", unit_label: "Block",
  parent_unit_label: "Pivot", sub_unit_label: "Block", yield_uom: "kg",
};
const boot = (manage: boolean): Boot => ({ crops: [crop], farms: ["Mutara"], can_see_pay: false, can_plan: true, can_manage: manage });
const person = (o: Partial<people.SupervisorPerson> & { employee: string; employee_name: string }): people.SupervisorPerson => ({
  image: null, phone: "0700111222", user: null, farm: "Mutara", active: true, blocks: 2, activities: 1, overseer: true, crew: 5, full: true,
  metrics: { assigned: 8, done: 3, on_time_pct: 62.5, late_pct: 25, logs: 6, active_days: 3, logs_per_day: 2, sent_back: 1, entries: 10, sent_back_pct: 10, check_days: 1.5 },
  scores: { on_time: 62.5, steady: 75, logging: 80, returns: 90, check_speed: 78 },
  flags: [{ kind: "overdue", label: "Overdue tasks", count: 2, detail: "2 unfinished past their due date." }],
  where: [{ key: "B1", label: "Block 1", count: 5, share: 62.5 }],
  weekly: [{ week: "2026-11-02", done: 1, logs: 2 }],
  ...o,
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
  vi.mocked(api.employeeOptions).mockResolvedValue([{ value: "E9", label: "Newbie Hand" }]);
  vi.mocked(api.assistantsWithoutManager).mockResolvedValue([]);
  vi.mocked(people.supervisorPeople).mockResolvedValue({
    from: "2026-11-02", to: "2026-11-27", weeks: ["2026-11-02"], can_manage: true,
    medians: { assigned: 6, on_time_pct: 70, late_pct: 20, logs_per_day: 1.5, sent_back_pct: 5, check_days: 1, on_time: 70, steady: 80, logging: 60, returns: 95, check_speed: 85 },
    people: [
      person({ employee: "E1", employee_name: "Grace Wambui" }),
      person({ employee: "E2", employee_name: "Peter Otieno", active: false, phone: null, overseer: false }),
      person({ employee: "E3", employee_name: "Ann Kamau", overseer: false, full: false, metrics: { assigned: 4, done: 1, on_time_pct: 50, late_pct: 40, logs: 0, active_days: 0, logs_per_day: null, sent_back: null, entries: null, sent_back_pct: null, check_days: null }, flags: [] }),
    ],
  });
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
  it("warns about assistant managers with no manager", async () => {
    vi.mocked(api.assistantsWithoutManager).mockResolvedValue([
      { user: "ann@x.com", full_name: "Ann Assistant", employee: "E7", reports_to: null, reason: "no_reports_to" },
    ]);
    renderIt();
    const box = await screen.findByTestId("assistants-without-manager");
    expect(box.textContent).toContain("Ann Assistant");
    expect(box.textContent).toContain("Set Reports To on their employee record");
  });

  it("shows no warning when every assistant has a manager", async () => {
    renderIt();
    await screen.findByTestId("supervisor-record");
    expect(screen.queryByTestId("assistants-without-manager")).toBeNull();
  });

  it("lists active supervisors in the roster and opens the first one's record against the farm median", async () => {
    renderIt();
    const record = await screen.findByTestId("supervisor-record");
    const roster = screen.getByTestId("person-E1");
    expect(within(roster).getByText("Grace Wambui")).toBeTruthy();
    expect(within(roster).getByText(/2 blocks, 1 activity · Overseer/)).toBeTruthy();
    expect(within(roster).getByText("62.5%")).toBeTruthy();
    expect(screen.queryByTestId("person-E2")).toBeNull(); // inactive hidden by default
    const table = within(record).getByRole("table", { name: "Against the farm median" });
    expect(within(table).getByText("Done on time")).toBeTruthy();
    expect(within(table).getByText("70%")).toBeTruthy(); // the farm median
    expect(within(record).getByText("Overdue tasks")).toBeTruthy();
    expect(within(record).getByText("Block 1")).toBeTruthy();
    expect(within(record).getByRole("img", { name: "Score parts" })).toBeTruthy();
    expect(api.getSupervisor).not.toHaveBeenCalled();
    expect(people.supervisorPeople).toHaveBeenCalledWith("Avocado", expect.stringMatching(/^\d{4}-\d\d-\d\d$/), expect.stringMatching(/^\d{4}-\d\d-\d\d$/));
  });

  it("switches the record when another supervisor is picked and shows private crew figures as a dash", async () => {
    renderIt();
    fireEvent.click(await screen.findByTestId("person-E3"));
    const record = await screen.findByText("crew figures are private");
    expect(record).toBeTruthy();
  });

  it("searches the roster", async () => {
    renderIt();
    await screen.findByTestId("supervisor-record");
    fireEvent.change(screen.getByLabelText("Find a supervisor"), { target: { value: "zzz" } });
    expect(await screen.findByText(/Nobody matches/)).toBeTruthy();
  });

  it("compares with another supervisor", async () => {
    renderIt();
    await screen.findByTestId("supervisor-record");
    fireEvent.click(screen.getByRole("button", { name: /Compare/ }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("How Grace Wambui compares")).toBeTruthy();
    fireEvent.click(within(dialog).getByRole("button", { name: /Ann Kamau/ }));
    expect(within(dialog).getByRole("table", { name: "Comparison figures" }).textContent).toContain("Ann Kamau");
  });

  it("opens the details with blocks and crew from the record", async () => {
    renderIt();
    await screen.findByTestId("supervisor-record");
    fireEvent.click(screen.getByRole("button", { name: /Details and edit/ }));
    expect(await screen.findByText("Jane Crew")).toBeTruthy();
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

  it("hides Add supervisor for a non-manager", async () => {
    renderIt(false);
    await screen.findByTestId("supervisor-record");
    expect(screen.queryByText("Add supervisor")).toBeNull();
  });
});

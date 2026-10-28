import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Boot, Crop, PlanTask } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getPlan: vi.fn(),
  generatePlanWeek: vi.fn(),
  listUnits: vi.fn(),
  listOperations: vi.fn(),
  listValueAdders: vi.fn(),
  recordTaskWork: vi.fn(),
  savePlanTasks: vi.fn(),
}));

import * as api from "@/lib/api";
import { CropProvider } from "@/lib/crops";
import { Plan } from "@/pages/Plan";

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
const boot = (over: Partial<Boot> = {}): Boot => ({
  crops: [crop],
  farms: ["Mutara"],
  can_see_pay: true,
  can_plan: true,
  can_manage: false,
  ...over,
});

const task = (over: Partial<PlanTask>): PlanTask => ({
  name: "T1",
  unit: "Block A",
  cycle: null,
  operation: "OP-1",
  operation_name: "Pruning",
  planned_qty: 10,
  done_qty: 0,
  uom: "trees",
  rate: 50,
  due_date: "2026-10-27",
  supervisor: null,
  supervisor_name: null,
  status: "Open",
  deviation: null,
  protocol_ref: null,
  note: null,
  work: [],
  ...over,
});

const renderPlan = (b: Boot = boot()) =>
  render(
    <CropProvider crop={crop} boot={b}>
      <Plan />
    </CropProvider>,
  );

const mocked = vi.mocked(api);

beforeEach(() => {
  vi.resetAllMocks();
  mocked.listUnits.mockResolvedValue({ units: [] });
  mocked.listOperations.mockResolvedValue({ rows: [] });
  mocked.listValueAdders.mockResolvedValue({ people: [{ name: "EMP-1", employee_name: "Jane Wanjiru", image: null }] });
});

describe("Plan", () => {
  it("shows an empty state with a generate button for an empty week", async () => {
    mocked.getPlan.mockResolvedValue({ plan: null, week_start: "2026-10-26", week_end: "2026-11-01", tasks: [] });
    renderPlan();
    expect(await screen.findByText(/Nothing planned for/)).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /Generate from protocols/ }).length).toBeGreaterThan(0);
  });

  it("groups tasks by unit and shows a Late badge", async () => {
    mocked.getPlan.mockResolvedValue({
      plan: "PLAN-1",
      week_start: "2026-10-26",
      week_end: "2026-11-01",
      tasks: [
        task({ name: "T1", deviation: "Late" }),
        task({ name: "T2", operation_name: "Spraying", status: "Done", done_qty: 10 }),
        task({ name: "T3", unit: "Block B", operation_name: "Weeding" }),
      ],
    });
    renderPlan();
    const a = await screen.findByRole("region", { name: "Block A" });
    expect(within(a).getByText("Pruning")).toBeTruthy();
    expect(within(a).getByText("Spraying")).toBeTruthy();
    expect(within(a).getByText("Late")).toBeTruthy();
    expect(within(a).getByText("1/2 done")).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Block B" })).getByText("Weeding")).toBeTruthy();
  });

  it("shows pending quantity apart from done, with an awaiting-approval chip", async () => {
    mocked.getPlan.mockResolvedValue({
      plan: "PLAN-1",
      week_start: "2026-10-26",
      week_end: "2026-11-01",
      tasks: [task({ name: "T1", done_qty: 4, pending_qty: 3 }), task({ name: "T2", operation_name: "Weeding" })],
    });
    renderPlan();
    expect(await screen.findByText("Awaiting approval", { selector: "span" })).toBeTruthy();
    expect(screen.getByText("+3")).toBeTruthy();
    expect(document.querySelector("[data-pending]")).toBeTruthy();
  });

  it("totals quantities per unit of measure, never across, and formats labour as KES", async () => {
    mocked.getPlan.mockResolvedValue({
      plan: "PLAN-1",
      week_start: "2026-10-26",
      week_end: "2026-11-01",
      tasks: [
        task({ name: "T1", planned_qty: 20, done_qty: 6, uom: "Hectare", work: [{ name: "W1", plan_task: "T1", employee: "E", employee_name: "E", qty: 6, hours: 1, pay_value: 4380.6, work_date: "2026-10-27", approval_status: "Approved" } as never] }),
        task({ name: "T2", unit: "Block B", operation_name: "Weeding", planned_qty: 400, done_qty: 100, pending_qty: 25.16, uom: "Tree" }),
      ],
    });
    renderPlan();
    await screen.findByText("Quantity done");
    expect(screen.getByText("100 Tree · 6 Hectare")).toBeTruthy();
    expect(screen.getByText(/of 400 Tree · 20 Hectare planned · 25.16 Tree awaiting approval/)).toBeTruthy();
    expect(screen.queryByText("106")).toBeNull();
    expect(screen.getByText("KES 4,381")).toBeTruthy();
    expect(screen.queryByText("4,380.60")).toBeNull();
  });

  it("tick-off Save calls recordTaskWork with entries and updates the row", async () => {
    const t1 = task({ name: "T1" });
    mocked.getPlan.mockResolvedValue({ plan: "PLAN-1", week_start: "2026-10-26", week_end: "2026-11-01", tasks: [t1] });
    mocked.recordTaskWork.mockResolvedValue({ task: { ...t1, status: "Done", done_qty: 10 }, work: ["W1"] });
    renderPlan();
    fireEvent.click(await screen.findByText("Pruning"));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("radio", { name: "Done" }));
    fireEvent.click(within(dialog).getByRole("button", { name: /Add value adder/ }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Value adder" }));
    fireEvent.click(await screen.findByRole("option", { name: "Jane Wanjiru" }));
    fireEvent.change(within(dialog).getByLabelText(/Quantity/), { target: { value: "10" } });
    fireEvent.change(within(dialog).getByLabelText("Hours"), { target: { value: "4" } });
    expect(within(dialog).getAllByText("500.00").length).toBe(2); // 10 x 50 preview
    fireEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(mocked.recordTaskWork).toHaveBeenCalledWith(
        "PLAN-1",
        "T1",
        "Done",
        [{ employee: "EMP-1", qty: 10, hours: 4 }],
        "",
      ),
    );
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(mocked.getPlan.mock.calls.length).toBeGreaterThan(1)); // quiet refetch
  });

  it("tick-off disables Save and hints when a row has no quantity", async () => {
    const t1 = task({ name: "T1" });
    mocked.getPlan.mockResolvedValue({ plan: "PLAN-1", week_start: "2026-10-26", week_end: "2026-11-01", tasks: [t1] });
    renderPlan();
    fireEvent.click(await screen.findByText("Pruning"));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /Add value adder/ }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Value adder" }));
    fireEvent.click(await screen.findByRole("option", { name: "Jane Wanjiru" }));
    fireEvent.change(within(dialog).getByLabelText("Hours"), { target: { value: "4" } });
    expect(within(dialog).getByText("Give each person the quantity they did.")).toBeTruthy();
    expect((within(dialog).getByRole("button", { name: "Save" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(within(dialog).getByLabelText(/Quantity/), { target: { value: "3" } });
    expect((within(dialog).getByRole("button", { name: "Save" }) as HTMLButtonElement).disabled).toBe(false);
  });
});

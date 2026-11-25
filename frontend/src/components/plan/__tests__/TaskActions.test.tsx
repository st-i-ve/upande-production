import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PlanTask } from "@/lib/api";

vi.mock("@/lib/api", () => ({ movePlanTask: vi.fn(), postponePlanTask: vi.fn(), deletePlanTask: vi.fn() }));

vi.mock("@/components/DatePicker", () => ({
  DatePicker: ({ value, onChange, "aria-label": label }: { value: string; onChange: (v: string) => void; "aria-label"?: string }) => (
    <input aria-label={label} value={value} onChange={(e) => onChange(e.target.value)} />
  ),
}));

import * as api from "@/lib/api";
import { TaskActions } from "@/components/plan/TaskActions";

const mocked = vi.mocked(api);
const weekStart = new Date(2026, 10, 23); // Mon 2026-11-23

const task = (over: Partial<PlanTask> = {}) =>
  ({ name: "T-1", operation_name: "Spraying", due_date: "2026-11-24", status: "Pending", work: [], ...over }) as unknown as PlanTask;

const warn = {
  error: "rule",
  breaches: [{ rule: "PAR-1", rule_type: "x", enforcement: "Warn", message: "Too close to harvest." }],
  rule_status: "Warn",
  needs_override_reason: true,
};

function setup(t: PlanTask = task(), onDone = vi.fn()) {
  render(<TaskActions plan="PLAN-1" task={t} weekStart={weekStart} onDone={onDone} />);
  fireEvent.click(screen.getByRole("button", { name: "Task actions" }));
  return onDone;
}

beforeEach(() => vi.resetAllMocks());

describe("TaskActions", () => {
  it("postpone needs a reason, then sends the reason and no override", async () => {
    mocked.postponePlanTask.mockResolvedValue({ plan: "PLAN-1", task: "T-1", split: false });
    const onDone = setup();
    fireEvent.click(screen.getByRole("menuitem", { name: "Postpone" }));
    const save = screen.getByRole("button", { name: "Postpone task" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Rain" } });
    // default new date is the day after the due date
    fireEvent.click(save);
    await waitFor(() => expect(mocked.postponePlanTask).toHaveBeenCalledWith("PLAN-1", "T-1", "2026-11-25", "Rain", null));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });

  it("a Warn envelope opens the override dialog and resends with the reason", async () => {
    mocked.postponePlanTask.mockResolvedValueOnce(warn).mockResolvedValueOnce({ plan: "PLAN-1", task: "T-1", split: false });
    setup();
    fireEvent.click(screen.getByRole("menuitem", { name: "Postpone" }));
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Rain" } });
    fireEvent.click(screen.getByRole("button", { name: "Postpone task" }));
    expect(await screen.findByText(/Too close to harvest/)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("Why does this need to happen now?"), { target: { value: "Agreed with manager" } });
    fireEvent.click(screen.getByRole("button", { name: "Save with reason" }));
    await waitFor(() =>
      expect(mocked.postponePlanTask).toHaveBeenLastCalledWith("PLAN-1", "T-1", "2026-11-25", "Rain", "Agreed with manager"),
    );
  });

  it("delete is disabled when work is recorded", () => {
    setup(task({ work: [{ employee: "E1" } as never] }));
    const item = screen.getByRole("menuitem", { name: "Delete" });
    expect(item).toHaveAttribute("aria-disabled", "true");
    expect(item).toHaveAttribute("title", "Work is recorded; mark it Skipped instead");
  });

  it("postpone is hidden for Done tasks", () => {
    setup(task({ status: "Done" }));
    expect(screen.queryByRole("menuitem", { name: "Postpone" })).toBeNull();
  });

  it("delete needs a reason and calls deletePlanTask", async () => {
    mocked.deletePlanTask.mockResolvedValue({ deleted: "T-1" });
    const onDone = setup();
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete" }));
    const go = screen.getByRole("button", { name: "Delete task" });
    expect(go).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Duplicate" } });
    fireEvent.click(go);
    await waitFor(() => expect(mocked.deletePlanTask).toHaveBeenCalledWith("PLAN-1", "T-1", "Duplicate"));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });

  it("change date calls movePlanTask", async () => {
    mocked.movePlanTask.mockResolvedValue({ plan: "PLAN-1", task: "T-1" });
    const onDone = setup();
    fireEvent.click(screen.getByRole("menuitem", { name: "Change date" }));
    fireEvent.click(screen.getByRole("button", { name: "Move task" }));
    await waitFor(() => expect(mocked.movePlanTask).toHaveBeenCalledWith("PLAN-1", "T-1", "2026-11-24", null));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });

  it("change date is hidden for Done and Skipped tasks", () => {
    const { unmount } = render(<TaskActions plan="PLAN-1" task={task({ status: "Done" })} weekStart={weekStart} onDone={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Task actions" }));
    expect(screen.queryByRole("menuitem", { name: "Change date" })).toBeNull();
    unmount();
    setup(task({ status: "Skipped" }));
    expect(screen.queryByRole("menuitem", { name: "Change date" })).toBeNull();
  });

  it("picking another date clears a Block so Move task is enabled again", async () => {
    mocked.movePlanTask.mockResolvedValue({
      error: "rule",
      breaches: [{ rule: "PAR-1", rule_type: "x", enforcement: "Block", message: "Not on this day." }],
      rule_status: "Block",
      needs_override_reason: false,
    } as never);
    setup();
    fireEvent.click(screen.getByRole("menuitem", { name: "Change date" }));
    fireEvent.click(screen.getByRole("button", { name: "Move task" }));
    expect(await screen.findByText(/An activity rule stops this/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Move task" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("New date"), { target: { value: "2026-11-26" } });
    expect(screen.queryByText(/An activity rule stops this/)).toBeNull();
    expect(screen.getByRole("button", { name: "Move task" })).toBeEnabled();
  });
});

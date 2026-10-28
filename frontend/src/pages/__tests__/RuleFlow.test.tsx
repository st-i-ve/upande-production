import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { PlanTask, UnitRow } from "@/lib/api";

vi.mock("@/lib/api", () => ({ savePlanTasks: vi.fn(), recordTaskWork: vi.fn() }));

import * as api from "@/lib/api";
import { AddTaskDialog } from "@/components/plan/AddTaskDialog";
import { TickOffDialog } from "@/components/plan/TickOffDialog";
import { RuleFlag } from "@/components/rules/RuleParts";
import { RuleBanner } from "@/components/approvals/RuleBanner";
import { ProtocolRuleCheck } from "@/components/approvals/ProtocolRuleCheck";
import { ruleFailure } from "@/lib/rules";

const mocked = vi.mocked(api);

const breach = (enforcement: "Block" | "Warn") => ({
  rule: "PAR-1",
  rule_type: "Not within days before harvest",
  enforcement,
  message: "Spraying is not allowed within 21 day(s) before harvest.",
});
const warnEnvelope = { error: "rule", breaches: [breach("Warn")], rule_status: "Warn", needs_override_reason: true };
const blockEnvelope = { error: "rule", breaches: [breach("Block")], rule_status: "Block", needs_override_reason: false };

const units = [{ name: "Block A", is_group: 0, current_cycle: "CY-1", item: "Hass", area_ha: 1 }] as unknown as UnitRow[];
const ops = [{ name: "OP-1", operation_name: "Spraying", work_uom: "Ha" }];

function addTask() {
  return render(
    <AddTaskDialog crop="Avocado" farm="Mutara" year={2026} week={44} weekStart={new Date(2026, 9, 26)} unitLabel="Block" units={units} operations={ops} supervisors={[]} onClose={() => {}} onAdded={vi.fn()} />,
  );
}

async function fillAdd() {
  fireEvent.click(screen.getByRole("button", { name: "Block" }));
  fireEvent.click(await screen.findByRole("option", { name: "Block A · Hass" }));
  fireEvent.click(screen.getByRole("button", { name: "Operation" }));
  fireEvent.click(await screen.findByRole("option", { name: "Spraying" }));
}

beforeEach(() => vi.resetAllMocks());

describe("ruleFailure", () => {
  it("reads breaches off an error envelope and ignores other errors", () => {
    expect(ruleFailure(warnEnvelope)).toMatchObject({ status: "Warn", needsReason: true });
    expect(ruleFailure(blockEnvelope)).toMatchObject({ status: "Block", needsReason: false });
    expect(ruleFailure({ error: "Not permitted." })).toBeNull();
  });
});

describe("Warn reason flow (add task)", () => {
  it("asks for a reason and resends with override_reason", async () => {
    mocked.savePlanTasks.mockResolvedValueOnce(warnEnvelope as never).mockResolvedValueOnce({ name: "WP-1" });
    addTask();
    await fillAdd();
    fireEvent.click(screen.getByRole("button", { name: "Add task" }));
    expect(await screen.findByText("Go ahead despite the rule?")).toBeInTheDocument();
    expect(screen.getAllByText(/within 21 day/).length).toBeGreaterThan(0);
    const send = screen.getByRole("button", { name: "Save with reason" });
    expect(send).toBeDisabled(); // a reason is required
    fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Blight outbreak" } });
    fireEvent.click(send);
    await waitFor(() => expect(mocked.savePlanTasks).toHaveBeenCalledTimes(2));
    expect(mocked.savePlanTasks.mock.calls[0][5]).toBeNull();
    expect(mocked.savePlanTasks.mock.calls[1][5]).toBe("Blight outbreak");
  });
});

describe("Block flow (add task)", () => {
  it("shows the breach and cannot be saved", async () => {
    mocked.savePlanTasks.mockResolvedValue(blockEnvelope as never);
    addTask();
    await fillAdd();
    fireEvent.click(screen.getByRole("button", { name: "Add task" }));
    expect(await screen.findByText(/cannot be saved/)).toBeInTheDocument();
    expect(screen.getByTestId("breach-list")).toHaveTextContent("within 21 day");
    expect(screen.getByRole("button", { name: "Add task" })).toBeDisabled();
    expect(screen.queryByText("Go ahead despite the rule?")).toBeNull();
  });
});

describe("tick-off", () => {
  const task = {
    name: "T1", unit: "Block A", cycle: "CY-1", operation: "OP-1", operation_name: "Spraying", planned_qty: 5, done_qty: 0, uom: "Ha",
    rate: 10, due_date: "2026-10-27", supervisor: null, supervisor_name: null, status: "Open", deviation: null, protocol_ref: null, note: null, work: [],
    rule_status: "Warn", rule_notes: "Close to harvest", override_reason: null,
  } as PlanTask;

  it("resends with the reason on Warn", async () => {
    mocked.recordTaskWork.mockResolvedValueOnce(warnEnvelope as never).mockResolvedValueOnce({ task, work: [] });
    const onSaved = vi.fn();
    render(<TickOffDialog plan="WP-1" task={task} people={[]} canSeePay onClose={() => {}} onSaved={onSaved} />);
    expect(screen.getByTestId("rule-flag")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    fireEvent.change(await screen.findByLabelText("Reason"), { target: { value: "Urgent" } });
    fireEvent.click(screen.getByRole("button", { name: "Save with reason" }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(mocked.recordTaskWork.mock.calls[1][6]).toBe("Urgent");
  });
});

describe("rule flags", () => {
  it("shows Warn amber / Block red with notes and the reason in the tooltip", () => {
    const { rerender } = render(<RuleFlag status="Warn" notes="Close to harvest" overrideReason="Urgent" />);
    const flag = screen.getByTestId("rule-flag");
    expect(flag).toHaveAttribute("title", "Close to harvest\nReason given: Urgent");
    expect(flag).toHaveTextContent("Warn");
    rerender(<RuleFlag status="Block" />);
    expect(screen.getByTestId("rule-flag")).toHaveTextContent("Block");
    rerender(<RuleFlag status="OK" />);
    expect(screen.queryByTestId("rule-flag")).toBeNull();
  });

  it("puts the override reason on the approval card for the manager", () => {
    render(<RuleBanner status="Warn" notes="Spraying is not allowed within 21 day(s)" overrideReason="Blight outbreak" />);
    expect(screen.getByTestId("rule-banner")).toHaveTextContent("Reason given: Blight outbreak");
  });

  it("lists protocol steps that break a rule", () => {
    render(<ProtocolRuleCheck problems={[{ operation: "OP-1", operation_name: "Spraying", repeat: 1, day: 300, stage: "Harvest", rule_status: "Block", breaches: [breach("Block")] }]} />);
    expect(screen.getByTestId("protocol-rule-check")).toHaveTextContent("Spraying");
    expect(screen.getByTestId("protocol-rule-check")).toHaveTextContent("day 300");
  });
});

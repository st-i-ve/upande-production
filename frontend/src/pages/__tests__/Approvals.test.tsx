import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/approvals-api", () => ({
  listApprovals: vi.fn(),
  approve: vi.fn(),
  sendBack: vi.fn(),
  resubmit: vi.fn(),
  approvalCounts: vi.fn(),
}));
import { approve, listApprovals, resubmit, sendBack, type ApprovalGroup } from "@/lib/approvals-api";
import { Approvals } from "@/pages/Approvals";

const entry = (n: string, who: string) => ({
  name: n, employee: who, employee_name: who, qty: 10, uom: "Kg", hours: 4, rate: 50, pay_value: 500,
  work_date: "2026-10-26", approval_status: "Pending" as const, review_note: null,
});
const group = (key: string, over: Partial<ApprovalGroup> = {}): ApprovalGroup => ({
  key, status: "Pending", crop: "Test Crop", unit: "B1", unit_name: "Block 1", operation: "Pruning",
  operation_name: "Pruning", plan: "P1", plan_year: 2026, plan_week: 44, plan_task: "T1",
  task_planned_qty: 100, task_done_qty: 20, task_pending_qty: 10, task_status: "Open", note: null,
  unplanned: 0, uom: "Kg", work_date: "2026-10-26", submitted_by: "moses@x.com", submitted_by_name: "Moses",
  created: "2026-10-26 10:00:00", age_days: 1, stale: false, total_qty: 10, total_pay: 500, review_note: null,
  reviewed_by: null, reviewed_at: null, names: [`${key}-1`], entries: [entry(`${key}-1`, "Alice")], ...over,
});
const counts = { Pending: 2, Approved: 4, "Sent Back": 1, stale: 1 };
let lists: Record<string, ApprovalGroup[]> = {};
const fresh = () => ({
  Pending: [group("a"), group("b", { stale: true, age_days: 4, unit_name: "Block 2" })],
  "Sent Back": [group("s", { status: "Sent Back", review_note: "Recount please" })],
  Approved: [group("z", { status: "Approved" })],
});
const drop = (names: string[]) => {
  lists.Pending = lists.Pending.filter((g) => !g.names.some((n) => names.includes(n)));
};

beforeEach(() => {
  lists = fresh();
  vi.mocked(listApprovals).mockReset().mockImplementation(async (_c, f) => ({
    groups: lists[f?.status ?? "Pending"], counts, stale_days: 2,
  }));
  vi.mocked(approve).mockReset().mockImplementation(async (n) => (drop(n), { approved: n }));
  vi.mocked(sendBack).mockReset().mockImplementation(async (n) => (drop(n), { sent_back: n }));
  vi.mocked(resubmit).mockReset().mockResolvedValue({ resubmitted: [] });
});

describe("Approvals", () => {
  it("formats entries, total and step line with one precision", async () => {
    const e = (n: string) => ({ ...entry(n, "Alice"), qty: 2.1 });
    lists.Pending = [
      group("p", { total_qty: 6.3, task_planned_qty: 100, task_done_qty: 20, entries: [e("p-1"), e("p-2"), e("p-3")], names: ["p-1", "p-2", "p-3"] }),
    ];
    renderPage(<Approvals />);
    const card = within(await screen.findByTestId("approval-card-p"));
    expect(card.getAllByText("2.1").length).toBe(3);
    // total row (6.3) reads like the step line (6.3), not "6"
    expect(card.getAllByText("6.3").length).toBeGreaterThan(0);
    expect(screen.getByTestId("step-line").textContent).toMatch(/This submission 6\.3/);
  });

  it("shows tabs with counts and the pending cards", async () => {
    renderPage(<Approvals />);
    expect(await screen.findByTestId("approval-card-a")).toBeInTheDocument();
    expect(screen.getByTestId("count-pending")).toHaveTextContent("2");
    expect(screen.getByTestId("count-stale")).toHaveTextContent("1");
    expect(screen.getByTestId("count-sent")).toHaveTextContent("1");
    expect(screen.getByTestId("count-approved")).toHaveTextContent("4");
    expect(within(screen.getByTestId("approval-card-b")).getByTestId("age").className).toMatch(/red/);
    fireEvent.mouseDown(screen.getByRole("tab", { name: /Stale/ }), { button: 0 });
    await waitFor(() => expect(screen.queryByTestId("approval-card-a")).toBeNull());
    expect(screen.getByTestId("approval-card-b")).toBeInTheDocument();
  });

  it("approve removes the card and toasts", async () => {
    renderPage(<Approvals />);
    const card = await screen.findByTestId("approval-card-a");
    fireEvent.click(within(card).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(screen.queryByTestId("approval-card-a")).toBeNull());
    expect(approve).toHaveBeenCalledWith(["a-1"]);
    expect(await screen.findByText(/Approved 1 submission/)).toBeInTheDocument();
  });

  it("send back requires a note", async () => {
    renderPage(<Approvals />);
    const card = await screen.findByTestId("approval-card-a");
    fireEvent.click(within(card).getByRole("button", { name: "Send back" }));
    const dialog = await screen.findByRole("dialog");
    const confirm = within(dialog).getByRole("button", { name: "Send back" });
    expect(confirm).toBeDisabled();
    fireEvent.change(within(dialog).getByLabelText("Note for the supervisor"), { target: { value: "Recount" } });
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);
    await waitFor(() => expect(sendBack).toHaveBeenCalledWith(["a-1"], "Recount"));
    await waitFor(() => expect(screen.queryByTestId("approval-card-a")).toBeNull());
  });

  it("selecting cards shows the floating pill and bulk approves", async () => {
    renderPage(<Approvals />);
    await screen.findByTestId("approval-card-a");
    expect(screen.queryByTestId("approval-action-pill")).toBeNull();
    fireEvent.click(screen.getByLabelText("Select Block 1 Pruning"));
    fireEvent.click(screen.getByLabelText("Select Block 2 Pruning"));
    const pill = await screen.findByTestId("approval-action-pill");
    expect(pill).toHaveTextContent("2 selected");
    fireEvent.click(within(pill).getByRole("button", { name: /Approve/ }));
    await waitFor(() => expect(approve).toHaveBeenCalledWith(["a-1", "b-1"]));
  });

  it("restores the card and toasts when approving fails", async () => {
    vi.mocked(approve).mockResolvedValue({ error: "Not allowed" });
    renderPage(<Approvals />);
    const card = await screen.findByTestId("approval-card-a");
    fireEvent.click(within(card).getByRole("button", { name: "Approve" }));
    expect(await screen.findByText("Not allowed")).toBeInTheDocument();
    expect(screen.getByTestId("approval-card-a")).toBeInTheDocument();
  });

  it("sent back tab shows the note and resubmits edited quantities", async () => {
    renderPage(<Approvals />);
    await screen.findByTestId("approval-card-a");
    fireEvent.mouseDown(screen.getByRole("tab", { name: /Sent back/ }), { button: 0 });
    expect(await screen.findByTestId("review-note")).toHaveTextContent("Recount please");
    fireEvent.change(screen.getByLabelText("Qty for Alice"), { target: { value: "12" } });
    fireEvent.click(screen.getByRole("button", { name: /Resubmit/ }));
    await waitFor(() => expect(resubmit).toHaveBeenCalledWith(["s-1"], [{ name: "s-1", qty: 12 }]));
  });

  it("hides pay when the user cannot see it", async () => {
    vi.mocked(listApprovals).mockImplementation(async () => ({
      groups: [group("a", { total_pay: null, entries: [{ ...entry("a-1", "Alice"), rate: null, pay_value: null }] })],
      counts, stale_days: 2,
    }));
    renderPage(<Approvals />, { can_see_pay: false });
    await screen.findByTestId("approval-card-a");
    expect(screen.queryByText(/KES/)).toBeNull();
    expect(screen.queryByText(/Pay awaiting/i)).toBeNull();
    expect(screen.queryByText("Pay")).toBeNull();
  });

  it("shows pay when visible", async () => {
    renderPage(<Approvals />);
    await screen.findByTestId("approval-card-a");
    expect(screen.getByText("Pay awaiting")).toBeInTheDocument();
    expect(screen.getAllByText("KES 500").length).toBeGreaterThan(0);
  });

  it("shows an empty state", async () => {
    vi.mocked(listApprovals).mockImplementation(async () => ({ groups: [], counts: { Pending: 0, Approved: 0, "Sent Back": 0, stale: 0 }, stale_days: 2 }));
    renderPage(<Approvals />);
    expect(await screen.findByText(/Nothing waiting for approval/)).toBeInTheDocument();
  });
});

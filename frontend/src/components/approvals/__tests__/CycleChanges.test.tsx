import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/Toast";
import { TooltipProvider } from "@/components/ui/tooltip";
import { CycleChanges } from "@/components/approvals/CycleChanges";
import * as setup from "@/lib/cycle-setup-api";
import type { CycleChangeRequest } from "@/lib/cycle-setup-api";

vi.mock("@/lib/cycle-setup-api", async (orig) => ({
  ...(await orig<typeof setup>()),
  listCycleChanges: vi.fn(),
  approveCycleChange: vi.fn(),
  sendBackCycleChange: vi.fn(),
  rejectCycleChange: vi.fn(),
  withdrawCycleChange: vi.fn(),
  resubmitCycleChange: vi.fn(),
}));

const row = (name: string, over: Partial<CycleChangeRequest> = {}): CycleChangeRequest => ({
  name, cycle: "CYC-1", action: "Edit", status: "Pending", reason: "Re-measured", requested_by: "sup@x.com", reviewed_by: null,
  reviewed_at: null, review_note: null, stale: 0, creation: "2026-11-20 09:00:00", crop: "Avocado", unit: "PH1-B1", cycle_title: "Hass",
  changes: { area_ha: { old: 10, new: 12 } }, ...over,
});
const show = (isManager: boolean, onChanged = vi.fn()) =>
  render(
    <TooltipProvider>
      <ToastProvider>
        <CycleChanges crop="Avocado" isManager={isManager} onChanged={onChanged} />
      </ToastProvider>
    </TooltipProvider>,
  );

describe("CycleChanges", () => {
  beforeEach(() => {
    vi.mocked(setup.listCycleChanges).mockReset().mockResolvedValue({ rows: [row("CCR-1")] });
    for (const f of [setup.approveCycleChange, setup.sendBackCycleChange, setup.rejectCycleChange, setup.withdrawCycleChange]) {
      vi.mocked(f).mockReset().mockResolvedValue({ request: "CCR-1" });
    }
  });

  it("shows the old and new values and who asked, with the reason", async () => {
    show(true);
    const card = await screen.findByTestId("cycle-change-CCR-1");
    expect(within(card).getByText(/Area/)).toBeTruthy();
    expect(within(card).getByText(/10/)).toBeTruthy();
    expect(within(card).getByText(/12/)).toBeTruthy();
    expect(within(card).getByText(/Re-measured/)).toBeTruthy();
    expect(within(card).getByText(/sup@x.com/)).toBeTruthy();
  });

  it("a manager approves without apply anyway", async () => {
    const onChanged = vi.fn();
    show(true, onChanged);
    fireEvent.click(within(await screen.findByTestId("cycle-change-CCR-1")).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(setup.approveCycleChange).toHaveBeenCalledWith("CCR-1", 0));
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });

  it("a stale request is held until Apply anyway is ticked, then approves with 1", async () => {
    vi.mocked(setup.approveCycleChange).mockResolvedValueOnce({ error: "area_ha changed since this request was made. Apply anyway to overwrite." });
    show(true);
    const card = await screen.findByTestId("cycle-change-CCR-1");
    fireEvent.click(within(card).getByRole("button", { name: "Approve" }));
    expect(await within(card).findByText(/changed since this request was made/)).toBeTruthy();
    const approve = within(card).getByRole("button", { name: "Approve" });
    expect(approve).toBeDisabled();
    fireEvent.click(within(card).getByRole("checkbox", { name: "Apply anyway" }));
    expect(approve).toBeEnabled();
    fireEvent.click(approve);
    await waitFor(() => expect(setup.approveCycleChange).toHaveBeenLastCalledWith("CCR-1", 1));
  });

  it("reject needs a note", async () => {
    show(true);
    fireEvent.click(within(await screen.findByTestId("cycle-change-CCR-1")).getByRole("button", { name: "Reject" }));
    const dialog = await screen.findByRole("dialog");
    const go = within(dialog).getByRole("button", { name: "Reject" });
    expect(go).toBeDisabled();
    fireEvent.change(within(dialog).getByLabelText("Note for the requester"), { target: { value: "Not this season" } });
    fireEvent.click(go);
    await waitFor(() => expect(setup.rejectCycleChange).toHaveBeenCalledWith("CCR-1", "Not this season"));
  });

  it("send back needs a note", async () => {
    show(true);
    fireEvent.click(within(await screen.findByTestId("cycle-change-CCR-1")).getByRole("button", { name: "Send back" }));
    const dialog = await screen.findByRole("dialog");
    const go = within(dialog).getByRole("button", { name: "Send back" });
    expect(go).toBeDisabled();
    fireEvent.change(within(dialog).getByLabelText("Note for the requester"), { target: { value: "Check the area" } });
    fireEvent.click(go);
    await waitFor(() => expect(setup.sendBackCycleChange).toHaveBeenCalledWith("CCR-1", "Check the area"));
  });

  it("a requester has no decide buttons: they withdraw, or edit and resubmit what was sent back", async () => {
    vi.mocked(setup.listCycleChanges).mockResolvedValue({ rows: [row("CCR-1"), row("CCR-2", { status: "Sent Back", review_note: "Check the area" })] });
    show(false);
    const pending = await screen.findByTestId("cycle-change-CCR-1");
    expect(within(pending).queryByRole("button", { name: "Approve" })).toBeNull();
    fireEvent.click(within(pending).getByRole("button", { name: "Withdraw" }));
    await waitFor(() => expect(setup.withdrawCycleChange).toHaveBeenCalledWith("CCR-1"));
    const back = screen.getByTestId("cycle-change-CCR-2");
    expect(within(back).getByText(/Check the area/)).toBeTruthy();
    expect(within(back).getByRole("button", { name: "Edit & resubmit" })).toBeTruthy();
  });

  it("lets the requester amend the reason when resubmitting a sent-back delete", async () => {
    vi.mocked(setup.listCycleChanges).mockResolvedValue({ rows: [row("CCR-4", { action: "Delete", status: "Sent Back", reason: "Planted twice", changes: {} })] });
    vi.mocked(setup.resubmitCycleChange).mockReset().mockResolvedValue({ request: "CCR-4", pending: true });
    show(false);
    fireEvent.click(within(await screen.findByTestId("cycle-change-CCR-4")).getByRole("button", { name: "Resubmit" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Reason for deleting"), { target: { value: "Planted twice, confirmed" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Resubmit" }));
    await waitFor(() => expect(setup.resubmitCycleChange).toHaveBeenCalledWith("CCR-4", {}, "Planted twice, confirmed"));
  });

  it("shows a Clear block request readably", async () => {
    vi.mocked(setup.listCycleChanges).mockResolvedValue({
      rows: [row("CCR-5", { action: "Clear block", cycle: "", reason: null, changes: {}, payload: { unit: "PH1-B1", on_date: "2026-11-20", reason: "Other", note: "Flooded" } })],
    });
    show(true);
    const card = await screen.findByTestId("cycle-change-CCR-5");
    expect(card).toHaveTextContent("Clear block PH1-B1");
    expect(card).toHaveTextContent("2026-11-20");
    expect(card).toHaveTextContent("Other");
    expect(card).toHaveTextContent("Flooded");
    expect(within(card).getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Send back" })).toBeInTheDocument();
    expect(within(card).getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });
});

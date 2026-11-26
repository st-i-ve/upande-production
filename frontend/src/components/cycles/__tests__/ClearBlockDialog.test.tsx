import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/Toast";
import { ClearBlockDialog } from "@/components/cycles/ClearBlockDialog";
import * as setup from "@/lib/cycle-setup-api";

vi.mock("@/lib/cycle-setup-api", async (orig) => ({ ...(await orig<typeof setup>()), clearBlockPreview: vi.fn(), clearBlock: vi.fn() }));

const preview = {
  unit: "PH1-B1", running: 1, planned_deleted: 1, planned_closed: 0, tasks_skipped: 4, on_date: "2026-11-20", earliest_start: "2026-01-01",
  cycles: [{ name: "CYC-1", variety: "Hass" }], planned: [{ name: "CYC-2", variety: "Fuerte" }],
};
const open = (isManager: boolean, onDone = vi.fn()) =>
  render(
    <ToastProvider>
      <ClearBlockDialog unit="PH1-B1" isManager={isManager} onClose={() => {}} onDone={onDone} />
    </ToastProvider>,
  );

describe("ClearBlockDialog", () => {
  beforeEach(() => {
    vi.mocked(setup.clearBlockPreview).mockReset().mockResolvedValue(preview);
    vi.mocked(setup.clearBlock).mockReset().mockResolvedValue({ request: "CCR-9", pending: true });
  });

  it("lists what clearing will do", async () => {
    open(true);
    expect(await screen.findByText(/CYC-1/)).toBeInTheDocument();
    expect(screen.getByText(/CYC-2/)).toBeInTheDocument();
    expect(screen.getByText(/4 open tasks/)).toBeInTheDocument();
  });

  it("needs a note for Other", async () => {
    open(true);
    await screen.findByText(/CYC-1/);
    const go = screen.getByRole("button", { name: "Clear block" });
    expect(go).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Uprooted" }));
    expect(go).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Other" }));
    expect(go).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Note"), { target: { value: "Flooded" } });
    expect(go).toBeEnabled();
  });

  it("clears at once for a manager", async () => {
    vi.mocked(setup.clearBlock).mockResolvedValue({ cleared: { unit: "PH1-B1", on_date: "2026-11-20", running_closed: 1, planned_deleted: 1, planned_closed: 0, tasks_skipped: 4, requests_rejected: 0 } });
    const onDone = vi.fn();
    open(true, onDone);
    await screen.findByText(/CYC-1/);
    fireEvent.click(screen.getByRole("button", { name: "Crop failed" }));
    fireEvent.click(screen.getByRole("button", { name: "Clear block" }));
    await waitFor(() => expect(setup.clearBlock).toHaveBeenCalledWith("PH1-B1", expect.stringMatching(/^\d{4}-\d\d-\d\d$/), "Crop failed", undefined));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });

  it("sends a request for anyone else", async () => {
    open(false);
    await screen.findByText(/CYC-1/);
    fireEvent.click(screen.getByRole("button", { name: "Replanting" }));
    fireEvent.click(screen.getByRole("button", { name: "Send clear request" }));
    await waitFor(() => expect(setup.clearBlock).toHaveBeenCalled());
  });

  it("shows a server refusal", async () => {
    vi.mocked(setup.clearBlock).mockResolvedValue({ error: "Block has records" } as never);
    open(true);
    await screen.findByText(/CYC-1/);
    fireEvent.click(screen.getByRole("button", { name: "Uprooted" }));
    fireEvent.click(screen.getByRole("button", { name: "Clear block" }));
    expect(await screen.findByText("Block has records")).toBeInTheDocument();
  });
});

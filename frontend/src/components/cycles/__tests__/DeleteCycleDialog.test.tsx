import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/Toast";
import { DeleteCycleDialog } from "@/components/cycles/DeleteCycleDialog";
import type { Cycle } from "@/lib/api";
import * as setup from "@/lib/cycle-setup-api";

vi.mock("@/lib/cycle-setup-api", async (orig) => ({ ...(await orig<typeof setup>()), deleteCycle: vi.fn() }));

const cycle = { name: "CYC-1", unit: "PH1-B1", variety: "Hass" } as Cycle;
const open = (isManager: boolean, onDone = vi.fn()) =>
  render(
    <ToastProvider>
      <DeleteCycleDialog cycle={cycle} isManager={isManager} onClose={() => {}} onDone={onDone} />
    </ToastProvider>,
  );

describe("DeleteCycleDialog", () => {
  beforeEach(() => vi.mocked(setup.deleteCycle).mockReset().mockResolvedValue({ request: "CCR-2", pending: true }));

  it("asks a non-manager for a reason and sends a delete request", async () => {
    const onDone = vi.fn();
    open(false, onDone);
    const send = screen.getByRole("button", { name: "Send delete request" });
    expect(send).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason for deleting"), { target: { value: "Planted twice" } });
    fireEvent.click(send);
    await waitFor(() => expect(setup.deleteCycle).toHaveBeenCalledWith("CYC-1", "Planted twice"));
    await waitFor(() => expect(onDone).toHaveBeenCalled());
  });

  it("lets a manager confirm the delete", async () => {
    vi.mocked(setup.deleteCycle).mockResolvedValue({ deleted: "CYC-1" });
    open(true);
    expect(screen.queryByLabelText("Reason for deleting")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Delete cycle" }));
    await waitFor(() => expect(setup.deleteCycle).toHaveBeenCalledWith("CYC-1", undefined));
  });
});

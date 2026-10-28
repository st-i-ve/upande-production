import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/api", () => ({ listOperations: vi.fn(), listProtocols: vi.fn(), saveOperation: vi.fn() }));
import { listOperations, listProtocols, saveOperation } from "@/lib/api";
import { Settings } from "@/pages/Settings";

describe("Settings", () => {
  beforeEach(() => {
    vi.mocked(listProtocols).mockResolvedValue({ rows: [] });
    vi.mocked(saveOperation).mockReset();
  });

  it("shows an empty state", async () => {
    vi.mocked(listOperations).mockResolvedValue({ rows: [] });
    renderPage(<Settings />);
    expect(await screen.findByText(/No operations defined/i)).toBeInTheDocument();
  });

  it("edits and saves one row for a manager", async () => {
    vi.mocked(listOperations).mockResolvedValue({
      rows: [{ name: "OP-1", operation_name: "Pruning", category: "Field Care", work_uom: "Nos", default_rate: 25, is_harvest: 0 }],
    });
    vi.mocked(saveOperation).mockResolvedValue({ name: "OP-1" });
    renderPage(<Settings />);
    const input = (await screen.findByDisplayValue("Pruning")) as HTMLInputElement;
    const save = screen.getByRole("button", { name: "Save Pruning" });
    expect(save).toBeDisabled();
    fireEvent.change(input, { target: { value: "Pruning heavy" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Pruning heavy" }));
    await waitFor(() => expect(saveOperation).toHaveBeenCalled());
    expect(vi.mocked(saveOperation).mock.calls[0][0]).toMatchObject({ name: "OP-1", operation_name: "Pruning heavy", default_rate: 25 });
  });

  it("is read-only for non-managers", async () => {
    vi.mocked(listOperations).mockResolvedValue({
      rows: [{ name: "OP-1", operation_name: "Pruning", category: "Field Care", work_uom: "Nos", default_rate: 25, is_harvest: 1 }],
    });
    renderPage(<Settings />, { can_manage: false });
    expect(await screen.findByText("Pruning")).toBeInTheDocument();
    expect(screen.getByText(/read these settings but not change/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Add operation/ })).toBeNull();
    expect(screen.getByText("KES 25")).toBeInTheDocument();
  });
});

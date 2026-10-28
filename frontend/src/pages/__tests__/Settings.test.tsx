import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/api", () => ({ listOperations: vi.fn(), saveOperation: vi.fn(), listProtocols: vi.fn() }));
vi.mock("@/lib/varieties-api", () => ({
  listVarieties: vi.fn(),
  listRules: vi.fn(),
  saveVariety: vi.fn(),
  saveRule: vi.fn(),
  setRuleEnabled: vi.fn(),
  RULE_TYPES: ["Not in stage", "Only in stage", "Not within days before harvest", "Not within days after operation"],
}));
vi.mock("@/lib/protocols-api", () => ({
  listProtocolFamilies: vi.fn(),
  newVersion: vi.fn(),
  submitForApproval: vi.fn(),
  approveProtocol: vi.fn(),
  sendBackProtocol: vi.fn(),
  saveProtocolDraft: vi.fn(),
}));
import { listOperations, listProtocols, saveOperation } from "@/lib/api";
import { listRules, listVarieties } from "@/lib/varieties-api";
import {
  approveProtocol,
  listProtocolFamilies,
  newVersion,
  submitForApproval,
  type ProtocolFamily,
  type ProtocolVersion,
} from "@/lib/protocols-api";
import { Settings } from "@/pages/Settings";

describe("Settings", () => {
  beforeEach(() => {
    vi.mocked(listProtocolFamilies).mockResolvedValue({ families: [] });
    vi.mocked(listProtocols).mockResolvedValue({ rows: [] });
    vi.mocked(listVarieties).mockResolvedValue({ varieties: [] });
    vi.mocked(listRules).mockResolvedValue({ rules: [] });
    vi.mocked(saveOperation).mockReset();
  });

  it("shows an empty state", async () => {
    vi.mocked(listOperations).mockResolvedValue({ rows: [] });
    renderPage(<Settings />);
    expect(await screen.findByText(/No operations defined/i)).toBeInTheDocument();
  });

  it("edits and saves one row for a manager", async () => {
    vi.mocked(listOperations).mockResolvedValue({
      rows: [{ name: "OP-1", operation_name: "Pruning", category: "Spraying", work_uom: "Nos", default_rate: 25, is_harvest: 0 }],
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
      rows: [{ name: "OP-1", operation_name: "Pruning", category: "Spraying", work_uom: "Nos", default_rate: 25, is_harvest: 1 }],
    });
    renderPage(<Settings />, { can_manage: false });
    expect(await screen.findByText("Pruning")).toBeInTheDocument();
    expect(screen.getByText(/read these settings but not change/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Add operation/ })).toBeNull();
    expect(screen.getAllByText("KES 25").length).toBeGreaterThan(0);
  });

  const ver = (n: number, status: ProtocolVersion["version_status"], over: Partial<ProtocolVersion> = {}): ProtocolVersion => ({
    name: n === 1 ? "Season" : `Season v${n}`, protocol_name: n === 1 ? "Season" : `Season v${n}`, crop: "Test Crop", item: null,
    version: n, version_status: status, protocol_family: "Season", previous_version: n > 1 ? "Season" : null,
    submitted_by: null, submitted_at: null, approved_by: null, approved_at: null, review_note: null,
    steps: [{ operation: "OP-1", day_offset: 3, repeat_every_days: 0, repeat_count: 1, planned_qty: 10, note: null }],
    ...over,
  });
  const family = (versions: ProtocolVersion[]): ProtocolFamily => ({
    family: "Season", label: "Season", crop: "Test Crop", item: null,
    active: versions.find((v) => v.version_status === "Active")?.name ?? null,
    has_pending: versions.some((v) => v.version_status === "Pending Approval"), versions,
  });
  const openProtocols = async () => {
    vi.mocked(listOperations).mockResolvedValue({ rows: [] });
    renderPage(<Settings />);
    fireEvent.mouseDown(await screen.findByRole("tab", { name: "Protocols" }), { button: 0 });
    fireEvent.click(await screen.findByRole("button", { name: /Season/ }));
  };

  it("offers New version on the active protocol and calls it", async () => {
    vi.mocked(listProtocolFamilies).mockResolvedValue({ families: [family([ver(1, "Active")])] });
    vi.mocked(newVersion).mockResolvedValue({ name: "Season v2", version: 2 });
    await openProtocols();
    expect(screen.getByTestId("status-chip")).toHaveTextContent("Active");
    expect(screen.queryByRole("button", { name: /Submit/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "New version of Season" }));
    await waitFor(() => expect(newVersion).toHaveBeenCalledWith("Season"));
  });

  it("edits only drafts and submits them for approval", async () => {
    vi.mocked(listProtocolFamilies).mockResolvedValue({
      families: [family([ver(2, "Draft", { review_note: "Keep the last pass" }), ver(1, "Active")])],
    });
    vi.mocked(submitForApproval).mockResolvedValue({ name: "Season v2" });
    await openProtocols();
    expect(screen.getByText(/Keep the last pass/)).toBeInTheDocument();
    expect(screen.getAllByLabelText(/Planned qty for/).length).toBe(1); // the Draft, not the Active
    fireEvent.click(screen.getByRole("button", { name: "Submit Season v2 for approval" }));
    await waitFor(() => expect(submitForApproval).toHaveBeenCalledWith("Season v2"));
  });

  it("shows manager actions on a pending version, hidden for non-managers", async () => {
    vi.mocked(listProtocolFamilies).mockResolvedValue({ families: [family([ver(2, "Pending Approval"), ver(1, "Active")])] });
    vi.mocked(approveProtocol).mockResolvedValue({ name: "Season v2" });
    await openProtocols();
    fireEvent.click(screen.getByRole("button", { name: "Approve Season v2" }));
    await waitFor(() => expect(approveProtocol).toHaveBeenCalledWith("Season v2"));
  });

  it("hides approve for non-managers", async () => {
    vi.mocked(listProtocolFamilies).mockResolvedValue({ families: [family([ver(2, "Pending Approval"), ver(1, "Active")])] });
    vi.mocked(listOperations).mockResolvedValue({ rows: [] });
    renderPage(<Settings />, { can_manage: false });
    fireEvent.mouseDown(await screen.findByRole("tab", { name: "Protocols" }), { button: 0 });
    fireEvent.click(await screen.findByRole("button", { name: /Season/ }));
    expect(screen.queryByRole("button", { name: /Approve/ })).toBeNull();
  });
});

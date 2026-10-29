import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/api", () => ({ listOperations: vi.fn(), saveOperation: vi.fn(), listProtocols: vi.fn() }));
vi.mock("@/lib/varieties-api", async (orig) => ({
  ...(await orig<typeof import("@/lib/varieties-api")>()),
  listVarieties: vi.fn(),
  listRules: vi.fn(),
  saveVariety: vi.fn(),
  saveRule: vi.fn(),
  setRuleEnabled: vi.fn(),
  RULE_TYPES: ["Not in stage", "Only in stage", "Not within days before harvest", "Not within days after operation"],
}));
vi.mock("@/components/cycles/ItemField", () => ({
  ItemField: ({ id, value, onChange }: { id?: string; value: string; onChange: (v: string) => void }) => (
    <input id={id} aria-label={id} value={value} onChange={(e) => onChange(e.target.value)} />
  ),
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
import { listRules, listVarieties, saveVariety, type Variety } from "@/lib/varieties-api";
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
    key_activities: [{ operation: "OP-1", week: 3, repeats: "Every cycle", planned_qty: 10, description: null }],
    cultural_activities: [], capital_activities: [],
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

  it("saves an activity colour and type", async () => {
    vi.mocked(listOperations).mockResolvedValue({
      rows: [{ name: "OP-1", operation_name: "Pruning", category: "Pruning", work_uom: "Nos", default_rate: 25, is_harvest: 0, activity_type: "Cultural", color: "" }],
    });
    vi.mocked(saveOperation).mockResolvedValue({ name: "OP-1" });
    renderPage(<Settings />);
    expect(await screen.findByRole("tab", { name: "Activities & rates" })).toBeInTheDocument();
    await screen.findByDisplayValue("Pruning");
    fireEvent.change(screen.getByLabelText("Activity colour"), { target: { value: "#ff0000" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Pruning" }));
    await waitFor(() => expect(saveOperation).toHaveBeenCalled());
    expect(vi.mocked(saveOperation).mock.calls[0][0]).toMatchObject({ name: "OP-1", color: "#ff0000", activity_type: "Cultural" });
  });

  const hass: Variety = {
    name: "Hass", variety_name: "Hass", crop: "Test Crop", product: null, item: "Avocado - Hass", enabled: 1,
    stage_anchor: "Planting", default_protocol: null, days_to_first_harvest: null, harvest_window_days: null,
    expected_yield_per_ha: null, expected_yield_per_plant: null, plants_per_ha: null, stages: [],
  };
  const openVariety = async (over: Partial<Variety> = {}) => {
    vi.mocked(listOperations).mockResolvedValue({ rows: [] });
    vi.mocked(listVarieties).mockResolvedValue({ varieties: [{ ...hass, ...over }] });
    renderPage(<Settings />);
    fireEvent.mouseDown(await screen.findByRole("tab", { name: "Varieties" }), { button: 0 });
    fireEvent.click(await screen.findByRole("button", { name: "Edit Hass" }));
    await screen.findByLabelText("Lifespan (years)");
  };

  it("shows flowering fields only when flowering", async () => {
    await openVariety();
    expect(screen.queryByLabelText("Weeks to first flowering")).toBeNull();
    expect(screen.queryByLabelText("Weeks from flowering to harvest")).toBeNull();
    fireEvent.click(screen.getByRole("switch", { name: "Flowering crop" }));
    expect(screen.getByLabelText("Weeks to first flowering")).toBeInTheDocument();
    expect(screen.getByLabelText("Weeks from flowering to harvest")).toBeInTheDocument();
  });

  it("seasonal shows seasons table and hides interval", async () => {
    await openVariety({ is_flowering: 1, flowering_pattern: "Seasonal", flowering_seasons: [{ season_name: "Main", start_month: "August", weeks_flowering_to_harvest: 36, crop_share_pct: 80 }] });
    expect(screen.getByTestId("seasons-editor")).toBeInTheDocument();
    expect(screen.getByLabelText("Season 1 name")).toHaveValue("Main");
    expect(screen.queryByLabelText("Weeks between flowerings")).toBeNull();
    expect(screen.queryByLabelText("Weeks to first flowering")).toBeNull();
    expect(screen.queryByLabelText("Weeks to re-flower after harvest")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Add season" }));
    expect(screen.getByLabelText("Season 2 name")).toBeInTheDocument();
  });

  it("interval shows interval weeks", async () => {
    await openVariety({ is_flowering: 1, flowering_pattern: "Interval", flowering_interval_weeks: 4 });
    expect(screen.getByLabelText("Weeks between flowerings")).toHaveValue("4");
    expect(screen.getByLabelText("Weeks to first flowering")).toBeInTheDocument();
    expect(screen.queryByTestId("seasons-editor")).toBeNull();
  });

  it("season shares total warning", async () => {
    await openVariety({
      is_flowering: 1, flowering_pattern: "Seasonal",
      flowering_seasons: [
        { season_name: "Main", start_month: "August", weeks_flowering_to_harvest: 36, crop_share_pct: 80 },
        { season_name: "Off", start_month: "February", weeks_flowering_to_harvest: 36, crop_share_pct: 10 },
      ],
    });
    expect(screen.getByTestId("season-total")).toHaveTextContent("Shares total 90%");
    expect(screen.getByRole("button", { name: "Save variety" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Season 2 crop share %"), { target: { value: "20" } });
    expect(screen.getByTestId("season-total")).toHaveTextContent("Shares total 100%");
    expect(screen.getByRole("button", { name: "Save variety" })).toBeEnabled();
  });

  it("saves maturity and seasons", async () => {
    vi.mocked(saveVariety).mockResolvedValue({ name: "Hass" });
    await openVariety({ is_flowering: 1, flowering_pattern: "Seasonal", weeks_to_maturity: 130, flowering_seasons: [{ season_name: "Main", start_month: "August", weeks_flowering_to_harvest: 36, crop_share_pct: 100 }] });
    fireEvent.click(screen.getByRole("button", { name: "Save variety" }));
    await waitFor(() => expect(saveVariety).toHaveBeenCalled());
    expect(vi.mocked(saveVariety).mock.calls[0][0]).toMatchObject({
      weeks_to_maturity: 130, flowering_pattern: "Seasonal", flowering_interval_weeks: null,
      flowering_seasons: [{ season_name: "Main", start_month: "August", weeks_flowering_to_harvest: 36, crop_share_pct: 100 }],
    });
  });

  it("computes weeks to first harvest for flowering", async () => {
    vi.mocked(saveVariety).mockResolvedValue({ name: "Hass" });
    await openVariety({ is_flowering: 1, flowering_interval_weeks: 4, weeks_to_first_flowering: 20, weeks_flowering_to_harvest: 30 });
    const first = screen.getByLabelText("Weeks to first harvest") as HTMLInputElement;
    expect(first).toHaveValue("50");
    expect(first.readOnly).toBe(true);
    fireEvent.change(screen.getByLabelText("Weeks to first flowering"), { target: { value: "24" } });
    expect(first).toHaveValue("54");
    fireEvent.click(screen.getByRole("button", { name: "Save variety" }));
    await waitFor(() => expect(saveVariety).toHaveBeenCalled());
    expect(vi.mocked(saveVariety).mock.calls.at(-1)![0]).toMatchObject({ is_flowering: 1, weeks_to_first_harvest: 54 });
  });
});

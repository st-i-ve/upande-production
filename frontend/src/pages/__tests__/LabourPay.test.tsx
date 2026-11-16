import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/labourpay-api", async (orig) => ({
  ...(await orig<typeof import("@/lib/labourpay-api")>()),
  labourModeStatus: vi.fn(),
  getLabourSettings: vi.fn(),
  saveLabourSettings: vi.fn(),
  listRates: vi.fn(),
  saveRate: vi.fn(),
  deleteRate: vi.fn(),
}));
import * as pay from "@/lib/labourpay-api";
import { LabourPayPanel } from "@/components/settings/LabourPayPanel";
import { OperationsTable } from "@/components/settings/OperationsTable";

const settings: pay.LabourSettings = {
  labour_mode: "Automatic", pay_period: "Weekly", pay_week_starts_on: "Monday", pay_day: "Friday", daily_wage: 600,
  duplicate_rule: "Block", multiple_jobs_per_day: "Warn", attendance_required: 0, attendance_source: "Production",
  max_backdate_days: 7, pay_reference_prefix: "MP-",
  options: {
    labour_mode: ["Automatic", "Built-in only"], pay_period: ["Weekly", "Fortnightly", "Monthly"],
    pay_week_starts_on: ["Monday", "Tuesday"], pay_day: ["Friday", "Saturday"], duplicate_rule: ["Block", "Warn", "Off"],
    multiple_jobs_per_day: ["Allow", "Warn", "Block"], attendance_source: ["Production", "HRMS Attendance", "Both"],
  },
};

beforeEach(() => {
  vi.mocked(pay.labourModeStatus).mockResolvedValue({ mode: "Automatic", wm_installed: false, wm_active: false });
  vi.mocked(pay.getLabourSettings).mockResolvedValue(settings);
  vi.mocked(pay.saveLabourSettings).mockReset();
  vi.mocked(pay.listRates).mockResolvedValue({
    rates: [{ name: "R1", operation: "OP-1", operation_name: "Pruning", valid_from: "2026-10-01", valid_to: null, rate: 25, daily_target: null, uom: "Tree", note: "Peak" }],
  });
  vi.mocked(pay.saveRate).mockReset();
  vi.mocked(pay.deleteRate).mockReset();
});

describe("LabourPayPanel", () => {
  it("says Work Management is not installed", async () => {
    renderPage(<LabourPayPanel canEdit canSeePay />);
    expect(await screen.findByText(/not installed — production handles pay on its own/)).toBeInTheDocument();
  });

  it.each([
    [{ mode: "Automatic", wm_installed: true, wm_active: true }, /installed — labour runs through it/],
    [{ mode: "Built-in only", wm_installed: true, wm_active: false }, /installed but switched off \(Built-in only\)/],
  ] as const)("describes %j", async (status, text) => {
    vi.mocked(pay.labourModeStatus).mockResolvedValue({ ...status });
    renderPage(<LabourPayPanel canEdit canSeePay />);
    expect(await screen.findByText(text)).toBeInTheDocument();
  });

  it("saves changed values and drops the wage for people who cannot see pay", async () => {
    vi.mocked(pay.saveLabourSettings).mockResolvedValue({ ...settings, max_backdate_days: 3 });
    renderPage(<LabourPayPanel canEdit canSeePay />);
    const days = (await screen.findByLabelText("Backdating limit (days)")) as HTMLInputElement;
    const save = screen.getByRole("button", { name: "Save labour settings" });
    expect(save).toBeDisabled();
    fireEvent.change(days, { target: { value: "3" } });
    fireEvent.click(save);
    await waitFor(() => expect(pay.saveLabourSettings).toHaveBeenCalled());
    expect(vi.mocked(pay.saveLabourSettings).mock.calls[0][0]).toMatchObject({ max_backdate_days: 3, daily_wage: 600, attendance_required: 0 });
  });

  it("is read-only for people who cannot manage", async () => {
    renderPage(<LabourPayPanel canEdit={false} canSeePay />);
    expect(await screen.findByLabelText("Backdating limit (days)")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save labour settings" })).not.toBeInTheDocument();
  });
});

describe("Rate periods", () => {
  const rows = [{ name: "OP-1", operation_name: "Pruning", category: "Pruning", work_uom: "Tree", default_rate: 20, is_harvest: 0 }];

  it("opens an operation's periods and adds one", async () => {
    vi.mocked(pay.saveRate).mockResolvedValue({} as never);
    renderPage(<OperationsTable crop="Test Crop" rows={rows} canEdit canSeePay onSaved={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Rate periods for Pruning" }));
    expect(await screen.findByText("Peak")).toBeInTheDocument();
    expect(pay.listRates).toHaveBeenCalledWith("OP-1");
    fireEvent.click(screen.getByRole("button", { name: /Add rate period/ }));
    fireEvent.change(screen.getByLabelText(/Rate per Tree/), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Save period" }));
    await waitFor(() => expect(pay.saveRate).toHaveBeenCalled());
    expect(vi.mocked(pay.saveRate).mock.calls[0][0]).toMatchObject({ operation: "OP-1", rate: 30, valid_to: null });
  });

  it("explains rate = daily wage ÷ target when the rate is blank", async () => {
    renderPage(<OperationsTable crop="Test Crop" rows={rows} canEdit canSeePay onSaved={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Rate periods for Pruning" }));
    fireEvent.click(await screen.findByRole("button", { name: /Add rate period/ }));
    fireEvent.change(screen.getByLabelText(/Daily target \(Tree/), { target: { value: "50" } });
    expect(await screen.findByTestId("rate-hint")).toHaveTextContent(/daily wage ÷ the daily target = .*12/);
  });

  it("has no rate periods button without pay access", () => {
    renderPage(<OperationsTable crop="Test Crop" rows={rows} canEdit canSeePay={false} onSaved={() => {}} />, { can_see_pay: false });
    expect(screen.queryByRole("button", { name: /Rate periods/ })).not.toBeInTheDocument();
  });
});

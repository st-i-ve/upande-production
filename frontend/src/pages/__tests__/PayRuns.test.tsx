import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/labourpay-api", async (orig) => ({
  ...(await orig<typeof import("@/lib/labourpay-api")>()),
  labourModeStatus: vi.fn(),
  listPayRuns: vi.fn(),
  newPayRun: vi.fn(),
  payRunDetail: vi.fn(),
  approvePayRun: vi.fn(),
  markPayRunPaid: vi.fn(),
  refreshPayRun: vi.fn(),
  cancelPayRun: vi.fn(),
  payRunCsv: vi.fn(),
  downloadCsv: vi.fn(),
}));
import * as pay from "@/lib/labourpay-api";
import { PayRuns } from "@/pages/PayRuns";

const summary = (name: string, status: pay.PayRunStatus): pay.PayRunSummary => ({
  name, company: "Mutara", farm: null, from_date: "2026-11-02", to_date: "2026-11-08", status, docstatus: status === "Draft" ? 0 : 1,
  total_people: 2, total_amount: 5400, payment_reference: null, paid_on: null,
});
const detail = (name: string, status: pay.PayRunStatus): pay.PayRunDetail => ({
  ...summary(name, status),
  lines: [
    { employee: "E1", employee_name: "Jane Wanjiru", days: 3, entries: 4, qty: 120, amount: 3000, work: ["W1"] },
    { employee: "E2", employee_name: "Peter Otieno", days: 2, entries: 2, qty: 80, amount: 2400, work: ["W2"] },
  ],
});

beforeEach(() => {
  vi.mocked(pay.labourModeStatus).mockResolvedValue({ mode: "Automatic", wm_installed: false, wm_active: false });
  vi.mocked(pay.listPayRuns).mockReset();
  vi.mocked(pay.listPayRuns).mockResolvedValue({
    runs: [summary("PR-1", "Draft"), summary("PR-2", "Approved"), summary("PR-3", "Paid")],
    default_period: { from_date: "2026-11-09", to_date: "2026-11-15" },
    pay_day: "Friday",
  });
  vi.mocked(pay.payRunDetail).mockImplementation(async (n) => detail(n, n === "PR-1" ? "Draft" : "Approved"));
  for (const f of [pay.approvePayRun, pay.markPayRunPaid, pay.refreshPayRun, pay.cancelPayRun, pay.newPayRun, pay.payRunCsv, pay.downloadCsv]) (f as unknown as ReturnType<typeof vi.fn>).mockReset();
});

describe("PayRuns", () => {
  it("lists runs with status chips and totals", async () => {
    renderPage(<PayRuns />);
    expect(await screen.findByText("PR-1")).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Paid")).toBeInTheDocument();
    expect(screen.getAllByText(/5,400/).length).toBeGreaterThan(0);
  });

  it("hides money and the list from people who cannot see pay", async () => {
    renderPage(<PayRuns />, { can_see_pay: false });
    expect(await screen.findByText(/only shown to people who can see pay/)).toBeInTheDocument();
    expect(pay.listPayRuns).not.toHaveBeenCalled();
  });

  it("starts a run for the default period and opens it", async () => {
    vi.mocked(pay.newPayRun).mockResolvedValue(detail("PR-9", "Draft"));
    renderPage(<PayRuns />);
    fireEvent.click(await screen.findByRole("button", { name: /New pay run/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Start pay run" }));
    await waitFor(() => expect(pay.newPayRun).toHaveBeenCalledWith("2026-11-09", "2026-11-15", undefined));
    expect(await screen.findByText("Jane Wanjiru")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  it("offers refresh, approve and delete on a draft, and approves it", async () => {
    vi.mocked(pay.approvePayRun).mockResolvedValue(detail("PR-1", "Approved"));
    renderPage(<PayRuns />);
    fireEvent.click(await screen.findByText("PR-1"));
    expect(await screen.findByRole("button", { name: "Refresh" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(pay.approvePayRun).toHaveBeenCalledWith("PR-1"));
    expect(await screen.findByRole("button", { name: "Mark paid" })).toBeInTheDocument();
  });

  it("marks an approved run paid with a reference", async () => {
    vi.mocked(pay.markPayRunPaid).mockResolvedValue({ ...detail("PR-2", "Paid"), payment_reference: "MP-77" });
    renderPage(<PayRuns />);
    fireEvent.click(await screen.findByText("PR-2"));
    fireEvent.click(await screen.findByRole("button", { name: "Mark paid" }));
    fireEvent.change(screen.getByLabelText("Payment reference"), { target: { value: "MP-77" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm paid" }));
    await waitFor(() => expect(pay.markPayRunPaid).toHaveBeenCalledWith("PR-2", "MP-77", expect.any(String)));
  });

  it("downloads the CSV", async () => {
    vi.mocked(pay.payRunCsv).mockResolvedValue({ filename: "PR-2.csv", csv: "a,b" });
    renderPage(<PayRuns />);
    fireEvent.click(await screen.findByText("PR-2"));
    fireEvent.click(await screen.findByRole("button", { name: /Download CSV/ }));
    await waitFor(() => expect(pay.downloadCsv).toHaveBeenCalledWith("PR-2.csv", "a,b"));
  });

  it("shows a Work Management banner and no create or approve actions when WM is active", async () => {
    vi.mocked(pay.labourModeStatus).mockResolvedValue({ mode: "Automatic", wm_installed: true, wm_active: true });
    renderPage(<PayRuns />);
    expect(await screen.findByText(/Pay is handled in Work Management/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Work Payment/ })).toHaveAttribute("href", "/work-payment");
    expect(screen.queryByRole("button", { name: /New pay run/ })).not.toBeInTheDocument();
    fireEvent.click(await screen.findByText("PR-1"));
    await screen.findByText("Jane Wanjiru");
    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Download CSV/ })).toBeInTheDocument();
  });
});

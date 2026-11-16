import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/labourers-api", () => ({ listLabourers: vi.fn() }));
vi.mock("@/lib/labourpay-api", async (orig) => ({
  ...(await orig<typeof import("@/lib/labourpay-api")>()),
  labourModeStatus: vi.fn(),
  getLabourSettings: vi.fn(),
  attendanceDay: vi.fn(),
  markAttendance: vi.fn(),
}));
import * as lab from "@/lib/labourers-api";
import * as pay from "@/lib/labourpay-api";
import { Attendance } from "@/pages/Attendance";

const person = (employee: string, employee_name: string) => ({ name: employee, employee, employee_name, crew: "Crew A" }) as never;

beforeEach(() => {
  vi.mocked(lab.listLabourers).mockResolvedValue({ rows: [person("E1", "Jane Wanjiru"), person("E2", "Peter Otieno"), person("E3", "Achieng Awino")], days: [], totals: {} } as never);
  vi.mocked(pay.labourModeStatus).mockResolvedValue({ mode: "Automatic", wm_installed: false, wm_active: false });
  vi.mocked(pay.getLabourSettings).mockResolvedValue({ attendance_required: 1, attendance_source: "Production", options: {} } as never);
  vi.mocked(pay.attendanceDay).mockResolvedValue({ date: "2026-11-16", rows: [{ name: "A1", employee: "E3", employee_name: "Achieng Awino", status: "Absent", farm: null, note: null }] });
  vi.mocked(pay.markAttendance).mockReset().mockImplementation(async (employees) => ({ marked: employees.length, names: [] }));
});

describe("Attendance", () => {
  it("lists the roster with saved statuses and says attendance is required", async () => {
    renderPage(<Attendance />);
    expect(await screen.findByText("Jane Wanjiru")).toBeInTheDocument();
    expect(await screen.findByText(/Attendance is required/)).toBeInTheDocument();
    const row = within(screen.getByTestId("att-E3"));
    expect(row.getByRole("radio", { name: "Absent" })).toHaveAttribute("aria-checked", "true");
  });

  it("marks everyone present, changes one person, and saves grouped by status", async () => {
    renderPage(<Attendance />);
    await screen.findByText("Jane Wanjiru");
    fireEvent.click(screen.getByRole("button", { name: /Mark all present/ }));
    fireEvent.click(within(screen.getByTestId("att-E2")).getByRole("radio", { name: "On Leave" }));
    fireEvent.click(screen.getByRole("button", { name: /Save attendance \(3\)/ }));
    await waitFor(() => expect(pay.markAttendance).toHaveBeenCalledTimes(2));
    const calls = vi.mocked(pay.markAttendance).mock.calls.map((c) => [c[2], [...c[0]].sort()]);
    expect(calls).toContainEqual(["Present", ["E1", "E3"]]);
    expect(calls).toContainEqual(["On Leave", ["E2"]]);
  });

  it("points to the Work Assigner when Work Management is active", async () => {
    vi.mocked(pay.labourModeStatus).mockResolvedValue({ mode: "Automatic", wm_installed: true, wm_active: true });
    renderPage(<Attendance />);
    const link = await screen.findByRole("link", { name: /Work Assigner/ });
    expect(link).toHaveAttribute("href", "/work-assigner");
  });
});

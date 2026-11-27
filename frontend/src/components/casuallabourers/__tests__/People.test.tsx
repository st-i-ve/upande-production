import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastProvider } from "@/components/Toast";
import type { Boot, Crop } from "@/lib/api";

vi.mock("@/lib/api", () => ({ listOperations: vi.fn().mockResolvedValue({ rows: [] }) }));
vi.mock("@/lib/people-api", () => ({ supervisorPeople: vi.fn(), labourerPeople: vi.fn() }));
vi.mock("@/lib/labourers-api", () => ({
  getSupervisorOptions: vi.fn().mockResolvedValue([]),
  getLabourerDetail: vi.fn(),
  candidateEmployees: vi.fn(),
  addLabourers: vi.fn(),
  saveLabourer: vi.fn(),
  removeLabourer: vi.fn(),
}));
vi.mock("@/lib/frappe", async (orig) => ({ ...(await orig<typeof import("@/lib/frappe")>()), searchLink: vi.fn().mockResolvedValue([]) }));

import { listOperations } from "@/lib/api";
import * as lab from "@/lib/labourers-api";
import * as people from "@/lib/people-api";
import { CropProvider } from "@/lib/crops";
import { CasualLabourers } from "@/pages/CasualLabourers";

const crop: Crop = {
  name: "Avocado", crop_key: "avocado", accent_color: "#3f8f4f", icon_key: "avocado", unit_label: "Block",
  parent_unit_label: "Pivot", sub_unit_label: "Block", yield_uom: "kg",
};
const boot: Boot = { crops: [crop], farms: ["Mutara"], can_see_pay: true, can_plan: true, can_manage: true };
const person = (o: Partial<people.LabourerPerson> & { employee: string; employee_name: string }): people.LabourerPerson => ({
  image: null, active: true, supervisor: "S1", supervisor_name: "Grace W", crew: "Pruning A", last_worked: "2026-11-25", output_uom: "Tree",
  metrics: { days_worked: 5, tasks: 4, entries: 6, output_per_day: 48, output_vs_peers: 120, sent_back: 1, sent_back_pct: 16.7, attendance_pct: 25 },
  scores: { attendance: 25, output: 60, quality: 83.3 },
  flags: [{ kind: "sent_back", label: "Sent-back work not fixed", count: 1, detail: "1 entries sent back and still waiting for a correction." }],
  where_blocks: [{ key: "B1", label: "Block 1", count: 6, share: 100 }],
  where_activities: [{ key: "OP", label: "Pruning", count: 6, share: 100 }],
  weekly: [{ week: "2026-11-02", days: 2, output: 90 }],
  ...o,
});
const renderIt = () =>
  render(
    <TooltipProvider>
      <ToastProvider>
        <CropProvider crop={crop} boot={boot}>
          <CasualLabourers />
        </CropProvider>
      </ToastProvider>
    </TooltipProvider>,
  );

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(listOperations).mockResolvedValue({ rows: [] } as never);
  vi.mocked(lab.getSupervisorOptions).mockResolvedValue([]);
  vi.mocked(people.labourerPeople).mockResolvedValue({
    from: "2026-11-02", to: "2026-11-27", weeks: ["2026-11-02"], workdays: 20,
    medians: { days_worked: 4, tasks: 3, output_vs_peers: 100, sent_back_pct: 5, attendance_pct: 20, attendance: 20, output: 50, quality: 95 },
    people: [
      person({ employee: "E1", employee_name: "Jane Wanjiru" }),
      person({ employee: "E2", employee_name: "Peter Otieno", active: false, last_worked: null, flags: [] }),
      person({ employee: "E5", employee_name: "Mary Njeri", supervisor: "S2", flags: [] }),
    ],
  });
  vi.mocked(lab.candidateEmployees).mockResolvedValue({
    people: [
      { name: "E3", employee_name: "Achieng Awino", department: null, designation: "Casual Labourer", image: null },
      { name: "E4", employee_name: "Barasa Wekesa", department: null, designation: "Casual Labourer", image: null },
    ],
    departments: [],
    designations: ["Casual Labourer"],
  });
  vi.mocked(lab.addLabourers).mockResolvedValue({ added: ["E3", "E4"], skipped: [] });
});

describe("Casual labourers page", () => {
  it("lists active labourers and opens the first record against the farm median, with no pay or hours", async () => {
    renderIt();
    const record = await screen.findByTestId("labourer-record");
    const row = screen.getByTestId("person-E1");
    expect(within(row).getByText("Jane Wanjiru")).toBeTruthy();
    expect(within(row).getByText(/Grace W · last worked/)).toBeTruthy();
    expect(screen.queryByTestId("person-E2")).toBeNull(); // inactive hidden by default
    const table = within(record).getByRole("table", { name: "Against the farm median" });
    expect(within(table).getByText("Days worked")).toBeTruthy();
    expect(within(record).getByText("Sent-back work not fixed")).toBeTruthy();
    expect(within(record).getByText("Pruning")).toBeTruthy();
    expect(within(record).getByText("Block 1")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/KES|unpaid|hours/i);
  });

  it("filters by supervisor id, built from the roster", async () => {
    vi.mocked(people.labourerPeople).mockResolvedValue({
      from: "2026-11-02", to: "2026-11-27", weeks: [], workdays: 20, medians: {},
      people: [
        person({ employee: "E1", employee_name: "Jane Wanjiru" }),
        person({ employee: "E5", employee_name: "Mary Njeri", supervisor: "S2", flags: [] }),
        person({ employee: "E6", employee_name: "Paul Mwangi", supervisor: "S3", supervisor_name: "Otto K", flags: [] }),
      ],
    });
    renderIt();
    await screen.findByTestId("labourer-record");
    fireEvent.click(await screen.findByRole("combobox", { name: /Supervisor/ }));
    fireEvent.click(await screen.findByRole("option", { name: "Grace W (S1)" }));
    await waitFor(() => expect(screen.queryByTestId("person-E5")).toBeNull());
    expect(screen.getByTestId("person-E1")).toBeTruthy();
    expect(screen.queryByTestId("person-E6")).toBeNull();
  });

  it("compares labourers", async () => {
    renderIt();
    await screen.findByTestId("labourer-record");
    fireEvent.click(screen.getByRole("button", { name: /Compare/ }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: /Mary Njeri/ }));
    expect(within(dialog).getByRole("table", { name: "Comparison figures" }).textContent).toContain("Mary Njeri");
  });

  it("opens Manage for targets and the roster settings", async () => {
    vi.mocked(lab.getLabourerDetail).mockResolvedValue({ error: "x" });
    renderIt();
    await screen.findByTestId("labourer-record");
    fireEvent.click(screen.getByRole("button", { name: /Manage/ }));
    await waitFor(() => expect(lab.getLabourerDetail).toHaveBeenCalledWith("Avocado", "E1", expect.any(String), expect.any(String)));
  });

  it("adds several employees at once", async () => {
    renderIt();
    await screen.findByTestId("labourer-record");
    fireEvent.click(screen.getByRole("button", { name: /Add labourers/ }));
    const dialog = await screen.findByRole("dialog");
    await within(dialog).findByText("Achieng Awino");
    fireEvent.click(within(dialog).getByLabelText("Select all shown"));
    fireEvent.click(within(dialog).getByRole("button", { name: /Add 2 to roster/ }));
    await waitFor(() => expect(lab.addLabourers).toHaveBeenCalledWith(["E3", "E4"], null, null));
  });
});

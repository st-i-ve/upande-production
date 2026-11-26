import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "@/components/Toast";
import type { SupervisorPlan } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  getSupervisorPlan: vi.fn(),
  getSupervisorOptions: vi.fn(),
  saveSupervisorPlan: vi.fn(),
  copySupervisorPlan: vi.fn(),
}));

import * as api from "@/lib/api";
import { SupervisorPlanView } from "@/components/plan/SupervisorPlanView";

const mocked = vi.mocked(api);

const plan = (over: Partial<SupervisorPlan> = {}): SupervisorPlan => ({
  week_start: "2026-11-23",
  week_end: "2026-11-29",
  can_edit: true,
  units: [{ name: "B1", unit_name: "B1", area_ha: 2, farm: "F" }],
  supervisors: [
    { name: "S1", employee_name: "Grace W", user: null, status: "Active" },
    { name: "S2", employee_name: "Otto K", user: null, status: "Inactive" },
  ],
  assignments: [{ name: "A1", unit: "B1", category: "", supervisor: "S2", supervisor_name: "Otto K" }],
  last_week: [],
  last_week_label: { year: 2026, week: 47 },
  warnings: [],
  ...over,
} as unknown as SupervisorPlan);

function setup() {
  return render(
    <ToastProvider>
      <SupervisorPlanView crop="Avocado" farm="F" year={2026} week={48} unitLabel="Block" canEdit />
    </ToastProvider>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  mocked.getSupervisorPlan.mockResolvedValue(plan());
  mocked.getSupervisorOptions.mockResolvedValue([{ name: "S1", employee_name: "Grace W", user: null, status: "Active" }]);
});

describe("SupervisorPlanView", () => {
  it("marks an assigned supervisor who is no longer active", async () => {
    setup();
    expect(await screen.findByText("Otto K (inactive)")).toBeInTheDocument();
  });

  it("refuses to save an activity with no category instead of dropping it", async () => {
    setup();
    await screen.findByText("Otto K (inactive)");
    fireEvent.click(screen.getByRole("button", { name: /Add activity for B1/ }));
    fireEvent.click(screen.getByLabelText(/Supervisor 1 of activity 1 for B1/));
    fireEvent.click(await screen.findByRole("option", { name: "Grace W" }));
    fireEvent.click(screen.getByRole("button", { name: /^Save$/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/Choose an activity/);
    await waitFor(() => expect(mocked.saveSupervisorPlan).not.toHaveBeenCalled());
  });
});

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProtocolsList, outOfOrder, type OpOption, type ProtocolActions } from "@/components/settings/ProtocolsList";
import type { ProtocolFamily, ProtocolVersion } from "@/lib/protocols-api";

const operations: OpOption[] = [
  { value: "OP-CAP", label: "Land clearing", type: "Capital" },
  { value: "OP-DRIP", label: "Drip lines", type: "Capital" },
  { value: "OP-SPRAY", label: "Spraying", type: "Cultural" },
  { value: "OP-PRUNE", label: "Pruning", type: "Key activity" },
];

const version = (over: Partial<ProtocolVersion> = {}): ProtocolVersion => ({
  name: "Season v2", protocol_name: "Season v2", crop: "Avocado", item: null, version: 2, version_status: "Draft",
  protocol_family: "Season", previous_version: "Season", submitted_by: null, submitted_at: null, approved_by: null,
  approved_at: null, review_note: null,
  harvest_pattern: "Interval", harvest_interval_weeks: 8, is_flowering: 1, weeks_to_first_flowering: 20,
  weeks_flowering_to_harvest: 30, plants_per_m2: 0.01,
  key_activities: [
    { operation: "OP-PRUNE", week: 10, repeats: "Every cycle", planned_qty: null, description: null },
    { operation: "OP-SPRAY", week: 4, repeats: "Every cycle", planned_qty: null, description: null },
  ],
  cultural_activities: [
    { operation: "OP-SPRAY", schedule: "Interval", interval_weeks: 2, establishment_period_weeks: 6, pre_harvest_interval_days: 14, planned_qty: null, description: null },
  ],
  capital_activities: [{ operation: "OP-CAP", description: null, budget_per_ha: 1000 }],
  ...over,
});
const family = (v: ProtocolVersion): ProtocolFamily => ({
  family: "Season", label: "Season", crop: "Avocado", item: null, active: null, has_pending: false, versions: [v],
});
const actions = (): ProtocolActions => ({ newVersion: vi.fn(), submit: vi.fn(), approve: vi.fn(), sendBack: vi.fn(), saveDraft: vi.fn() });

function open(v = version(), a = actions()) {
  render(<ProtocolsList families={[family(v)]} operations={operations} canPlan canManage actions={a} />);
  fireEvent.click(screen.getByRole("button", { name: /Season/ }));
  return a;
}

describe("ProtocolsList", () => {
  it("shows the three sections, the key hint and the variety template", () => {
    open();
    for (const t of ["Capital activities", "Key activities", "Cultural activities"]) expect(screen.getByRole("region", { name: t })).toBeInTheDocument();
    expect(screen.getByText("List key activities in the order of their week.")).toBeInTheDocument();
    expect(within(screen.getByTestId("protocol-template")).getByText("Interval")).toBeInTheDocument();
  });

  it("template strip shows weeks to maturity and the flowering pattern, not re-flower", () => {
    open(version({
      weeks_to_reflower_after_harvest: 12, weeks_to_maturity: 130, flowering_pattern: "Seasonal",
      flowering_seasons: [{ season_name: "Main", start_month: "August" }, { season_name: "Off-season", start_month: "February" }],
    }));
    const t = within(screen.getByTestId("protocol-template"));
    expect(t.getByText("Weeks to maturity")).toBeInTheDocument();
    expect(t.getByText("130")).toBeInTheDocument();
    expect(t.getByText("Main (August), Off-season (February)")).toBeInTheDocument();
    expect(t.queryByText("Weeks to re-flower")).toBeNull();
  });

  it("template strip shows an interval flowering pattern", () => {
    open(version({ weeks_to_maturity: 30, flowering_pattern: "Interval", flowering_interval_weeks: 4 }));
    expect(within(screen.getByTestId("protocol-template")).getByText("Every 4 weeks")).toBeInTheDocument();
  });

  it("interval weeks disabled for as needed", () => {
    open();
    const interval = screen.getByLabelText("Interval weeks for Spraying") as HTMLInputElement;
    expect(interval).toBeEnabled();
    expect(interval).toHaveValue(2);
    fireEvent.click(screen.getByRole("combobox", { name: "Schedule for Spraying" }));
    fireEvent.click(screen.getByRole("option", { name: "As needed" }));
    expect(screen.getByLabelText("Interval weeks for Spraying")).toBeDisabled();
    expect(screen.getByLabelText("Interval weeks for Spraying")).toHaveValue(null);
  });

  it("occurrences column: empty means until the cycle ends, editable", () => {
    open();
    expect(screen.getByText("Occurrences")).toBeInTheDocument();
    const occ = screen.getByLabelText("Occurrences for Spraying") as HTMLInputElement;
    expect(occ).toHaveValue(null);
    fireEvent.change(occ, { target: { value: "4" } });
    expect(screen.getByLabelText("Occurrences for Spraying")).toHaveValue(4);
  });

  it("out of order week highlighted", () => {
    expect(outOfOrder(version().key_activities)).toEqual(new Set([1]));
    open();
    expect(screen.getByTestId("key-row-1")).toHaveAttribute("data-out-of-order", "true");
    expect(screen.getByTestId("key-row-0")).not.toHaveAttribute("data-out-of-order");
    expect(screen.getByRole("alert")).toHaveTextContent(/order of their week/);
    fireEvent.change(screen.getByLabelText("Week for Spraying"), { target: { value: "12" } });
    expect(screen.getByTestId("key-row-1")).not.toHaveAttribute("data-out-of-order");
  });

  it("capital picker lists only capital activities", () => {
    open();
    fireEvent.click(screen.getByRole("combobox", { name: "Capital activity 1" }));
    const names = screen.getAllByRole("option").map((o) => o.textContent);
    expect(names).toEqual(["Land clearing", "Drip lines"]);
  });

  it("saves all three tables on Save draft", () => {
    const a = open();
    fireEvent.change(screen.getByLabelText("Budget per ha 1"), { target: { value: "1500" } });
    fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
    const [, tables] = vi.mocked(a.saveDraft).mock.calls[0];
    expect(tables.capital_activities[0].budget_per_ha).toBe(1500);
    expect(tables.key_activities).toHaveLength(2);
    expect(tables.cultural_activities).toHaveLength(1);
  });

  it("adds a row", () => {
    open();
    fireEvent.click(screen.getByRole("button", { name: "Add row to Key activities" }));
    expect(screen.getByTestId("key-row-2")).toBeInTheDocument();
  });

  it("is read-only on an active version", () => {
    open(version({ version_status: "Active" }));
    expect(screen.queryByRole("button", { name: "Save draft" })).toBeNull();
    expect(screen.queryByLabelText("Week for Spraying")).toBeNull();
  });
});

import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProtocolDiff } from "@/components/approvals/ProtocolDiff";

describe("ProtocolDiff", () => {
  it("shows a change to Times per week", () => {
    render(
      <ProtocolDiff
        diff={{
          name: "S v2", previous: "S", fields: [],
          steps: [{ table: "cultural_activities", change: "changed", operation: "OP", operation_name: "Irrigation",
            changes: [{ field: "times_per_week", before: 1, after: 3 }] }],
        }}
      />,
    );
    expect(screen.getByText(/Times per week/)).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("says ×N / week on an added cultural row", () => {
    render(
      <ProtocolDiff
        diff={{
          name: "S", previous: null, fields: [],
          steps: [{ table: "cultural_activities", change: "added", operation: "OP", operation_name: "Irrigation",
            after: { operation: "OP", schedule: "Interval", interval_weeks: 1, times_per_week: 3, establishment_period_weeks: 0, pre_harvest_interval_days: 0, planned_qty: null, description: null } }],
        }}
      />,
    );
    expect(screen.getByText(/3× \/ week/)).toBeInTheDocument();
  });
});

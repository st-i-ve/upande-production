import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { NewProtocolDialog } from "@/components/settings/NewProtocolDialog";
import { ToastProvider } from "@/components/Toast";
import type { ProtocolFamily } from "@/lib/protocols-api";

vi.mock("@/lib/protocols-api", async (orig) => ({ ...(await orig<typeof import("@/lib/protocols-api")>()), createProtocol: vi.fn() }));

const fam = {
  family: "Season", label: "Season", crop: "C", item: null, active: "Season", has_pending: false,
  versions: [{
    name: "Season", protocol_name: "Season", crop: "C", item: null, version: 1, version_status: "Active", protocol_family: "Season",
    previous_version: null, submitted_by: null, submitted_at: null, approved_by: null, approved_at: null, review_note: null,
    key_activities: [{ operation: "OP-P", week: 4, repeats: "Every cycle", planned_qty: null, description: null }],
    cultural_activities: [{ operation: "OP-I", schedule: "Interval", interval_weeks: 1, times_per_week: 3, establishment_period_weeks: 0, pre_harvest_interval_days: 0, planned_qty: null, description: null }],
    capital_activities: [],
  }],
} as ProtocolFamily;

describe("NewProtocolDialog", () => {
  it("is wide and previews the activities of the version to copy", () => {
    render(<ToastProvider><NewProtocolDialog crop="C" varieties={[]} families={[fam]} opNames={{ "OP-P": "Pruning", "OP-I": "Irrigation" }} onClose={() => {}} onCreated={() => {}} /></ToastProvider>);
    expect(screen.getByRole("dialog").className).toMatch(/max-w-\[60rem\]/);
    expect(screen.getByTestId("copy-preview")).toHaveTextContent("starts empty");
    fireEvent.click(screen.getByRole("combobox", { name: "Copy activities from" }));
    fireEvent.click(screen.getByRole("option", { name: "Season v1 (Active)" }));
    const p = within(screen.getByTestId("copy-preview"));
    expect(p.getByText("Pruning: week 4")).toBeInTheDocument();
    expect(p.getByText("Irrigation: every 1 wk, 3× / week")).toBeInTheDocument();
  });
});

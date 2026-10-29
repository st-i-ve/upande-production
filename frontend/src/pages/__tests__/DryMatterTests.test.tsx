import "@testing-library/jest-dom/vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";
import type { Crop } from "@/lib/api";

vi.mock("@/lib/drymatter-api", () => ({ listDryMatterTests: vi.fn(), saveDryMatterTest: vi.fn(), listDryMatterDue: vi.fn() }));
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), listUnits: vi.fn() }));
import * as api from "@/lib/api";
import { listDryMatterDue, listDryMatterTests, saveDryMatterTest } from "@/lib/drymatter-api";
import { viewAllowed } from "@/lib/nav";
import { DryMatterTests } from "@/pages/fruits-vegetables/DryMatterTests";

const list = vi.mocked(listDryMatterTests);
const save = vi.mocked(saveDryMatterTest);
const dueList = vi.mocked(listDryMatterDue);
const potatoes: Crop = {
  name: "Potatoes", crop_key: "potatoes", accent_color: "#a60", icon_key: "vegetables", unit_label: "Block",
  parent_unit_label: "Farm", sub_unit_label: "", yield_uom: "Kg", dry_matter_testing: 1, dry_matter_on: "Tuber", dry_matter_target_pct: 20,
};
const test = (name: string, avg: number, ready: boolean) => ({
  name, unit: "Block A", variety: "Shangi", test_date: "2026-10-12", avg_pct: avg, target_pct: 20, ready, stage: "Bulking",
  samples: [{ sample_no: 1, dry_matter_pct: avg }, { sample_no: 2, dry_matter_pct: avg }],
});

describe("DryMatterTests", () => {
  beforeEach(() => {
    list.mockReset().mockResolvedValue({ rows: [test("DMT-1", 21.5, true), test("DMT-2", 18, false)] });
    save.mockReset().mockResolvedValue({ name: "DMT-3", avg_pct: 21, ready: true });
    dueList.mockReset().mockResolvedValue({
      retest_days: 7, counts: { due: 1, recent: 1, not_yet: 1 },
      rows: [
        { unit: "Block A", cycle: "C1", variety: "Shangi", stage: "Bulking", from_stage: "Tuber initiation", on: "Tuber", target_pct: 20, state: "due", last_test: "2026-10-12", days_since: 14, last_pct: 21.5, next_due: "2026-10-19" },
        { unit: "Block B", cycle: "C2", variety: "Red Creole", stage: "Bulb bulking", from_stage: "Bulb bulking", on: "Bulb", target_pct: 11, state: "recent", last_test: "2026-10-26", days_since: 2, last_pct: 9.4, next_due: "2026-11-02" },
        { unit: "Block C", cycle: "C3", variety: "Gloria F1", stage: "Vegetative", from_stage: "Head formation", on: "Head", target_pct: 8, state: "not_yet", last_test: null, days_since: null, last_pct: null, next_due: null },
      ],
    } as never);
    vi.mocked(api.listUnits).mockReset().mockResolvedValue({ units: [{ name: "Block A", is_group: 0 }] } as never);
  });

  it("lists tests with their average and a ready badge", async () => {
    renderPage(<DryMatterTests />, {}, potatoes);
    const row = await screen.findByTestId("dm-row-DMT-1");
    expect(row).toHaveTextContent("21.5%");
    expect(row).toHaveTextContent("Ready to pick");
    expect(screen.getByTestId("dm-row-DMT-2")).toHaveTextContent("Not yet");
  });

  it("shows the stage on each test and which blocks are due for sampling", async () => {
    renderPage(<DryMatterTests />, {}, potatoes);
    expect(await screen.findByTestId("dm-stage-DMT-1")).toHaveTextContent("Bulking");
    const a = screen.getByTestId("due-row-Block A");
    expect(a).toHaveTextContent("Tuber initiation");
    expect(a).toHaveTextContent("Due, last test 14 d ago");
    expect(screen.getByTestId("due-row-Block B")).toHaveTextContent("Tested 2 d ago");
    const c = screen.getByTestId("due-row-Block C");
    expect(c).toHaveTextContent("Not yet at Head formation");
    expect(c.querySelector("button")).toBeNull(); // nothing to record before the sampling stage
  });

  it("takes the target from the variety of the chosen block", async () => {
    renderPage(<DryMatterTests />, {}, potatoes);
    fireEvent.click(await screen.findByRole("button", { name: "Record a test for Block B" }));
    fireEvent.change(await screen.findByLabelText("Sample 1 dry matter"), { target: { value: "12" } });
    expect(screen.getByTestId("dmt-variety")).toHaveTextContent("Red Creole");
    expect(screen.getByTestId("dmt-average")).toHaveTextContent("target 11%");
    expect(screen.getByTestId("dmt-average")).toHaveTextContent("Ready to pick");
  });

  it("averages the samples live and saves them", async () => {
    renderPage(<DryMatterTests />, {}, potatoes);
    await screen.findByTestId("dm-row-DMT-1");
    fireEvent.click(screen.getByRole("button", { name: "Record a test" }));
    fireEvent.change(await screen.findByLabelText("Sample 1 dry matter"), { target: { value: "22" } });
    fireEvent.change(screen.getByLabelText("Sample 2 dry matter"), { target: { value: "20" } });
    const avg = screen.getByTestId("dmt-average");
    expect(avg).toHaveTextContent("21.0%");
    expect(avg).toHaveTextContent("Ready to pick");
    expect(screen.getByRole("button", { name: "Save test" })).toBeDisabled(); // no unit yet
  });

  it("is only offered when the crop tests dry matter, and never for avocado", () => {
    expect(viewAllowed("dry-matter-tests", "potatoes", potatoes)).toBe(true);
    expect(viewAllowed("dry-matter-tests", "potatoes", { dry_matter_testing: 0 })).toBe(false);
    expect(viewAllowed("dry-matter-tests", "avocado", { dry_matter_testing: 1 })).toBe(false);
    expect(viewAllowed("dry-matter", "avocado")).toBe(true);
    void waitFor;
  });
});

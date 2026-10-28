import "@testing-library/jest-dom/vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";
import type { Crop } from "@/lib/api";

vi.mock("@/lib/drymatter-api", () => ({ listDryMatterTests: vi.fn(), saveDryMatterTest: vi.fn() }));
vi.mock("@/lib/api", async (orig) => ({ ...(await orig<typeof import("@/lib/api")>()), listUnits: vi.fn() }));
import * as api from "@/lib/api";
import { listDryMatterTests, saveDryMatterTest } from "@/lib/drymatter-api";
import { viewAllowed } from "@/lib/nav";
import { DryMatterTests } from "@/pages/fruits-vegetables/DryMatterTests";

const list = vi.mocked(listDryMatterTests);
const save = vi.mocked(saveDryMatterTest);
const potatoes: Crop = {
  name: "Potatoes", crop_key: "potatoes", accent_color: "#a60", icon_key: "vegetables", unit_label: "Block",
  parent_unit_label: "Farm", sub_unit_label: "", yield_uom: "Kg", dry_matter_testing: 1, dry_matter_on: "Tuber", dry_matter_target_pct: 20,
};
const test = (name: string, avg: number, ready: boolean) => ({
  name, unit: "Block A", variety: "Shangi", test_date: "2026-10-12", avg_pct: avg, target_pct: 20, ready,
  samples: [{ sample_no: 1, dry_matter_pct: avg }, { sample_no: 2, dry_matter_pct: avg }],
});

describe("DryMatterTests", () => {
  beforeEach(() => {
    list.mockReset().mockResolvedValue({ rows: [test("DMT-1", 21.5, true), test("DMT-2", 18, false)] });
    save.mockReset().mockResolvedValue({ name: "DMT-3", avg_pct: 21, ready: true });
    vi.mocked(api.listUnits).mockReset().mockResolvedValue({ units: [{ name: "Block A", is_group: 0 }] } as never);
  });

  it("lists tests with their average and a ready badge", async () => {
    renderPage(<DryMatterTests />, {}, potatoes);
    const row = await screen.findByTestId("dm-row-DMT-1");
    expect(row).toHaveTextContent("21.5%");
    expect(row).toHaveTextContent("Ready to pick");
    expect(screen.getByTestId("dm-row-DMT-2")).toHaveTextContent("Not yet");
  });

  it("averages the samples live and saves them", async () => {
    renderPage(<DryMatterTests />, {}, potatoes);
    await screen.findByTestId("dm-row-DMT-1");
    fireEvent.click(screen.getByRole("button", { name: /Record a test/ }));
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

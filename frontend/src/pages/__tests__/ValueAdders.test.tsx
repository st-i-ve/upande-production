import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Boot, Crop } from "@/lib/api";

vi.mock("@/lib/api", () => ({ valueAdderSummary: vi.fn() }));

import * as api from "@/lib/api";
import { CropProvider } from "@/lib/crops";
import { ValueAdders } from "@/pages/ValueAdders";

const crop: Crop = {
  name: "Avocado",
  crop_key: "avocado",
  accent_color: "#3f8f4f",
  icon_key: "avocado",
  unit_label: "Block",
  parent_unit_label: "Pivot",
  sub_unit_label: "Block",
  yield_uom: "kg",
};
const boot = (can_see_pay: boolean): Boot => ({ crops: [crop], farms: ["Mutara"], can_see_pay, can_plan: true, can_manage: false });
const renderIt = (pay: boolean) =>
  render(
    <CropProvider crop={crop} boot={boot(pay)}>
      <ValueAdders />
    </CropProvider>,
  );

beforeEach(() => {
  vi.mocked(api.valueAdderSummary).mockResolvedValue({
    rows: [
      { key: "E1", label: "Jane Wanjiru", qty: 30, hours: 12, pay_value: 1500, entries: 3 },
      { key: "E2", label: "Peter Otieno", qty: 20, hours: 8, pay_value: 1000, entries: 2 },
    ],
    total_pay: 2500,
  });
});

describe("ValueAdders", () => {
  it("shows rows and the total pay", async () => {
    renderIt(true);
    expect(await screen.findByText("Jane Wanjiru")).toBeTruthy();
    expect(screen.getByText("2,500.00")).toBeTruthy();
    expect(screen.getByText("Pay")).toBeTruthy();
  });

  it("hides pay when the user cannot see it", async () => {
    renderIt(false);
    expect(await screen.findByText("Jane Wanjiru")).toBeTruthy();
    expect(screen.queryByText("2,500.00")).toBeNull();
    expect(screen.queryByText("Pay")).toBeNull();
  });
});

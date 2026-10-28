import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/fv-api", () => ({ getIrrigation: vi.fn(), saveIrrigationRun: vi.fn(), getGrading: vi.fn(), saveGrading: vi.fn() }));
import { getGrading, saveGrading } from "@/lib/fv-api";
import { Grading } from "@/pages/fruits-vegetables/Grading";

const get = vi.mocked(getGrading);
const save = vi.mocked(saveGrading);

const bucket = (key: string, c1: number, c2: number, rej: number) => ({
  key, graded_kg: c1 + c2, rejects_kg: rej, received_kg: c1 + c2 + rej, grades: { "Class 1": c1, "Class 2": c2 },
  class1_pct: Math.round((c1 / (c1 + c2)) * 1000) / 10, reject_pct: Math.round((rej / (c1 + c2 + rej)) * 1000) / 10,
});
const payload = () => ({
  from_date: "2026-09-21", to_date: "2026-10-28", unit: null, item: null, units: ["P1-B4", "P2-B3"], items: ["Cabbage", "Potatoes"],
  kpis: { graded_kg: 9500, received_kg: 10000, rejects_kg: 500, class1_pct: 66.3, reject_pct: 5, top_reject_reason: "Rot", top_reject_pct: 60, logs: 2 },
  grades: ["Class 1", "Class 2"],
  by_item: [bucket("Cabbage", 4000, 1000, 250), bucket("Potatoes", 2300, 2200, 250)],
  by_block: [bucket("P1-B4", 4000, 1000, 250), bucket("P2-B3", 2300, 2200, 250)],
  reasons: [{ reason: "Rot", kg: 300, pct: 60 }, { reason: "Greening", kg: 200, pct: 40 }],
  series: [{ week: "2026-10-12", graded_kg: 4750, class1_pct: 80, reject_pct: 5 }, { week: "2026-10-19", graded_kg: 4750, class1_pct: 51, reject_pct: 5 }],
  rows: [
    { name: "HGL-1", unit: "P1-B4", cycle: "C1", item: "Cabbage", grading_date: "2026-10-14", received_kg: 5250, received_crates: 175, graded_kg: 5000, class1_kg: 4000, rejects_kg: 250, reject_reason: "Rot", graded_by: null, notes: null, lines: [] },
    { name: "HGL-2", unit: "P2-B3", cycle: "C2", item: "Potatoes", grading_date: "2026-10-21", received_kg: 4750, received_crates: 95, graded_kg: 4500, class1_kg: 2300, rejects_kg: 250, reject_reason: "Greening", graded_by: null, notes: null, lines: [] },
  ],
  form: { units: [{ name: "P1-B4", parent: "Pivot 1", item: "Cabbage", cycle: "C1" }, { name: "P2-B3", parent: "Pivot 2", item: "Potatoes", cycle: "C2" }], reasons: ["Rot", "Greening"], default_grades: ["Class 1", "Class 2", "Ware"] },
});

async function openDialog() {
  renderPage(<Grading />);
  await screen.findByTestId("by-item");
  fireEvent.click(screen.getByRole("button", { name: /Record grading/ }));
  return await screen.findByRole("dialog");
}

describe("Grading", () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue(payload() as never);
    save.mockReset().mockResolvedValue({ ok: true, name: "HGL-9", graded_kg: 900 } as never);
  });

  it("shows KPIs, stacked grade bars per crop and block, reasons and rows", async () => {
    renderPage(<Grading />);
    const cab = await screen.findByTestId("by-item-Cabbage");
    expect(cab).toHaveTextContent("80% class 1");
    expect(within(cab).getByRole("img", { name: "Cabbage grade split" }).children).toHaveLength(3); // 2 grades + rejects
    expect(screen.getByTestId("by-block-P2-B3")).toBeInTheDocument();
    expect(screen.getByText("66.3%")).toBeInTheDocument();
    expect(screen.getByTestId("reasons")).toHaveTextContent("Greening");
    expect(screen.getAllByTestId("grading-row")).toHaveLength(2);
    expect(screen.getByTestId("grade-trend")).toBeInTheDocument();
  });

  it("filters by crop item through the server", async () => {
    renderPage(<Grading />);
    await screen.findByTestId("by-item");
    fireEvent.click(screen.getByRole("combobox", { name: /Crop item/ }));
    fireEvent.click(await screen.findByRole("option", { name: "Potatoes" }));
    await waitFor(() => expect(get).toHaveBeenLastCalledWith(expect.objectContaining({ item: "Potatoes" })));
  });

  it("shows an empty state with no logs", async () => {
    get.mockResolvedValue({ ...payload(), rows: [], by_item: [], by_block: [], reasons: [] } as never);
    renderPage(<Grading />);
    expect(await screen.findByTestId("no-logs")).toBeInTheDocument();
  });

  it("validates the dialog: block, received kg, balance and reject reason", async () => {
    const dialog = await openDialog();
    fireEvent.click(within(dialog).getByRole("button", { name: "Save grading" }));
    expect(await within(dialog).findByText("Choose the block.")).toBeInTheDocument();
    expect(within(dialog).getByText("Enter the kg received, more than zero.")).toBeInTheDocument();
    fireEvent.change(within(dialog).getByLabelText("Received (kg)"), { target: { value: "1000" } });
    fireEvent.change(within(dialog).getByLabelText("Grade 1 kg"), { target: { value: "900" } });
    fireEvent.change(within(dialog).getByLabelText("Rejects (kg)"), { target: { value: "200" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save grading" }));
    expect(await within(dialog).findByText(/is more than the 1,000.0 kg received/)).toBeInTheDocument();
    expect(within(dialog).getByText("Give a reason for the rejects.")).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();
  });

  it("saves a grading with its lines, then refreshes", async () => {
    const dialog = await openDialog();
    fireEvent.click(within(dialog).getByRole("combobox", { name: "Block" }));
    fireEvent.click(await screen.findByRole("option", { name: "P1-B4 · Cabbage" }));
    fireEvent.change(within(dialog).getByLabelText("Received (kg)"), { target: { value: "1000" } });
    fireEvent.change(within(dialog).getByLabelText("Grade 1 kg"), { target: { value: "700" } });
    fireEvent.change(within(dialog).getByLabelText("Grade 2 kg"), { target: { value: "250" } });
    fireEvent.change(within(dialog).getByLabelText("Rejects (kg)"), { target: { value: "50" } });
    fireEvent.click(within(dialog).getByRole("combobox", { name: "Reject reason" }));
    fireEvent.click(await screen.findByRole("option", { name: "Rot" }));
    expect(within(dialog).getByTestId("gr-balance")).toHaveTextContent("1,000.0 of 1,000.0 kg accounted for");
    fireEvent.click(within(dialog).getByRole("button", { name: "Save grading" }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({
        unit: "P1-B4", item: "Cabbage", cycle: "C1", received_kg: 1000, rejects_kg: 50, reject_reason: "Rot",
        lines: [{ grade: "Class 1", kg: 700, crates: undefined }, { grade: "Class 2", kg: 250, crates: undefined }],
      }),
    );
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
  });
});

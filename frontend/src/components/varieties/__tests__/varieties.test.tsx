import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/varieties-api", async (orig) => ({
  ...(await orig<typeof import("@/lib/varieties-api")>()),
  saveVariety: vi.fn(),
  saveRule: vi.fn(),
}));
vi.mock("@/components/cycles/ItemField", () => ({
  ItemField: ({ id, value, onChange }: { id?: string; value: string; onChange: (v: string) => void }) => (
    <input id={id} aria-label={id} value={value} onChange={(e) => onChange(e.target.value)} />
  ),
}));

import { ToastProvider } from "@/components/Toast";
import { RuleDialog, ruleProblem, toRuleForm } from "@/components/varieties/RuleDialog";
import { StageEditor, StageTimeline, stageProblem, toStageDrafts } from "@/components/varieties/StageEditor";
import { VarietyDialog } from "@/components/varieties/VarietyDialog";
import { yieldModelProblem } from "@/components/varieties/YieldModelEditor";
import * as vapi from "@/lib/varieties-api";
import type { Variety } from "@/lib/varieties-api";
import { CATEGORIES } from "@/components/settings/OperationsTable";

const mocked = vi.mocked(vapi);

const potato: Variety = {
  name: "Shangi",
  variety_name: "Shangi",
  crop: "Potatoes",
  product: "Potatoes",
  item: "Potatoes - Shangi",
  enabled: 1,
  stage_anchor: "Planting",
  default_protocol: null,
  days_to_first_harvest: 90,
  harvest_window_days: 14,
  expected_yield_per_ha: 20000,
  expected_yield_per_plant: null,
  plants_per_ha: 40000,
  stages: [
    { stage: "Vegetative", start_day: 0, length_days: 30, is_harvest: 0 },
    { stage: "Tuber initiation", start_day: 30, length_days: 25, is_harvest: 0 },
    { stage: "Harvest", start_day: 90, length_days: 14, is_harvest: 1 },
  ],
};

const wrap = (ui: React.ReactElement) => render(<ToastProvider>{ui}</ToastProvider>);

beforeEach(() => {
  vi.resetAllMocks();
});

describe("operation categories", () => {
  it("are exactly the rule categories, in order", () => {
    expect(CATEGORIES).toEqual(["Spraying", "Weeding", "Fertilising", "Irrigation", "Harvesting", "Pruning", "Feeding", "Other"]);
  });
});

describe("stage editor", () => {
  it("draws a bar per stage with the harvest stage marked", () => {
    render(<StageTimeline stages={potato.stages} accent="#2a7" />);
    expect(screen.getAllByTestId(/^stage-bar-/)).toHaveLength(3);
    expect(within(screen.getByTestId("stage-bar-Harvest")).getByText(/harvest/)).toBeInTheDocument();
  });

  it("validates names, lengths and a single harvest stage", () => {
    const d = toStageDrafts(potato.stages);
    expect(stageProblem(d)).toBeNull();
    expect(stageProblem([{ ...d[0], stage: " " }])).toMatch(/name/);
    expect(stageProblem([d[0], { ...d[1], stage: "vegetative" }])).toMatch(/twice/);
    expect(stageProblem([{ ...d[0], length_days: "0" }])).toMatch(/length/);
    expect(stageProblem([{ ...d[0], is_harvest: true }, { ...d[1], is_harvest: true }])).toMatch(/harvest/);
  });

  it("adds a stage after the last one and marks one harvest at a time", () => {
    const onChange = vi.fn();
    render(<StageEditor rows={toStageDrafts(potato.stages)} onChange={onChange} accent="#2a7" />);
    fireEvent.click(screen.getByRole("button", { name: /Add stage/ }));
    const added = onChange.mock.calls[0][0].at(-1);
    expect(added.start_day).toBe("104");
    fireEvent.click(screen.getByRole("switch", { name: "Stage 1 is the harvest stage" }));
    const rows = onChange.mock.calls[1][0];
    expect(rows.filter((r: { is_harvest: boolean }) => r.is_harvest).map((r: { stage: string }) => r.stage)).toEqual(["Vegetative"]);
  });
});

describe("variety form", () => {
  it("saves a new variety with its stages", async () => {
    mocked.saveVariety.mockResolvedValue({ name: "Markies" });
    const onSaved = vi.fn();
    wrap(<VarietyDialog crop="Potatoes" accent="#2a7" variety={null} protocols={[]} onClose={() => {}} onSaved={onSaved} />);
    const save = screen.getByRole("button", { name: "Save variety" });
    expect(save).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Variety name"), { target: { value: "Markies" } });
    fireEvent.change(screen.getByLabelText("v-item"), { target: { value: "Potatoes - Markies" } });
    fireEvent.click(screen.getByRole("button", { name: /Add stage/ }));
    fireEvent.change(screen.getByLabelText("Stage 1 name"), { target: { value: "Vegetative" } });
    expect(save).toBeDisabled(); // no length yet
    fireEvent.change(screen.getByLabelText("Stage 1 length in days"), { target: { value: "30" } });
    expect(save).toBeEnabled();
    fireEvent.click(save);
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    const sent = mocked.saveVariety.mock.calls[0][0];
    expect(sent).toMatchObject({ variety_name: "Markies", crop: "Potatoes", item: "Potatoes - Markies" });
    expect(sent.stages).toEqual([{ stage: "Vegetative", start_day: 0, length_days: 30, is_harvest: 0 }]);
  });

  it("edits an existing variety by name and shows a server refusal", async () => {
    mocked.saveVariety.mockResolvedValue({ error: "Stage Harvest is listed twice" });
    wrap(<VarietyDialog crop="Potatoes" accent="#2a7" variety={potato} protocols={[]} onClose={() => {}} onSaved={() => {}} />);
    expect(screen.getByLabelText("Variety name")).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Weeks to first harvest"), { target: { value: "95" } });
    fireEvent.click(screen.getByRole("button", { name: "Save variety" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("listed twice");
    expect(mocked.saveVariety.mock.calls[0][0]).toMatchObject({ name: "Shangi", weeks_to_first_harvest: 95 });
  });
});

describe("variety yield model", () => {
  const hass: Variety = {
    ...potato, name: "Hass", variety_name: "Hass", crop: "Avocado", item: "Hass Avocado", is_flowering: 1, flowering_pattern: "Interval",
    weeks_to_first_flowering: 20, weeks_flowering_to_harvest: 30, flowering_interval_weeks: 52, harvest_pattern: "Interval", harvest_interval_weeks: 52,
    yield_by_age: [{ age_years: 0, kg_per_plant: 0 }, { age_years: 2, kg_per_plant: 12 }],
    biennial_off_factor: 0.58, on_years: "Even", late_crop_share_pct: 84.6,
  };

  it("only a flowering variety shows it, with the saved rows", () => {
    wrap(<VarietyDialog crop="Potatoes" accent="#2a7" variety={potato} protocols={[]} onClose={() => {}} onSaved={() => {}} />);
    expect(screen.queryByTestId("yield-model-editor")).toBeNull();
    cleanup();
    wrap(<VarietyDialog crop="Avocado" accent="#2a7" variety={hass} protocols={[]} onClose={() => {}} onSaved={() => {}} />);
    expect(screen.getByTestId("yield-model-editor")).toBeInTheDocument();
    expect(screen.getByLabelText("Yield row 2 kg per plant")).toHaveValue("12");
    expect(screen.getByLabelText("Off-year factor")).toHaveValue("0.58");
    expect(screen.getByLabelText("Late crop share (%)")).toHaveValue("84.6");
  });

  it("saves edited rows, the off-year factor and the late share", async () => {
    mocked.saveVariety.mockResolvedValue({ name: "Hass" });
    wrap(<VarietyDialog crop="Avocado" accent="#2a7" variety={hass} protocols={[]} onClose={() => {}} onSaved={() => {}} />);
    fireEvent.change(screen.getByLabelText("Yield row 2 kg per plant"), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: /Add age/ }));
    fireEvent.change(screen.getByLabelText("Yield row 3 from age (years)"), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText("Yield row 3 kg per plant"), { target: { value: "63" } });
    fireEvent.change(screen.getByLabelText("Off-year factor"), { target: { value: "0.6" } });
    fireEvent.change(screen.getByLabelText("Late crop share (%)"), { target: { value: "80" } });
    fireEvent.click(screen.getByRole("button", { name: "Save variety" }));
    await waitFor(() => expect(mocked.saveVariety).toHaveBeenCalled());
    expect(mocked.saveVariety.mock.calls[0][0]).toMatchObject({
      yield_by_age: [{ age_years: 0, kg_per_plant: 0 }, { age_years: 2, kg_per_plant: 20 }, { age_years: 5, kg_per_plant: 63 }],
      biennial_off_factor: 0.6, on_years: "Even", late_crop_share_pct: 80,
    });
  });

  it("refuses an age listed twice and an off-year factor with no on years", () => {
    expect(yieldModelProblem({ ages: [{ age: "2", kg: "1" }, { age: "2", kg: "2" }], offFactor: "", onYears: "", lateShare: "" })).toMatch(/twice/);
    expect(yieldModelProblem({ ages: [], offFactor: "0.6", onYears: "", lateShare: "" })).toMatch(/even or odd/);
    expect(yieldModelProblem({ ages: [{ age: "2", kg: "1" }], offFactor: "", onYears: "", lateShare: "" })).toBeNull();
  });
});

describe("rule form validation", () => {
  const base = toRuleForm(null);
  const stages = ["Vegetative", "Tuber initiation"];
  it("needs an operation or category", () => {
    expect(ruleProblem(base, stages)).toMatch(/operation/);
    expect(ruleProblem({ ...base, category: "Weeding", stage: "Vegetative" }, stages)).toBeNull();
  });
  it("needs a stage for stage rules, from the chosen variety", () => {
    expect(ruleProblem({ ...base, category: "Weeding" }, stages)).toMatch(/needs a stage/);
    expect(ruleProblem({ ...base, category: "Weeding", variety: "Shangi", stage: "Nope" }, stages)).toMatch(/not a stage/);
  });
  it("needs days for window rules and a target for after-operation rules", () => {
    const b = { ...base, category: "Spraying", rule_type: "Not within days before harvest" };
    expect(ruleProblem(b, stages)).toMatch(/Days/);
    expect(ruleProblem({ ...b, days: "21" }, stages)).toBeNull();
    const a = { ...b, rule_type: "Not within days after operation", days: "3" };
    expect(ruleProblem(a, stages)).toMatch(/other operation/);
    expect(ruleProblem({ ...a, other_category: "Spraying" }, stages)).toBeNull();
  });

  it("offers the chosen variety's stages and saves", async () => {
    mocked.saveRule.mockResolvedValue({ name: "PAR-00001" });
    const onSaved = vi.fn();
    wrap(<RuleDialog crop="Potatoes" rule={null} varieties={[potato]} operations={[]} onClose={() => {}} onSaved={onSaved} />);
    const save = screen.getByRole("button", { name: "Save rule" });
    expect(save).toBeDisabled();
    fireEvent.click(screen.getByRole("combobox", { name: "Operation category" }));
    fireEvent.click(await screen.findByRole("option", { name: "Weeding" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Variety" }));
    fireEvent.click(await screen.findByRole("option", { name: "Shangi" }));
    fireEvent.click(screen.getByRole("combobox", { name: "Stage" }));
    expect(await screen.findAllByRole("option")).toHaveLength(3);
    fireEvent.click(screen.getByRole("option", { name: "Tuber initiation" }));
    expect(save).toBeEnabled();
    fireEvent.click(save);
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(mocked.saveRule.mock.calls[0][0]).toMatchObject({
      crop: "Potatoes", variety: "Shangi", stage: "Tuber initiation", operation_category: "Weeding", rule_type: "Not in stage", enforcement: "Block",
    });
  });
});

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/crop-model-api", () => ({ getCropModel: vi.fn(), saveCropModel: vi.fn() }));
import { ToastProvider } from "@/components/Toast";
import { CropModelPanel, draftOf, payloadOf } from "@/components/settings/CropModelPanel";
import { getCropModel, saveCropModel, type CropModel } from "@/lib/crop-model-api";

const model: CropModel = {
  crop: "Avocado",
  crop_key: "avocado",
  can_edit: true,
  groups: [
    {
      label: "Harvest",
      fields: [
        { fieldname: "harvests_in_crates", label: "Harvests in Crates", fieldtype: "Check", options: null, description: null, depends_on: null, value: 1 },
        { fieldname: "avg_kg_per_crate", label: "Avg Kg per Crate", fieldtype: "Float", options: null, description: "Weight of a full crate.", depends_on: "harvests_in_crates", value: 18 },
      ],
      tables: [],
    },
    {
      label: "Crop model",
      fields: [
        { fieldname: "price_per_kg", label: "Price per Kg", fieldtype: "Currency", options: null, description: null, depends_on: null, value: 95 },
        { fieldname: "default_pick_weeks", label: "Default Pick Weeks", fieldtype: "Int", options: null, description: null, depends_on: null, value: 6 },
      ],
      tables: [
        {
          fieldname: "count_sizes",
          label: "Count Sizes",
          description: null,
          columns: [
            { fieldname: "count", label: "Count", fieldtype: "Int", options: null },
            { fieldname: "min_g", label: "Min Weight (g)", fieldtype: "Float", options: null },
            { fieldname: "max_g", label: "Max Weight (g)", fieldtype: "Float", options: null },
          ],
          rows: [{ count: 14, min_g: 275, max_g: 317 }],
        },
      ],
    },
  ],
};

const wrap = (canEdit = true) =>
  render(
    <ToastProvider>
      <CropModelPanel crop="Avocado" canEdit={canEdit} />
    </ToastProvider>,
  );

describe("CropModelPanel", () => {
  beforeEach(() => {
    vi.mocked(getCropModel).mockReset().mockResolvedValue(structuredClone(model));
    vi.mocked(saveCropModel).mockReset().mockResolvedValue(structuredClone(model));
  });

  it("draws the groups, fields and tables the server described", async () => {
    wrap();
    expect(await screen.findByTestId("cm-group-Crop model")).toBeInTheDocument();
    expect(screen.getByLabelText("Price per Kg")).toHaveValue("95");
    expect(screen.getByLabelText("Default Pick Weeks")).toHaveValue("6");
    expect(screen.getByLabelText("Avg Kg per Crate")).toHaveValue("18");
    expect(screen.getByLabelText("Count Sizes 1 Min Weight (g)")).toHaveValue("275");
    expect(screen.getByText("Weight of a full crate.")).toBeInTheDocument();
  });

  it("hides a field whose switch is off", async () => {
    const m = structuredClone(model);
    m.groups[0].fields[0].value = 0;
    vi.mocked(getCropModel).mockResolvedValue(m);
    wrap();
    await screen.findByTestId("cm-group-Harvest");
    expect(screen.queryByLabelText("Avg Kg per Crate")).toBeNull();
  });

  it("saves numbers as numbers and the table rows as edited", async () => {
    wrap();
    fireEvent.change(await screen.findByLabelText("Price per Kg"), { target: { value: "110" } });
    fireEvent.change(screen.getByLabelText("Default Pick Weeks"), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: /Add row/ }));
    fireEvent.change(screen.getByLabelText("Count Sizes 2 Count"), { target: { value: "16" } });
    fireEvent.click(screen.getByRole("button", { name: "Save crop model" }));
    await waitFor(() => expect(saveCropModel).toHaveBeenCalled());
    const [crop, data] = vi.mocked(saveCropModel).mock.calls[0] as [string, Record<string, unknown>];
    expect(crop).toBe("Avocado");
    expect(data).toMatchObject({ price_per_kg: 110, default_pick_weeks: 4, harvests_in_crates: 1, avg_kg_per_crate: 18 });
    expect(data.count_sizes).toEqual([
      { count: 14, min_g: 275, max_g: 317 },
      { count: 16, min_g: null, max_g: null },
    ]);
    expect(await screen.findByText("Crop model saved.")).toBeInTheDocument();
  });

  it("is read-only for someone who cannot manage, and shows the server's refusal", async () => {
    wrap(false);
    expect(await screen.findByLabelText("Price per Kg")).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save crop model" })).toBeNull();
  });

  it("shows the error when the model cannot be read", async () => {
    vi.mocked(getCropModel).mockResolvedValue({ error: "Not permitted." });
    wrap();
    expect(await screen.findByRole("alert")).toHaveTextContent("Not permitted.");
  });

  it("round-trips the draft", () => {
    const d = draftOf(model);
    expect(payloadOf(model, d.values, d.tables)).toMatchObject({ price_per_kg: 95, harvests_in_crates: 1 });
  });
});

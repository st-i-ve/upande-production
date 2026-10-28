import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/apiary-api", () => ({ getHiveInspections: vi.fn(), saveHiveInspection: vi.fn() }));
import { getHiveInspections, saveHiveInspection } from "@/lib/apiary-api";
import { HiveInspections } from "@/pages/apiary/HiveInspections";

const get = vi.mocked(getHiveInspections);
const save = vi.mocked(saveHiveInspection);

const group = (unit: string, mites: number, status: string, queen: string) => ({
  unit, label: unit, farm: "Mutara", inspections: 2, last_date: "2026-10-20", days_since: 8, colonies: 12, queenright: queen === "queenright" ? 12 : 8,
  queenright_pct: queen === "queenright" ? 100 : 66.7, queen_status: queen, queen_seen: true, eggs_seen: true, mites_per_100: mites, mite_status: status,
  brood_pattern: "Solid", temperament: "Calm", disease_signs: "None", frames_brood: 6, frames_honey: 3, frames_stores: 2, inspector: null,
  trend: [{ date: "2026-10-10", mites: mites - 1, queenright_pct: 100 }, { date: "2026-10-20", mites, queenright_pct: 100 }],
});
const payload = () => ({
  from_date: "2026-08-05", to_date: "2026-10-28", unit: null, threshold: 3,
  kpis: { inspections: 4, colonies: 48, queenright_pct: 83.3, avg_mites: 3.2, avg_mites_prev: 2.1, mites_trend: 1.1, colonies_above_threshold: 12, groups_above_threshold: 1, disease_flags: 1 },
  series: [{ week: "2026-10-12", inspections: 2, colonies: 24, queenright_pct: 90, avg_mites: 2.5, disease_flags: 0 }, { week: "2026-10-19", inspections: 2, colonies: 24, queenright_pct: 80, avg_mites: 3.2, disease_flags: 1 }],
  groups: [group("Hive Group North", 4.2, "high", "queenright"), group("Hive Group South", 1.1, "ok", "weak")],
  rows: [{ name: "HIL-1", unit: "Hive Group North", unit_label: "Hive Group North", inspection_date: "2026-10-20", inspector: null, colonies_inspected: 12, colonies_queenright: 12,
    queen_seen: true, eggs_seen: true, brood_pattern: "Solid", temperament: "Calm", varroa_per_100: 4.2, mite_status: "high", disease_signs: "Chalkbrood",
    frames_brood: 6, frames_honey: 3, frames_stores: 2, feeding_kg: 0, actions: "Treatment planned" }],
  form: {
    units: [{ value: "Hive Group North", label: "Hive Group North", farm: "Mutara" }, { value: "Hive Group South", label: "Hive Group South", farm: "Mutara" }],
    employees: [{ value: "EMP-1", label: "Wanjiru Kamau" }], today: "2026-10-28", brood_patterns: ["Solid", "Patchy", "None"],
    temperaments: ["Calm", "Nervous", "Aggressive"], disease_options: ["None", "Chalkbrood"], threshold: 3,
  },
});

async function openDialog() {
  renderPage(<HiveInspections />);
  await screen.findByTestId("hg-card-Hive Group North");
  fireEvent.click(screen.getByRole("button", { name: /Record inspection/ }));
  return await screen.findByRole("dialog");
}

describe("HiveInspections", () => {
  beforeEach(() => {
    // recharts' ResponsiveContainer needs it; jsdom has none.
    vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
    get.mockReset().mockResolvedValue(payload() as never);
    save.mockReset().mockResolvedValue({ ok: true, name: "HIL-2", message: "ok" } as never);
  });

  it("draws KPIs, a health card per hive group and the log", async () => {
    renderPage(<HiveInspections />);
    const north = await screen.findByTestId("hg-card-Hive Group North");
    expect(within(north).getByTestId("hg-mites")).toHaveTextContent("4.2");
    expect(north).toHaveTextContent("Treat now");
    expect(north).toHaveTextContent("Queenright");
    const south = screen.getByTestId("hg-card-Hive Group South");
    expect(south).toHaveTextContent("Some queenless");
    expect(south).toHaveTextContent("Mites low");
    expect(screen.getByText("Average mite load")).toBeInTheDocument();
    expect(screen.getByText("Colonies over 3 mites")).toBeInTheDocument();
    const table = screen.getByTestId("inspection-table");
    expect(table).toHaveTextContent("Chalkbrood");
    expect(table).toHaveTextContent("Treatment planned");
  });

  it("shows an empty state with no inspections", async () => {
    get.mockResolvedValue({ ...payload(), rows: [], groups: [], series: [] } as never);
    renderPage(<HiveInspections />);
    expect(await screen.findByText(/No hive groups yet/)).toBeInTheDocument();
    expect(screen.getByText(/No inspections recorded yet/)).toBeInTheDocument();
  });

  it("validates before saving", async () => {
    const dialog = await openDialog();
    fireEvent.click(within(dialog).getByRole("button", { name: "Save inspection" }));
    expect(await within(dialog).findByText("Choose the hive group.")).toBeInTheDocument();
    expect(within(dialog).getByText(/Colonies inspected must be at least 1/)).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();

    fireEvent.change(within(dialog).getByLabelText("Colonies inspected"), { target: { value: "5" } });
    fireEvent.change(within(dialog).getByLabelText("Colonies queenright"), { target: { value: "7" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save inspection" }));
    expect(await within(dialog).findByText(/Queenright colonies cannot be more than/)).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();
  });

  it("previews the mite state and saves, then refreshes", async () => {
    get.mockResolvedValue(payload() as never);
    renderPage(<HiveInspections />);
    await screen.findByTestId("hg-card-Hive Group North");
    fireEvent.click(screen.getByRole("combobox", { name: "Hive group" }));
    fireEvent.click(await screen.findByRole("option", { name: "Hive Group North" }));
    await waitFor(() => expect(get).toHaveBeenLastCalledWith(expect.objectContaining({ unit: "Hive Group North" })));
    fireEvent.click(screen.getByRole("button", { name: /Record inspection/ }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Colonies inspected"), { target: { value: "10" } });
    fireEvent.change(within(dialog).getByLabelText("Colonies queenright"), { target: { value: "9" } });
    fireEvent.change(within(dialog).getByLabelText("Varroa mites per 100 bees"), { target: { value: "3.8" } });
    expect(within(dialog).getByTestId("hi-preview")).toHaveTextContent("90% queenright");
    expect(within(dialog).getByTestId("hi-preview")).toHaveTextContent("Treat now");
    const calls = get.mock.calls.length;
    fireEvent.click(within(dialog).getByRole("button", { name: "Save inspection" }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    expect(save).toHaveBeenCalledWith(expect.objectContaining({
      unit: "Hive Group North", colonies_inspected: 10, colonies_queenright: 9, varroa_per_100: 3.8, inspection_date: "2026-10-28",
    }));
    await waitFor(() => expect(get.mock.calls.length).toBeGreaterThan(calls));
    expect(await screen.findByText("Inspection saved.")).toBeInTheDocument();
  });

  it("shows the server's error as a toast and keeps the dialog open", async () => {
    save.mockResolvedValue({ error: "Colonies queenright must be between 0 and the colonies inspected." } as never);
    renderPage(<HiveInspections />);
    await screen.findByTestId("hg-card-Hive Group North");
    fireEvent.click(screen.getByRole("combobox", { name: "Hive group" }));
    fireEvent.click(await screen.findByRole("option", { name: "Hive Group South" }));
    await waitFor(() => expect(get).toHaveBeenLastCalledWith(expect.objectContaining({ unit: "Hive Group South" })));
    fireEvent.click(screen.getByRole("button", { name: /Record inspection/ }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Colonies inspected"), { target: { value: "4" } });
    fireEvent.change(within(dialog).getByLabelText("Colonies queenright"), { target: { value: "4" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save inspection" }));
    expect(await screen.findByText(/must be between 0 and the colonies inspected/)).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
});

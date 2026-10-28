import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/avocado-api", () => ({ getDryMatter: vi.fn(), saveDryMatter: vi.fn() }));
import { getDryMatter, saveDryMatter } from "@/lib/avocado-api";
import { DryMatter } from "@/pages/avocado/DryMatter";

const get = vi.mocked(getDryMatter);
const save = vi.mocked(saveDryMatter);

const blk = (block: string, state: string, dm: number | null) => ({
  block, farm: "Mutara", planting_year: 2018, state, dry_matter_pct: dm, short_pct: dm != null && dm < 24 ? +(24 - dm).toFixed(1) : 0,
  sample_date: dm != null ? "2026-10-12" : null, samples: dm != null ? 2 : 0, gain_pct_per_week: dm != null ? 0.8 : null, gain_basis: null,
  weeks_to_minimum: state === "rising" ? 3 : null, ready_date: null, sample_age_weeks: dm != null ? 2 : null,
  needs: state === "never_sampled" ? "A first dry matter test." : null, measured_on: dm != null ? "block" : null,
  trend: dm != null ? [{ date: "2026-09-28", dry_matter_pct: dm - 1.5, measured_on: "block" }, { date: "2026-10-12", dry_matter_pct: dm, measured_on: "block" }] : [],
});
const payload = () => ({
  farm: null, block: null, farms: ["Mutara"],
  form: {
    blocks: [{ block: "Block A", farm: "Mutara", planting_year: 2018 }, { block: "Block B", farm: "Mutara", planting_year: 2018 }],
    block_source: "Orchard Block", areas: ["23 Ha"],
    sizes: [{ count: 12, min_g: 400, max_g: 500 }, { count: 16, min_g: 300, max_g: 400 }],
    min_pct: 24, max_pct: 32, today: "2026-10-28", week_number: 44,
  },
  minimum_pct: 24, maximum_pct: 32,
  blocks: [blk("Block A", "rising", 22.5), blk("Block B", "never_sampled", null)],
  summary: { blocks: 2, ready: 0, rising: 1, stale: 0, never_sampled: 1 },
  recent_visits: [{ test_date: "2026-10-12", where: "Block A", measured_on: "block", week_number: 42, sizes: [], average_dry_matter: 22.5, ready: false }],
  units: {},
});

async function openDialog() {
  renderPage(<DryMatter />);
  await screen.findByTestId("dm-card-Block A");
  fireEvent.click(screen.getByRole("button", { name: /Record a sample/ }));
  return await screen.findByRole("dialog");
}

describe("DryMatter", () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue(payload() as never);
    save.mockReset().mockResolvedValue({ ok: true, saved: [{ name: "x", count_size: 12, dry_matter_pct: 25, ready: true }], skipped: [], average_dry_matter: 25, ready: 1, of: 1, verdict: "Ready to pick" } as never);
  });

  it("draws a card per block with its state, plus the visits table", async () => {
    renderPage(<DryMatter />);
    const a = await screen.findByTestId("dm-card-Block A");
    expect(a).toHaveTextContent("Rising");
    expect(a).toHaveTextContent("22.5%");
    expect(a).toHaveTextContent("1.5 points under the 24% floor");
    expect(within(a).getByTestId("dm-trend")).toBeInTheDocument();
    const b = screen.getByTestId("dm-card-Block B");
    expect(b).toHaveTextContent("Never sampled");
    expect(b).toHaveTextContent("A first dry matter test.");
    expect(screen.getByText("Earlier tests")).toBeInTheDocument();
  });

  it("validates before saving, with a live preview from the moisture", async () => {
    const dialog = await openDialog();
    fireEvent.click(within(dialog).getByRole("button", { name: "Save sample" }));
    expect(await within(dialog).findByText(/Name the block, or the planting area/)).toBeInTheDocument();
    expect(within(dialog).getByText(/Enter at least one moisture reading/)).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();

    fireEvent.change(within(dialog).getByLabelText("Moisture for count 12"), { target: { value: "0.75" } });
    expect(within(dialog).getByTestId("dm-verdict")).toHaveTextContent("Average 25.0% · 1 of 1 sizes at or above 24% · ready to pick");
  });

  it("saves an area test, then refreshes", async () => {
    const dialog = await openDialog();
    fireEvent.change(within(dialog).getByLabelText("Planting area"), { target: { value: "23 Ha" } });
    fireEvent.change(within(dialog).getByLabelText("Moisture for count 12"), { target: { value: "75" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save sample" }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({ planting_area: "23 Ha", week_number: 44, test_date: "2026-10-28", readings: [{ count_size: 12, moisture: "75" }] }),
    );
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("1 reading saved.")).toBeInTheDocument();
  });
});

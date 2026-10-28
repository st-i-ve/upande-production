import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";
import { FISH, feedingPage } from "./aquaculture-fixtures";

vi.mock("@/lib/aquaculture-api", () => ({ getFeedingMortality: vi.fn(), saveFeeding: vi.fn(), saveMortality: vi.fn() }));
import { getFeedingMortality, saveFeeding, saveMortality } from "@/lib/aquaculture-api";
import { Feeding } from "@/pages/aquaculture/Feeding";

const get = vi.mocked(getFeedingMortality);
const feed = vi.mocked(saveFeeding);
const dead = vi.mocked(saveMortality);
const render = () => renderPage(<Feeding />, {}, FISH);

describe("Feeding and mortality", () => {
  beforeEach(() => {
    vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
    get.mockReset().mockResolvedValue(feedingPage() as never);
    feed.mockReset().mockResolvedValue({ ok: true, name: "PFL-1" } as never);
    dead.mockReset().mockResolvedValue({ ok: true, name: "FML-1" } as never);
  });

  it("shows totals, per-pond cards, causes and both logs", async () => {
    render();
    const p4 = await screen.findByTestId("feed-pond-Pond 4");
    expect(p4).toHaveTextContent("5.69%");
    expect(p4).toHaveTextContent("Low DO");
    expect(screen.getByTestId("feed-pond-Pond 1")).toHaveTextContent("900 kg");
    expect(screen.getByText("Hardest hit")).toBeInTheDocument();
    expect(screen.getAllByText("Pond 4").length).toBeGreaterThan(1);
    expect(screen.getByText("Aerators were off")).toBeInTheDocument();
    expect(screen.getByText("Grower Pellet 4mm")).toBeInTheDocument();
    expect(screen.getByTestId("feed-mortality-chart")).toBeInTheDocument();
    expect(screen.getByTestId("causes-chart")).toBeInTheDocument();
  });

  it("refuses to feed a pond with no growing batch, then saves a valid feeding", async () => {
    render();
    await screen.findByTestId("feed-pond-Pond 1");
    fireEvent.click(screen.getByRole("button", { name: /Record feeding/ }));
    const d = await screen.findByRole("dialog");
    fireEvent.click(within(d).getByRole("button", { name: "Save feeding" }));
    expect(await within(d).findByText("Choose the pond.")).toBeInTheDocument();
    expect(within(d).getByText("Kilograms fed must be above zero.")).toBeInTheDocument();

    fireEvent.click(within(d).getByRole("combobox", { name: "Pond" }));
    fireEvent.click(await screen.findByRole("option", { name: "Pond 2" }));
    expect(await within(d).findByText(/no growing batch to feed/)).toBeInTheDocument();

    fireEvent.click(within(d).getByRole("combobox", { name: "Pond" }));
    fireEvent.click(await screen.findByRole("option", { name: "Pond 1" }));
    fireEvent.change(within(d).getByLabelText("Feed (kg)"), { target: { value: "25" } });
    fireEvent.click(within(d).getByRole("button", { name: "Save feeding" }));
    await waitFor(() => expect(feed).toHaveBeenCalledWith(expect.objectContaining({ pond: "Pond 1", kg_fed: 25 })));
  });

  it("validates and saves mortality with a cause", async () => {
    render();
    await screen.findByTestId("feed-pond-Pond 1");
    fireEvent.click(screen.getByRole("button", { name: /Record mortality/ }));
    const d = await screen.findByRole("dialog");
    fireEvent.click(within(d).getByRole("button", { name: "Save mortality" }));
    expect(await within(d).findByText(/whole number above zero/)).toBeInTheDocument();
    fireEvent.click(within(d).getByRole("combobox", { name: "Pond" }));
    fireEvent.click(await screen.findByRole("option", { name: "Pond 4" }));
    fireEvent.change(within(d).getByLabelText("Dead fish"), { target: { value: "12" } });
    fireEvent.click(within(d).getByRole("combobox", { name: "Cause" }));
    fireEvent.click(await screen.findByRole("option", { name: "Disease" }));
    fireEvent.click(within(d).getByRole("button", { name: "Save mortality" }));
    await waitFor(() => expect(dead).toHaveBeenCalledWith(expect.objectContaining({ pond: "Pond 4", dead_count: 12, cause: "Disease" })));
  });

  it("explains an empty period", async () => {
    get.mockResolvedValue({ ...feedingPage(), causes: [], feed_log: [], mortality_log: [] } as never);
    render();
    expect(await screen.findByText("No feeding recorded in this period.")).toBeInTheDocument();
    expect(screen.getAllByText("No deaths recorded in this period.").length).toBe(2);
  });
});

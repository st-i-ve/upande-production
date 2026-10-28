import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";
import { batchesPage, FISH } from "./aquaculture-fixtures";

vi.mock("@/lib/aquaculture-api", () => ({
  getPondBatches: vi.fn(), saveStocking: vi.fn(), saveSampling: vi.fn(), saveFishHarvest: vi.fn(),
}));
import { getPondBatches, saveFishHarvest, saveSampling, saveStocking } from "@/lib/aquaculture-api";
import { PondBatches } from "@/pages/aquaculture/PondBatches";

const get = vi.mocked(getPondBatches);
const stock = vi.mocked(saveStocking);
const sample = vi.mocked(saveSampling);
const harvest = vi.mocked(saveFishHarvest);
const render = () => renderPage(<PondBatches />, {}, FISH);

describe("PondBatches", () => {
  beforeEach(() => {
    vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
    get.mockReset().mockResolvedValue(batchesPage() as never);
    stock.mockReset().mockResolvedValue({ ok: true, name: "PST-9" } as never);
    sample.mockReset().mockResolvedValue({ ok: true, name: "FSL-1" } as never);
    harvest.mockReset().mockResolvedValue({ ok: true, name: "PST-1", status: "Harvested" } as never);
  });

  it("draws a card per batch with live count, FCR, survival and projection", async () => {
    render();
    const a = await screen.findByTestId("batch-card-Pond 1");
    expect(a).toHaveTextContent("7,784");
    expect(a).toHaveTextContent("97.3%");
    expect(a).toHaveTextContent("1.51");
    expect(a).toHaveTextContent("On track");
    expect(within(a).getByTestId("projection")).toHaveTextContent("Reaches 450 g around 12 Mar");
    expect(screen.getByTestId("batch-card-Pond 3")).toHaveTextContent("Harvested 22 Oct");
    expect(screen.getByTestId("batch-card-Pond 4")).toHaveTextContent("Behind target");
    expect(screen.getByTestId("batch-row-Pond 3")).toHaveTextContent("1.7 t");
    expect(screen.getByText("Fish alive")).toBeInTheDocument();
  });

  it("filters by status through the API", async () => {
    render();
    await screen.findByTestId("batch-card-Pond 1");
    fireEvent.click(screen.getByRole("combobox", { name: "Status" }));
    fireEvent.click(await screen.findByRole("option", { name: "Harvested" }));
    await waitFor(() => expect(get).toHaveBeenLastCalledWith({ status: "Harvested", unit: undefined }));
  });

  it("validates a new stocking, then saves it", async () => {
    render();
    await screen.findByTestId("batch-card-Pond 1");
    fireEvent.click(screen.getByRole("button", { name: /Stock a pond/ }));
    const d = await screen.findByRole("dialog");
    fireEvent.click(within(d).getByRole("button", { name: "Stock pond" }));
    expect(await within(d).findByText("Choose the pond to stock.")).toBeInTheDocument();
    expect(within(d).getByText(/Fingerlings count must be a whole number/)).toBeInTheDocument();
    expect(stock).not.toHaveBeenCalled();

    fireEvent.click(within(d).getByRole("combobox", { name: "Pond" }));
    fireEvent.click(await screen.findByRole("option", { name: "Pond 2" }));
    fireEvent.change(within(d).getByLabelText("Fingerlings stocked"), { target: { value: "5000" } });
    fireEvent.change(within(d).getByLabelText("Average weight (g)"), { target: { value: "5" } });
    fireEvent.click(within(d).getByRole("button", { name: "Stock pond" }));
    await waitFor(() => expect(stock).toHaveBeenCalledTimes(1));
    expect(stock.mock.calls[0][0]).toMatchObject({ pond: "Pond 2", species: "Tilapia", fingerlings_count: 5000, avg_weight_g: 5, target_harvest_weight_g: 450 });
    await waitFor(() => expect(get.mock.calls.length).toBeGreaterThan(1));
  });

  it("records a sample against the batch and refuses a harvest of more fish than are alive", async () => {
    render();
    const card = await screen.findByTestId("batch-card-Pond 1");
    fireEvent.click(within(card).getByRole("button", { name: "Record sample" }));
    const d = await screen.findByRole("dialog");
    fireEvent.click(within(d).getByRole("button", { name: "Save sample" }));
    expect(await within(d).findByText("Average weight must be above zero.")).toBeInTheDocument();
    fireEvent.change(within(d).getByLabelText("Average weight (g)"), { target: { value: "140" } });
    fireEvent.click(within(d).getByRole("button", { name: "Save sample" }));
    await waitFor(() => expect(sample).toHaveBeenCalledWith(expect.objectContaining({ pond: "Pond 1", stocking: "PST-1", avg_weight_g: 140, sample_size: 30 })));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

    fireEvent.click(within(await screen.findByTestId("batch-card-Pond 1")).getByRole("button", { name: "Record harvest" }));
    const h = await screen.findByRole("dialog");
    fireEvent.change(within(h).getByLabelText("Fish harvested"), { target: { value: "9000" } });
    fireEvent.change(within(h).getByLabelText("Weight (kg)"), { target: { value: "1200" } });
    fireEvent.click(within(h).getByRole("button", { name: "Save harvest" }));
    expect(await within(h).findByText("Only 7,784 fish are left in Pond 1.")).toBeInTheDocument();
    expect(harvest).not.toHaveBeenCalled();
  });

  it("shows an empty state when nothing is stocked", async () => {
    get.mockResolvedValue({ ...batchesPage(), batches: [] } as never);
    render();
    expect(await screen.findByText(/No pond has been stocked yet/)).toBeInTheDocument();
  });

  it("surfaces a server error as a toast", async () => {
    get.mockResolvedValue({ error: "You are not permitted." } as never);
    render();
    expect(await screen.findByText("You are not permitted.")).toBeInTheDocument();
  });
});

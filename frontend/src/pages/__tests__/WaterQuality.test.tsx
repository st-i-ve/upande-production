import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";
import { FISH, waterPage } from "./aquaculture-fixtures";

vi.mock("@/lib/aquaculture-api", () => ({ getWaterQuality: vi.fn(), saveWaterReading: vi.fn() }));
import { getWaterQuality, saveWaterReading } from "@/lib/aquaculture-api";
import { WaterQuality } from "@/pages/aquaculture/WaterQuality";

const get = vi.mocked(getWaterQuality);
const save = vi.mocked(saveWaterReading);
const render = () => renderPage(<WaterQuality />, {}, FISH);

describe("WaterQuality", () => {
  beforeEach(() => {
    vi.stubGlobal("ResizeObserver", class { observe() {} unobserve() {} disconnect() {} });
    get.mockReset().mockResolvedValue(waterPage() as never);
    save.mockReset().mockResolvedValue({ ok: true, name: "WQR-1", out_of_band: false, flags: "" } as never);
  });

  it("marks a pond out of band and lists the alert with the safe bands", async () => {
    render();
    const bad = await screen.findByTestId("water-card-Pond 4");
    expect(bad).toHaveTextContent("Out of band");
    expect(bad.querySelector('[data-bad="true"]')).toHaveTextContent("2.4");
    expect(screen.getByTestId("water-card-Pond 1")).toHaveTextContent("In band");
    expect(within(screen.getByTestId("alerts")).getByText("Dissolved oxygen 2.4 mg/L is under 4")).toBeInTheDocument();
    expect(screen.getByText(/oxygen at least 4 mg\/L/)).toBeInTheDocument();
    expect(screen.getByText("1 of 2")).toBeInTheDocument();
    expect(screen.getByTestId("do-chart")).toBeInTheDocument();
    expect(screen.getByTestId("temp-chart")).toBeInTheDocument();
  });

  it("asks for the period and pond, and clears them", async () => {
    render();
    await screen.findByTestId("water-card-Pond 1");
    expect(get.mock.calls[0][0]).toMatchObject({ unit: undefined });
    fireEvent.click(screen.getByRole("combobox", { name: "Pond" }));
    fireEvent.click(await screen.findByRole("option", { name: "Pond 4" }));
    await waitFor(() => expect(get).toHaveBeenLastCalledWith(expect.objectContaining({ unit: "Pond 4" })));
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    await waitFor(() => expect(get).toHaveBeenLastCalledWith(expect.objectContaining({ unit: undefined })));
  });

  it("validates a reading and warns about out-of-band values as they are typed", async () => {
    render();
    await screen.findByTestId("water-card-Pond 1");
    fireEvent.click(screen.getByRole("button", { name: /Record a reading/ }));
    const d = await screen.findByRole("dialog");
    fireEvent.click(within(d).getByRole("button", { name: "Save reading" }));
    expect(await within(d).findByText("Choose the pond.")).toBeInTheDocument();
    expect(within(d).getByText("Enter at least one measurement.")).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();

    fireEvent.change(within(d).getByLabelText("Dissolved oxygen (mg/L)"), { target: { value: "3.1" } });
    fireEvent.change(within(d).getByLabelText("Ammonia (mg/L)"), { target: { value: "0.5" } });
    const warn = within(d).getByTestId("band-warnings");
    expect(warn).toHaveTextContent("Dissolved oxygen 3.1 mg/L is outside the safe band (min 4)");
    expect(warn).toHaveTextContent("Ammonia 0.5 mg/L");

    fireEvent.click(within(d).getByRole("combobox", { name: "Pond" }));
    fireEvent.click(await screen.findByRole("option", { name: "Pond 4" }));
    fireEvent.click(within(d).getByRole("button", { name: "Save reading" }));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(save.mock.calls[0][0]).toMatchObject({ pond: "Pond 4", dissolved_oxygen_mg_l: 3.1, ammonia_mg_l: 0.5 });
    expect(save.mock.calls[0][0]).not.toHaveProperty("ph");
  });

  it("shows an empty alerts state", async () => {
    get.mockResolvedValue({ ...waterPage(), alerts: [] } as never);
    render();
    expect(await screen.findByText(/No alerts\. Every reading/)).toBeInTheDocument();
  });
});

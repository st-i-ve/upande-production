import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderPage } from "./helpers";

vi.mock("@/lib/machines-api", () => ({
  listMachines: vi.fn(),
  saveMachine: vi.fn(),
  machineLabels: vi.fn(),
  allocationForm: vi.fn(),
  scanMachine: vi.fn(),
  startAllocation: vi.fn(),
  closeAllocation: vi.fn(),
  submitAllocation: vi.fn(),
  listAllocations: vi.fn(),
}));
import { allocationForm, closeAllocation, listMachines, scanMachine, startAllocation } from "@/lib/machines-api";
import { Machines } from "@/pages/machines/Machines";
import { ScanMachine } from "@/pages/machines/ScanMachine";

const machine = (name: string, open = false) => ({
  name,
  machine_name: name,
  machine_type: "Tractor",
  asset: null,
  fuel_item: "Diesel",
  default_cost_center: "Main - MUT",
  qr_code: "AB12CD34EF",
  disabled: 0,
  last_latitude: 0.0612,
  last_longitude: 36.7531,
  last_seen_at: "2026-11-11 07:30:00",
  notes: null,
  has_position: true,
  open_allocation: open
    ? { name: "PAA-1", operator: "EMP-1", operator_name: "John Kamau", allocated_to: "Feedlot", reference_name: null, start_time: "2026-11-11 07:30:00", running_hours: 1.5 }
    : null,
});

const rights = { can_manage: true, can_allocate: true, can_submit: true };
const settings = { fuel_warehouse: null, feedlot_cost_center: "Feedlot - MUT" };

const form = () => ({
  ...rights,
  machines: [],
  employees: [{ value: "EMP-1", label: "John Kamau" }],
  me: "EMP-1",
  allocated_to: ["Feedlot", "Production Unit", "Silage Cycle", "Other"],
  reference_doctypes: { "Production Unit": "Production Unit" },
  references: { "Production Unit": [] },
  cost_centers: [],
  settings,
  now: "2026-11-11 09:00:00",
});

const allocation = (over: Record<string, unknown> = {}) => ({
  name: "PAA-1",
  machine: "Tractor 1",
  operator: "EMP-1",
  operator_name: "John Kamau",
  allocated_to: "Feedlot",
  status: "Open",
  docstatus: 0,
  start_time: "2026-11-11 09:00:00",
  end_time: null,
  duration_hours: 0,
  diesel_stock_entry: null,
  ...over,
});

describe("Machines", () => {
  beforeEach(() => {
    vi.mocked(listMachines).mockReset().mockResolvedValue({ ...rights, machines: [machine("Tractor 1", true), machine("Chopper")], machine_types: ["Tractor", "Chopper"], settings } as never);
  });

  it("lists machines with who has them and warns when no fuel warehouse is set", async () => {
    renderPage(<Machines />);
    const table = await screen.findByTestId("machine-table");
    expect(table).toHaveTextContent("Tractor 1");
    expect(table).toHaveTextContent("John Kamau");
    expect(table).toHaveTextContent("idle");
    expect(table).toHaveTextContent("AB12CD34EF");
    expect(screen.getByRole("status")).toHaveTextContent("No Fuel Warehouse");
    expect(screen.getByText("Print all labels")).toBeInTheDocument();
  });
});

describe("ScanMachine", () => {
  const getCurrentPosition = vi.fn();

  beforeEach(() => {
    getCurrentPosition.mockReset().mockImplementation((ok: (p: unknown) => void) => ok({ coords: { latitude: 0.0612, longitude: 36.7531, accuracy: 5 } }));
    Object.defineProperty(navigator, "geolocation", { value: { getCurrentPosition, watchPosition: vi.fn() }, configurable: true });
    vi.mocked(allocationForm).mockReset().mockResolvedValue(form() as never);
    vi.mocked(startAllocation).mockReset().mockResolvedValue({ ok: true, allocation: allocation() } as never);
    vi.mocked(closeAllocation).mockReset().mockResolvedValue({ ok: true, allocation: allocation({ status: "Posted", docstatus: 1, end_time: "2026-11-11 11:00:00", duration_hours: 2, diesel_stock_entry: "MAT-STE-1" }) } as never);
  });
  afterEach(() => {
    window.history.replaceState(null, "", "/");
  });

  it("does not read the location until a code is scanned, then reads it once and allocates with it", async () => {
    vi.mocked(scanMachine).mockReset().mockResolvedValue({ machine: machine("Tractor 1"), open_allocation: null } as never);
    renderPage(<ScanMachine />);
    await waitFor(() => expect(allocationForm).toHaveBeenCalled());
    expect(getCurrentPosition).not.toHaveBeenCalled();

    fireEvent.change(await screen.findByLabelText("Or type the code under the QR"), { target: { value: "ab12cd34ef" } });
    fireEvent.click(screen.getByRole("button", { name: /Find/ }));
    expect(await screen.findByText(/free\. Allocate it/)).toBeInTheDocument();
    expect(getCurrentPosition).toHaveBeenCalledTimes(1);
    expect(scanMachine).toHaveBeenCalledWith("AB12CD34EF");
    expect(screen.getByTestId("scan-position")).toHaveTextContent("0.06120, 36.75310");

    fireEvent.click(screen.getByRole("button", { name: "Allocate machine" }));
    await screen.findByTestId("scan-done");
    expect(startAllocation).toHaveBeenCalledWith(
      expect.objectContaining({ code: "AB12CD34EF", operator: "EMP-1", allocated_to: "Feedlot", latitude: 0.0612, longitude: 36.7531, accuracy: 5 }),
    );
    expect(getCurrentPosition).toHaveBeenCalledTimes(1);
    expect(navigator.geolocation.watchPosition).not.toHaveBeenCalled();
  });

  it("a label opened with the phone camera closes a running machine and posts its diesel", async () => {
    window.history.replaceState(null, "", "/production_app?machine=AB12CD34EF#/avocado/scan");
    vi.mocked(scanMachine).mockReset().mockResolvedValue({ machine: machine("Tractor 1", true), open_allocation: allocation({ running_hours: 2 }) } as never);
    renderPage(<ScanMachine />);
    expect(await screen.findByText(/Close it to stop the clock/)).toBeInTheDocument();
    expect(window.location.search).toBe("");
    expect(getCurrentPosition).toHaveBeenCalledTimes(1);
    fireEvent.change(screen.getByLabelText("Diesel used (litres)"), { target: { value: "35" } });
    fireEvent.click(screen.getByRole("button", { name: "Close and post diesel" }));
    await screen.findByTestId("scan-done");
    expect(closeAllocation).toHaveBeenCalledWith(expect.objectContaining({ code: "AB12CD34EF", diesel_litres: 35, submit: 1, latitude: 0.0612 }));
    expect(screen.getByTestId("scan-done")).toHaveTextContent("diesel issued from stock");
  });
});

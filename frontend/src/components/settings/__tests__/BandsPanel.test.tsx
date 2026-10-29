import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { BandsPanel } from "@/components/settings/BandsPanel";
import { ToastProvider } from "@/components/Toast";
import * as bands from "@/lib/bands";
import { BANDS } from "@/pages/__tests__/bands-fixtures";

vi.mock("@/lib/bands", async (orig) => ({ ...(await orig<typeof bands>()), getBands: vi.fn(), saveBands: vi.fn() }));
const get = vi.mocked(bands.getBands);
const save = vi.mocked(bands.saveBands);

const view = (canEdit: boolean) => render(<ToastProvider><BandsPanel canEdit={canEdit} /></ToastProvider>);

describe("BandsPanel", () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue(structuredClone(BANDS));
    save.mockReset().mockResolvedValue(structuredClone(BANDS));
  });

  it("lists every band set from the server", async () => {
    view(true);
    for (const set of Object.keys(BANDS)) expect(await screen.findByTestId(`band-set-${set}`)).toBeInTheDocument();
    expect(screen.getAllByLabelText("Queen status label").map((i) => (i as HTMLInputElement).value)).toEqual(["queenless", "weak", "queenright"]);
  });

  it("saves edited rows, an empty upper limit as no limit", async () => {
    view(true);
    const upTo = (await screen.findAllByLabelText("Fish survival up to"))[0];
    fireEvent.change(upTo, { target: { value: "85" } });
    fireEvent.click(screen.getByRole("button", { name: "Save bands" }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    const rows = save.mock.calls[0][0] as { band_set: string; max: number; min: number }[];
    const fish = rows.filter((r) => r.band_set === "Fish survival");
    expect(fish[0].max).toBe(85);
    expect(fish[1].max).toBe(0);
    expect(rows).toHaveLength(Object.values(BANDS).flat().length);
  });

  it("is read-only for people who cannot manage", async () => {
    view(false);
    expect((await screen.findAllByLabelText("Fish survival up to"))[0]).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Save bands" })).toBeNull();
  });
});

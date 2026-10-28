import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MapControlPanel } from "../MapControlPanel";
import { MapFloatingCard } from "../MapFloatingCard";
import { MapKpiPill } from "../MapKpiPill";
import { MapPanelDock } from "../MapPanelDock";
import { formatQty } from "@/lib/map-api";

describe("map panels", () => {
  it("closes the card with the button and Escape", () => {
    const onClose = vi.fn();
    render(<MapFloatingCard title="P1-B1" eyebrow="Pivot 1" onClose={onClose} />);
    fireEvent.click(screen.getByLabelText("Close card"));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("flows panels inside the dock instead of floating them", () => {
    render(
      <MapPanelDock>
        <MapControlPanel title="Legend">x</MapControlPanel>
        <MapFloatingCard title="T" onClose={() => {}} />
      </MapPanelDock>,
    );
    expect(screen.getByTestId("map-control-panel").className).toContain("relative");
    expect(screen.getByTestId("map-floating-card").className).not.toContain("absolute");
  });

  it("collapses a control panel and shows the KPI pill", () => {
    render(
      <>
        <MapKpiPill>16 blocks</MapKpiPill>
        <MapControlPanel title="Legend" count={3}>
          body
        </MapControlPanel>
      </>,
    );
    expect(screen.getByText("16 blocks")).toBeTruthy();
    expect(screen.getByText("body")).toBeTruthy();
    fireEvent.click(screen.getByText("Legend"));
    expect(screen.queryByText("body")).toBeNull();
  });

  it("formats remaining quantities", () => {
    expect(formatQty({ Bed: 120, Hectare: 2.5, Crate: 0 })).toBe("120 Bed · 2.5 Hectare");
    expect(formatQty({})).toBe("Nothing left");
  });
});

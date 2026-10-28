import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard } from "@/components/KpiCard";
import { flagCurrentWeek, seriesDelta } from "@/components/Sparkline";
import { PageShell } from "@/components/PageShell";
import { TogglePill } from "@/components/TogglePill";

describe("SCP primitives", () => {
  it("PageShell renders eyebrow, title and the toolbar slots", () => {
    render(
      <PageShell title="Weekly Plan" eyebrow="Avocado" tabs={<span>tabs</span>} actions={<button>go</button>}>
        <p>body</p>
      </PageShell>,
    );
    expect(screen.getByRole("heading", { name: "Weekly Plan" })).toBeInTheDocument();
    expect(screen.getByText("Avocado")).toBeInTheDocument();
    expect(screen.getByTestId("page-toolbar")).toHaveTextContent("tabs");
    expect(screen.getByText("go")).toBeInTheDocument();
    expect(screen.getByText("body")).toBeInTheDocument();
  });

  it("ClearFiltersPill shows only when active", () => {
    const onClear = vi.fn();
    const { rerender } = render(<ClearFiltersPill active={false} onClear={onClear} />);
    expect(screen.queryByText("Clear")).toBeNull();
    rerender(<ClearFiltersPill active onClear={onClear} />);
    fireEvent.click(screen.getByText("Clear"));
    expect(onClear).toHaveBeenCalled();
  });

  it("TogglePill reports the flipped state", () => {
    const onChange = vi.fn();
    render(<TogglePill pressed={false} onPressedChange={onChange}>Group</TogglePill>);
    fireEvent.click(screen.getByText("Group"));
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("FilterSelect accepts strings and {value,label} and names itself", () => {
    render(<FilterSelect label="Farm" value="" allLabel="All farms" options={["A", { value: "b", label: "Bee" }]} onChange={() => {}} />);
    expect(screen.getByRole("combobox", { name: "Farm" })).toBeInTheDocument();
  });

  it("KpiCard shows the figure with separators and a delta", () => {
    render(
      <KpiCard
        label="Done"
        value={12345}
        series={[{ week: "W1", value: 1 }, { week: "W2", value: 2 }, { week: "W3", value: 3 }]}
      />,
    );
    expect(screen.getByText("12,345")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-sparkline")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-delta")).toHaveAttribute("data-dir", "up");
  });

  const pts = (...v: number[]) => v.map((value, i) => ({ week: `W${i + 1}`, value }));

  it("hides the delta chip when there is no meaningful basis", () => {
    // previous value 0, flat series, a single point: nothing to compare
    expect(seriesDelta(pts(0, 5))).toBeNull();
    expect(seriesDelta(pts(0, 0, 0))).toBeNull();
    expect(seriesDelta(pts(4, 4, 4))).toBeNull();
    expect(seriesDelta(pts(7))).toBeNull();
    expect(seriesDelta(pts(2, 3))?.dir).toBe("up");
  });

  it("compares the last two COMPLETE weeks, skipping the running one", () => {
    const series = [...pts(10, 20), { week: "W3", value: 1, partial: true }];
    const d = seriesDelta(series)!;
    expect(d.dir).toBe("up");
    expect(d.pct).toBeCloseTo(100);
    expect(d.fullWeeks).toBe(true);
    // only one complete week behind the running one: no basis
    expect(seriesDelta([{ week: "W1", value: 5 }, { week: "W2", value: 1, partial: true }])).toBeNull();
  });

  it("flags only the point in the current ISO week (date or YYYY-Www label)", () => {
    const now = new Date(2026, 9, 28); // Wed 28 Oct 2026, ISO week 44
    const out = flagCurrentWeek(
      [{ week: "2026-10-19", value: 1 }, { week: "2026-10-26", value: 2 }, { week: "2026-W43", value: 3 }, { week: "2026-W44", value: 4 }],
      now,
    )!;
    expect(out.map((p) => !!p.partial)).toEqual([false, true, false, true]);
  });

  it("KpiCard shows no delta chip against a running week and no sparkline for a flat series", () => {
    const { rerender } = render(<KpiCard label="Costs" value={5} series={[{ week: "a", value: 0 }, { week: "b", value: 9 }, { week: "c", value: 1, partial: true }]} />);
    expect(screen.queryByTestId("kpi-delta")).toBeNull();
    rerender(<KpiCard label="Cycles" value={5} series={pts(3, 3, 3)} />);
    expect(screen.queryByTestId("kpi-sparkline")).toBeNull();
    rerender(<KpiCard label="Cycles" value={5} series={pts(3)} />);
    expect(screen.queryByTestId("kpi-sparkline")).toBeNull();
    rerender(<KpiCard label="Cycles" value={5} series={pts(3, 4, 5)} />);
    expect(screen.getByTestId("kpi-sparkline")).toBeInTheDocument();
  });

  it("KpiCard 'accent' tone uses the crop accent variable, and href makes it a link", () => {
    render(<KpiCard label="In harvest" value={2} tone="accent" href="#/avocado/approvals" />);
    expect(screen.getByText("2").className).toContain("--crop-accent");
    expect(screen.getByRole("link").getAttribute("href")).toBe("#/avocado/approvals");
  });
});

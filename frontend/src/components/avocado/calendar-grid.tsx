import { useState } from "react";
import type { BlockState, CalendarBlock, HarvestCalendar } from "@/lib/avocado-api";
import { cn } from "@/lib/utils";
import { cellFigure, dayMonth, fmtNum, fmtUnit, mondayOf, shadeColor, type CellUnit } from "./calendar-format";

const HATCH =
  "repeating-linear-gradient(135deg, rgba(10,10,10,0.13) 0 2px, transparent 2px 6px), var(--sd-bg-soft)";
const DOTS = "radial-gradient(rgba(10,10,10,0.28) 1px, transparent 1.4px) 0 0 / 6px 6px, var(--sd-card)";

const STATE_TONE: Record<BlockState, string> = {
  ready: "bg-[var(--sd-alert-ok)] text-[var(--sd-sev-moderate)]",
  waiting: "bg-[var(--sd-alert-warn)] text-[var(--sd-sev-high)]",
  last_season: "bg-[var(--sd-alert-info)] text-[var(--sd-muted)]",
  nodate: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
  unsampled: "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]",
};

export function Chip({ children, className, title, "data-testid": testId }: { children: React.ReactNode; className?: string; title?: string; "data-testid"?: string }) {
  return (
    <span
      title={title}
      data-testid={testId}
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-[var(--sd-radius-pill)] px-2 py-0.5 text-[11px] font-medium tabular-nums",
        className,
      )}
    >
      {children}
    </span>
  );
}

function BlockChips({ b, states, minimum }: { b: CalendarBlock; states: Record<BlockState, string>; minimum: number }) {
  return (
    <span className="mt-1 flex flex-wrap gap-1">
      <Chip className={STATE_TONE[b.state]} title={b.cohort_note || undefined}>
        {b.state === "waiting" && b.weeks_to_go != null
          ? `Ready in ${b.weeks_to_go} ${b.weeks_to_go === 1 ? "week" : "weeks"}`
          : (states[b.state] ?? b.state).replace(/\bN weeks?\b/, "a few weeks")}
      </Chip>
      {b.dry_matter_pct != null && (
        <Chip
          className="bg-[var(--sd-bg-soft)] text-[var(--sd-muted)]"
          title={b.cohort_note || `Dry matter ${b.dry_matter_pct}%, export minimum ${minimum}%`}
        >
          {b.dry_matter_pct.toFixed(1)}% DM
        </Chip>
      )}
      {b.state === "waiting" && b.ready_date && (
        <Chip className="bg-[var(--sd-bg-soft)] text-[var(--sd-muted)]">
          locked until {dayMonth(b.ready_date)}
        </Chip>
      )}
      {b.cohort_note && (
        <Chip className="bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]" title={b.cohort_note}>
          cohort
        </Chip>
      )}
      {b.stale && <Chip className="bg-[var(--sd-alert-warn)] text-[var(--sd-sev-high)]">stale</Chip>}
    </span>
  );
}

interface Tip {
  x: number;
  y: number;
  text: string;
}

export function CalendarGrid({
  data,
  unit,
  accent,
}: {
  data: HarvestCalendar;
  unit: CellUnit;
  accent: string;
}) {
  const [tip, setTip] = useState<Tip | null>(null);
  const thisWeek = mondayOf();
  const minimum = data.minimum_pct;
  const show = (e: React.MouseEvent | React.FocusEvent, text: string) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setTip({ x: r.left + r.width / 2, y: r.top, text });
  };

  if (!data.blocks.length || !data.weeks.length) {
    return (
      <p className="px-5 py-10 text-center text-[13px] text-[var(--sd-quiet)]">
        No weeks yet. A block needs a forecast in kilograms and a dry matter reading that dates its pick.
      </p>
    );
  }

  const stickyCell = "sticky left-0 z-[2] bg-[var(--sd-card)]";
  return (
    <div className="relative">
      <div className="max-h-[min(70vh,720px)] overflow-auto" data-testid="calendar-scroll">
        <table className="border-separate border-spacing-0 text-[12px]" data-testid="calendar-grid">
          <thead>
            <tr>
              <th
                className={cn(
                  stickyCell,
                  "top-0 z-[3] min-w-[250px] px-5 py-2 text-left text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--sd-quiet)] shadow-[0_1px_0_0_var(--sd-line)]",
                )}
              >
                Block
              </th>
              {data.weeks.map((w) => (
                <th
                  key={w.week}
                  data-today={w.week === thisWeek ? "true" : undefined}
                  className={cn(
                    "sticky top-0 z-[1] min-w-[46px] bg-[var(--sd-card)] px-1 py-2 text-center text-[11px] font-medium leading-tight shadow-[0_1px_0_0_var(--sd-line)]",
                    w.is_peak ? "text-foreground" : "text-[var(--sd-quiet)]",
                  )}
                >
                  <span className="block tabular-nums">{w.label}</span>
                  <span className="block text-[10px] font-normal opacity-70">W{w.iso_week}</span>
                  {w.week === thisWeek && (
                    <span
                      className="mx-auto mt-0.5 block h-1 w-1 rounded-full bg-foreground"
                      aria-label="This week"
                      title="This week"
                    />
                  )}
                </th>
              ))}
              <th className="sticky top-0 z-[1] min-w-[84px] bg-[var(--sd-card)] px-4 py-2 text-right text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--sd-quiet)] shadow-[0_1px_0_0_var(--sd-line)]">
                Total
              </th>
            </tr>
          </thead>
          <tbody>
            {data.blocks.map((b) => (
              <tr key={b.block} data-testid={`calendar-row-${b.block}`}>
                <th scope="row" className={cn(stickyCell, "border-b border-[var(--sd-line-soft)] px-5 py-2.5 text-left font-normal align-top")}>
                  <span className="block text-[13px] font-semibold text-foreground">{b.block}</span>
                  <span className="block text-[11.5px] text-[var(--sd-quiet)]">
                    {b.farm || "no farm"} · {b.planting_year ?? "no year"} · {fmtUnit(b.expected_kg, b.expected_kg / data.kg_per_crate, "tonnes")}
                  </span>
                  <BlockChips b={b} states={data.states} minimum={minimum} />
                </th>
                {b.cells.map((c, i) => {
                  const w = data.weeks[i];
                  const peak = w?.is_peak;
                  const base = "h-[46px] border-b border-[var(--sd-line-soft)] p-0.5 text-center align-middle tabular-nums";
                  const today = w?.week === thisWeek ? "border-x border-x-foreground/25" : "";
                  let style: React.CSSProperties | undefined;
                  let body: React.ReactNode = null;
                  let tipText = "";
                  let kind = c.kind;
                  if (kind === "fill" && c.kg <= 0) kind = "empty";
                  if (kind === "fill") {
                    style = { background: shadeColor(accent, c.shade) };
                    body = cellFigure(c.kg, c.crates, unit);
                    tipText = `${b.block} · week of ${dayMonth(c.week)} · ${fmtNum(c.kg)} kg · ${fmtNum(c.crates)} crates`;
                  } else if (kind === "locked") {
                    style = { background: HATCH };
                    tipText = `${b.block} is under ${minimum}% dry matter until about ${dayMonth(b.ready_date)}`;
                  } else if (kind === "no_sample") {
                    style = { background: DOTS };
                    tipText = `${b.block} has no dry matter reading, so no week can be given`;
                  }
                  return (
                    <td
                      key={c.week}
                      className={cn(base, today)}
                      onMouseEnter={tipText ? (e) => show(e, tipText) : undefined}
                      onMouseLeave={() => setTip(null)}
                    >
                      <div
                        data-testid={kind === "fill" ? "calendar-cell" : `calendar-cell-${kind}`}
                        data-shade={kind === "fill" ? c.shade : undefined}
                        data-peak={peak && kind === "fill" ? "true" : undefined}
                        aria-label={tipText || undefined}
                        className={cn(
                          "flex h-full w-full items-center justify-center rounded-md text-[11.5px] font-medium",
                          c.shade >= 4 ? "text-white" : "text-foreground",
                          peak && kind === "fill" && "ring-2 ring-foreground/70 ring-offset-1 ring-offset-[var(--sd-card)]",
                        )}
                        style={style}
                      >
                        {body}
                      </div>
                    </td>
                  );
                })}
                <td className="border-b border-[var(--sd-line-soft)] px-4 text-right text-[12.5px] font-semibold tabular-nums">
                  {b.row_kg ? (
                    fmtUnit(b.row_kg, b.row_crates, unit)
                  ) : (
                    <span className="font-normal text-[var(--sd-quiet)]">no date</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <th scope="row" className={cn(stickyCell, "bottom-0 px-5 py-3 text-left text-[12px] font-semibold uppercase tracking-[0.08em]")}>
                All blocks
              </th>
              {data.weeks.map((w) => (
                <td
                  key={w.week}
                  data-testid={w.is_peak ? "calendar-week-total-peak" : undefined}
                  className={cn(
                    "sticky bottom-0 bg-[var(--sd-card)] px-1 py-3 text-center text-[11.5px] font-semibold tabular-nums",
                    w.is_peak && "text-foreground underline decoration-2 underline-offset-4",
                    !w.kg && "font-normal text-[var(--sd-quiet)]",
                  )}
                  style={w.is_peak ? { textDecorationColor: accent } : undefined}
                >
                  {cellFigure(w.kg, w.crates, unit) || "–"}
                </td>
              ))}
              <td className="sticky bottom-0 bg-[var(--sd-card)] px-4 py-3 text-right text-[12.5px] font-semibold tabular-nums">
                {fmtUnit(data.summary.total_kg, data.summary.total_crates, unit)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
      {tip && (
        <div
          role="tooltip"
          className="pointer-events-none fixed z-50 -translate-x-1/2 -translate-y-full rounded-lg bg-foreground px-2.5 py-1.5 text-[11.5px] text-background shadow-[var(--sd-shadow-3)]"
          style={{ left: tip.x, top: tip.y - 6 }}
        >
          {tip.text}
        </div>
      )}
    </div>
  );
}

export function CalendarLegend({ accent, data, unit }: { accent: string; data: HarvestCalendar; unit: CellUnit }) {
  const item = "flex items-center gap-2";
  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-4 text-[12px] text-[var(--sd-muted)]">
      <div className={item}>
        <span>Less</span>
        <span className="flex gap-0.5">
          {[1, 2, 3, 4, 5].map((s) => (
            <i key={s} className="h-3.5 w-5 rounded-sm" style={{ background: shadeColor(accent, s) }} />
          ))}
        </span>
        <span>
          more fruit, cells in {unit}
          {data.max_cell_kg ? ` (max ${fmtNum(data.max_cell_kg / 1000, 1)} t)` : ""}
        </span>
      </div>
      <div className={item}>
        <i className="h-3.5 w-5 rounded-sm" style={{ background: HATCH }} />
        Locked, under {data.minimum_pct}% DM
      </div>
      <div className={item}>
        <i className="h-3.5 w-5 rounded-sm border border-[var(--sd-line)]" style={{ background: DOTS }} />
        Never sampled
      </div>
      <div className={item}>
        <i className="h-3.5 w-5 rounded-sm bg-white ring-2 ring-foreground/70" />
        Peak week
      </div>
      <div className={item}>
        <i className="h-1.5 w-1.5 rounded-full bg-foreground" />
        This week
      </div>
      <div>Weeks start Monday · 1 crate = {data.kg_per_crate} kg</div>
    </div>
  );
}

/** Scopes the "good" green of KpiCards inside it to the crop accent. */
export function AccentScope({ accent, className, children }: { accent: string; className?: string; children: React.ReactNode }) {
  return (
    <div className={className} style={{ "--sd-data-green": accent } as React.CSSProperties}>
      {children}
    </div>
  );
}

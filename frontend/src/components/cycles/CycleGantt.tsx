import { useMemo } from "react";
import type { Cycle } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { StatusPill } from "@/components/blocks/StatusPill";
import { StageChip } from "@/components/varieties/StageChip";

const DAY = 86400000;
const t = (ymd: string | null | undefined) => (ymd ? new Date(`${ymd.slice(0, 10)}T00:00:00`).getTime() : NaN);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Where a cycle's bar ends: its harvest window, else a quiet stub from the start. */
function endOf(c: Cycle): number {
  const bands = c.stage_bands ?? [];
  if (bands.length) return Math.max(...bands.map((b) => t(b.end)), t(c.expected_harvest_end) || 0);
  const e = t(c.expected_harvest_end);
  if (Number.isFinite(e)) return e;
  const h = t(c.expected_harvest_start);
  if (Number.isFinite(h)) return h + 30 * DAY;
  return t(c.start_date) + 60 * DAY;
}

/**
 * One row per cycle on a shared time axis: growing stage (tint) then harvest
 * window (accent), a line for today. The left column is sticky so the labels
 * stay put while the axis scrolls on a narrow screen.
 */
/** A diamond on the bar's row: hollow for expected, filled for actual (red when later than expected). */
function Marker({ at, pct, kind, late, title, testId }: { at: number; pct: (ms: number) => number; kind: "expected" | "actual"; late?: boolean; title: string; testId: string }) {
  if (!Number.isFinite(at)) return null;
  const colour = late ? "var(--sd-data-red)" : "var(--sd-ink)";
  return (
    <span
      data-testid={testId}
      data-late={late ? "true" : undefined}
      title={title}
      className="pointer-events-auto absolute top-[21px] z-[4] h-[10px] w-[10px] -translate-x-1/2 rotate-45 border-2"
      style={{ left: `${pct(at)}%`, borderColor: colour, background: kind === "actual" ? colour : "var(--sd-card)" }}
    />
  );
}

const RANK: Record<string, number> = { Harvesting: 0, Active: 1, Planned: 2, Closed: 3 };

export function CycleGantt({
  cycles,
  accent,
  unitLabel,
  preHarvestDays,
  onSelect,
}: {
  cycles: Cycle[];
  accent: string;
  unitLabel: string;
  /** Days before harvest in which some work (spraying) is forbidden; shaded on the bar. */
  preHarvestDays?: (c: Cycle) => number;
  onSelect?: (c: Cycle) => void;
}) {
  const today = useMemo(() => {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  }, []);

  const rows = useMemo(
    // Running cycles first (the ones a supervisor acts on), then planned, then closed; oldest start first within each.
    () =>
      cycles
        .filter((c) => Number.isFinite(t(c.start_date)))
        .sort((a, b) => (RANK[a.status] ?? 9) - (RANK[b.status] ?? 9) || t(a.start_date) - t(b.start_date)),
    [cycles],
  );
  const { lo, hi, months } = useMemo(() => {
    const starts = rows.map((c) => Math.min(t(c.start_date), ...(c.stage_bands ?? []).map((b) => t(b.start))));
    const ends = rows.map(endOf);
    const first = new Date(Math.min(...starts, today - 30 * DAY));
    const last = new Date(Math.max(...ends, today + 30 * DAY));
    const lo = new Date(first.getFullYear(), first.getMonth(), 1).getTime();
    const hi = new Date(last.getFullYear(), last.getMonth() + 1, 1).getTime();
    const months: { at: number; label: string }[] = [];
    for (let d = new Date(lo); d.getTime() < hi; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) {
      months.push({ at: d.getTime(), label: d.getMonth() === 0 || months.length === 0 ? `${MONTHS[d.getMonth()]} ${d.getFullYear()}` : MONTHS[d.getMonth()] });
    }
    return { lo, hi, months };
  }, [rows, today]);

  if (!rows.length) return null;
  const pct = (ms: number) => ((ms - lo) / (hi - lo)) * 100;
  const widthPx = Math.max(720, months.length * 64);

  return (
    <div className="overflow-x-auto rounded-[var(--sd-radius-lg)] border border-[var(--sd-line)]" data-testid="cycle-gantt">
      <div className="relative" style={{ minWidth: widthPx + 220 }}>
        <div className="flex border-b border-[var(--sd-line)] text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
          <div className="sticky left-0 z-10 w-[220px] shrink-0 bg-[var(--sd-card)] px-3 py-2.5">{unitLabel} · cycle</div>
          <div className="relative flex-1">
            {months.map((m) => (
              <div key={m.at} className="absolute top-0 bottom-0 border-l border-[var(--sd-line-soft)] py-2.5 pl-1.5 normal-case tracking-normal" style={{ left: `${pct(m.at)}%` }}>
                {m.label}
              </div>
            ))}
          </div>
        </div>
        {rows.map((c) => {
          const s = t(c.start_date);
          const hs = t(c.expected_harvest_start);
          const e = endOf(c);
          const closed = c.status === "Closed";
          const hasWindow = Number.isFinite(hs);
          const growEnd = hasWindow ? hs : e;
          const bands = c.stage_bands ?? [];
          const bar0 = bands.length ? Math.min(s, ...bands.map((b) => t(b.start))) : s;
          const harvestBand = bands.find((b) => !!Number(b.is_harvest));
          const harvestAt = harvestBand ? t(harvestBand.start) : hasWindow ? hs : NaN;
          const days = preHarvestDays?.(c) ?? 0;
          const flowerExp = t(c.expected_flowering_date);
          const flowerAct = t(c.actual_flowering_date);
          const harvestAct = t(c.actual_harvest_start);
          const flags = c.flags ?? [];
          const uproot = !!Number(c.due_for_uprooting);
          const shade: [number, number] | null = days > 0 && Number.isFinite(harvestAt) ? [harvestAt - days * DAY, harvestAt] : null;
          return (
            <div key={c.name} data-testid={`gantt-${c.name}`} className="flex border-b border-[var(--sd-line-soft)] last:border-0">
              <div className="sticky left-0 z-10 flex w-[220px] shrink-0 flex-col justify-center gap-0.5 bg-[var(--sd-card)] px-3 py-2">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  {/* Full names, wrapping if needed (SCP rule): never an ellipsis. */}
                  {onSelect ? (
                    <button type="button" className="min-w-0 break-words text-left text-[13px] font-medium text-[var(--sd-ink)] underline-offset-2 hover:underline" onClick={() => onSelect(c)}>
                      {c.unit}
                    </button>
                  ) : (
                    <span className="min-w-0 break-words text-[13px] font-medium text-[var(--sd-ink)]">{c.unit}</span>
                  )}
                  {(c.cycle_no ?? 1) > 1 && (
                    <span data-testid={`gantt-cycleno-${c.name}`} className="rounded-full bg-[var(--sd-bg-soft)] px-1.5 py-0.5 text-[10.5px] font-medium tabular-nums text-[var(--sd-muted)]">
                      Cycle {c.cycle_no}
                    </span>
                  )}
                  <StatusPill status={c.status} />
                  <StageChip stage={c.current_stage} accent={accent} />
                  {uproot && (
                    <span data-testid={`gantt-uproot-${c.name}`} className="rounded-full bg-[var(--sd-alert-warn)] px-2 py-0.5 text-[10.5px] font-medium text-[var(--sd-sev-high)]">
                      Due for uprooting
                    </span>
                  )}
                  {flags.length > 0 && (
                    <span data-testid={`gantt-flags-${c.name}`} title={flags.join("\n")} className="rounded-full bg-[var(--sd-alert-warn)] px-2 py-0.5 text-[10.5px] font-medium text-[var(--sd-sev-high)]">
                      {flags.length} {flags.length === 1 ? "flag" : "flags"}
                    </span>
                  )}
                </div>
                {flags.map((f) => (
                  <div key={f} className="break-words text-[11px] text-[var(--sd-sev-high)]">{f}</div>
                ))}
                <div className="break-words text-[11px] tabular-nums text-[var(--sd-quiet)]">
                  {c.variety ? <span>{c.variety} · </span> : c.item ? <span>{c.item} · </span> : null}
                  <span>{c.name}</span>
                </div>
              </div>
              <div className="relative min-h-[52px] flex-1">
                {months.map((m) => (
                  <div key={m.at} className="absolute top-0 bottom-0 border-l border-[var(--sd-line-soft)]" style={{ left: `${pct(m.at)}%` }} />
                ))}
                <div
                  className="absolute top-[17px] h-[18px] overflow-hidden rounded-full"
                  style={{ left: `${pct(bar0)}%`, width: `${Math.max(0.6, pct(e) - pct(bar0))}%` }}
                  title={`${c.item || c.title || c.name}: ${shortDate(c.start_date)}${hasWindow ? ` · harvest ${shortDate(c.expected_harvest_start)} to ${shortDate(c.expected_harvest_end)}` : ""}${c.protocol ? ` · ${c.protocol}` : ""}`}
                >
                  {bands.length ? (
                    bands.map((b, i) => {
                      const bs = t(b.start);
                      const be = t(b.end);
                      const harvest = !!Number(b.is_harvest);
                      return (
                        <div
                          key={`${b.stage}-${i}`}
                          data-testid={`gantt-band-${c.name}-${b.stage}`}
                          title={`${b.stage}: ${shortDate(b.start)} to ${shortDate(b.end)}${b.actual ? " (recorded)" : ""}`}
                          className="absolute inset-y-0 border-r border-[var(--sd-card)]"
                          style={{
                            left: `${((bs - bar0) / (e - bar0 || 1)) * 100}%`,
                            width: `${((be - bs) / (e - bar0 || 1)) * 100}%`,
                            background: closed ? (harvest ? "var(--sd-quiet)" : "var(--sd-line)") : accent,
                            opacity: closed ? 1 : harvest ? 1 : i % 2 ? 0.5 : 0.32,
                          }}
                        />
                      );
                    })
                  ) : (
                    <>
                      <div
                        className="absolute inset-y-0 left-0"
                        style={{ width: `${((growEnd - s) / (e - s || 1)) * 100}%`, background: closed ? "var(--sd-line)" : accent, opacity: closed ? 1 : 0.35 }}
                      />
                      {hasWindow && (
                        <div
                          className="absolute inset-y-0 right-0"
                          style={{ width: `${((e - hs) / (e - s || 1)) * 100}%`, background: closed ? "var(--sd-quiet)" : accent }}
                        />
                      )}
                    </>
                  )}
                </div>
                <Marker at={flowerExp} pct={pct} kind="expected" testId={`gantt-flower-expected-${c.name}`} title={`Flowering expected ${shortDate(c.expected_flowering_date)}`} />
                <Marker
                  at={flowerAct}
                  pct={pct}
                  kind="actual"
                  late={Number.isFinite(flowerExp) && flowerAct > flowerExp}
                  testId={`gantt-flower-actual-${c.name}`}
                  title={`Flowered ${shortDate(c.actual_flowering_date)}${Number.isFinite(flowerExp) && flowerAct > flowerExp ? ` (expected ${shortDate(c.expected_flowering_date)})` : ""}`}
                />
                <Marker
                  at={harvestAct}
                  pct={pct}
                  kind="actual"
                  late={hasWindow && harvestAct > hs}
                  testId={`gantt-harvest-actual-${c.name}`}
                  title={`Harvest began ${shortDate(c.actual_harvest_start)}${hasWindow ? ` (expected ${shortDate(c.expected_harvest_start)})` : ""}`}
                />
                {shade && (
                  <div
                    data-testid={`gantt-preharvest-${c.name}`}
                    title={`No spraying in the ${days} days before harvest`}
                    className="pointer-events-none absolute top-[13px] h-[26px] rounded-sm border border-dashed border-[var(--sd-amber)]"
                    style={{
                      left: `${pct(shade[0])}%`,
                      width: `${pct(shade[1]) - pct(shade[0])}%`,
                      background: "repeating-linear-gradient(135deg, rgba(180,83,9,0.22) 0 4px, transparent 4px 8px)",
                    }}
                  />
                )}
                {c.protocol && (
                  <span className={cn("pointer-events-none absolute top-[37px] text-[10px] text-[var(--sd-quiet)]")} style={{ left: `${pct(s)}%` }}>
                    {c.protocol}
                  </span>
                )}
              </div>
            </div>
          );
        })}
        <div
          data-testid="gantt-today"
          className="pointer-events-none absolute top-[38px] bottom-0 z-[5] w-[2px] bg-[var(--sd-data-red)]"
          style={{ left: `calc(220px + (100% - 220px) * ${pct(today) / 100} - 1px)` }}
        />
      </div>
      <div className="flex flex-wrap items-center gap-4 border-t border-[var(--sd-line)] px-3 py-2 text-[11.5px] text-[var(--sd-muted)]">
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-full" style={{ background: accent, opacity: 0.35 }} /> Growing</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-4 rounded-full" style={{ background: accent }} /> Harvest window</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-3 w-4 rounded-sm border border-dashed border-[var(--sd-amber)]" /> Pre-harvest window</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rotate-45 border-2 border-[var(--sd-ink)] bg-[var(--sd-card)]" /> Expected flowering</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rotate-45 bg-[var(--sd-ink)]" /> Recorded (red when late)</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-3 w-[2px] bg-[var(--sd-data-red)]" /> Today</span>
      </div>
    </div>
  );
}

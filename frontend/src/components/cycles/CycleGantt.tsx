import { useMemo } from "react";
import type { Cycle } from "@/lib/api";
import { shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { StatusPill } from "@/components/blocks/StatusPill";

const DAY = 86400000;
const t = (ymd: string | null | undefined) => (ymd ? new Date(`${ymd.slice(0, 10)}T00:00:00`).getTime() : NaN);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Where a cycle's bar ends: its harvest window, else a quiet stub from the start. */
function endOf(c: Cycle): number {
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
export function CycleGantt({ cycles, accent, unitLabel }: { cycles: Cycle[]; accent: string; unitLabel: string }) {
  const today = useMemo(() => {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  }, []);

  const rows = useMemo(
    () => cycles.filter((c) => Number.isFinite(t(c.start_date))).sort((a, b) => t(a.start_date) - t(b.start_date)),
    [cycles],
  );
  const { lo, hi, months } = useMemo(() => {
    const starts = rows.map((c) => t(c.start_date));
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
          return (
            <div key={c.name} data-testid={`gantt-${c.name}`} className="flex border-b border-[var(--sd-line-soft)] last:border-0">
              <div className="sticky left-0 z-10 flex w-[220px] shrink-0 flex-col justify-center gap-0.5 bg-[var(--sd-card)] px-3 py-2">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  {/* Full names, wrapping if needed (SCP rule): never an ellipsis. */}
                  <span className="min-w-0 break-words text-[13px] font-medium text-[var(--sd-ink)]">{c.unit}</span>
                  <StatusPill status={c.status} />
                </div>
                <div className="break-words text-[11px] tabular-nums text-[var(--sd-quiet)]">
                  {c.item ? <span>{c.item} · </span> : null}
                  <span>{c.name}</span>
                </div>
              </div>
              <div className="relative min-h-[52px] flex-1">
                {months.map((m) => (
                  <div key={m.at} className="absolute top-0 bottom-0 border-l border-[var(--sd-line-soft)]" style={{ left: `${pct(m.at)}%` }} />
                ))}
                <div
                  className="absolute top-[17px] h-[18px] overflow-hidden rounded-full"
                  style={{ left: `${pct(s)}%`, width: `${Math.max(0.6, pct(e) - pct(s))}%` }}
                  title={`${c.item || c.title || c.name}: ${shortDate(c.start_date)}${hasWindow ? ` · harvest ${shortDate(c.expected_harvest_start)} to ${shortDate(c.expected_harvest_end)}` : ""}${c.protocol ? ` · ${c.protocol}` : ""}`}
                >
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
                </div>
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
        <span className="inline-flex items-center gap-1.5"><span className="h-3 w-[2px] bg-[var(--sd-data-red)]" /> Today</span>
      </div>
    </div>
  );
}

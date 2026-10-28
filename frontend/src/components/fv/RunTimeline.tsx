import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import type { IrrigationPage } from "@/lib/fv-api";
import { dayMonth, fmtNum, hhmm, FAULT_COLOR } from "./fv-format";

const DAY = 86_400_000;

function ms(s: string): number {
  return new Date(s.replace(" ", "T")).getTime();
}

/** One lane per pivot, one bar per run positioned on the period's time axis. */
export function RunTimeline({ data, accent }: { data: IrrigationPage; accent: string }) {
  const start = new Date(data.from_date + "T00:00:00").getTime();
  const end = new Date(data.to_date + "T00:00:00").getTime() + DAY;
  const span = end - start;
  const ticks: number[] = [];
  for (let t = start; t < end; t += 7 * DAY) ticks.push(t);
  const lanes = data.pivots;
  return (
    <div data-testid="run-timeline" className="px-5 pb-5">
      <div className="relative ml-20 h-5 text-[11px] text-[var(--sd-quiet)]">
        {ticks.map((t) => (
          <span key={t} className="absolute -translate-x-0" style={{ left: `${((t - start) / span) * 100}%` }}>
            {dayMonth(new Date(t).toISOString())}
          </span>
        ))}
      </div>
      <div className="flex flex-col gap-2">
        {lanes.map((p) => {
          const runs = data.runs.filter((r) => r.unit === p.name);
          return (
            <div key={p.name} className="flex items-center gap-3" data-testid={`lane-${p.name}`}>
              <div className="w-[68px] shrink-0 text-[13px] font-medium">{p.name}</div>
              <div className="relative h-8 flex-1 rounded-lg bg-[var(--sd-line-soft)]">
                {ticks.map((t) => (
                  <span key={t} className="absolute top-0 h-full w-px bg-[var(--sd-line)]" style={{ left: `${((t - start) / span) * 100}%` }} />
                ))}
                {runs.map((r) => {
                  const a = Math.max(ms(r.start_time), start);
                  const b = Math.min(ms(r.end_time), end);
                  const faulty = !!r.fault && r.fault !== "None";
                  return (
                    <Tooltip key={r.name}>
                      <TooltipTrigger asChild>
                        <span
                          data-testid="run-bar"
                          className="absolute top-1 h-6 min-w-[4px] rounded-md"
                          style={{
                            left: `${((a - start) / span) * 100}%`,
                            width: `${Math.max(((b - a) / span) * 100, 0.4)}%`,
                            background: faulty ? FAULT_COLOR[r.fault as string] ?? "#c0392b" : accent,
                            opacity: faulty ? 1 : 0.85,
                          }}
                        />
                      </TooltipTrigger>
                      <TooltipContent>
                        <div className="text-[12px]">
                          <div className="font-medium">
                            {dayMonth(r.start_time)} {hhmm(r.start_time)} to {hhmm(r.end_time)} · {fmtNum(r.hours, 1)} h
                          </div>
                          <div>
                            {fmtNum(r.depth_mm, 1)} mm · {r.slices.length ? r.slices.join(", ") : "all slices"}
                          </div>
                          {faulty && <div>{r.fault}</div>}
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

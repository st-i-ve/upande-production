import { AlertTriangle } from "lucide-react";
import type { FaultRow } from "@/lib/fv-api";
import { dayMonth, fmtNum, hhmm, FAULT_COLOR } from "./fv-format";

export function FaultList({ faults }: { faults: FaultRow[] }) {
  if (!faults.length) {
    return (
      <div className="px-5 pb-6 text-[13px] text-[var(--sd-quiet)]" data-testid="no-faults">
        No faults in this period. Every run completed.
      </div>
    );
  }
  return (
    <ul className="flex flex-col divide-y divide-[var(--sd-line-soft)] px-5 pb-3" data-testid="fault-list">
      {faults.map((f) => (
        <li key={f.name} className="flex gap-3 py-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: FAULT_COLOR[f.fault] ?? "#c0392b" }} />
          <div className="min-w-0 text-[13px]">
            <div className="font-medium">
              {f.fault} · {f.pivot}
            </div>
            <div className="text-[var(--sd-quiet)]">
              {dayMonth(f.start_time)} {hhmm(f.start_time)} · ran {fmtNum(f.hours, 1)} h, {fmtNum(f.depth_mm, 1)} mm
              {f.operator ? ` · ${f.operator}` : ""}
            </div>
            {f.notes && <div className="mt-0.5">{f.notes.replace("[fv-seed]", "").trim()}</div>}
          </div>
        </li>
      ))}
    </ul>
  );
}

import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { VarietyStage } from "@/lib/varieties-api";
import { cn } from "@/lib/utils";

export interface StageDraft {
  key: string;
  stage: string;
  start_day: string;
  length_days: string;
  is_harvest: boolean;
}

let seq = 0;
export const newStageKey = () => `s${++seq}`;

export const toStageDrafts = (stages: VarietyStage[] = []): StageDraft[] =>
  stages.map((s) => ({
    key: newStageKey(),
    stage: s.stage,
    start_day: String(s.start_day ?? 0),
    length_days: String(s.length_days ?? 0),
    is_harvest: !!Number(s.is_harvest),
  }));

export const fromStageDrafts = (rows: StageDraft[]): VarietyStage[] =>
  rows.map((r) => ({
    stage: r.stage.trim(),
    start_day: Number(r.start_day) || 0,
    length_days: Number(r.length_days) || 0,
    is_harvest: r.is_harvest ? 1 : 0,
  }));

/** The first problem with the stage list, or null when it can be saved. */
export function stageProblem(rows: StageDraft[]): string | null {
  const seen = new Set<string>();
  for (const r of rows) {
    const name = r.stage.trim();
    if (!name) return "Every stage needs a name.";
    if (seen.has(name.toLowerCase())) return `Stage ${name} is listed twice.`;
    seen.add(name.toLowerCase());
    if (!(Number(r.length_days) > 0)) return `Stage ${name} needs a length of at least 1 day.`;
    if (!(Number(r.start_day) >= 0)) return `Stage ${name} cannot start before day 0.`;
  }
  if (rows.filter((r) => r.is_harvest).length > 1) return "Only one stage can be the harvest stage.";
  return null;
}

/** Horizontal bars from start_day for length_days; the harvest stage in the accent colour. */
export function StageTimeline({ stages, accent, compact }: { stages: VarietyStage[]; accent: string; compact?: boolean }) {
  const rows = stages.filter((s) => s.stage && Number(s.length_days) > 0);
  if (!rows.length) return null;
  const total = Math.max(...rows.map((s) => Number(s.start_day) + Number(s.length_days)), 1);
  return (
    <div data-testid="stage-timeline" className="flex flex-col gap-1">
      {rows.map((s, i) => {
        const left = (Number(s.start_day) / total) * 100;
        const width = Math.max((Number(s.length_days) / total) * 100, 1.5);
        const harvest = !!Number(s.is_harvest);
        return (
          <div key={`${s.stage}-${i}`} className="flex items-center gap-2" data-testid={`stage-bar-${s.stage}`}>
            <span className={cn("shrink-0 break-words text-[12px] text-[var(--sd-muted)]", compact ? "w-28" : "w-36")}>{s.stage}</span>
            <div className="relative h-4 flex-1 rounded-full bg-[var(--sd-bg-soft)]">
              <div
                className="absolute inset-y-0 rounded-full"
                style={{ left: `${left}%`, width: `${width}%`, background: accent, opacity: harvest ? 1 : 0.4 }}
                title={`${s.stage}: day ${s.start_day} to ${Number(s.start_day) + Number(s.length_days)}${harvest ? " (harvest)" : ""}`}
              />
            </div>
            <span className="w-24 shrink-0 text-right text-[11.5px] tabular-nums text-[var(--sd-quiet)]">
              d{s.start_day}–{Number(s.start_day) + Number(s.length_days)}
              {harvest ? " · harvest" : ""}
            </span>
          </div>
        );
      })}
    </div>
  );
}

const NUM = "h-8 w-20 tabular-nums";

/** Timeline preview plus editable stage rows; the harvest stage is marked with a toggle. */
export function StageEditor({
  rows,
  onChange,
  accent,
  disabled,
}: {
  rows: StageDraft[];
  onChange: (rows: StageDraft[]) => void;
  accent: string;
  disabled?: boolean;
}) {
  const patch = (key: string, p: Partial<StageDraft>) => onChange(rows.map((r) => (r.key === key ? { ...r, ...p } : r)));
  const problem = stageProblem(rows);
  return (
    <div className="flex flex-col gap-3" data-testid="stage-editor">
      <StageTimeline stages={fromStageDrafts(rows)} accent={accent} compact />
      <div className="flex flex-col gap-2">
        {rows.map((r, i) => (
          <div key={r.key} className="flex flex-wrap items-center gap-2" data-testid="stage-row">
            <Input
              aria-label={`Stage ${i + 1} name`}
              placeholder="Stage name"
              className="h-8 min-w-[9rem] flex-1"
              value={r.stage}
              disabled={disabled}
              onChange={(e) => patch(r.key, { stage: e.target.value })}
            />
            <Input
              aria-label={`Stage ${i + 1} start day`}
              inputMode="numeric"
              placeholder="Start day"
              className={NUM}
              value={r.start_day}
              disabled={disabled}
              onChange={(e) => patch(r.key, { start_day: e.target.value })}
            />
            <Input
              aria-label={`Stage ${i + 1} length in days`}
              inputMode="numeric"
              placeholder="Days"
              className={NUM}
              value={r.length_days}
              disabled={disabled}
              onChange={(e) => patch(r.key, { length_days: e.target.value })}
            />
            <button
              type="button"
              role="switch"
              aria-checked={r.is_harvest}
              aria-label={`Stage ${i + 1} is the harvest stage`}
              disabled={disabled}
              onClick={() => onChange(rows.map((x) => ({ ...x, is_harvest: x.key === r.key ? !r.is_harvest : false })))}
              className={cn(
                "h-8 rounded-full px-3 text-[12px] font-medium transition-colors",
                r.is_harvest ? "bg-[var(--sd-alert-ok)] text-[var(--sd-sev-moderate)]" : "bg-[var(--sd-bg-soft)] text-[var(--sd-muted)]",
              )}
            >
              {r.is_harvest ? "Harvest" : "Mark harvest"}
            </button>
            <button
              type="button"
              aria-label={`Remove stage ${i + 1}`}
              disabled={disabled}
              className="rounded-full p-1 text-[var(--sd-quiet)] hover:text-[var(--sd-sev-critical)]"
              onClick={() => onChange(rows.filter((x) => x.key !== r.key))}
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between gap-3">
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => {
            const last = rows[rows.length - 1];
            const start = last ? Number(last.start_day || 0) + Number(last.length_days || 0) : 0;
            onChange([...rows, { key: newStageKey(), stage: "", start_day: String(start), length_days: "", is_harvest: false }]);
          }}
        >
          <Plus className="h-3.5 w-3.5" /> Add stage
        </Button>
        {problem && rows.length > 0 && <span role="alert" className="text-[12px] text-[var(--sd-amber)]">{problem}</span>}
      </div>
    </div>
  );
}

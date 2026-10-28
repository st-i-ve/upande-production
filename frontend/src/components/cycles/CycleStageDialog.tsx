import { useCallback, useEffect, useState } from "react";
import { DatePicker } from "@/components/DatePicker";
import { useToast } from "@/components/Toast";
import { StageChip } from "@/components/varieties/StageChip";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import type { Cycle } from "@/lib/api";
import { isError } from "@/lib/frappe";
import { shortDate } from "@/lib/format";
import { getCycleStages, setStageActual, type CycleStage } from "@/lib/varieties-api";
import { todayISO } from "@/lib/utils";

/**
 * A cycle's growth stages with their dates, and (for supervisors) the date a stage really began.
 * Recording one moves that stage and every later one by the same shift.
 */
export function CycleStageDialog({
  cycle,
  accent,
  canRecord,
  onClose,
  onChanged,
}: {
  cycle: Cycle;
  accent: string;
  canRecord: boolean;
  onClose: () => void;
  onChanged: () => void;
}) {
  const toast = useToast();
  const [stages, setStages] = useState<CycleStage[] | null>(null);
  const [current, setCurrent] = useState<string | null>(cycle.current_stage ?? null);
  const [stage, setStage] = useState("");
  const [date, setDate] = useState(todayISO());
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const r = await getCycleStages(cycle.name);
    if (isError(r)) {
      toast(r.error, "error");
      setStages([]);
      return;
    }
    setStages(r.stages);
    setCurrent(r.current_stage);
  }, [cycle.name, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  async function record(clear = false) {
    setBusy(true);
    const r = await setStageActual(cycle.name, stage, clear ? null : date);
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(clear ? `${stage} date cleared.` : `${stage} recorded as started ${shortDate(date)}.`);
    onChanged();
    await load();
  }

  const chosen = stages?.find((s) => s.stage === stage);

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-lg" aria-describedby="stage-desc">
        <DialogHeader>
          <DialogTitle>{cycle.unit} · {cycle.variety || cycle.item || cycle.name}</DialogTitle>
          <DialogDescription id="stage-desc">
            Growth stages of cycle {cycle.name}. {cycle.variety ? "" : "This cycle has no variety, so it has no stages."}
          </DialogDescription>
        </DialogHeader>
        <div className="flex items-center gap-2 text-[13px] text-[var(--sd-muted)]">
          Now: {current ? <StageChip stage={current} accent={accent} /> : "no stage"}
        </div>
        <ul className="divide-y divide-[var(--sd-line-soft)] rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] px-3.5 shadow-[var(--sd-shadow-inset)]" data-testid="cycle-stages">
          {(stages ?? []).map((s) => (
            <li key={s.stage} className="flex items-center gap-3 py-2 text-[13px] tabular-nums">
              <span className="min-w-0 flex-1 break-words text-[var(--sd-ink)]">{s.stage}{s.is_harvest ? " (harvest)" : ""}</span>
              <span className="text-[var(--sd-muted)]">{shortDate(s.start)} – {shortDate(s.end)}</span>
              {s.actual && <span className="rounded-full bg-[var(--sd-alert-ok)] px-2 py-0.5 text-[11px] font-medium text-[var(--sd-sev-moderate)]">Recorded</span>}
            </li>
          ))}
          {stages && stages.length === 0 && <li className="py-2 text-[13px] text-[var(--sd-quiet)]">No stages.</li>}
        </ul>
        {canRecord && !!stages?.length && (
          <div className="flex flex-col gap-3">
            <Label>Record when a stage began</Label>
            <div className="flex flex-wrap items-center gap-2">
              <div className="min-w-[10rem] flex-1">
                <Picker label="Stage" value={stage} onChange={setStage} options={stages.map((s) => s.stage)} placeholder="Choose a stage" />
              </div>
              <DatePicker value={date} onChange={setDate} aria-label="Stage start date" />
              <Button onClick={() => void record()} disabled={busy || !stage || !date}>
                {busy ? "Saving…" : "Record"}
              </Button>
              {chosen?.actual && (
                <Button variant="outline" onClick={() => void record(true)} disabled={busy}>
                  Clear
                </Button>
              )}
            </div>
          </div>
        )}
        <div className="flex justify-end">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

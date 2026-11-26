import { useEffect, useState } from "react";
import { DatePicker } from "@/components/DatePicker";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { CLEAR_REASONS, clearBlock, clearBlockPreview, type ClearPreview, type ClearPreviewCycle } from "@/lib/cycle-setup-api";
import { isError } from "@/lib/frappe";
import { cn, todayISO } from "@/lib/utils";

const label = (c: ClearPreviewCycle) => [c.name, c.variety || c.title].filter(Boolean).join(" · ");
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

function Group({ title, items }: { title: string; items: ClearPreviewCycle[] }) {
  if (!items.length) return null;
  return (
    <div>
      <p className="text-[12px] font-medium text-[var(--sd-muted)]">{title}</p>
      <ul className="text-[13px] text-[var(--sd-ink)]">
        {items.map((c) => (
          <li key={c.name}>{label(c)}</li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Clear a block: close its running cycles, remove or close the planned ones, skip their open tasks and mark the
 * block Fallow. A manager clears at once; anyone else sends a request for a manager to decide.
 */
export function ClearBlockDialog({
  unit,
  isManager,
  onClose,
  onDone,
}: {
  unit: string;
  isManager: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [date, setDate] = useState(todayISO());
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<ClearPreview | null>(null);

  useEffect(() => {
    let live = true;
    setPreview(null);
    void clearBlockPreview(unit, date).then((r) => {
      if (!live) return;
      if (isError(r)) toast(r.error, "error");
      else setPreview(r as ClearPreview);
    });
    return () => {
      live = false;
    };
  }, [unit, date, toast]);

  const earliest = preview?.earliest_start ?? undefined;
  const dateOk = !!date && date <= todayISO() && (!earliest || date >= earliest);
  const ok = !!preview && dateOk && !!reason && (reason !== "Other" || !!note.trim()) && !busy;

  async function go() {
    setBusy(true);
    const r = await clearBlock(unit, date, reason, note.trim() || undefined);
    setBusy(false);
    const err = (r as { error?: string }).error;
    if (err) {
      toast(err, "error");
      return;
    }
    toast(isManager ? `${unit} cleared. It is now fallow.` : "Sent to a manager for approval");
    onDone();
    onClose();
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Clear block {unit}</DialogTitle>
          <DialogDescription>
            {isManager
              ? "Closes what is running, removes what was planned and leaves the block fallow."
              : "A manager decides whether the block is cleared. It stays as it is until then."}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="cb-date">Cleared on</Label>
          <DatePicker id="cb-date" value={date} onChange={setDate} max={todayISO()} min={earliest} aria-label="Cleared on" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Reason</Label>
          <div className="flex flex-wrap gap-2">
            {CLEAR_REASONS.map((r) => (
              <button
                key={r}
                type="button"
                aria-pressed={reason === r}
                onClick={() => setReason(r)}
                className={cn(
                  "rounded-full px-3 py-1 text-[12.5px] ring-1 ring-[var(--sd-line)]",
                  reason === r ? "bg-[var(--sd-ink)] text-[var(--sd-card)]" : "bg-[var(--sd-card)] text-[var(--sd-muted)]",
                )}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="cb-note">Note</Label>
          <Textarea id="cb-note" value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder={reason === "Other" ? "Required" : "Optional"} />
        </div>
        <div data-testid="clear-preview" className="flex flex-col gap-2 rounded-[var(--sd-radius-md)] bg-[var(--sd-bg-soft)] px-3 py-2">
          {!preview ? (
            <p className="text-[13px] text-[var(--sd-muted)]">Checking what this will change…</p>
          ) : (
            <>
              <Group title={`Cycles to close (${preview.cycles.length})`} items={preview.cycles} />
              <Group title={`Planned cycles (${preview.planned.length}): removed, or closed if they have records`} items={preview.planned} />
              {!preview.cycles.length && !preview.planned.length && <p className="text-[13px] text-[var(--sd-muted)]">No cycles on this block.</p>}
              <p className="text-[13px] text-[var(--sd-ink)]">{plural(preview.tasks_skipped, "open task")} will be skipped.</p>
            </>
          )}
        </div>
        {!dateOk && !!preview && <p className="text-[12px] text-[var(--sd-sev-high)]">Pick a day {earliest ? `from ${earliest} ` : ""}up to today.</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => void go()} disabled={!ok}>
            {busy ? "Working…" : isManager ? "Clear block" : "Send clear request"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

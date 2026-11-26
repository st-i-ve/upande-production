import { useRef, useState } from "react";
import { Paperclip, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { rowDate } from "@/components/plan/fmt";
import { logTaskProgress, type PlanTask, type ProgressLog } from "@/lib/api";
import { isError, uploadFile } from "@/lib/frappe";
import { num } from "@/lib/utils";

/**
 * Log progress on a task: a note, the quantity done today, and photos or files.
 * At least one of the three is needed. Files go up as private files first; the
 * log carries their URLs. A task can be logged any number of times a day.
 */
export function LogProgressDialog({
  plan,
  task,
  onClose,
  onLogged,
}: {
  plan: string;
  task: PlanTask;
  onClose: () => void;
  onLogged: (log: ProgressLog) => void;
}) {
  const [notes, setNotes] = useState("");
  const [qty, setQty] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  // Uploaded URLs stay with their File, so a retry after a failure does not upload again.
  const uploaded = useRef(new Map<File, string>());
  const picker = useRef<HTMLInputElement>(null);
  const uom = task.uom ?? "";
  const qtyNum = num(qty);
  const badQty = qty.trim() !== "" && !(qtyNum >= 0);
  const ready = (notes.trim() !== "" || qtyNum > 0 || files.length > 0) && !badQty;

  async function save() {
    setBusy(true);
    setFailure(null);
    const urls: string[] = [];
    for (const f of files) {
      let url = uploaded.current.get(f);
      if (!url) {
        const up = await uploadFile(f, true);
        if ("error" in up) {
          setBusy(false);
          setFailure(`${f.name}: ${up.error}`);
          return;
        }
        url = up.file_url;
        uploaded.current.set(f, url);
      }
      urls.push(url);
    }
    const r = await logTaskProgress(plan, task.name as string, notes.trim(), qtyNum > 0 ? qtyNum : null, urls);
    setBusy(false);
    if (isError(r)) {
      setFailure(r.error);
      return;
    }
    onLogged(r as ProgressLog);
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-md" aria-describedby="log-progress-desc">
        <DialogHeader>
          <DialogTitle>Log progress</DialogTitle>
          <DialogDescription id="log-progress-desc">
            {task.operation_name} · due {rowDate(task.due_date)}
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="progress-notes">Notes</Label>
          <Textarea id="progress-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="What was done, what is left" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="progress-qty">{`Quantity${uom ? ` (${uom})` : ""}`}</Label>
          <Input
            id="progress-qty"
            inputMode="decimal"
            className="w-32 tabular-nums"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            placeholder={uom || "Qty"}
          />
          {badQty && <p className="text-[12px] text-[var(--sd-amber)]">Quantity cannot be negative.</p>}
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="progress-files">Attach files</Label>
          <input
            ref={picker}
            id="progress-files"
            type="file"
            multiple
            accept="image/*,application/pdf"
            className="text-[13px] text-[var(--sd-muted)]"
            onChange={(e) => {
              const picked = Array.from(e.target.files ?? []);
              if (picked.length) setFiles((all) => [...all, ...picked]);
              if (picker.current) picker.current.value = "";
            }}
          />
          {files.length > 0 && (
            <ul className="flex flex-col gap-1">
              {files.map((f, i) => (
                <li key={`${f.name}-${i}`} className="flex items-center gap-2 text-[12.5px] text-[var(--sd-ink)]">
                  <Paperclip className="size-3.5 text-[var(--sd-muted)]" aria-hidden />
                  <span className="min-w-0 flex-1 truncate">{f.name}</span>
                  <button
                    type="button"
                    aria-label={`Remove ${f.name}`}
                    className="rounded-full p-1 text-[var(--sd-quiet)] hover:text-[var(--sd-sev-critical)]"
                    onClick={() => setFiles((all) => all.filter((_, j) => j !== i))}
                  >
                    <X className="size-3.5" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {failure && (
          <p role="alert" className="rounded-[var(--sd-radius)] bg-[var(--sd-alert-error)] px-3 py-2 text-[13px] text-[var(--sd-ink)]">
            {failure}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => void save()} disabled={busy || !ready}>
            {busy ? "Saving…" : "Log progress"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

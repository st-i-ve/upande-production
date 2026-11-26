import { useDialogDraft } from "@/hooks/useDialogDraft";
import { DraftBar } from "@/components/DraftBar";
import { useState } from "react";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Cycle } from "@/lib/api";
import { deleteCycle } from "@/lib/cycle-setup-api";

/**
 * Delete a cycle. A manager confirms and it goes; anyone else gives a reason and sends a delete request for a
 * manager to decide. A cycle with records against it cannot be deleted (the server says so).
 */
export function DeleteCycleDialog({
  cycle,
  isManager,
  onClose,
  onDone,
}: {
  cycle: Cycle;
  isManager: boolean;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const draft = useDialogDraft({ key: `delete-cycle:${cycle.name}`, open: true, value: reason, setValue: setReason, enabled: !isManager });
  const ok = (isManager || reason.trim().length > 0) && !busy;

  async function go() {
    setBusy(true);
    const r = await deleteCycle(cycle.name, isManager ? undefined : reason.trim());
    setBusy(false);
    const err = (r as { error?: string }).error;
    if (err) {
      toast(err, "error");
      return;
    }
    toast(isManager ? `Cycle ${cycle.name} deleted.` : "Sent to a manager for approval");
    draft.clear();
    onDone();
    onClose();
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Delete cycle {cycle.name}?</DialogTitle>
          <DialogDescription>
            {isManager
              ? `${cycle.unit}${cycle.variety ? ` · ${cycle.variety}` : ""}. This cannot be undone, and a cycle with records against it cannot be deleted.`
              : "A manager decides whether the cycle is deleted. It stays as it is until then."}
          </DialogDescription>
        </DialogHeader>
        <DraftBar restored={draft.restored} onDiscard={draft.discard} />
        {!isManager && (
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dc-reason">Reason for deleting</Label>
            <Textarea id="dc-reason" value={reason} onChange={(e) => setReason(e.target.value)} rows={3} autoFocus />
          </div>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => void go()} disabled={!ok}>
            {busy ? "Working…" : isManager ? "Delete cycle" : "Send delete request"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

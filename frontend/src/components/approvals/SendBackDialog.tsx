import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";

/** Asks the manager why. A note is required: the supervisor reads it when fixing the work. */
export function SendBackDialog({
  open,
  cards,
  busy,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  cards: number;
  busy: boolean;
  onCancel: () => void;
  onConfirm: (note: string) => void;
}) {
  const [note, setNote] = useState("");
  useEffect(() => {
    if (open) setNote("");
  }, [open]);
  const ok = note.trim().length > 0;
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Send back {cards} {cards === 1 ? "submission" : "submissions"}</DialogTitle>
          <DialogDescription>
            The supervisor sees this note, fixes the work and resubmits it. Nothing counts until you approve it.
          </DialogDescription>
        </DialogHeader>
        <Textarea
          aria-label="Note for the supervisor"
          placeholder="What needs fixing?"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={4}
          autoFocus
        />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button type="button" disabled={!ok || busy} onClick={() => onConfirm(note.trim())}>
            Send back
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

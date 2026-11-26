import { useDialogDraft } from "@/hooks/useDialogDraft";
import { DraftBar } from "@/components/DraftBar";
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
  draftKey = "send-back",
}: {
  open: boolean;
  cards: number;
  busy: boolean;
  onCancel: () => void;
  onConfirm: (note: string) => void;
  draftKey?: string;
}) {
  const [note, setNote] = useState("");
  useEffect(() => {
    if (open) setNote("");
  }, [open]);
  const draft = useDialogDraft({ key: draftKey, open, value: note, setValue: setNote });
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
        <DraftBar restored={draft.restored} onDiscard={draft.discard} />
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
          <Button type="button" disabled={!ok || busy} onClick={() => { draft.clear(); onConfirm(note.trim()); }}>
            Send back
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

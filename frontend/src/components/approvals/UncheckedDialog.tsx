import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

/** A manager approving work an assistant manager has not checked: ask once, then approve anyway. */
export function UncheckedDialog({
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
  onConfirm: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onCancel()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Approve work that is not checked?</DialogTitle>
          <DialogDescription>
            {cards === 1 ? "This submission has" : `${cards} submissions have`} not been checked by the assistant manager.
            Approving now skips the check.
          </DialogDescription>
        </DialogHeader>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button type="button" disabled={busy} onClick={onConfirm}>Approve anyway</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

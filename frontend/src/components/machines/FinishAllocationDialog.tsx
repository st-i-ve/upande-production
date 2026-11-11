import { useEffect, useState } from "react";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { isError } from "@/lib/frappe";
import { durationLabel } from "@/lib/machine-scan";
import { closeAllocation, type Allocation } from "@/lib/machines-api";

/**
 * Finish an allocation from the desk: an open one is closed now (no scan, so no position), a
 * closed one keeps its end time; litres are entered and, for a user who may submit, the diesel is
 * issued from stock.
 */
export function FinishAllocationDialog({
  allocation,
  canSubmit,
  onOpenChange,
  onDone,
}: {
  allocation: Allocation | null;
  canSubmit: boolean;
  onOpenChange: (o: boolean) => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [litres, setLitres] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (allocation) setLitres(allocation.diesel_litres ? String(allocation.diesel_litres) : "");
  }, [allocation]);

  const n = litres.trim() === "" ? null : Number(litres);
  const bad = n != null && (!Number.isFinite(n) || n < 0);

  const go = async (submit: boolean) => {
    if (!allocation || bad) return;
    setBusy(true);
    const r = await closeAllocation({ diesel_litres: n, submit: submit ? 1 : 0 }, allocation.name);
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(submit ? (n ? "Allocation posted; diesel issued from stock." : "Allocation posted.") : "Allocation closed.", "ok");
    onOpenChange(false);
    onDone();
  };

  const open = !!allocation;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{allocation ? `${allocation.machine} · ${allocation.operator_name ?? allocation.operator}` : ""}</DialogTitle>
          <DialogDescription>
            {allocation?.end_time
              ? `Ran ${durationLabel(allocation.duration_hours)} for ${allocation.allocated_to}${allocation.reference_name ? ` (${allocation.reference_name})` : ""}.`
              : `Running ${durationLabel(allocation?.running_hours)}. It is closed now; scanning the machine instead also records where it is.`}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="fa-litres">Diesel (litres)</Label>
          <Input id="fa-litres" type="number" min={0} step="0.1" inputMode="decimal" value={litres} onChange={(e) => setLitres(e.target.value)} />
          <p className="text-[12px] text-[var(--sd-quiet)]">
            {bad ? "Litres must be a number, 0 or more." : "Issued from the fuel warehouse on posting; its cost is the stock value."}
          </p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button variant="outline" onClick={() => go(false)} disabled={busy || bad}>
            {allocation?.end_time ? "Save litres" : "Close"}
          </Button>
          {canSubmit && (
            <Button onClick={() => go(true)} disabled={busy || bad}>
              {busy ? "Posting…" : "Close and post diesel"}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

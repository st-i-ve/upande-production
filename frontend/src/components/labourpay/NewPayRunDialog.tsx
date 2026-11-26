import { useDraftFields } from "@/hooks/useDialogDraft";
import { DraftBar } from "@/components/DraftBar";
import { useState } from "react";
import { DatePicker } from "@/components/DatePicker";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { isError } from "@/lib/frappe";
import { newPayRun, type PayRunDetail } from "@/lib/labourpay-api";

/** Start a pay run for a period (prefilled from the pay settings) and optionally one farm. */
export function NewPayRunDialog({
  period,
  farms,
  onClose,
  onCreated,
}: {
  period: { from_date: string; to_date: string };
  farms: string[];
  onClose: () => void;
  onCreated: (run: PayRunDetail) => void;
}) {
  const toast = useToast();
  const [from, setFrom] = useState(period.from_date);
  const [to, setTo] = useState(period.to_date);
  const [farm, setFarm] = useState("");
  const [busy, setBusy] = useState(false);
  const draft = useDraftFields({ key: "new-pay-run", open: true, fields: { from: [from, setFrom], to: [to, setTo], farm: [farm, setFarm] } });

  async function create() {
    setBusy(true);
    const r = await newPayRun(from, to, farm || undefined);
    setBusy(false);
    if (isError(r)) return void toast(r.error, "error");
    toast(`Pay run ${r.name} started.`);
    draft.clear();
    onCreated(r);
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-lg" aria-describedby="npr-desc">
        <DialogHeader>
          <DialogTitle>New pay run</DialogTitle>
          <DialogDescription id="npr-desc">
            Gathers approved, unpaid casual labour work dated within the period. You can review and refresh it before approving.
          </DialogDescription>
        </DialogHeader>
        <DraftBar restored={draft.restored} onDiscard={draft.discard} />
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="npr-from">From</Label>
            <DatePicker id="npr-from" aria-label="From" value={from} onChange={setFrom} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="npr-to">To</Label>
            <DatePicker id="npr-to" aria-label="To" value={to} onChange={setTo} min={from} />
          </div>
          {farms.length > 0 && (
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label htmlFor="npr-farm">Farm (optional)</Label>
              <Picker id="npr-farm" label="Farm" value={farm} onChange={setFarm} options={farms} clearable clearLabel="All farms" placeholder="All farms" />
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => void create()} disabled={busy || !from || !to}>
            {busy ? "Starting…" : "Start pay run"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

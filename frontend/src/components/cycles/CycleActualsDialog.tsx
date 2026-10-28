import { useState } from "react";
import { DatePicker } from "@/components/DatePicker";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { saveCycle, type Cycle } from "@/lib/api";
import { isError } from "@/lib/frappe";
import { shortDate } from "@/lib/format";

/**
 * Record what really happened on a cycle: when it flowered, when picking began and when it ended.
 * The manager flags and the next cycle in the chain are worked out from these on the server.
 */
export function CycleActualsDialog({
  cycle,
  onClose,
  onSaved,
}: {
  cycle: Cycle;
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [flowering, setFlowering] = useState(cycle.actual_flowering_date ?? "");
  const [harvestStart, setHarvestStart] = useState(cycle.actual_harvest_start ?? "");
  const [harvestEnd, setHarvestEnd] = useState(cycle.actual_harvest_end ?? "");
  const [busy, setBusy] = useState(false);

  async function save(close = false) {
    setBusy(true);
    const r = await saveCycle({
      name: cycle.name,
      actual_flowering_date: flowering || null,
      actual_harvest_start: harvestStart || null,
      actual_harvest_end: harvestEnd || null,
      ...(close ? { status: "Closed" } : {}),
    });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(close ? `${cycle.name} closed.` : `Dates saved for ${cycle.name}.`);
    if (r.proposed_next_cycle) toast(`Next cycle proposed: ${r.proposed_next_cycle}`);
    onSaved();
    onClose();
  }

  const row = (label: string, expected: string | null | undefined, value: string, set: (v: string) => void) => (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      <div className="flex flex-wrap items-center gap-3">
        <DatePicker value={value} onChange={set} aria-label={label} />
        {expected && <span className="text-[12px] text-[var(--sd-quiet)]">Expected {shortDate(expected)}</span>}
      </div>
    </div>
  );

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-md" aria-describedby="actuals-desc">
        <DialogHeader>
          <DialogTitle>Record dates · {cycle.unit}</DialogTitle>
          <DialogDescription id="actuals-desc">
            When cycle {cycle.name} really flowered and was picked. Late or missing dates are flagged for the manager.
          </DialogDescription>
        </DialogHeader>
        {row("Flowering date", cycle.expected_flowering_date, flowering, setFlowering)}
        {row("Harvest start", cycle.expected_harvest_start, harvestStart, setHarvestStart)}
        {row("Harvest end", cycle.expected_harvest_end, harvestEnd, setHarvestEnd)}
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          {cycle.status !== "Closed" && (
            <Button variant="outline" onClick={() => void save(true)} disabled={busy}>
              Save and close cycle
            </Button>
          )}
          <Button onClick={() => void save()} disabled={busy}>
            {busy ? "Saving…" : "Save dates"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

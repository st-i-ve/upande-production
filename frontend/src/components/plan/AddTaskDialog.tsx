import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DatePicker } from "@/components/DatePicker";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SearchPicker } from "@/components/ui/search-picker";
import { savePlanTasks, type UnitRow } from "@/lib/api";
import { isError } from "@/lib/frappe";
import { addDays } from "@/components/plan/fmt";
import { num, ymd } from "@/lib/utils";

export interface OperationOption {
  name: string;
  operation_name: string;
  work_uom: string | null;
}

/** Plan one more task in the chosen week. */
export function AddTaskDialog({
  crop,
  farm,
  year,
  week,
  weekStart,
  unitLabel,
  units,
  operations,
  supervisors,
  onClose,
  onAdded,
}: {
  crop: string;
  farm: string;
  year: number;
  week: number;
  weekStart: Date;
  unitLabel: string;
  units: UnitRow[];
  operations: OperationOption[];
  supervisors: { value: string; label: string }[];
  onClose: () => void;
  onAdded: () => void;
}) {
  const min = ymd(weekStart);
  const max = ymd(addDays(weekStart, 6));
  const [unit, setUnit] = useState("");
  const [operation, setOperation] = useState("");
  const [planned, setPlanned] = useState("");
  const [due, setDue] = useState(min);
  const [supervisor, setSupervisor] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  const unitOptions = useMemo(
    () =>
      units
        .filter((u) => !u.is_group)
        .map((u) => ({ value: u.name, label: u.item ? `${u.name} · ${u.item}` : u.name, short: u.name })),
    [units],
  );
  const opOptions = useMemo(
    () => operations.map((o) => ({ value: o.name, label: o.operation_name || o.name, short: o.operation_name || o.name })),
    [operations],
  );
  const op = operations.find((o) => o.name === operation);
  const ready = !!unit && !!operation && !!due;

  async function save() {
    setBusy(true);
    setFailure(null);
    const u = units.find((x) => x.name === unit);
    const r = await savePlanTasks(crop, farm, year, week, [
      {
        unit,
        cycle: u?.current_cycle ?? null,
        operation,
        planned_qty: num(planned),
        uom: op?.work_uom ?? null,
        due_date: due,
        supervisor: supervisor || null,
      },
    ]);
    setBusy(false);
    if (isError(r)) {
      setFailure(r.error);
      return;
    }
    onAdded();
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-md" aria-describedby="add-desc">
        <DialogHeader>
          <DialogTitle>Add task</DialogTitle>
          <DialogDescription id="add-desc">
            Planned for week {week}, {year} · {farm}
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label>{unitLabel}</Label>
          <SearchPicker value={unit} onChange={setUnit} options={unitOptions} placeholder={`Choose a ${unitLabel.toLowerCase()}`} label={unitLabel} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Operation</Label>
          <SearchPicker value={operation} onChange={setOperation} options={opOptions} placeholder="Choose an operation" label="Operation" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="add-qty">Planned quantity{op?.work_uom ? ` (${op.work_uom})` : ""}</Label>
            <Input id="add-qty" inputMode="decimal" className="tabular-nums" value={planned} onChange={(e) => setPlanned(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Due date</Label>
            <DatePicker value={due} onChange={setDue} min={min} max={max} aria-label="Due date" />
          </div>
        </div>
        {supervisors.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <Label>Supervisor (optional)</Label>
            <SearchPicker value={supervisor} onChange={setSupervisor} options={supervisors} placeholder="None" label="Supervisor" />
          </div>
        )}
        {failure && (
          <p role="alert" className="rounded-[var(--sd-radius)] bg-[var(--sd-alert-error)] px-3 py-2 text-[13px] text-[var(--sd-ink)]">
            {failure}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={save} disabled={busy || !ready}>
            {busy ? "Adding…" : "Add task"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

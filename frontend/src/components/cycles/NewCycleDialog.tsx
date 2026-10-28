import { useEffect, useState } from "react";
import { DatePicker } from "@/components/DatePicker";
import { useToast } from "@/components/Toast";
import { ItemField } from "@/components/cycles/ItemField";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { SearchPicker } from "@/components/ui/search-picker";
import { listProtocols, saveCycle, type Crop } from "@/lib/api";
import { isError } from "@/lib/frappe";
import { listVarieties, type Variety } from "@/lib/varieties-api";
import { todayISO } from "@/lib/utils";

/** Select options of the Crop Cycle doctype. */
export const CYCLE_TYPES = ["Season", "Planting", "Pond Cycle", "Hive Season"];
export const CYCLE_STATUSES = ["Planned", "Active", "Harvesting", "Closed"];

export function NewCycleDialog({
  crop,
  units,
  defaultUnit,
  open,
  onOpenChange,
  onSaved,
}: {
  crop: Crop;
  units: { name: string; is_group: boolean }[];
  defaultUnit?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [unit, setUnit] = useState(defaultUnit ?? "");
  const [item, setItem] = useState("");
  const [type, setType] = useState(CYCLE_TYPES[0]);
  const [start, setStart] = useState(todayISO());
  const [hStart, setHStart] = useState("");
  const [hEnd, setHEnd] = useState("");
  const [protocol, setProtocol] = useState("");
  const [protocols, setProtocols] = useState<{ value: string; label: string }[]>([]);
  const [variety, setVariety] = useState("");
  const [varieties, setVarieties] = useState<Variety[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setUnit(defaultUnit ?? "");
    let live = true;
    void listVarieties(crop.name).then((r) => live && !isError(r) && setVarieties(r.varieties.filter((v) => !!Number(v.enabled))));
    void listProtocols(crop.name).then((r) => {
      if (!live || isError(r)) {
        if (live && isError(r)) toast(r.error, "error");
        return;
      }
      setProtocols(
        (r as { rows: Record<string, unknown>[] }).rows.map((p) => ({
          value: String(p.name),
          label: String(p.protocol_name ?? p.name),
        })),
      );
    });
    return () => {
      live = false;
    };
  }, [open, crop.name, defaultUnit, toast]);

  const label = crop.unit_label;
  const can = !!unit && !!start && !busy;

  async function save() {
    setBusy(true);
    const r = await saveCycle({
      crop: crop.name,
      unit,
      variety: variety || null,
      item: variety ? undefined : item.trim() || null,
      cycle_type: type,
      start_date: start,
      expected_harvest_start: hStart || null,
      expected_harvest_end: hEnd || null,
      protocol: protocol || null,
    });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(`Cycle ${(r as { name: string }).name} saved.`);
    setItem("");
    setVariety("");
    setHStart("");
    setHEnd("");
    setProtocol("");
    onOpenChange(false);
    onSaved();
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>New crop cycle</DialogTitle>
          <DialogDescription>
            Start a cycle on a {label.toLowerCase()}. A protocol, if chosen, schedules its steps from the start
            date.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label htmlFor="cy-unit">{label}</Label>
            <SearchPicker
              id="cy-unit"
              label={label}
              value={unit}
              onChange={setUnit}
              placeholder={`Choose a ${label.toLowerCase()}…`}
              options={units.filter((u) => !u.is_group).map((u) => ({ value: u.name, label: u.name }))}
            />
          </div>
          {varieties.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cy-variety">Variety</Label>
              <Picker
                id="cy-variety"
                label="Variety"
                value={variety}
                onChange={setVariety}
                options={varieties.map((v) => ({ value: v.name, label: v.variety_name }))}
                clearable
                clearLabel="No variety"
                placeholder="No variety"
              />
            </div>
          )}
          {!variety && (
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="cy-item">Item</Label>
              <ItemField id="cy-item" value={item} onChange={setItem} />
            </div>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cy-type">Cycle type</Label>
            <Picker id="cy-type" label="Cycle type" value={type} onChange={setType} options={CYCLE_TYPES} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Start date</Label>
            <DatePicker value={start} onChange={setStart} aria-label="Start date" className="w-full" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cy-protocol">Protocol</Label>
            <Picker
              id="cy-protocol"
              label="Protocol"
              value={protocol}
              onChange={setProtocol}
              options={protocols}
              clearable
              clearLabel="No protocol"
              placeholder="No protocol"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Harvest from</Label>
            <DatePicker value={hStart} onChange={setHStart} min={start} aria-label="Harvest from" className="w-full" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Harvest until</Label>
            <DatePicker value={hEnd} onChange={setHEnd} min={hStart || start} aria-label="Harvest until" className="w-full" />
          </div>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={save} disabled={!can}>
            {busy ? "Saving…" : "Create cycle"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}


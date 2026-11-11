import { useEffect, useMemo, useState } from "react";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { isError, searchItems, searchLink } from "@/lib/frappe";
import { saveMachine, type Machine } from "@/lib/machines-api";

function Field({ id, label, children, hint }: { id?: string; label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-[12px] text-[var(--sd-quiet)]">{hint}</p>}
    </div>
  );
}

/** A text box that offers existing records as you type (Link-field search), so a value is never misspelt. */
function LinkInput({
  id,
  value,
  onChange,
  search,
  placeholder,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  search: (term: string) => Promise<{ value: string; label: string }[]>;
  placeholder?: string;
}) {
  const [opts, setOpts] = useState<{ value: string; label: string }[]>([]);
  useEffect(() => {
    let live = true;
    const t = window.setTimeout(() => {
      void search(value).then((r) => live && setOpts(r));
    }, 200);
    return () => {
      live = false;
      window.clearTimeout(t);
    };
  }, [value, search]);
  return (
    <>
      <Input id={id} list={`${id}-list`} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} autoComplete="off" />
      <datalist id={`${id}-list`}>
        {opts.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </datalist>
    </>
  );
}

const searchItem = async (term: string) =>
  (await searchItems(term)).map((i) => ({ value: i.name, label: `${i.item_name} (${i.stock_uom})` }));
const searchDoctype = (doctype: string) => async (term: string) =>
  ((await searchLink(doctype, term)) ?? []).map((r) => ({ value: r.value, label: r.description || r.value }));
const searchCostCenter = searchDoctype("Cost Center");
const searchAsset = searchDoctype("Asset");

export function MachineDialog({
  open,
  onOpenChange,
  machine,
  machineTypes,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  /** null: a new machine */
  machine: Machine | null;
  machineTypes: string[];
  onSaved: () => void;
}) {
  const toast = useToast();
  const blank = useMemo(
    () => ({ machine_name: "", machine_type: machineTypes[0] ?? "", fuel_item: "", default_cost_center: "", asset: "", notes: "", disabled: false }),
    [machineTypes],
  );
  const [v, setV] = useState(blank);
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTried(false);
    setV(
      machine
        ? {
            machine_name: machine.machine_name,
            machine_type: machine.machine_type,
            fuel_item: machine.fuel_item ?? "",
            default_cost_center: machine.default_cost_center ?? "",
            asset: machine.asset ?? "",
            notes: machine.notes ?? "",
            disabled: !!machine.disabled,
          }
        : blank,
    );
  }, [open, machine, blank]);

  const problems: string[] = [];
  if (!v.machine_name.trim()) problems.push("Give the machine a name.");
  if (!v.machine_type) problems.push("Choose the machine type.");

  const save = async () => {
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    const r = await saveMachine({
      ...(machine ? { name: machine.name } : {}),
      machine_name: v.machine_name.trim(),
      machine_type: v.machine_type,
      fuel_item: v.fuel_item.trim() || null,
      default_cost_center: v.default_cost_center.trim() || null,
      asset: v.asset.trim() || null,
      notes: v.notes.trim() || null,
      disabled: v.disabled ? 1 : 0,
    });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(machine ? "Machine saved." : "Machine added. Print its QR label next.", "ok");
    onOpenChange(false);
    onSaved();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{machine ? machine.machine_name : "New machine"}</DialogTitle>
          <DialogDescription>
            A tractor, chopper or mixer wagon that is allocated to work. Its diesel is issued from stock when an allocation is submitted.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="m-name" label="Name">
            <Input id="m-name" value={v.machine_name} onChange={(e) => setV({ ...v, machine_name: e.target.value })} disabled={!!machine} />
          </Field>
          <Field id="m-type" label="Type">
            <Picker id="m-type" label="Type" value={v.machine_type} onChange={(x) => setV({ ...v, machine_type: x })} options={machineTypes} />
          </Field>
          <Field id="m-fuel" label="Fuel item" hint="The diesel item issued from the fuel warehouse.">
            <LinkInput id="m-fuel" value={v.fuel_item} onChange={(x) => setV({ ...v, fuel_item: x })} search={searchItem} placeholder="e.g. Diesel" />
          </Field>
          <Field id="m-cc" label="Default cost centre" hint="Used when the allocation's target has none.">
            <LinkInput id="m-cc" value={v.default_cost_center} onChange={(x) => setV({ ...v, default_cost_center: x })} search={searchCostCenter} />
          </Field>
          <Field id="m-asset" label="Asset (optional)">
            <LinkInput id="m-asset" value={v.asset} onChange={(x) => setV({ ...v, asset: x })} search={searchAsset} />
          </Field>
          <div className="flex items-end gap-3 pb-1">
            <Switch id="m-disabled" checked={v.disabled} onCheckedChange={(x: boolean) => setV({ ...v, disabled: x })} />
            <Label htmlFor="m-disabled">Disabled (sold or scrapped)</Label>
          </div>
          <div className="sm:col-span-2">
            <Field id="m-notes" label="Notes">
              <Textarea id="m-notes" rows={2} value={v.notes} onChange={(e) => setV({ ...v, notes: e.target.value })} />
            </Field>
          </div>
        </div>
        {tried && problems.length > 0 && (
          <ul className="space-y-1 rounded-xl bg-[var(--sd-alert-error)] px-4 py-3 text-[12.5px] text-[var(--sd-data-red)]" role="alert">
            {problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={save} disabled={busy}>
            {busy ? "Saving…" : "Save machine"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Pencil, Plus } from "lucide-react";
import { ItemField } from "@/components/cycles/ItemField";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { RowsSkeleton } from "@/components/Loading";
import { isError } from "@/lib/frappe";
import { listFieldCrops, saveFieldCrop, type FieldCrop } from "@/lib/field-crops-api";
import { cn } from "@/lib/utils";

/** Units a crop is usually harvested in; any other unit of measure can be typed. */
export const HARVEST_UNITS = ["Kg", "Pieces", "Bunch", "Box", "Tonne", "Crate"];

/** The problem with a crop form, or null. Exported for the tests. */
export function fieldCropProblem(f: { crop_name: string; harvest_uom: string }): string | null {
  if (!f.crop_name.trim()) return "Give the crop a name.";
  if (!f.harvest_uom.trim()) return "Choose the unit this crop is harvested in.";
  return null;
}

/**
 * The named crops inside a section that grows several (Cabbage, Maize, Onion ... in Fruits & Vegetables): the product
 * item each is sold as and the unit it is harvested in. Managers add and edit; everyone else reads.
 */
export function FieldCropsPanel({ crop, canEdit, onChanged }: { crop: string; canEdit: boolean; onChanged?: () => void }) {
  const toast = useToast();
  const [rows, setRows] = useState<FieldCrop[] | null>(null);
  // undefined: closed; null: a new crop; otherwise the one being edited.
  const [editing, setEditing] = useState<FieldCrop | null | undefined>(undefined);

  const load = useCallback(async () => {
    const r = await listFieldCrops(crop);
    if (isError(r)) {
      toast(r.error, "error");
      setRows([]);
      return;
    }
    setRows(r.field_crops);
  }, [crop, toast]);

  useEffect(() => {
    setRows(null);
    void load();
  }, [load]);

  return (
    <div className="flex flex-col gap-3">
      {canEdit && (
        <div className="flex justify-end">
          <Button size="sm" onClick={() => setEditing(null)}>
            <Plus className="h-4 w-4" /> New crop
          </Button>
        </div>
      )}
      {!rows ? (
        <RowsSkeleton rows={4} />
      ) : rows.length === 0 ? (
        <p className="text-[13px] text-[var(--sd-muted)]">No crops for {crop} yet.{canEdit ? " Use New crop to add one." : ""}</p>
      ) : (
        <table className="w-full text-[13px]" data-testid="field-crops">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
              <th className="py-2 pr-3 font-medium">Crop</th>
              <th className="py-2 pr-3 font-medium">Product item</th>
              <th className="py-2 pr-3 font-medium">Harvest unit</th>
              <th className="py-2 pr-3 text-right font-medium">Varieties</th>
              {canEdit && <th className="py-2"><span className="sr-only">Edit</span></th>}
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.name} className="border-t border-[var(--sd-line-soft)]">
                <td className="py-2.5 pr-3 font-medium text-[var(--sd-ink)]">
                  <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle" style={{ background: c.color || "var(--sd-line)" }} />
                  {c.crop_name}
                  {!Number(c.enabled) && <span className="ml-2 rounded-full bg-[var(--sd-bg-soft)] px-2 py-0.5 text-[11px] font-medium text-[var(--sd-quiet)]">Disabled</span>}
                </td>
                <td className="py-2.5 pr-3 text-[var(--sd-muted)]">{c.product_name || c.product || "—"}</td>
                <td className="py-2.5 pr-3">{c.harvest_uom}</td>
                <td className="py-2.5 pr-3 text-right tabular-nums">{c.varieties ?? 0}</td>
                {canEdit && (
                  <td className="py-2.5 text-right">
                    <Button variant="outline" size="sm" aria-label={`Edit ${c.crop_name}`} onClick={() => setEditing(c)}>
                      <Pencil className="h-3.5 w-3.5" /> Edit
                    </Button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editing !== undefined && (
        <FieldCropDialog
          section={crop}
          fieldCrop={editing}
          onClose={() => setEditing(undefined)}
          onSaved={() => {
            setEditing(undefined);
            void load();
            onChanged?.();
          }}
        />
      )}
    </div>
  );
}

function FieldCropDialog({ section, fieldCrop, onClose, onSaved }: { section: string; fieldCrop: FieldCrop | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [name, setName] = useState(fieldCrop?.crop_name ?? "");
  const [product, setProduct] = useState(fieldCrop?.product ?? "");
  const [uom, setUom] = useState(fieldCrop?.harvest_uom ?? "Kg");
  const [color, setColor] = useState(fieldCrop?.color ?? "");
  const [enabled, setEnabled] = useState(fieldCrop ? !!Number(fieldCrop.enabled) : true);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  async function save() {
    const problem = fieldCropProblem({ crop_name: name, harvest_uom: uom });
    if (problem) return setFailure(problem);
    setBusy(true);
    const r = await saveFieldCrop({
      ...(fieldCrop ? { name: fieldCrop.name } : { crop_name: name.trim(), production_crop: section }),
      product: product.trim() || null,
      harvest_uom: uom.trim(),
      color: color || null,
      enabled: enabled ? 1 : 0,
    });
    setBusy(false);
    if (isError(r)) return setFailure(r.error);
    toast(`${fieldCrop ? fieldCrop.crop_name : name.trim()} saved.`);
    onSaved();
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{fieldCrop ? `Edit ${fieldCrop.crop_name}` : "New crop"}</DialogTitle>
          <DialogDescription>A crop of {section}: the product it is sold as and the unit its harvest is counted in.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fc-name">Crop name</Label>
            <Input id="fc-name" value={name} disabled={!!fieldCrop} onChange={(e) => setName(e.target.value)} placeholder="e.g. Cabbage" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fc-uom">Harvest unit</Label>
            <Input id="fc-uom" list="fc-units" value={uom} onChange={(e) => setUom(e.target.value)} placeholder="Kg" />
            <datalist id="fc-units">
              {HARVEST_UNITS.map((u) => <option key={u} value={u} />)}
            </datalist>
          </div>
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label htmlFor="fc-product">Product item</Label>
            <ItemField id="fc-product" value={product} onChange={setProduct} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fc-color">Chart colour (optional)</Label>
            <input id="fc-color" type="color" value={color || "#3f7d3a"} onChange={(e) => setColor(e.target.value)} className="h-9 w-16 cursor-pointer rounded border border-[var(--sd-line)] bg-transparent" />
          </div>
          <label className={cn("flex items-center gap-2 self-end pb-2 text-[13px] text-[var(--sd-ink)]")}>
            <Switch checked={enabled} onCheckedChange={setEnabled} aria-label="Enabled" />
            Enabled
          </label>
        </div>
        {failure && <p role="alert" className="text-[12.5px] text-[var(--sd-sev-high)]">{failure}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save crop"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

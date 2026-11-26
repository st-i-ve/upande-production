import { useDraftFields } from "@/hooks/useDialogDraft";
import { DraftBar } from "@/components/DraftBar";
import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { Pencil, Plus } from "lucide-react";
import { ItemField } from "@/components/cycles/ItemField";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { Switch } from "@/components/ui/switch";
import { RowsSkeleton } from "@/components/Loading";
import { isError } from "@/lib/frappe";
import { getCropTree, saveCropGroup, saveFieldCrop, saveSubCrop, type CropGroup, type FieldCrop, type SubCrop } from "@/lib/field-crops-api";
import { cn } from "@/lib/utils";

/** Units a crop is usually harvested in; any other unit of measure can be typed. */
export const HARVEST_UNITS = ["Kg", "Pieces", "Bunch", "Stem", "Box", "Tonne", "Crate"];

/** The problem with a crop form, or null. Exported for the tests. */
export function fieldCropProblem(f: { crop_name: string; harvest_uom: string }): string | null {
  if (!f.crop_name.trim()) return "Give the crop a name.";
  if (!f.harvest_uom.trim()) return "Choose the unit this crop is harvested in.";
  return null;
}

const NO_PARENT = "";

/**
 * The crop classification: crop groups as a tree on the left (Summer Flowers inside Floriculture), the crops of the
 * selected group on the right, each with its sub-crops. Managers add and edit; everyone else reads.
 */
export function FieldCropsPanel({ canEdit, onChanged }: { canEdit: boolean; onChanged?: () => void }) {
  const toast = useToast();
  const [tree, setTree] = useState<{ groups: CropGroup[]; crops: FieldCrop[] } | null>(null);
  const [selected, setSelected] = useState("");
  // undefined: closed; null: new; otherwise the one being edited.
  const [cropForm, setCropForm] = useState<FieldCrop | null | undefined>(undefined);
  const [groupForm, setGroupForm] = useState<CropGroup | null | undefined>(undefined);
  // A sub-crop form: the crop it belongs to, and the sub-crop being edited (null for a new one).
  const [subForm, setSubForm] = useState<{ crop: FieldCrop; sub: SubCrop | null } | undefined>(undefined);

  const load = useCallback(async () => {
    const r = await getCropTree();
    if (isError(r)) {
      toast(r.error, "error");
      setTree({ groups: [], crops: [] });
      return;
    }
    setTree(r);
    setSelected((cur) => (cur && r.groups.some((g) => g.name === cur) ? cur : r.groups[0]?.name ?? ""));
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const childrenOf = useMemo(() => {
    const m = new Map<string, CropGroup[]>();
    for (const g of [...(tree?.groups ?? [])].sort((a, b) => a.sort_order - b.sort_order || a.name.localeCompare(b.name))) {
      const k = g.parent ?? NO_PARENT;
      m.set(k, [...(m.get(k) ?? []), g]);
    }
    return m;
  }, [tree]);

  const saved = () => {
    void load();
    onChanged?.();
  };

  const renderGroups = (parent: string) => {
    const kids = childrenOf.get(parent);
    if (!kids?.length) return null;
    return (
      <ul className={cn("flex flex-col gap-0.5", parent !== NO_PARENT && "ml-4 mt-0.5 border-l border-[var(--sd-line-soft)] pl-2")}>
        {kids.map((g) => (
          <li key={g.name}>
            <button
              type="button"
              onClick={() => setSelected(g.name)}
              aria-current={selected === g.name}
              className={cn(
                "w-full rounded-md px-2 py-1.5 text-left text-[13px]",
                selected === g.name ? "bg-[var(--sd-bg-soft)] font-medium text-[var(--sd-ink)]" : "text-[var(--sd-muted)] hover:bg-[var(--sd-bg-soft)]",
              )}
            >
              {g.name}
            </button>
            {renderGroups(g.name)}
          </li>
        ))}
      </ul>
    );
  };

  if (!tree) return <RowsSkeleton rows={4} />;
  const crops = tree.crops.filter((c) => c.crop_group === selected);
  const group = tree.groups.find((g) => g.name === selected);

  return (
    <div className="grid gap-5 md:grid-cols-[14rem_1fr]">
      <div className="flex flex-col gap-2" data-testid="crop-groups">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium uppercase tracking-[0.1em] text-[var(--sd-quiet)]">Crop groups</span>
          {canEdit && (
            <Button variant="outline" size="sm" onClick={() => setGroupForm(null)}>
              <Plus className="h-3.5 w-3.5" /> New group
            </Button>
          )}
        </div>
        {tree.groups.length === 0 ? <p className="text-[13px] text-[var(--sd-muted)]">No crop groups yet.</p> : renderGroups(NO_PARENT)}
      </div>

      <div className="flex min-w-0 flex-col gap-3">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-[14px] font-semibold text-[var(--sd-ink)]">{selected || "Crops"}</h3>
          {canEdit && (
            <div className="flex gap-2">
              {group && (
                <Button variant="outline" size="sm" aria-label={`Edit group ${group.name}`} onClick={() => setGroupForm(group)}>
                  <Pencil className="h-3.5 w-3.5" /> Edit group
                </Button>
              )}
              <Button size="sm" onClick={() => setCropForm(null)} disabled={!selected}>
                <Plus className="h-4 w-4" /> New crop
              </Button>
            </div>
          )}
        </div>
        {crops.length === 0 ? (
          <p className="text-[13px] text-[var(--sd-muted)]">No crops in {selected || "this group"} yet.{canEdit ? " Use New crop to add one." : ""}</p>
        ) : (
          <table className="w-full text-[13px]" data-testid="field-crops">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
                <th className="py-2 pr-3 font-medium">Crop</th>
                <th className="py-2 pr-3 font-medium">Product item</th>
                <th className="py-2 pr-3 font-medium">Harvest unit</th>
                {canEdit && <th className="py-2"><span className="sr-only">Edit</span></th>}
              </tr>
            </thead>
            <tbody>
              {crops.map((c) => (
                <Fragment key={c.name}>
                  <tr className="border-t border-[var(--sd-line-soft)]">
                    <td className="py-2.5 pr-3 font-medium text-[var(--sd-ink)]">
                      <span className="mr-2 inline-block h-2.5 w-2.5 rounded-full align-middle" style={{ background: c.color || "var(--sd-line)" }} />
                      {c.crop_name}
                      {!Number(c.enabled) && <span className="ml-2 rounded-full bg-[var(--sd-bg-soft)] px-2 py-0.5 text-[11px] font-medium text-[var(--sd-quiet)]">Disabled</span>}
                    </td>
                    <td className="py-2.5 pr-3 text-[var(--sd-muted)]">{c.product_name || c.product || "—"}</td>
                    <td className="py-2.5 pr-3">{c.harvest_uom}</td>
                    {canEdit && (
                      <td className="py-2.5 text-right">
                        <div className="flex justify-end gap-2">
                          <Button variant="outline" size="sm" aria-label={`Add sub-crop to ${c.crop_name}`} onClick={() => setSubForm({ crop: c, sub: null })}>
                            <Plus className="h-3.5 w-3.5" /> Sub-crop
                          </Button>
                          <Button variant="outline" size="sm" aria-label={`Edit ${c.crop_name}`} onClick={() => setCropForm(c)}>
                            <Pencil className="h-3.5 w-3.5" /> Edit
                          </Button>
                        </div>
                      </td>
                    )}
                  </tr>
                  {(c.sub_crops ?? []).map((s) => (
                    <tr key={s.name} className="text-[12.5px]">
                      <td className="py-1.5 pl-6 pr-3 text-[var(--sd-ink)]">{s.name}</td>
                      <td className="py-1.5 pr-3 text-[var(--sd-muted)]">{s.product || ""}</td>
                      <td className="py-1.5 pr-3">{s.harvest_uom}</td>
                      {canEdit && (
                        <td className="py-1.5 text-right">
                          <Button variant="outline" size="sm" aria-label={`Edit ${s.name}`} onClick={() => setSubForm({ crop: c, sub: s })}>
                            <Pencil className="h-3.5 w-3.5" /> Edit
                          </Button>
                        </td>
                      )}
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {cropForm !== undefined && (
        <FieldCropDialog
          groups={tree.groups}
          group={selected}
          fieldCrop={cropForm}
          onClose={() => setCropForm(undefined)}
          onSaved={() => {
            setCropForm(undefined);
            saved();
          }}
        />
      )}
      {groupForm !== undefined && (
        <GroupDialog
          groups={tree.groups}
          group={groupForm}
          parentDefault={groupForm ? null : selected || null}
          onClose={() => setGroupForm(undefined)}
          onSaved={() => {
            setGroupForm(undefined);
            saved();
          }}
        />
      )}
      {subForm && (
        <SubCropDialog
          crop={subForm.crop}
          sub={subForm.sub}
          onClose={() => setSubForm(undefined)}
          onSaved={() => {
            setSubForm(undefined);
            saved();
          }}
        />
      )}
    </div>
  );
}

function FieldCropDialog({ groups, group, fieldCrop, onClose, onSaved }: { groups: CropGroup[]; group: string; fieldCrop: FieldCrop | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [name, setName] = useState(fieldCrop?.crop_name ?? "");
  const [cropGroup, setCropGroup] = useState(fieldCrop?.crop_group ?? group);
  const [scientific, setScientific] = useState(fieldCrop?.scientific_name ?? "");
  const [product, setProduct] = useState(fieldCrop?.product ?? "");
  const [uom, setUom] = useState(fieldCrop?.harvest_uom ?? "Kg");
  const [color, setColor] = useState(fieldCrop?.color ?? "");
  const [enabled, setEnabled] = useState(fieldCrop ? !!Number(fieldCrop.enabled) : true);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const draft = useDraftFields({ key: `field-crop:${fieldCrop?.name ?? "new"}`, open: true, fields: { name: [name, setName], cropGroup: [cropGroup, setCropGroup], scientific: [scientific, setScientific], product: [product, setProduct], uom: [uom, setUom], color: [color, setColor], enabled: [enabled, setEnabled] } });

  async function save() {
    const problem = fieldCropProblem({ crop_name: name, harvest_uom: uom });
    if (problem) return setFailure(problem);
    if (!cropGroup) return setFailure("Choose the crop group.");
    setBusy(true);
    const r = await saveFieldCrop({
      ...(fieldCrop ? { name: fieldCrop.name } : { crop_name: name.trim() }),
      crop_group: cropGroup,
      // an edit sends only what the form shows and the person changed: nothing else is nulled
      ...(!fieldCrop || scientific.trim() !== (fieldCrop.scientific_name ?? "") ? { scientific_name: scientific.trim() || null } : {}),
      ...(!fieldCrop || product.trim() !== (fieldCrop.product ?? "") ? { product: product.trim() || null } : {}),
      harvest_uom: uom.trim(),
      color: color || null,
      enabled: enabled ? 1 : 0,
    });
    setBusy(false);
    if (isError(r)) return setFailure(r.error);
    toast(`${fieldCrop ? fieldCrop.crop_name : name.trim()} saved.`);
    draft.clear();
    onSaved();
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{fieldCrop ? `Edit ${fieldCrop.crop_name}` : "New crop"}</DialogTitle>
          <DialogDescription>A crop: the product it is sold as and the unit its harvest is counted in. Sections pick up their crops from their varieties.</DialogDescription>
        </DialogHeader>
        <DraftBar restored={draft.restored} onDiscard={draft.discard} />
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fc-name">Crop name</Label>
            <Input id="fc-name" value={name} disabled={!!fieldCrop} onChange={(e) => setName(e.target.value)} placeholder="e.g. Cabbage" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fc-group">Crop group</Label>
            <Picker id="fc-group" label="Crop group" value={cropGroup} onChange={setCropGroup} options={groups.map((g) => g.name)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fc-sci">Scientific name (optional)</Label>
            <Input id="fc-sci" value={scientific} onChange={(e) => setScientific(e.target.value)} />
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
          <label className="flex items-center gap-2 self-end pb-2 text-[13px] text-[var(--sd-ink)]">
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

function GroupDialog({ groups, group, parentDefault, onClose, onSaved }: { groups: CropGroup[]; group: CropGroup | null; parentDefault: string | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [name, setName] = useState(group?.name ?? "");
  const [parent, setParent] = useState(group ? group.parent ?? "" : parentDefault ?? "");
  const [order, setOrder] = useState(String(group?.sort_order ?? 0));
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const draft = useDraftFields({ key: `crop-group:${group?.name ?? "new"}`, open: true, fields: { name: [name, setName], parent: [parent, setParent], order: [order, setOrder] } });

  async function save() {
    if (!group && !name.trim()) return setFailure("Give the group a name.");
    setBusy(true);
    const r = await saveCropGroup({
      ...(group ? { name: group.name } : { group_name: name.trim() }),
      parent: parent || null,
      sort_order: Number(order) || 0,
    });
    setBusy(false);
    if (isError(r)) return setFailure(r.error);
    toast(`${group ? group.name : name.trim()} saved.`);
    draft.clear();
    onSaved();
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{group ? `Edit ${group.name}` : "New group"}</DialogTitle>
          <DialogDescription>A group holds crops and other groups (Summer Flowers sits inside Floriculture).</DialogDescription>
        </DialogHeader>
        <DraftBar restored={draft.restored} onDiscard={draft.discard} />
        <div className="grid gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cg-name">Group name</Label>
            <Input id="cg-name" value={name} disabled={!!group} onChange={(e) => setName(e.target.value)} placeholder="e.g. Fodder Crops" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cg-parent">Inside group</Label>
            <Picker id="cg-parent" label="Inside group" value={parent} onChange={setParent} options={groups.filter((g) => g.name !== group?.name).map((g) => g.name)} clearable clearLabel="Top level" placeholder="Top level" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="cg-order">Order</Label>
            <Input id="cg-order" inputMode="numeric" className="tabular-nums" value={order} onChange={(e) => setOrder(e.target.value)} />
          </div>
        </div>
        {failure && <p role="alert" className="text-[12.5px] text-[var(--sd-sev-high)]">{failure}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save group"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function SubCropDialog({ crop, sub, onClose, onSaved }: { crop: FieldCrop; sub: SubCrop | null; onClose: () => void; onSaved: () => void }) {
  const toast = useToast();
  const [name, setName] = useState(sub?.name ?? "");
  const [uom, setUom] = useState(sub?.harvest_uom ?? crop.harvest_uom);
  const [product, setProduct] = useState(sub?.product ?? "");
  const [enabled, setEnabled] = useState(sub ? sub.enabled === undefined || !!Number(sub.enabled) : true);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const draft = useDraftFields({ key: `sub-crop:${crop.name}:${sub?.name ?? "new"}`, open: true, fields: { name: [name, setName], uom: [uom, setUom], product: [product, setProduct], enabled: [enabled, setEnabled] } });

  async function save() {
    if (!sub && !name.trim()) return setFailure("Give the sub-crop a name.");
    if (!uom.trim()) return setFailure("Choose the unit this sub-crop is harvested in.");
    setBusy(true);
    const r = await saveSubCrop({
      ...(sub ? { name: sub.name } : { sub_crop_name: name.trim(), field_crop: crop.name }),
      harvest_uom: uom.trim(),
      ...(!sub || product.trim() !== (sub.product ?? "") ? { product: product.trim() || null } : {}),
      enabled: enabled ? 1 : 0,
    });
    setBusy(false);
    if (isError(r)) return setFailure(r.error);
    toast(`${sub ? sub.name : name.trim()} saved.`);
    draft.clear();
    onSaved();
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{sub ? `Edit ${sub.name}` : `New sub-crop of ${crop.crop_name}`}</DialogTitle>
          <DialogDescription>A division of one crop, like Standard rose and Spray rose. Varieties of {crop.crop_name} pick one.</DialogDescription>
        </DialogHeader>
        <DraftBar restored={draft.restored} onDiscard={draft.discard} />
        <div className="grid gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sc-name">Sub-crop name</Label>
            <Input id="sc-name" value={name} disabled={!!sub} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sc-uom">Harvest unit</Label>
            <Input id="sc-uom" list="fc-units" value={uom} onChange={(e) => setUom(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="sc-product">Product item</Label>
            <ItemField id="sc-product" value={product} onChange={setProduct} />
          </div>
          <label className="flex items-center gap-2 text-[13px] text-[var(--sd-ink)]">
            <Switch checked={enabled} onCheckedChange={setEnabled} aria-label="Enabled" />
            Enabled
          </label>
        </div>
        {failure && <p role="alert" className="text-[12.5px] text-[var(--sd-sev-high)]">{failure}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save sub-crop"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

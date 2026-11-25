import { useEffect, useMemo, useState } from "react";
import { TriangleAlert } from "lucide-react";
import { DatePicker } from "@/components/DatePicker";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { SearchPicker } from "@/components/ui/search-picker";
import { Textarea } from "@/components/ui/textarea";
import { CYCLE_STATUSES } from "@/components/cycles/NewCycleDialog";
import { listProtocols, type Crop, type Cycle, type UnitRow } from "@/lib/api";
import { getCycleForEdit, updateCycle, type CycleEdit } from "@/lib/cycle-setup-api";
import { isError } from "@/lib/frappe";
import { SubCropField } from "@/components/cycles/SubCropField";
import { cropLabel, cropPickerOptions, hasFieldCrops, subCropsOf } from "@/lib/field-crops";
import { listVarieties, type Variety } from "@/lib/varieties-api";

function Field({ label, htmlFor, hint, children, className }: { label: string; htmlFor?: string; hint?: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`flex min-w-0 flex-col gap-1.5 ${className ?? ""}`}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && <span className="text-[11.5px] text-[var(--sd-quiet)]">{hint}</span>}
    </div>
  );
}

const num = (v: string): number | null => (v.trim() === "" ? null : Number(v));

/**
 * Edit a cycle that already exists (managers). The block is fixed once the cycle has tasks. Changing the
 * protocol or the start date of a running cycle plans from today; tasks already in weekly plans stay as they are.
 * Closing the cycle asks first.
 */
export function EditCycleDialog({
  cycle,
  crop,
  units,
  onClose,
  onSaved,
}: {
  cycle: Cycle;
  crop: Crop;
  units: UnitRow[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [orig, setOrig] = useState<CycleEdit | null>(null);
  const [unit, setUnit] = useState("");
  const [fieldCrop, setFieldCrop] = useState("");
  const [subCrop, setSubCrop] = useState("");
  const [variety, setVariety] = useState("");
  const [protocol, setProtocol] = useState("");
  const [start, setStart] = useState("");
  const [planting, setPlanting] = useState("");
  const [area, setArea] = useState("");
  const [trees, setTrees] = useState("");
  const [hFrom, setHFrom] = useState("");
  const [hTo, setHTo] = useState("");
  const [status, setStatus] = useState("");
  const [notes, setNotes] = useState("");
  const [varieties, setVarieties] = useState<Variety[]>([]);
  const [protocols, setProtocols] = useState<{ value: string; label: string; variety: string | null }[]>([]);
  const [confirmClose, setConfirmClose] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    void getCycleForEdit(cycle.name).then((r) => {
      if (!live) return;
      if (isError(r)) {
        toast(r.error, "error");
        onClose();
        return;
      }
      const c = r as CycleEdit;
      setOrig(c);
      setUnit(c.unit);
      setFieldCrop(c.field_crop ?? "");
      setSubCrop(c.sub_crop ?? "");
      setVariety(c.variety ?? "");
      setProtocol(c.protocol ?? "");
      setStart(c.start_date ?? "");
      setPlanting(c.planting_date ?? "");
      setArea(c.area_ha != null ? String(c.area_ha) : "");
      setTrees(c.plant_count != null ? String(c.plant_count) : "");
      setHFrom(c.expected_harvest_start ?? "");
      setHTo(c.expected_harvest_end ?? "");
      setStatus(c.status);
      setNotes(c.notes ?? "");
    });
    void listVarieties(crop.name).then((r) => live && !isError(r) && setVarieties(r.varieties.filter((v) => !!Number(v.enabled))));
    void listProtocols(crop.name).then((r) => {
      if (!live || isError(r)) return;
      setProtocols(
        (r as { rows: Record<string, unknown>[] }).rows.map((p) => ({
          value: String(p.name),
          label: `${String(p.protocol_name ?? p.name)}${p.version ? ` v${String(p.version)}` : ""}`,
          variety: (p.variety as string) || null,
        })),
      );
    });
    return () => {
      live = false;
    };
  }, [cycle.name, crop.name, toast, onClose]);

  const protoOptions = useMemo(() => {
    const own = protocols.filter((p) => !p.variety || !variety || p.variety === variety);
    return orig?.protocol && !own.some((p) => p.value === orig.protocol) ? [...own, { value: orig.protocol, label: orig.protocol, variety: null }] : own;
  }, [protocols, variety, orig]);

  const withCrops = hasFieldCrops(crop);
  const cropSubs = withCrops ? subCropsOf(crop.field_crops, fieldCrop) : [];
  const shownVarieties = withCrops && fieldCrop ? varieties.filter((x) => x.field_crop === fieldCrop && (!subCrop || !x.sub_crop || x.sub_crop === subCrop)) : varieties;
  const running = status === "Active" || status === "Harvesting";
  const replans = !!orig && running && (protocol !== (orig.protocol ?? "") || start !== orig.start_date);
  const badRange = !!hFrom && !!hTo && hTo < hFrom;
  const can = !!orig && !!unit && !!start && !badRange && !busy;
  const label = crop.unit_label;

  async function save() {
    if (!orig) return;
    setBusy(true);
    const r = await updateCycle(orig.name, {
      unit,
      ...(withCrops && cropSubs.length ? { sub_crop: subCrop || null } : {}),
      variety: variety || null,
      protocol: protocol || null,
      start_date: start,
      planting_date: planting || null,
      area_ha: num(area),
      plant_count: num(trees),
      expected_harvest_start: hFrom || null,
      expected_harvest_end: hTo || null,
      status,
      notes: notes.trim() || null,
    });
    setBusy(false);
    setConfirmClose(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    const ok = r as { name: string; warnings: string[]; notes: string[] };
    toast(`Cycle ${ok.name} saved.`);
    ok.notes.forEach((n) => toast(n));
    ok.warnings.forEach((w) => toast(w, "error"));
    onSaved();
    onClose();
  }

  function submit() {
    if (status === "Closed" && orig && orig.status !== "Closed") setConfirmClose(true);
    else void save();
  }

  return (
    <>
      <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
        <DialogContent className="max-w-3xl grid-cols-[minmax(0,1fr)]">
          <DialogHeader>
            <DialogTitle>Edit cycle {cycle.name}</DialogTitle>
            <DialogDescription>
              {cycle.unit} · {cropLabel(cycle.field_crop, cycle.variety, null, cycle.sub_crop) || cycle.item || cycle.name}. Tasks already in weekly plans are left as they are.
            </DialogDescription>
          </DialogHeader>

          {!orig ? (
            <p className="text-[13px] text-[var(--sd-muted)]">Loading…</p>
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-3">
                <Field label={label} htmlFor="ec-unit" hint={orig.has_tasks ? "Fixed: this cycle already has tasks." : undefined}>
                  {orig.has_tasks ? (
                    <Input id="ec-unit" value={unit} readOnly aria-readonly />
                  ) : (
                    <SearchPicker
                      id="ec-unit"
                      label={label}
                      value={unit}
                      onChange={setUnit}
                      options={units.filter((u) => !u.is_group && u.status !== "Retired").map((u) => ({ value: u.name, label: u.name }))}
                    />
                  )}
                </Field>
                {withCrops && (
                  <Field label="Crop" htmlFor="ec-crop">
                    <Picker
                      id="ec-crop"
                      label="Crop"
                      value={fieldCrop}
                      onChange={(c) => {
                        setFieldCrop(c);
                        setSubCrop("");
                        if (variety && varieties.find((x) => x.name === variety)?.field_crop !== c) setVariety("");
                      }}
                      options={cropPickerOptions(crop.field_crops, { includeDisabled: true })}
                      placeholder="Choose a crop…"
                    />
                  </Field>
                )}
                {withCrops && <SubCropField id="ec-subcrop" subCrops={cropSubs} value={subCrop} onChange={setSubCrop} />}
                <Field label="Variety" htmlFor="ec-variety" hint={!variety && orig.item ? `Item ${orig.item}` : undefined}>
                  <Picker
                    id="ec-variety"
                    label="Variety"
                    value={variety}
                    onChange={setVariety}
                    options={shownVarieties.map((x) => ({ value: x.name, label: x.variety_name }))}
                    clearable={!!orig.item}
                    clearLabel="No variety"
                    placeholder="No variety"
                  />
                </Field>
                <Field label="Protocol" htmlFor="ec-protocol">
                  <Picker id="ec-protocol" label="Protocol" value={protocol} onChange={setProtocol} options={protoOptions} clearable clearLabel="No protocol" placeholder="No protocol" />
                </Field>
                <Field label="Start date">
                  <DatePicker value={start} onChange={setStart} aria-label="Start date" className="w-full" />
                </Field>
                <Field label="Planting date (optional)">
                  <DatePicker value={planting} onChange={setPlanting} aria-label="Planting date" className="w-full" />
                </Field>
                <Field label="Status" htmlFor="ec-status">
                  <Picker id="ec-status" label="Status" value={status} onChange={setStatus} options={CYCLE_STATUSES} />
                </Field>
                <Field label="Area (ha)" htmlFor="ec-area">
                  <Input id="ec-area" inputMode="decimal" className="tabular-nums" value={area} onChange={(e) => setArea(e.target.value)} />
                </Field>
                <Field label="Plant count" htmlFor="ec-trees">
                  <Input id="ec-trees" inputMode="numeric" className="tabular-nums" value={trees} onChange={(e) => setTrees(e.target.value)} />
                </Field>
                <span className="hidden sm:block" />
                <Field label="Expected harvest from">
                  <DatePicker value={hFrom} onChange={setHFrom} min={start} aria-label="Expected harvest from" className="w-full" />
                </Field>
                <Field label="Expected harvest until">
                  <DatePicker value={hTo} onChange={setHTo} min={hFrom || start} aria-label="Expected harvest until" className="w-full" />
                </Field>
                <Field label="Notes" htmlFor="ec-notes" className="sm:col-span-3">
                  <Textarea id="ec-notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
                </Field>
              </div>

              {badRange && (
                <div role="alert" className="flex items-start gap-2 rounded-[var(--sd-radius-md)] bg-[var(--sd-alert-warn)] px-3 py-2 text-[12.5px] text-[var(--sd-sev-high)]">
                  <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>Harvest until is before harvest from.</span>
                </div>
              )}
              {replans && (
                <p className="text-[12.5px] text-[var(--sd-muted)]">
                  Changing the protocol or start date of a running cycle plans from today. Nothing before today is back-filled.
                </p>
              )}

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={onClose} disabled={busy}>
                  Cancel
                </Button>
                <Button onClick={submit} disabled={!can}>
                  {busy ? "Saving…" : "Save cycle"}
                </Button>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={confirmClose} onOpenChange={(o) => !o && !busy && setConfirmClose(false)}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Close cycle {cycle.name}?</DialogTitle>
            <DialogDescription>A closed cycle is no longer planned or counted as running. Its history stays.</DialogDescription>
          </DialogHeader>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setConfirmClose(false)} disabled={busy}>
              Keep it open
            </Button>
            <Button onClick={() => void save()} disabled={busy}>
              {busy ? "Closing…" : "Close cycle"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

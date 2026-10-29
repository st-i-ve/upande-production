import { useEffect, useMemo, useState } from "react";
import { DatePicker } from "@/components/DatePicker";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { Textarea } from "@/components/ui/textarea";
import { saveHoneyHarvest, type HoneyHarvestPage } from "@/lib/apiary-api";
import { isError } from "@/lib/frappe";

type Form = HoneyHarvestPage["form"];
const num = (v: string): number | null => (v.trim() === "" || !Number.isFinite(Number(v)) ? null : Number(v));

function Field({ id, label, children, hint }: { id?: string; label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      {children}
      {hint && <p className="text-[12px] text-[var(--sd-quiet)]">{hint}</p>}
    </div>
  );
}

export function HarvestDialog({
  open,
  onOpenChange,
  form,
  defaultUnit,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  form: Form;
  defaultUnit?: string;
  onSaved: () => void;
}) {
  const toast = useToast();
  const blank = { unit: "", date: form.today, supers: "", frames: "", kg: "", moisture: "", grade: "A", wax: "", notes: "" };
  const [v, setV] = useState(blank);
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);
  const set = <K extends keyof typeof blank>(k: K, val: string) => setV((p) => ({ ...p, [k]: val }));

  useEffect(() => {
    if (open) {
      setV({ ...blank, unit: defaultUnit ?? "" });
      setTried(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, defaultUnit, form.today]);

  const kg = num(v.kg);
  const moisture = num(v.moisture);
  const problems = useMemo(() => {
    const p: string[] = [];
    if (!v.unit) p.push("Choose the hive group.");
    if (!v.date) p.push("Choose the harvest date.");
    else if (v.date > form.today) p.push("The harvest date cannot be in the future.");
    if (kg == null || kg <= 0) p.push("Honey kg must be more than zero.");
    if (v.moisture.trim() !== "" && (moisture == null || moisture < 5 || moisture > 40)) p.push("Moisture must be between 5 and 40%.");
    for (const [k, l] of [["supers", "Supers removed"], ["frames", "Frames extracted"], ["wax", "Wax"]] as const) {
      const n = num(v[k]);
      if (v[k].trim() !== "" && (n == null || n < 0)) p.push(`${l} must be a number, 0 or more.`);
    }
    return p;
  }, [v, kg, moisture, form.today]);

  const wet = moisture != null && form.moisture_limit != null && moisture > form.moisture_limit;

  const save = async () => {
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    const r = await saveHoneyHarvest({
      unit: v.unit, harvest_date: v.date, supers_removed: num(v.supers) ?? undefined,
      frames_extracted: num(v.frames) ?? undefined, honey_kg: kg as number, moisture_pct: moisture, grade: v.grade,
      wax_kg: num(v.wax) ?? undefined, notes: v.notes.trim() || undefined,
    });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast("Harvest saved.", "ok", wet ? { hint: `Moisture is over ${form.moisture_limit}%. This honey may ferment in storage.` } : undefined);
    onOpenChange(false);
    onSaved();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Record harvest</DialogTitle>
          <DialogDescription>Honey taken off one hive group on one day. It also counts as a harvest for the Overview and Costs pages.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="hh-unit" label="Hive group">
            <Picker id="hh-unit" label="Hive group" value={v.unit} onChange={(x) => set("unit", x)} placeholder="Choose a hive group" options={form.units} />
          </Field>
          <Field label="Harvest date">
            <DatePicker value={v.date} onChange={(x) => set("date", x)} aria-label="Harvest date" className="w-full" />
          </Field>
          <Field id="hh-supers" label="Supers removed"><Input id="hh-supers" type="number" min={0} inputMode="numeric" value={v.supers} onChange={(e) => set("supers", e.target.value)} /></Field>
          <Field id="hh-frames" label="Frames extracted"><Input id="hh-frames" type="number" min={0} inputMode="numeric" value={v.frames} onChange={(e) => set("frames", e.target.value)} /></Field>
          <Field id="hh-kg" label="Honey (kg)"><Input id="hh-kg" type="number" min={0} step="0.1" inputMode="decimal" value={v.kg} onChange={(e) => set("kg", e.target.value)} /></Field>
          <Field id="hh-moisture" label="Moisture %" hint={wet ? `Over ${form.moisture_limit}%: too wet to store safely.` : form.moisture_limit != null ? `Keep under ${form.moisture_limit}%.` : undefined}>
            <Input id="hh-moisture" type="number" min={5} max={40} step="0.1" inputMode="decimal" value={v.moisture} onChange={(e) => set("moisture", e.target.value)} />
          </Field>
          <Field id="hh-grade" label="Grade"><Picker id="hh-grade" label="Grade" value={v.grade} onChange={(x) => set("grade", x || "A")} options={form.grades.map((g) => ({ value: g, label: `Grade ${g}` }))} /></Field>
          <Field id="hh-wax" label="Wax (kg)"><Input id="hh-wax" type="number" min={0} step="0.1" inputMode="decimal" value={v.wax} onChange={(e) => set("wax", e.target.value)} /></Field>
          <div className="sm:col-span-2">
            <Field id="hh-notes" label="Notes"><Textarea id="hh-notes" rows={2} value={v.notes} onChange={(e) => set("notes", e.target.value)} /></Field>
          </div>
        </div>
        {tried && problems.length > 0 && (
          <ul className="space-y-1 rounded-xl bg-[var(--sd-alert-error)] px-4 py-3 text-[12.5px] text-[var(--sd-data-red)]" role="alert">
            {problems.map((p) => <li key={p}>{p}</li>)}
          </ul>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save harvest"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

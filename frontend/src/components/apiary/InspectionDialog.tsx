import { useEffect, useMemo, useState } from "react";
import { DatePicker } from "@/components/DatePicker";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { saveHiveInspection, type InspectionForm } from "@/lib/apiary-api";
import { isError } from "@/lib/frappe";
import { Chip, MITE_LABEL, MITE_TONE } from "./ui";

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

export function InspectionDialog({
  open,
  onOpenChange,
  form,
  defaultUnit,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  form: InspectionForm;
  defaultUnit?: string;
  onSaved: () => void;
}) {
  const toast = useToast();
  const blank = { unit: "", date: form.today, inspector: "", inspected: "", queenright: "", queenSeen: false, eggs: false,
    brood: "", temper: "", mites: "", disease: "None", fb: "", fh: "", fs: "", feed: "", notes: "" };
  const [v, setV] = useState(blank);
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);
  const set = <K extends keyof typeof blank>(k: K, val: (typeof blank)[K]) => setV((p) => ({ ...p, [k]: val }));

  useEffect(() => {
    if (open) {
      setV({ ...blank, unit: defaultUnit ?? "" });
      setTried(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, defaultUnit, form.today]);

  const inspected = num(v.inspected);
  const queenright = num(v.queenright);
  const mites = num(v.mites);
  const problems = useMemo(() => {
    const p: string[] = [];
    if (!v.unit) p.push("Choose the hive group.");
    if (!v.date) p.push("Choose the inspection date.");
    else if (v.date > form.today) p.push("The inspection date cannot be in the future.");
    if (inspected == null || !Number.isInteger(inspected) || inspected < 1) p.push("Colonies inspected must be at least 1.");
    if (queenright == null || !Number.isInteger(queenright) || queenright < 0) p.push("Enter how many colonies are queenright (0 if none).");
    else if (inspected != null && queenright > inspected) p.push("Queenright colonies cannot be more than the colonies inspected.");
    if (v.mites.trim() !== "" && (mites == null || mites < 0)) p.push("Varroa mites per 100 bees must be a number, 0 or more.");
    for (const [k, l] of [["fb", "Frames of brood"], ["fh", "Frames of honey"], ["fs", "Frames of stores"], ["feed", "Feeding"]] as const) {
      const n = num(v[k]);
      if (v[k].trim() !== "" && (n == null || n < 0)) p.push(`${l} must be a number, 0 or more.`);
    }
    return p;
  }, [v, inspected, queenright, mites, form.today]);

  const miteState = mites == null ? "none" : mites > form.threshold ? "high" : mites >= form.threshold * 0.67 ? "watch" : "ok";
  const qrPct = inspected && queenright != null ? Math.round((100 * queenright) / inspected) : null;

  const save = async () => {
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    const r = await saveHiveInspection({
      unit: v.unit, inspection_date: v.date, inspector: v.inspector || undefined,
      colonies_inspected: inspected as number, colonies_queenright: queenright as number,
      queen_seen: v.queenSeen, eggs_seen: v.eggs, brood_pattern: v.brood || undefined, temperament: v.temper || undefined,
      varroa_per_100: mites, disease_signs: v.disease, frames_brood: num(v.fb) ?? undefined,
      frames_honey: num(v.fh) ?? undefined, frames_stores: num(v.fs) ?? undefined, feeding_kg: num(v.feed) ?? undefined,
      actions: v.notes.trim() || undefined,
    });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast("Inspection saved.", "ok", mites != null && mites > form.threshold ? { hint: `Mite load is over ${form.threshold} per 100 bees. Plan a treatment.` } : undefined);
    onOpenChange(false);
    onSaved();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Record inspection</DialogTitle>
          <DialogDescription>One visit to one hive group. Count the colonies you opened, not the ones in the apiary.</DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="hi-unit" label="Hive group">
            <Picker id="hi-unit" label="Hive group" value={v.unit} onChange={(x) => set("unit", x)} placeholder="Choose a hive group" options={form.units} />
          </Field>
          <Field label="Inspection date">
            <DatePicker value={v.date} onChange={(x) => set("date", x)} aria-label="Inspection date" className="w-full" />
          </Field>
          <Field id="hi-inspector" label="Inspector">
            <Picker id="hi-inspector" label="Inspector" value={v.inspector} onChange={(x) => set("inspector", x)} placeholder="Who inspected" clearable clearLabel="Not recorded" options={form.employees} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field id="hi-inspected" label="Colonies inspected">
              <Input id="hi-inspected" type="number" min={1} inputMode="numeric" value={v.inspected} onChange={(e) => set("inspected", e.target.value)} />
            </Field>
            <Field id="hi-queenright" label="Colonies queenright">
              <Input id="hi-queenright" type="number" min={0} inputMode="numeric" value={v.queenright} onChange={(e) => set("queenright", e.target.value)} />
            </Field>
          </div>
          <div className="flex items-center justify-between gap-3 rounded-xl border border-[var(--sd-line)] px-3 py-2">
            <Label htmlFor="hi-queen">Queen seen</Label>
            <Switch id="hi-queen" checked={v.queenSeen} onCheckedChange={(c) => set("queenSeen", c)} />
          </div>
          <div className="flex items-center justify-between gap-3 rounded-xl border border-[var(--sd-line)] px-3 py-2">
            <Label htmlFor="hi-eggs">Eggs seen</Label>
            <Switch id="hi-eggs" checked={v.eggs} onCheckedChange={(c) => set("eggs", c)} />
          </div>
          <Field id="hi-brood" label="Brood pattern">
            <Picker id="hi-brood" label="Brood pattern" value={v.brood} onChange={(x) => set("brood", x)} placeholder="Choose" clearable clearLabel="Not noted" options={form.brood_patterns} />
          </Field>
          <Field id="hi-temper" label="Temperament">
            <Picker id="hi-temper" label="Temperament" value={v.temper} onChange={(x) => set("temper", x)} placeholder="Choose" clearable clearLabel="Not noted" options={form.temperaments} />
          </Field>
          <Field id="hi-mites" label="Varroa mites per 100 bees" hint={`Treat above ${form.threshold}. Leave blank if you did not count.`}>
            <Input id="hi-mites" type="number" min={0} step="0.1" inputMode="decimal" value={v.mites} onChange={(e) => set("mites", e.target.value)} />
          </Field>
          <Field id="hi-disease" label="Disease signs">
            <Picker id="hi-disease" label="Disease signs" value={v.disease} onChange={(x) => set("disease", x || "None")} options={form.disease_options} />
          </Field>
          <div className="grid grid-cols-3 gap-3 sm:col-span-2">
            <Field id="hi-fb" label="Frames of brood"><Input id="hi-fb" type="number" min={0} step="0.5" value={v.fb} onChange={(e) => set("fb", e.target.value)} /></Field>
            <Field id="hi-fh" label="Frames of honey"><Input id="hi-fh" type="number" min={0} step="0.5" value={v.fh} onChange={(e) => set("fh", e.target.value)} /></Field>
            <Field id="hi-fs" label="Frames of stores"><Input id="hi-fs" type="number" min={0} step="0.5" value={v.fs} onChange={(e) => set("fs", e.target.value)} /></Field>
          </div>
          <Field id="hi-feed" label="Feeding given (sugar syrup kg)">
            <Input id="hi-feed" type="number" min={0} step="0.5" value={v.feed} onChange={(e) => set("feed", e.target.value)} />
          </Field>
          <div className="sm:col-span-2">
            <Field id="hi-notes" label="Actions and notes">
              <Textarea id="hi-notes" rows={2} value={v.notes} onChange={(e) => set("notes", e.target.value)} placeholder="Queen introduced, supers added, treatment applied" />
            </Field>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-[12.5px]" data-testid="hi-preview">
          {qrPct != null && queenright != null && inspected != null && queenright <= inspected && (
            <Chip className="bg-[var(--sd-bg-soft)] text-[var(--sd-muted)]">{qrPct}% queenright</Chip>
          )}
          {mites != null && <Chip className={MITE_TONE[miteState]}>{MITE_LABEL[miteState]}</Chip>}
        </div>

        {tried && problems.length > 0 && (
          <ul className="space-y-1 rounded-xl bg-[var(--sd-alert-error)] px-4 py-3 text-[12.5px] text-[var(--sd-data-red)]" role="alert">
            {problems.map((p) => <li key={p}>{p}</li>)}
          </ul>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save inspection"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

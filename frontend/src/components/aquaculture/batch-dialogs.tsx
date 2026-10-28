import { useEffect, useState } from "react";
import { DatePicker } from "@/components/DatePicker";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Picker } from "@/components/ui/picker";
import {
  saveFishHarvest,
  saveSampling,
  saveStocking,
  type PondBatch,
  type PondBatchesPage,
} from "@/lib/aquaculture-api";
import { isError } from "@/lib/frappe";
import { todayISO } from "@/lib/utils";
import { numOf } from "./format";
import { Field, Problems } from "./ui";

interface DialogProps {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  onSaved: () => void;
}

function Actions({ busy, label, onCancel, onSave }: { busy: boolean; label: string; onCancel: () => void; onSave: () => void }) {
  return (
    <div className="flex justify-end gap-2">
      <Button variant="outline" onClick={onCancel} disabled={busy}>Cancel</Button>
      <Button onClick={onSave} disabled={busy}>{busy ? "Saving…" : label}</Button>
    </div>
  );
}

export function StockingDialog({ open, onOpenChange, onSaved, form }: DialogProps & { form: PondBatchesPage["form"] }) {
  const toast = useToast();
  const [pond, setPond] = useState("");
  const [species, setSpecies] = useState("Tilapia");
  const [date, setDate] = useState(todayISO());
  const [count, setCount] = useState("");
  const [weight, setWeight] = useState("");
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("450");
  const [targetDate, setTargetDate] = useState("");
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (open) {
      setPond(""); setSpecies("Tilapia"); setDate(todayISO()); setCount(""); setWeight(""); setSource("");
      setTarget("450"); setTargetDate(""); setTried(false);
    }
  }, [open]);

  const free = form.ponds.filter((p) => !p.active_stocking);
  const n = numOf(count);
  const w = numOf(weight);
  const t = numOf(target);
  const problems: string[] = [];
  if (!pond) problems.push("Choose the pond to stock.");
  if (n == null || !Number.isInteger(n) || n <= 0) problems.push("Fingerlings count must be a whole number above zero.");
  if (w == null || w <= 0) problems.push("Average weight at stocking must be above zero.");
  if (t != null && w != null && t <= w) problems.push("Target weight must be above the weight at stocking.");
  if (targetDate && targetDate < date) problems.push("Target harvest date cannot be before the stocking date.");

  const save = async () => {
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    const r = await saveStocking({
      pond, species, stocking_date: date, fingerlings_count: n as number, avg_weight_g: w as number,
      source: source.trim() || undefined, target_harvest_weight_g: t ?? undefined, target_harvest_date: targetDate || undefined,
    });
    setBusy(false);
    if (isError(r)) return void toast(r.error, "error");
    toast(`${pond} stocked.`, "ok", { hint: `${r.name} · ${n?.toLocaleString("en-US")} ${species.toLowerCase()} fingerlings` });
    onOpenChange(false);
    onSaved();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Stock a pond</DialogTitle>
          <DialogDescription>A new batch. A pond holds one growing batch at a time, so harvest or close the last one first.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="st-pond" label="Pond" hint={free.length ? undefined : "Every pond already has a growing batch."}>
            <Picker id="st-pond" label="Pond" value={pond} onChange={setPond} placeholder="Choose a pond" options={free.map((p) => ({ value: p.unit, label: p.label }))} />
          </Field>
          <Field id="st-species" label="Species">
            <Picker id="st-species" label="Species" value={species} onChange={setSpecies} options={form.species} />
          </Field>
          <Field label="Stocking date"><DatePicker value={date} onChange={setDate} max={todayISO()} aria-label="Stocking date" className="w-full" /></Field>
          <Field id="st-source" label="Source / hatchery"><Input id="st-source" value={source} onChange={(e) => setSource(e.target.value)} placeholder="Hatchery name" /></Field>
          <Field id="st-count" label="Fingerlings stocked"><Input id="st-count" inputMode="numeric" value={count} onChange={(e) => setCount(e.target.value)} placeholder="8000" /></Field>
          <Field id="st-weight" label="Average weight (g)"><Input id="st-weight" inputMode="decimal" value={weight} onChange={(e) => setWeight(e.target.value)} placeholder="5" /></Field>
          <Field id="st-target" label="Target harvest weight (g)"><Input id="st-target" inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} /></Field>
          <Field label="Target harvest date"><DatePicker value={targetDate} onChange={setTargetDate} min={date} aria-label="Target harvest date" className="w-full" /></Field>
        </div>
        <Problems show={tried} items={problems} />
        <Actions busy={busy} label="Stock pond" onCancel={() => onOpenChange(false)} onSave={save} />
      </DialogContent>
    </Dialog>
  );
}

export function SamplingDialog({ open, onOpenChange, onSaved, batch }: DialogProps & { batch: PondBatch | null }) {
  const toast = useToast();
  const [date, setDate] = useState(todayISO());
  const [size, setSize] = useState("30");
  const [weight, setWeight] = useState("");
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (open) { setDate(todayISO()); setSize("30"); setWeight(""); setTried(false); }
  }, [open, batch?.name]);

  const n = numOf(size);
  const w = numOf(weight);
  const problems: string[] = [];
  if (n == null || !Number.isInteger(n) || n <= 0) problems.push("Sample size must be a whole number above zero.");
  if (w == null || w <= 0) problems.push("Average weight must be above zero.");
  if (batch && date < batch.stocking_date) problems.push("The sample is dated before the pond was stocked.");
  if (w != null && batch && w < batch.stocking_weight_g * 0.5) problems.push("That is well under the stocking weight; check the figure.");

  const save = async () => {
    setTried(true);
    if (!batch || problems.length) return;
    setBusy(true);
    const r = await saveSampling({ pond: batch.pond, stocking: batch.name, sample_date: date, sample_size: n as number, avg_weight_g: w as number });
    setBusy(false);
    if (isError(r)) return void toast(r.error, "error");
    toast("Sample saved.", "ok", { hint: `${batch.pond_name} · ${w} g average` });
    onOpenChange(false);
    onSaved();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Record a weight sample</DialogTitle>
          <DialogDescription>{batch ? `${batch.pond_name} · ${batch.species}, ${batch.live.toLocaleString("en-US")} alive` : ""}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Sample date" className="sm:col-span-2"><DatePicker value={date} onChange={setDate} max={todayISO()} aria-label="Sample date" className="w-full" /></Field>
          <Field id="sp-size" label="Fish weighed"><Input id="sp-size" inputMode="numeric" value={size} onChange={(e) => setSize(e.target.value)} /></Field>
          <Field id="sp-weight" label="Average weight (g)"><Input id="sp-weight" inputMode="decimal" value={weight} onChange={(e) => setWeight(e.target.value)} placeholder={batch ? String(Math.round(batch.avg_weight_g)) : ""} /></Field>
        </div>
        <Problems show={tried} items={problems} />
        <Actions busy={busy} label="Save sample" onCancel={() => onOpenChange(false)} onSave={save} />
      </DialogContent>
    </Dialog>
  );
}

export function HarvestDialog({ open, onOpenChange, onSaved, batch }: DialogProps & { batch: PondBatch | null }) {
  const toast = useToast();
  const [date, setDate] = useState(todayISO());
  const [count, setCount] = useState("");
  const [kg, setKg] = useState("");
  const [price, setPrice] = useState("");
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (open) { setDate(todayISO()); setCount(batch ? String(batch.live) : ""); setKg(""); setPrice(""); setTried(false); }
  }, [open, batch]);

  const n = numOf(count);
  const k = numOf(kg);
  const problems: string[] = [];
  if (n == null || !Number.isInteger(n) || n <= 0) problems.push("Number of fish must be a whole number above zero.");
  else if (batch && n > batch.live) problems.push(`Only ${batch.live.toLocaleString("en-US")} fish are left in ${batch.pond_name}.`);
  if (k == null || k <= 0) problems.push("Kilograms harvested must be above zero.");
  if (batch && date < batch.stocking_date) problems.push("The harvest is dated before the pond was stocked.");
  const mean = n && k ? Math.round((k / n) * 1000) : null;

  const save = async () => {
    setTried(true);
    if (!batch || problems.length) return;
    setBusy(true);
    const p = numOf(price);
    const r = await saveFishHarvest({ stocking: batch.name, harvest_date: date, count: n as number, qty_kg: k as number, price_per_kg: p ?? undefined, final: n === batch.live });
    setBusy(false);
    if (isError(r)) return void toast(r.error, "error");
    toast("Harvest saved.", "ok", { hint: r.status === "Harvested" ? `${batch.pond_name} is now empty` : `${batch.pond_name} still has fish` });
    onOpenChange(false);
    onSaved();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Record a harvest</DialogTitle>
          <DialogDescription>
            {batch ? `${batch.pond_name} · ${batch.live.toLocaleString("en-US")} alive. Harvesting every fish closes the batch. The kilograms also go to the crop's harvest records.` : ""}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Harvest date" className="sm:col-span-2"><DatePicker value={date} onChange={setDate} max={todayISO()} aria-label="Harvest date" className="w-full" /></Field>
          <Field id="hv-count" label="Fish harvested"><Input id="hv-count" inputMode="numeric" value={count} onChange={(e) => setCount(e.target.value)} /></Field>
          <Field id="hv-kg" label="Weight (kg)" hint={mean ? `About ${mean} g a fish` : undefined}><Input id="hv-kg" inputMode="decimal" value={kg} onChange={(e) => setKg(e.target.value)} /></Field>
          <Field id="hv-price" label="Price per kg (optional)" className="sm:col-span-2"><Input id="hv-price" inputMode="decimal" value={price} onChange={(e) => setPrice(e.target.value)} /></Field>
        </div>
        <Problems show={tried} items={problems} />
        <Actions busy={busy} label="Save harvest" onCancel={() => onOpenChange(false)} onSave={save} />
      </DialogContent>
    </Dialog>
  );
}

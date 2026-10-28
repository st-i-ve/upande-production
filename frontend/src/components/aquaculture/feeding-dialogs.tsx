import { useEffect, useState } from "react";
import { DatePicker } from "@/components/DatePicker";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Picker } from "@/components/ui/picker";
import { Textarea } from "@/components/ui/textarea";
import { saveFeeding, saveMortality, type FeedingMortalityPage, type MortalityCause } from "@/lib/aquaculture-api";
import { isError } from "@/lib/frappe";
import { todayISO } from "@/lib/utils";
import { numOf } from "./format";
import { Field, Problems } from "./ui";

interface Props {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  form: FeedingMortalityPage["form"];
  defaultPond?: string;
  onSaved: () => void;
}

function Buttons({ busy, label, onCancel, onSave }: { busy: boolean; label: string; onCancel: () => void; onSave: () => void }) {
  return (
    <div className="flex justify-end gap-2">
      <Button variant="outline" onClick={onCancel} disabled={busy}>Cancel</Button>
      <Button onClick={onSave} disabled={busy}>{busy ? "Saving…" : label}</Button>
    </div>
  );
}

const pondOptions = (form: Props["form"]) => form.ponds.map((p) => ({ value: p.unit, label: p.label }));

export function FeedingDialog({ open, onOpenChange, form, defaultPond, onSaved }: Props) {
  const toast = useToast();
  const [pond, setPond] = useState("");
  const [date, setDate] = useState(todayISO());
  const [kg, setKg] = useState("");
  const [type, setType] = useState("");
  const [times, setTimes] = useState("");
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (open) { setPond(defaultPond ?? ""); setDate(todayISO()); setKg(""); setType(""); setTimes(""); setTried(false); }
  }, [open, defaultPond]);

  const k = numOf(kg);
  const stocking = form.ponds.find((p) => p.unit === pond)?.active_stocking;
  const problems: string[] = [];
  if (!pond) problems.push("Choose the pond.");
  else if (!stocking) problems.push("That pond has no growing batch to feed. Stock it first.");
  if (k == null || k <= 0) problems.push("Kilograms fed must be above zero.");
  if (date > todayISO()) problems.push("The feeding cannot be in the future.");

  const save = async () => {
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    const r = await saveFeeding({ pond, feed_date: date, kg_fed: k as number, feed_type: type || undefined, feeding_times: times.trim() || undefined });
    setBusy(false);
    if (isError(r)) return void toast(r.error, "error");
    toast("Feeding saved.", "ok", { hint: `${k} kg` });
    onOpenChange(false);
    onSaved();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Record a feeding</DialogTitle>
          <DialogDescription>One entry for the day's feed in a pond. It counts toward that batch's FCR.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="fd-pond" label="Pond"><Picker id="fd-pond" label="Pond" value={pond} onChange={setPond} placeholder="Choose a pond" options={pondOptions(form)} /></Field>
          <Field label="Date"><DatePicker value={date} onChange={setDate} max={todayISO()} aria-label="Feeding date" className="w-full" /></Field>
          <Field id="fd-kg" label="Feed (kg)"><Input id="fd-kg" inputMode="decimal" value={kg} onChange={(e) => setKg(e.target.value)} placeholder="25" /></Field>
          <Field id="fd-type" label="Feed type"><Picker id="fd-type" label="Feed type" value={type} onChange={setType} clearable clearLabel="Not stated" placeholder="Optional" options={form.feed_types} /></Field>
          <Field id="fd-times" label="Feeding times" className="sm:col-span-2" hint="Optional, comma separated"><Input id="fd-times" value={times} onChange={(e) => setTimes(e.target.value)} placeholder="06:30, 12:30, 17:00" /></Field>
        </div>
        <Problems show={tried} items={problems} />
        <Buttons busy={busy} label="Save feeding" onCancel={() => onOpenChange(false)} onSave={save} />
      </DialogContent>
    </Dialog>
  );
}

export function MortalityDialog({ open, onOpenChange, form, defaultPond, onSaved }: Props) {
  const toast = useToast();
  const [pond, setPond] = useState("");
  const [date, setDate] = useState(todayISO());
  const [count, setCount] = useState("");
  const [cause, setCause] = useState<string>("Unknown");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (open) { setPond(defaultPond ?? ""); setDate(todayISO()); setCount(""); setCause("Unknown"); setNotes(""); setTried(false); }
  }, [open, defaultPond]);

  const n = numOf(count);
  const problems: string[] = [];
  if (!pond) problems.push("Choose the pond.");
  if (n == null || !Number.isInteger(n) || n <= 0) problems.push("Number of dead fish must be a whole number above zero.");
  if (date > todayISO()) problems.push("The date cannot be in the future.");

  const save = async () => {
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    const r = await saveMortality({ pond, mortality_date: date, dead_count: n as number, cause: cause as MortalityCause, notes: notes.trim() || undefined });
    setBusy(false);
    if (isError(r)) return void toast(r.error, "error");
    toast("Mortality saved.", "ok", { hint: `${n} fish · ${cause}` });
    onOpenChange(false);
    onSaved();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Record mortality</DialogTitle>
          <DialogDescription>Dead fish counted in a pond. They come off the batch's live count and its survival.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field id="mt-pond" label="Pond"><Picker id="mt-pond" label="Pond" value={pond} onChange={setPond} placeholder="Choose a pond" options={pondOptions(form)} /></Field>
          <Field label="Date"><DatePicker value={date} onChange={setDate} max={todayISO()} aria-label="Mortality date" className="w-full" /></Field>
          <Field id="mt-count" label="Dead fish"><Input id="mt-count" inputMode="numeric" value={count} onChange={(e) => setCount(e.target.value)} /></Field>
          <Field id="mt-cause" label="Cause"><Picker id="mt-cause" label="Cause" value={cause} onChange={setCause} options={form.causes} /></Field>
          <Field id="mt-notes" label="Notes" className="sm:col-span-2"><Textarea id="mt-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        </div>
        <Problems show={tried} items={problems} />
        <Buttons busy={busy} label="Save mortality" onCancel={() => onOpenChange(false)} onSave={save} />
      </DialogContent>
    </Dialog>
  );
}

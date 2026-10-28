import { useEffect, useState } from "react";
import { DatePicker } from "@/components/DatePicker";
import { TimePicker } from "@/components/TimePicker";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Picker } from "@/components/ui/picker";
import { Textarea } from "@/components/ui/textarea";
import { saveWaterReading, type Bands, type WaterQualityPage } from "@/lib/aquaculture-api";
import { isError } from "@/lib/frappe";
import { todayISO } from "@/lib/utils";
import { METRIC_LABEL, numOf } from "./format";
import { cells } from "./water-card";
import { Field, Problems } from "./ui";

export const WATER_FIELDS = [
  { key: "dissolved_oxygen_mg_l", label: "Dissolved oxygen (mg/L)", ph: "5.5" },
  { key: "ph", label: "pH", ph: "7.6" },
  { key: "temperature_c", label: "Temperature (°C)", ph: "27.5" },
  { key: "ammonia_mg_l", label: "Ammonia (mg/L)", ph: "0.2" },
  { key: "nitrite_mg_l", label: "Nitrite (mg/L)", ph: "0.1" },
  { key: "secchi_cm", label: "Turbidity / Secchi (cm)", ph: "30" },
] as const;
type Key = (typeof WATER_FIELDS)[number]["key"];

/** Messages for each out-of-band value, from the same bands the server uses. */
export function bandWarnings(vals: Partial<Record<Key, number | null>>, bands: Bands): string[] {
  const m = {
    dissolved_oxygen_mg_l: vals.dissolved_oxygen_mg_l ?? null, ph: vals.ph ?? null, temperature_c: vals.temperature_c ?? null,
    ammonia_mg_l: vals.ammonia_mg_l ?? null, nitrite_mg_l: vals.nitrite_mg_l ?? null, secchi_cm: vals.secchi_cm ?? null,
  };
  const names: Record<string, string> = { do: METRIC_LABEL.do, ph: METRIC_LABEL.ph, temp: METRIC_LABEL.temp, ammonia: METRIC_LABEL.ammonia, nitrite: METRIC_LABEL.nitrite };
  return cells(m, bands).filter((c) => c.bad).map((c) => `${names[c.key]} ${c.value}${c.unit ? ` ${c.unit}` : ""} is outside the safe band (${c.band})`);
}

export function WaterReadingDialog({
  open, onOpenChange, form, bands, defaultPond, onSaved,
}: { open: boolean; onOpenChange: (o: boolean) => void; form: WaterQualityPage["form"]; bands: Bands; defaultPond?: string; onSaved: () => void }) {
  const toast = useToast();
  const [pond, setPond] = useState("");
  const [date, setDate] = useState(todayISO());
  const [time, setTime] = useState("06:00");
  const [vals, setVals] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (open) {
      setPond(defaultPond ?? ""); setDate(form.now.slice(0, 10)); setTime(form.now.slice(11, 16) || "06:00");
      setVals({}); setNotes(""); setTried(false);
    }
  }, [open, defaultPond, form.now]);

  const parsed = Object.fromEntries(WATER_FIELDS.map((f) => [f.key, numOf(vals[f.key] ?? "")])) as Record<Key, number | null>;
  const bad = WATER_FIELDS.filter((f) => {
    const p = parsed[f.key];
    return ((vals[f.key] ?? "").trim() !== "" && p == null) || (p != null && p < 0);
  });
  const entered = WATER_FIELDS.filter((f) => parsed[f.key] != null);
  const problems: string[] = [];
  if (!pond) problems.push("Choose the pond.");
  if (!entered.length) problems.push("Enter at least one measurement.");
  if (bad.length) problems.push(`Cannot read: ${bad.map((b) => b.label).join(", ")}.`);
  if (parsed.ph != null && parsed.ph > 14) problems.push("pH must be between 0 and 14.");
  if (date > todayISO()) problems.push("The reading cannot be in the future.");
  const warnings = bandWarnings(parsed, bands);

  const save = async () => {
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    const r = await saveWaterReading({
      pond, reading_datetime: `${date} ${time}:00`, notes: notes.trim() || undefined,
      ...Object.fromEntries(entered.map((f) => [f.key, parsed[f.key]])),
    });
    setBusy(false);
    if (isError(r)) return void toast(r.error, "error");
    if (r.out_of_band) toast("Reading saved, but out of band.", "warn", { hint: r.flags });
    else toast("Reading saved.", "ok");
    onOpenChange(false);
    onSaved();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Record a water reading</DialogTitle>
          <DialogDescription>Leave a measurement blank if you did not take it. Values outside the safe band are flagged.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field id="wq-pond" label="Pond">
            <Picker id="wq-pond" label="Pond" value={pond} onChange={setPond} placeholder="Choose a pond" options={form.ponds.map((p) => ({ value: p.unit, label: p.label }))} />
          </Field>
          <Field label="Date"><DatePicker value={date} onChange={setDate} max={todayISO()} aria-label="Reading date" className="w-full" /></Field>
          <Field label="Time"><TimePicker value={time} onChange={setTime} label="Reading time" /></Field>
          {WATER_FIELDS.map((f) => (
            <Field key={f.key} id={`wq-${f.key}`} label={f.label}>
              <Input id={`wq-${f.key}`} inputMode="decimal" value={vals[f.key] ?? ""} placeholder={f.ph} onChange={(e) => setVals((v) => ({ ...v, [f.key]: e.target.value }))} />
            </Field>
          ))}
          <Field id="wq-notes" label="Notes" className="sm:col-span-3"><Textarea id="wq-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} /></Field>
        </div>
        {warnings.length > 0 && (
          <ul data-testid="band-warnings" className="list-disc space-y-0.5 rounded-xl bg-[var(--sd-alert-warn)] py-2 pl-7 pr-3 text-[12.5px] text-[var(--sd-sev-high)]">
            {warnings.map((w) => <li key={w}>{w}</li>)}
          </ul>
        )}
        <Problems show={tried} items={problems} />
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Cancel</Button>
          <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save reading"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

import { useEffect, useMemo, useState } from "react";
import { DatePicker } from "@/components/DatePicker";
import { TimePicker } from "@/components/TimePicker";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { SearchPicker } from "@/components/ui/search-picker";
import { Textarea } from "@/components/ui/textarea";
import { isError, searchLink } from "@/lib/frappe";
import { saveIrrigationRun, type IrrigationPage } from "@/lib/fv-api";
import { cn, todayISO } from "@/lib/utils";
import { fmtNum } from "./fv-format";

type Form = IrrigationPage["form"];

/** Hours between two local date+time pairs, or null when either is missing. */
export function runHours(d1: string, t1: string, d2: string, t2: string): number | null {
  if (!d1 || !d2 || !t1 || !t2) return null;
  const a = new Date(`${d1}T${t1}:00`).getTime();
  const b = new Date(`${d2}T${t2}:00`).getTime();
  return Number.isFinite(a) && Number.isFinite(b) ? (b - a) / 3_600_000 : null;
}

export function IrrigationDialog({
  open,
  onOpenChange,
  form,
  defaultPivot,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  form: Form;
  defaultPivot?: string;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [pivot, setPivot] = useState("");
  const [d1, setD1] = useState(todayISO());
  const [t1, setT1] = useState("06:00");
  const [d2, setD2] = useState(todayISO());
  const [t2, setT2] = useState("14:00");
  const [depth, setDepth] = useState("");
  const [timer, setTimer] = useState("");
  const [direction, setDirection] = useState("Forward");
  const [source, setSource] = useState("");
  const [operator, setOperator] = useState("");
  const [fault, setFault] = useState("None");
  const [notes, setNotes] = useState("");
  const [slices, setSlices] = useState<string[]>([]);
  const [people, setPeople] = useState<{ value: string; label: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (!open) return;
    const p = defaultPivot || form.pivots[0]?.name || "";
    setPivot(p);
    setSlices(form.pivots.find((x) => x.name === p)?.slices ?? []);
    setD1(todayISO());
    setD2(todayISO());
    setT1("06:00");
    setT2("14:00");
    setDepth("");
    setTimer("");
    setDirection("Forward");
    setSource("");
    setOperator("");
    setFault("None");
    setNotes("");
    setTried(false);
    void searchLink("Employee", "", 50).then((rows) =>
      setPeople((rows ?? []).map((r) => ({ value: r.value, label: r.description ? `${r.value} · ${r.description}` : r.value }))),
    );
  }, [open, defaultPivot, form.pivots]);

  const pivotSlices = useMemo(() => form.pivots.find((x) => x.name === pivot)?.slices ?? [], [form.pivots, pivot]);
  const hours = runHours(d1, t1, d2, t2);
  const depthN = Number(depth);
  const timerN = timer === "" ? null : Number(timer);

  const problems: string[] = [];
  if (!pivot) problems.push("Choose the pivot.");
  if (hours == null || hours <= 0) problems.push("The run must end after it starts.");
  else if (hours > 72) problems.push("A run longer than 72 hours looks like a typo.");
  if (!depth.trim() || !Number.isFinite(depthN) || depthN <= 0) problems.push("Enter the depth applied in mm, more than zero.");
  else if (depthN > 100) problems.push("Depth over 100 mm in one run looks like a typo.");
  if (timerN != null && (!Number.isFinite(timerN) || timerN < 0 || timerN > 100)) problems.push("Percent timer must be between 0 and 100.");
  if (!slices.length) problems.push("Pick at least one slice that was covered.");

  const toggle = (s: string) => setSlices((cur) => (cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]));

  const save = async () => {
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    const r = await saveIrrigationRun({
      unit: pivot,
      start_time: `${d1} ${t1}:00`,
      end_time: `${d2} ${t2}:00`,
      depth_mm: depthN,
      direction,
      percent_timer: timerN ?? undefined,
      water_source: source.trim() || undefined,
      operator: operator || undefined,
      fault,
      notes: notes.trim() || undefined,
      slices,
    });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast("Irrigation run saved.", "ok", { hint: `${pivot} · ${fmtNum(r.hours, 1)} h` });
    onOpenChange(false);
    onSaved();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Record an irrigation run</DialogTitle>
          <DialogDescription>One pass of a pivot. The depth applies to every slice it covered.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ir-pivot">Pivot</Label>
            <Picker
              id="ir-pivot"
              label="Pivot"
              value={pivot}
              onChange={(v) => {
                setPivot(v);
                setSlices(form.pivots.find((x) => x.name === v)?.slices ?? []);
              }}
              placeholder="Choose a pivot"
              options={form.pivots.map((p) => p.name)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ir-depth">Depth applied (mm)</Label>
            <Input id="ir-depth" type="number" min={0} step="0.1" value={depth} onChange={(e) => setDepth(e.target.value)} placeholder="12" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Start</Label>
            <div className="flex gap-2">
              <DatePicker value={d1} onChange={setD1} max={todayISO()} aria-label="Start date" className="flex-1" />
              <TimePicker value={t1} onChange={setT1} label="Start time" />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>End</Label>
            <div className="flex gap-2">
              <DatePicker value={d2} onChange={setD2} max={todayISO()} aria-label="End date" className="flex-1" />
              <TimePicker value={t2} onChange={setT2} label="End time" />
            </div>
          </div>
          <p className="text-[12px] text-[var(--sd-quiet)] sm:col-span-2" data-testid="ir-hours">
            {hours != null && hours > 0 ? `${fmtNum(hours, 1)} hours` : "Hours are worked out from the start and end."}
          </p>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ir-timer">Percent timer</Label>
            <Input id="ir-timer" type="number" min={0} max={100} value={timer} onChange={(e) => setTimer(e.target.value)} placeholder="70" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ir-dir">Direction</Label>
            <Picker id="ir-dir" label="Direction" value={direction} onChange={setDirection} options={form.directions} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ir-source">Water source</Label>
            <Input id="ir-source" list="ir-sources" value={source} onChange={(e) => setSource(e.target.value)} placeholder="Borehole 2" />
            <datalist id="ir-sources">{form.water_sources.map((w) => <option key={w} value={w} />)}</datalist>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ir-operator">Operator</Label>
            <SearchPicker id="ir-operator" label="Operator" value={operator} onChange={setOperator} options={people} placeholder="Search employees" />
          </div>
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label>Slices covered</Label>
            <div className="flex flex-wrap gap-2" role="group" aria-label="Slices covered">
              {pivotSlices.map((s) => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={slices.includes(s)}
                  onClick={() => toggle(s)}
                  className={cn(
                    "h-8 rounded-full border px-3 text-[13px] transition-colors",
                    slices.includes(s) ? "border-transparent bg-[var(--crop-accent,var(--sd-data-green))] text-white" : "bg-[var(--sd-card)] text-[var(--sd-muted)]",
                  )}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ir-fault">Fault</Label>
            <Picker id="ir-fault" label="Fault" value={fault} onChange={setFault} options={form.faults} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="ir-notes">Notes</Label>
            <Textarea id="ir-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
        </div>
        {tried && problems.length > 0 && (
          <ul className="list-disc pl-5 text-[13px] text-[var(--sd-data-red)]" role="alert">
            {problems.map((p) => <li key={p}>{p}</li>)}
          </ul>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Cancel</Button>
          <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save run"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

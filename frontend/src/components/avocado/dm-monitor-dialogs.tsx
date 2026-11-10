import { useEffect, useMemo, useState } from "react";
import { DatePicker } from "@/components/DatePicker";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/Toast";
import {
  addFruitReading,
  combinePct,
  microwavePct,
  saveFruitTag,
  type FruitTag,
  type Monitor,
  type ReadingInput,
} from "@/lib/dmmonitor-api";
import { isError } from "@/lib/frappe";
import { cn, todayISO } from "@/lib/utils";

interface Draft {
  date: string;
  fresh: string;
  dish: string;
  dry: string;
  machine: string;
  instrument: string;
  notes: string;
}

const emptyDraft = (): Draft => ({ date: todayISO(), fresh: "", dish: "", dry: "", machine: "", instrument: "", notes: "" });

/** What a draft works out to, with the same rules the server applies. */
export function evaluate(d: Draft, target: number | null) {
  const mw = microwavePct(d.fresh, d.dry, d.dish);
  const mcRaw = d.machine.trim();
  const mc = mcRaw === "" ? null : Number(mcRaw);
  const problems: string[] = [];
  if (mw.problem) problems.push(mw.problem);
  if (mc != null && (!Number.isFinite(mc) || mc <= 0 || mc > 100)) problems.push("The machine reading must be a percentage between 0 and 100.");
  const machine = mc != null && Number.isFinite(mc) && mc > 0 && mc <= 100 ? mc : null;
  const dm = combinePct(mw.pct, machine);
  if (dm == null && !problems.length) problems.push("Enter the microwave weights, the machine reading, or both.");
  return { micro: mw.pct, machine, dm, problems, ready: dm != null && target != null && dm >= target };
}

function toInput(d: Draft): ReadingInput {
  const n = (s: string) => (s.trim() === "" ? undefined : Number(s));
  return {
    reading_date: d.date,
    fresh_g: n(d.fresh),
    dish_g: n(d.dish),
    dry_g: n(d.dry),
    machine_pct: n(d.machine),
    instrument: d.instrument.trim() || undefined,
    notes: d.notes.trim() || undefined,
  };
}

/** The two methods side by side, with the result worked out as the numbers are typed. */
function ReadingFields({ d, set, target }: { d: Draft; set: (p: Partial<Draft>) => void; target: number | null }) {
  const ev = evaluate(d, target);
  const num = (id: string, label: string, key: "fresh" | "dish" | "dry" | "machine", ph: string) => (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input id={id} inputMode="decimal" placeholder={ph} value={d[key]} onChange={(e) => set({ [key]: e.target.value })} className="tabular-nums" />
    </div>
  );
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <section className="space-y-3 rounded-xl border border-[var(--sd-line)] p-4">
          <h3 className="text-[13px] font-semibold">Microwave method</h3>
          <div className="grid grid-cols-3 gap-3">
            {num("dmr-fresh", "Fresh weight (g)", "fresh", "24.5")}
            {num("dmr-dry", "Dry weight (g)", "dry", "10.2")}
            {num("dmr-dish", "Dish (g), optional", "dish", "4.5")}
          </div>
          <p className="text-[12px] text-[var(--sd-quiet)]">Weigh the sample, dry it in the microwave, weigh again. With a dish weight, both weighings are taken with the dish on and it is subtracted.</p>
          <div className="text-[13px]" data-testid="dmr-micro">
            Dry matter <span className="font-semibold tabular-nums">{ev.micro != null ? `${ev.micro.toFixed(1)}%` : "—"}</span>
          </div>
        </section>
        <section className="space-y-3 rounded-xl border border-[var(--sd-line)] p-4">
          <h3 className="text-[13px] font-semibold">Machine method</h3>
          <div className="grid grid-cols-2 gap-3">
            {num("dmr-machine", "Meter reading (% dry matter)", "machine", "24.8")}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="dmr-instrument">Instrument, optional</Label>
              <Input id="dmr-instrument" placeholder="NIR-1" value={d.instrument} onChange={(e) => set({ instrument: e.target.value })} />
            </div>
          </div>
          <p className="text-[12px] text-[var(--sd-quiet)]">Read straight off the dry matter meter. Fill in either method, or both.</p>
        </section>
      </div>
      <div
        data-testid="dmr-result"
        className={cn("rounded-xl bg-[var(--sd-bg-soft)] px-4 py-3 text-[13px] font-medium", ev.dm == null ? "text-[var(--sd-quiet)]" : ev.ready ? "text-[var(--sd-data-green)]" : "text-foreground")}
      >
        {ev.dm == null
          ? "Nothing worked out yet"
          : `${ev.dm.toFixed(1)}% dry matter${ev.micro != null && ev.machine != null ? ` (average of microwave ${ev.micro.toFixed(1)}% and machine ${ev.machine.toFixed(1)}%)` : ev.micro != null ? " (microwave)" : " (machine)"}${
              target != null ? (ev.ready ? ` · at or over the ${target}% export target` : ` · ${(target - ev.dm).toFixed(1)} points under the ${target}% export target`) : ""
            }`}
      </div>
    </div>
  );
}

function useDraft(open: boolean) {
  const [d, setD] = useState<Draft>(emptyDraft);
  useEffect(() => {
    if (open) setD(emptyDraft());
  }, [open]);
  return [d, (p: Partial<Draft>) => setD((x) => ({ ...x, ...p }))] as const;
}

export function AddReadingDialog({
  open,
  onOpenChange,
  monitor,
  tag,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  monitor: Monitor;
  tag: FruitTag | null;
  onSaved: (t: FruitTag) => void;
}) {
  const toast = useToast();
  const [d, set] = useDraft(open);
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);
  useEffect(() => {
    if (open) {
      setPick(tag?.name ?? "");
      setTried(false);
    }
  }, [open, tag]);

  const active = useMemo(() => monitor.tags.filter((t) => t.status === "Active" || t.name === tag?.name), [monitor, tag]);
  const chosen = monitor.tags.find((t) => t.name === pick) ?? null;
  const ev = evaluate(d, monitor.target_pct);
  const problems = [...(chosen ? [] : ["Choose the fruit."]), ...(!d.date ? ["Pick the date."] : []), ...ev.problems];

  const save = async () => {
    setTried(true);
    if (problems.length || !chosen) return;
    setBusy(true);
    const r = await addFruitReading(chosen.name, toInput(d));
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(`Reading saved: ${(r.latest_pct ?? ev.dm ?? 0).toFixed(1)}% dry matter.`, "ok");
    onOpenChange(false);
    onSaved(r);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl" aria-describedby="dmr-desc">
        <DialogHeader>
          <DialogTitle>Add a reading</DialogTitle>
          <DialogDescription id="dmr-desc">Measure the same tagged fruit again. The percentage is worked out for you.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dmr-fruit">Fruit</Label>
            <Picker
              id="dmr-fruit"
              label="Fruit"
              value={pick}
              onChange={setPick}
              placeholder="Choose a tagged fruit"
              options={active.map((t) => ({ value: t.name, label: `${t.unit} · ${t.tree_label} · fruit ${t.fruit_tag}` }))}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Reading date</Label>
            <DatePicker value={d.date} onChange={(v) => set({ date: v })} max={todayISO()} min={chosen?.tagged_on ?? undefined} aria-label="Reading date" className="w-full" />
          </div>
        </div>
        <ReadingFields d={d} set={set} target={monitor.target_pct} />
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="dmr-notes">Notes</Label>
          <Textarea id="dmr-notes" rows={2} value={d.notes} onChange={(e) => set({ notes: e.target.value })} />
        </div>
        {tried && problems.length > 0 && (
          <ul role="alert" className="list-disc space-y-0.5 pl-5 text-[12.5px] text-[var(--sd-data-red)]">
            {problems.map((p) => <li key={p}>{p}</li>)}
          </ul>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Cancel</Button>
          <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save reading"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function TagFruitDialog({
  open,
  onOpenChange,
  monitor,
  defaultUnit,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  monitor: Monitor;
  defaultUnit?: string;
  onSaved: (t: FruitTag) => void;
}) {
  const toast = useToast();
  const [unit, setUnit] = useState("");
  const [tree, setTree] = useState("");
  const [fruit, setFruit] = useState("");
  const [tagged, setTagged] = useState(todayISO());
  const [notes, setNotes] = useState("");
  const [first, setFirst] = useState(false);
  const [d, set] = useDraft(open);
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);
  useEffect(() => {
    if (open) {
      setUnit(defaultUnit ?? "");
      setTree("");
      setFruit("");
      setTagged(todayISO());
      setNotes("");
      setFirst(false);
      setTried(false);
    }
  }, [open, defaultUnit]);

  const trees = useMemo(() => [...new Set(monitor.tags.filter((t) => t.unit === unit).map((t) => t.tree_label))], [monitor, unit]);
  const taken = monitor.tags.some((t) => t.unit === unit && t.tree_label === tree.trim() && t.fruit_tag === fruit.trim());
  const ev = evaluate(d, monitor.target_pct);
  const problems = [
    ...(!unit ? ["Choose the block."] : []),
    ...(!tree.trim() ? ["Name the tree, e.g. R12-T7."] : []),
    ...(!fruit.trim() ? ["Give the fruit its tag number."] : []),
    ...(taken ? [`Fruit ${fruit.trim()} on ${tree.trim()} is already tagged.`] : []),
    ...(first ? ev.problems : []),
  ];

  const save = async () => {
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    const r = await saveFruitTag({
      unit,
      tree_label: tree.trim(),
      fruit_tag: fruit.trim(),
      tagged_on: tagged,
      notes: notes.trim() || undefined,
      reading: first ? toInput(d) : undefined,
    });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(`Fruit ${r.fruit_tag} on ${r.tree_label} tagged.`, "ok");
    onOpenChange(false);
    onSaved(r);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl" aria-describedby="dmt-desc">
        <DialogHeader>
          <DialogTitle>Tag a fruit</DialogTitle>
          <DialogDescription id="dmt-desc">Pick a fruit on a tree and keep measuring that same fruit as it matures. A tree is its block and a label such as R12-T7.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dmt-block">Block</Label>
            <Picker id="dmt-block" label="Block" value={unit} onChange={setUnit} placeholder="Choose a block" options={monitor.blocks.map((b) => ({ value: b.unit, label: b.farm ? `${b.unit} · ${b.farm}` : b.unit }))} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Tagged on</Label>
            <DatePicker value={tagged} onChange={setTagged} max={todayISO()} aria-label="Tagged on" className="w-full" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dmt-tree">Tree</Label>
            <Input id="dmt-tree" list="dmt-trees" placeholder="R12-T7" value={tree} onChange={(e) => setTree(e.target.value)} />
            <datalist id="dmt-trees">{trees.map((t) => <option key={t} value={t} />)}</datalist>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dmt-fruit">Fruit tag number</Label>
            <Input id="dmt-fruit" placeholder="3" value={fruit} onChange={(e) => setFruit(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label htmlFor="dmt-notes">Notes</Label>
            <Textarea id="dmt-notes" rows={2} placeholder="Which side of the tree, the tag colour" value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-[13px]">
          <input type="checkbox" checked={first} onChange={(e) => setFirst(e.target.checked)} className="h-4 w-4" />
          Record a first reading now
        </label>
        {first && (
          <>
            <div className="flex flex-col gap-1.5 sm:w-1/2">
              <Label>Reading date</Label>
              <DatePicker value={d.date} onChange={(v) => set({ date: v })} max={todayISO()} min={tagged} aria-label="First reading date" className="w-full" />
            </div>
            <ReadingFields d={d} set={set} target={monitor.target_pct} />
          </>
        )}
        {tried && problems.length > 0 && (
          <ul role="alert" className="list-disc space-y-0.5 pl-5 text-[12.5px] text-[var(--sd-data-red)]">
            {problems.map((p) => <li key={p}>{p}</li>)}
          </ul>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Cancel</Button>
          <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Tag fruit"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

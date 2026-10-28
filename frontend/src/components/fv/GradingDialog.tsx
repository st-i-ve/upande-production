import { useEffect, useMemo, useState } from "react";
import { Plus, X } from "lucide-react";
import { DatePicker } from "@/components/DatePicker";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { SearchPicker } from "@/components/ui/search-picker";
import { Textarea } from "@/components/ui/textarea";
import { isError, searchLink } from "@/lib/frappe";
import { saveGrading, type GradingPage } from "@/lib/fv-api";
import { todayISO } from "@/lib/utils";
import { fmtNum } from "./fv-format";

type Form = GradingPage["form"];
interface Line { grade: string; kg: string; crates: string }

export function GradingDialog({
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
  const [unit, setUnit] = useState("");
  const [date, setDate] = useState(todayISO());
  const [received, setReceived] = useState("");
  const [crates, setCrates] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [rejects, setRejects] = useState("");
  const [reason, setReason] = useState("");
  const [by, setBy] = useState("");
  const [notes, setNotes] = useState("");
  const [people, setPeople] = useState<{ value: string; label: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (!open) return;
    setUnit(defaultUnit ?? "");
    setDate(todayISO());
    setReceived("");
    setCrates("");
    setLines(form.default_grades.slice(0, 3).map((g) => ({ grade: g, kg: "", crates: "" })));
    setRejects("");
    setReason("");
    setBy("");
    setNotes("");
    setTried(false);
    void searchLink("Employee", "", 50).then((rows) =>
      setPeople((rows ?? []).map((r) => ({ value: r.value, label: r.description ? `${r.value} · ${r.description}` : r.value }))),
    );
  }, [open, defaultUnit, form.default_grades]);

  const picked = form.units.find((u) => u.name === unit);
  const recvN = Number(received);
  const rejN = rejects.trim() === "" ? 0 : Number(rejects);
  const gradedN = useMemo(() => lines.reduce((t, l) => t + (Number(l.kg) > 0 ? Number(l.kg) : 0), 0), [lines]);
  const used = gradedN + (Number.isFinite(rejN) ? rejN : 0);

  const problems: string[] = [];
  if (!unit) problems.push("Choose the block.");
  if (!received.trim() || !Number.isFinite(recvN) || recvN <= 0) problems.push("Enter the kg received, more than zero.");
  if (!Number.isFinite(rejN) || rejN < 0) problems.push("Rejects cannot be negative.");
  if (rejN > 0 && !reason) problems.push("Give a reason for the rejects.");
  if (lines.some((l) => l.kg.trim() !== "" && !(Number(l.kg) >= 0))) problems.push("Grade kg must be a number, zero or more.");
  if (lines.some((l) => Number(l.kg) > 0 && !l.grade.trim())) problems.push("Name every grade that has kg.");
  if (!lines.some((l) => Number(l.kg) > 0 && l.grade.trim())) problems.push("Enter kg for at least one grade.");
  if (recvN > 0 && used > recvN * 1.005 + 0.01) problems.push(`Graded kg plus rejects (${fmtNum(used, 1)}) is more than the ${fmtNum(recvN, 1)} kg received.`);

  const setLine = (i: number, patch: Partial<Line>) => setLines((cur) => cur.map((l, j) => (j === i ? { ...l, ...patch } : l)));

  const save = async () => {
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    const r = await saveGrading({
      unit,
      grading_date: date,
      received_kg: recvN,
      received_crates: crates.trim() ? Number(crates) : undefined,
      rejects_kg: rejN || undefined,
      reject_reason: rejN > 0 ? reason : undefined,
      graded_by: by || undefined,
      notes: notes.trim() || undefined,
      item: picked?.item ?? undefined,
      cycle: picked?.cycle ?? undefined,
      lines: lines.filter((l) => Number(l.kg) > 0 && l.grade.trim()).map((l) => ({ grade: l.grade.trim(), kg: Number(l.kg), crates: l.crates.trim() ? Number(l.crates) : undefined })),
    });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast("Grading saved.", "ok", { hint: `${unit} · ${fmtNum(r.graded_kg, 1)} kg graded` });
    onOpenChange(false);
    onSaved();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Record grading</DialogTitle>
          <DialogDescription>What came in from a block and how it split by grade. Grades and rejects must not add up to more than was received.</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gr-unit">Block</Label>
            <Picker id="gr-unit" label="Block" value={unit} onChange={setUnit} placeholder="Choose a block" options={form.units.map((u) => ({ value: u.name, label: `${u.name}${u.item ? ` · ${u.item}` : ""}` }))} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Grading date</Label>
            <DatePicker value={date} onChange={setDate} max={todayISO()} aria-label="Grading date" className="w-full" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gr-recv">Received (kg)</Label>
            <Input id="gr-recv" type="number" min={0} step="0.1" value={received} onChange={(e) => setReceived(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gr-crates">Received (crates)</Label>
            <Input id="gr-crates" type="number" min={0} value={crates} onChange={(e) => setCrates(e.target.value)} />
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <Label>Grade split</Label>
          {lines.map((l, i) => (
            <div key={i} className="grid grid-cols-[1fr_7rem_6rem_2rem] items-center gap-2">
              <Input aria-label={`Grade ${i + 1} name`} value={l.grade} onChange={(e) => setLine(i, { grade: e.target.value })} placeholder="Grade" />
              <Input aria-label={`Grade ${i + 1} kg`} type="number" min={0} step="0.1" value={l.kg} onChange={(e) => setLine(i, { kg: e.target.value })} placeholder="kg" />
              <Input aria-label={`Grade ${i + 1} crates`} type="number" min={0} value={l.crates} onChange={(e) => setLine(i, { crates: e.target.value })} placeholder="crates" />
              <button type="button" aria-label={`Remove grade ${i + 1}`} className="grid h-8 w-8 place-items-center rounded-full text-[var(--sd-quiet)] hover:bg-[var(--sd-line-soft)]" onClick={() => setLines((c) => c.filter((_, j) => j !== i))}>
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
          <div>
            <Button type="button" variant="outline" size="sm" onClick={() => setLines((c) => [...c, { grade: "", kg: "", crates: "" }])}>
              <Plus className="mr-1 h-4 w-4" /> Add grade
            </Button>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gr-rej">Rejects (kg)</Label>
            <Input id="gr-rej" type="number" min={0} step="0.1" value={rejects} onChange={(e) => setRejects(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gr-reason">Reject reason</Label>
            <Picker id="gr-reason" label="Reject reason" value={reason} onChange={setReason} placeholder="Choose a reason" clearable clearLabel="None" options={form.reasons} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gr-by">Graded by</Label>
            <SearchPicker id="gr-by" label="Graded by" value={by} onChange={setBy} options={people} placeholder="Search employees" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gr-notes">Notes</Label>
            <Textarea id="gr-notes" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </div>
        </div>
        <p className="text-[12px] text-[var(--sd-quiet)]" data-testid="gr-balance">
          {recvN > 0 ? `${fmtNum(used, 1)} of ${fmtNum(recvN, 1)} kg accounted for (${fmtNum(gradedN, 1)} graded, ${fmtNum(Number.isFinite(rejN) ? rejN : 0, 1)} rejects).` : "Enter the kg received to see the balance."}
        </p>
        {tried && problems.length > 0 && (
          <ul className="list-disc pl-5 text-[13px] text-[var(--sd-data-red)]" role="alert">
            {problems.map((p) => <li key={p}>{p}</li>)}
          </ul>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Cancel</Button>
          <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save grading"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

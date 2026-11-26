import { useDraftFields } from "@/hooks/useDialogDraft";
import { DraftBar } from "@/components/DraftBar";
import { useEffect, useState } from "react";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { searchLink, isError } from "@/lib/frappe";
import { saveSupervisor, type SupervisorDetail } from "@/lib/supervisors-api";

interface Person {
  value: string;
  label: string;
}

/** Add a supervisor (pick an Employee; photo and phone come from the Employee) or edit one: active, farm, sections, notes. */
export function SupervisorForm({
  open,
  onOpenChange,
  existing,
  crops,
  farms,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  existing: SupervisorDetail["supervisor"] | null;
  crops: string[];
  farms: string[];
  onSaved: () => void;
}) {
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [people, setPeople] = useState<Person[]>([]);
  const [picked, setPicked] = useState<Person | null>(null);
  const [active, setActive] = useState(true);
  const [farm, setFarm] = useState("");
  const [sections, setSections] = useState<string[]>([]);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSearch("");
    setPeople([]);
    setPicked(existing ? { value: existing.employee, label: existing.employee_name } : null);
    setActive(existing ? existing.active : true);
    setFarm(existing?.farm ?? "");
    setSections(existing?.crops ?? []);
    setNotes(existing?.notes ?? "");
  }, [open, existing]);
  const draft = useDraftFields({ key: `supervisor-form:${existing?.employee ?? "new"}`, open, fields: { picked: [picked, setPicked], active: [active, setActive], farm: [farm, setFarm], sections: [sections, setSections], notes: [notes, setNotes] } });

  useEffect(() => {
    if (!open || existing || picked) return;
    let live = true;
    const t = setTimeout(() => {
      void searchLink("Employee", search, 15).then((rows) => {
        if (live) setPeople((rows ?? []).map((r) => ({ value: r.value, label: r.label || r.description || r.value })));
      });
    }, 200);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [open, existing, picked, search]);

  const toggle = (c: string) => setSections((s) => (s.includes(c) ? s.filter((x) => x !== c) : [...s, c]));

  async function save() {
    if (!picked) return;
    setBusy(true);
    const r = await saveSupervisor({ employee: picked.value, active, farm: farm || null, crops: sections, notes: notes.trim() || null });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(existing ? "Supervisor saved." : "Supervisor added.");
    onOpenChange(false);
    draft.clear();
    onSaved();
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{existing ? "Edit supervisor" : "Add supervisor"}</DialogTitle>
          <DialogDescription>Photo and phone come from the Employee record.</DialogDescription>
        </DialogHeader>
        <DraftBar restored={draft.restored} onDiscard={draft.discard} />

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="sv-emp">Employee</Label>
          {picked ? (
            <div className="flex items-center justify-between rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] px-3 py-2 text-[13px]">
              <span className="font-medium text-[var(--sd-ink)]">
                {picked.label} <span className="text-[var(--sd-quiet)]">({picked.value})</span>
              </span>
              {!existing && (
                <button type="button" className="text-[12px] text-[var(--sd-muted)] underline" onClick={() => setPicked(null)}>
                  Change
                </button>
              )}
            </div>
          ) : (
            <>
              <Input id="sv-emp" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search employees" autoComplete="off" />
              <ul className="max-h-48 overflow-y-auto rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)]">
                {people.length === 0 && <li className="px-3 py-2 text-[12.5px] text-[var(--sd-muted)]">No employees found.</li>}
                {people.map((p) => (
                  <li key={p.value}>
                    <button type="button" className="flex w-full items-center justify-between px-3 py-2 text-left text-[13px] hover:bg-[var(--sd-card)]" onClick={() => setPicked(p)}>
                      <span>{p.label}</span>
                      <span className="text-[11.5px] text-[var(--sd-quiet)]">{p.value}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>

        <div className="flex items-center justify-between">
          <Label htmlFor="sv-active">Active</Label>
          <Switch id="sv-active" checked={active} onCheckedChange={setActive} />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label>Farm (optional)</Label>
          <Picker label="Farm" value={farm} onChange={setFarm} options={farms} clearable clearLabel="Any farm" placeholder="Any farm" />
        </div>

        <fieldset className="flex flex-col gap-1.5">
          <legend className="text-[13px] font-medium">Sections</legend>
          <p className="text-[12px] text-[var(--sd-quiet)]">Leave all unticked for every crop.</p>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {crops.map((c) => (
              <label key={c} className="flex items-center gap-1.5 text-[13px]">
                <input type="checkbox" checked={sections.includes(c)} onChange={() => toggle(c)} />
                {c}
              </label>
            ))}
          </div>
        </fieldset>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="sv-notes">Notes</Label>
          <Textarea id="sv-notes" value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => void save()} disabled={busy || !picked}>
            {busy ? "Saving…" : "Save"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

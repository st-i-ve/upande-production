import { useEffect, useMemo, useState } from "react";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { SearchPicker } from "@/components/ui/search-picker";
import { SearchInput } from "@/components/SearchInput";
import { isError, searchLink } from "@/lib/frappe";
import { addLabourers, candidateEmployees, type Candidate } from "@/lib/labourers-api";
import { cn } from "@/lib/utils";

const DEFAULT_DESIGNATION = "Casual Labourer";

/** Pick any number of existing Employees to put on the casual labour roster. The list is filtered
 *  by department and designation (default: Casual Labourer) and searchable; people already on the
 *  roster are not offered. */
export function AddLabourersDialog({
  open,
  onOpenChange,
  onAdded,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAdded: () => void;
}) {
  const toast = useToast();
  const [people, setPeople] = useState<Candidate[] | null>(null);
  const [departments, setDepartments] = useState<string[]>([]);
  const [designations, setDesignations] = useState<string[]>([]);
  const [department, setDepartment] = useState("");
  const [designation, setDesignation] = useState(DEFAULT_DESIGNATION);
  const [search, setSearch] = useState("");
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [supervisor, setSupervisor] = useState("");
  const [crew, setCrew] = useState("");
  const [sups, setSups] = useState<{ value: string; label: string }[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setPicked(new Set());
    setSupervisor("");
    setCrew("");
    let live = true;
    void searchLink("Employee", "", 200).then(
      (r) => live && setSups((r ?? []).map((x) => ({ value: x.value, label: x.description ? `${x.description} (${x.value})` : x.value }))),
    );
    return () => {
      live = false;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    let live = true;
    const t = setTimeout(() => {
      void candidateEmployees({ search, department, designation }).then((r) => {
        if (!live) return;
        if (isError(r)) {
          setError(r.error);
          setPeople([]);
          return;
        }
        setError(null);
        setPeople(r.people);
        setDepartments(r.departments);
        setDesignations(r.designations);
      });
    }, 200);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [open, search, department, designation]);

  const list = people ?? [];
  const allShown = list.length > 0 && list.every((p) => picked.has(p.name));
  const toggle = (id: string) =>
    setPicked((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });
  const toggleAll = () =>
    setPicked((s) => {
      const n = new Set(s);
      for (const p of list) {
        if (allShown) n.delete(p.name);
        else n.add(p.name);
      }
      return n;
    });
  const designationOptions = useMemo(() => designations.map((d) => ({ value: d, label: d })), [designations]);

  async function add() {
    setBusy(true);
    const r = await addLabourers([...picked], supervisor || null, crew.trim() || null);
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(`${r.added.length} labourer${r.added.length === 1 ? "" : "s"} added to the roster.`);
    onOpenChange(false);
    onAdded();
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Add casual labourers</DialogTitle>
          <DialogDescription>
            Choose people from the Employee list. Filter by department or designation, then tick as many as you need.
          </DialogDescription>
        </DialogHeader>

        <div className="flex flex-wrap items-center gap-2">
          <SearchInput size="md" value={search} onChange={setSearch} placeholder="Search employees" className="w-56" />
          <Picker
            label="Designation"
            value={designation}
            onChange={setDesignation}
            options={designationOptions}
            clearable
            clearLabel="All designations"
            placeholder="All designations"
            className="w-48"
          />
          <Picker
            label="Department"
            value={department}
            onChange={setDepartment}
            options={departments}
            clearable
            clearLabel="All departments"
            placeholder="All departments"
            className="w-48"
          />
        </div>

        <div className="max-h-[340px] overflow-y-auto rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] shadow-[var(--sd-shadow-inset)]">
          <label className="flex cursor-pointer items-center gap-3 border-b border-[var(--sd-line)] px-4 py-2 text-[12.5px] font-medium text-[var(--sd-muted)]">
            <input type="checkbox" checked={allShown} onChange={toggleAll} disabled={!list.length} aria-label="Select all shown" />
            Select all shown ({list.length})
          </label>
          {people == null ? (
            <p className="px-4 py-6 text-[13px] text-[var(--sd-muted)]">Loading employees…</p>
          ) : error ? (
            <p className="px-4 py-6 text-[13px] text-[var(--sd-muted)]">{error}</p>
          ) : list.length === 0 ? (
            <p className="px-4 py-6 text-[13px] text-[var(--sd-muted)]">
              No employees to add with these filters. People already on the roster are not listed.
            </p>
          ) : (
            <ul className="divide-y divide-[var(--sd-line-soft)]">
              {list.map((p) => (
                <li key={p.name}>
                  <label
                    className={cn(
                      "flex cursor-pointer items-center gap-3 px-4 py-2 text-[13px] hover:bg-[var(--sd-card)]",
                      picked.has(p.name) && "bg-[var(--sd-card)]",
                    )}
                  >
                    <input type="checkbox" checked={picked.has(p.name)} onChange={() => toggle(p.name)} aria-label={p.employee_name} />
                    <span className="min-w-0 flex-1 truncate font-medium text-[var(--sd-ink)]">{p.employee_name}</span>
                    <span className="text-[12px] text-[var(--sd-muted)]">{[p.designation, p.department].filter(Boolean).join(" · ")}</span>
                    <span className="w-24 text-right text-[11.5px] tabular-nums text-[var(--sd-quiet)]">{p.name}</span>
                  </label>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="al-sup">Default supervisor (optional)</Label>
            <SearchPicker id="al-sup" label="Default supervisor" value={supervisor} onChange={setSupervisor} options={sups} placeholder="Choose a supervisor…" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="al-crew">Default crew (optional)</Label>
            <Input id="al-crew" value={crew} onChange={(e) => setCrew(e.target.value)} placeholder="e.g. Pruning crew A" />
          </div>
        </div>

        <div className="flex items-center justify-between gap-3">
          <span className="text-[13px] text-[var(--sd-muted)]">{picked.size} selected</span>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
              Cancel
            </Button>
            <Button onClick={() => void add()} disabled={busy || picked.size === 0}>
              {busy ? "Adding…" : `Add ${picked.size || ""} to roster`.replace("  ", " ")}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

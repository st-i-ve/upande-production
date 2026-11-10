import { useState } from "react";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { isError } from "@/lib/frappe";
import { createProtocol, type ProtocolFamily, type ProtocolVersion } from "@/lib/protocols-api";

/** The first problem with the form, or null. Exported for the tests. */
export function newProtocolProblem(name: string, families: ProtocolFamily[]): string | null {
  const n = name.trim();
  if (!n) return "Give the protocol a name.";
  if (families.some((f) => f.family.toLowerCase() === n.toLowerCase() || f.label.toLowerCase() === n.toLowerCase())) {
    return `A protocol named ${n} already exists.`;
  }
  return null;
}

/**
 * A new protocol family: version 1 as a Draft, optionally starting from the activities of an existing
 * version. The harvest pattern and the other template values come from the chosen variety.
 */
export function NewProtocolDialog({ crop, varieties, families, opNames = {}, onClose, onCreated }: {
  crop: string;
  varieties: { value: string; label: string }[];
  families: ProtocolFamily[];
  /** Field Operation name -> label, for the copy preview. */
  opNames?: Record<string, string>;
  onClose: () => void;
  /** Called with the new family's name once it exists. */
  onCreated: (family: string) => void;
}) {
  const toast = useToast();
  const [name, setName] = useState("");
  const [variety, setVariety] = useState("");
  const [copy, setCopy] = useState("");
  const [busy, setBusy] = useState(false);
  const copyOptions = families.flatMap((f) =>
    f.versions.map((v) => ({ value: v.name, label: `${f.label} v${v.version} (${v.version_status})` })),
  );

  const source = families.flatMap((f) => f.versions).find((v) => v.name === copy) ?? null;

  async function create() {
    const problem = newProtocolProblem(name, families);
    if (problem) {
      toast(problem, "error");
      return;
    }
    setBusy(true);
    const r = await createProtocol({ crop, protocol_name: name.trim(), variety: variety || null, copy_from: copy || null });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(`${name.trim()} created as a draft.`);
    onCreated(name.trim());
  }

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-[60rem] overflow-y-auto" aria-describedby="np-desc">
        <DialogHeader>
          <DialogTitle>New protocol</DialogTitle>
          <DialogDescription id="np-desc">
            Starts as version 1, a draft you can edit. It plans work once a manager approves it. The harvest pattern comes from the variety.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-6 md:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
         <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="np-name">Protocol name</Label>
            <Input id="np-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Hass season" autoFocus />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="np-variety">Variety (optional)</Label>
            <Picker id="np-variety" label="Variety" value={variety} onChange={setVariety} options={varieties} clearable clearLabel="No variety" placeholder="No variety" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="np-copy">Copy activities from (optional)</Label>
            <Picker id="np-copy" label="Copy activities from" value={copy} onChange={setCopy} options={copyOptions} clearable clearLabel="Start empty" placeholder="Start empty" />
          </div>
         </div>
         <CopyPreview v={source} opNames={opNames} />
        </div>
        <div className="flex items-center justify-end gap-3">
          <Button variant="outline" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button onClick={create} disabled={busy}>{busy ? "Creating…" : "Create protocol"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

const label = (names: Record<string, string>, op: string | null) => (op && names[op]) || op || "—";

/** What copying a version brings along: its activities, listed by table. */
function CopyPreview({ v, opNames }: { v: ProtocolVersion | null; opNames: Record<string, string> }) {
  if (!v) {
    return (
      <div data-testid="copy-preview" className="flex min-h-40 items-center justify-center rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] px-4 py-6 text-center text-[12.5px] text-[var(--sd-muted)]">
        The new protocol starts empty. Choose a version to copy to see its activities here.
      </div>
    );
  }
  const groups: [string, string[]][] = [
    ["Capital activities", (v.capital_activities ?? []).map((r) => label(opNames, r.operation))],
    ["Key activities", (v.key_activities ?? []).map((r) => `${label(opNames, r.operation)}: week ${r.week ?? "—"}`)],
    ["Cultural activities", (v.cultural_activities ?? []).map((r) => `${label(opNames, r.operation)}: ${
      r.schedule === "As needed" ? "as needed" : `every ${r.interval_weeks ?? "—"} wk`}${(r.times_per_week ?? 1) > 1 ? `, ${r.times_per_week}× / week` : ""}`)],
  ];
  return (
    <div data-testid="copy-preview" className="max-h-80 overflow-y-auto rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] px-4 py-3">
      <p className="mb-2 text-[12.5px] font-medium text-[var(--sd-ink)]">Copies from {v.protocol_name}</p>
      {groups.map(([title, rows]) => (
        <section key={title} aria-label={title} className="mb-2 last:mb-0">
          <h4 className="text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">{title} ({rows.length})</h4>
          {rows.length === 0 ? <p className="text-[12px] text-[var(--sd-muted)]">None</p> : (
            <ul className="text-[12.5px] text-[var(--sd-ink)]">{rows.map((t, i) => <li key={i}>{t}</li>)}</ul>
          )}
        </section>
      ))}
    </div>
  );
}

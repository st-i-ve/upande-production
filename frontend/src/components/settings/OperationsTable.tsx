import { useEffect, useRef, useState } from "react";
import { Plus } from "lucide-react";
import { FilterSelect } from "@/components/FilterSelect";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { saveOperation, type Row } from "@/lib/api";
import { isError } from "@/lib/frappe";
import { kes } from "@/lib/format";
import { cn, matchesQuery } from "@/lib/utils";

/** Operation categories: the same list the activity rules use. */
export const CATEGORIES: string[] = ["Spraying", "Weeding", "Fertilising", "Irrigation", "Harvesting", "Pruning", "Feeding", "Other"];

/** Activity types of a Production Operation; the protocol tables pick from these. */
export const ACTIVITY_TYPES = ["Capital", "Planting", "Key activity", "Cultural", "Harvesting", "Uprooting"] as const;
const NO_COLOUR = "#9aa5a0";

interface Draft {
  key: string;
  name?: string;
  operation_name: string;
  category: string;
  work_uom: string;
  default_rate: string;
  is_harvest: boolean;
  activity_type: string;
  color: string;
}

function toDraft(r: Row): Draft {
  return {
    key: String(r.name),
    name: String(r.name),
    operation_name: String(r.operation_name ?? ""),
    category: String(r.category ?? ""),
    work_uom: String(r.work_uom ?? ""),
    default_rate: r.default_rate == null ? "" : String(r.default_rate),
    is_harvest: !!Number(r.is_harvest ?? 0),
    activity_type: String(r.activity_type ?? "Cultural"),
    color: String(r.color ?? ""),
  };
}

const same = (a: Draft, b: Draft) =>
  a.operation_name === b.operation_name &&
  a.category === b.category &&
  a.work_uom === b.work_uom &&
  a.default_rate === b.default_rate &&
  a.is_harvest === b.is_harvest &&
  a.activity_type === b.activity_type &&
  a.color === b.color;

const TH = "px-3 py-2.5 font-medium";

/**
 * Operations and their default rates. Editable inline when `canEdit`, one Save
 * per row; read-only text otherwise. The rate column is left out entirely when
 * the viewer may not see pay.
 */
export function OperationsTable({
  crop,
  rows,
  canEdit,
  canSeePay,
  onSaved,
  query = "",
  category = "",
}: {
  query?: string;
  category?: string;
  crop: string;
  rows: Row[];
  canEdit: boolean;
  canSeePay: boolean;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [drafts, setDrafts] = useState<Draft[]>(() => rows.map(toDraft));
  const [fresh, setFresh] = useState<Draft[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const counter = useRef(0);

  // A re-read from the server replaces the saved rows; unsaved new rows stay.
  useEffect(() => setDrafts(rows.map(toDraft)), [rows]);

  const base = new Map(rows.map((r) => [String(r.name), toDraft(r)]));

  const patch = (key: string, p: Partial<Draft>) => {
    const f = (list: Draft[]) => list.map((d) => (d.key === key ? { ...d, ...p } : d));
    setDrafts(f);
    setFresh(f);
  };

  const add = () => {
    counter.current += 1;
    setFresh((f) => [
      { key: `new-${counter.current}`, operation_name: "", category: "Other", work_uom: "", default_rate: "", is_harvest: false, activity_type: "Cultural", color: "" },
      ...f,
    ]);
  };

  async function save(d: Draft) {
    setBusy(d.key);
    const payload: Row = {
      crop,
      operation_name: d.operation_name.trim(),
      category: d.category || undefined,
      work_uom: d.work_uom.trim() || undefined,
      is_harvest: d.is_harvest ? 1 : 0,
      activity_type: d.activity_type || "Cultural",
      color: d.color || undefined,
    };
    if (canSeePay && d.default_rate !== "") payload.default_rate = Number(d.default_rate);
    if (d.name) payload.name = d.name;
    const r = await saveOperation(payload);
    setBusy(null);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(`Saved ${d.operation_name.trim()}.`);
    if (!d.name) setFresh((f) => f.filter((x) => x.key !== d.key));
    onSaved();
  }

  const everything = [...fresh, ...drafts];
  // New (unsaved) rows always show so a filter never hides what is being typed.
  const all = everything.filter(
    (d) => !d.name || ((!query || matchesQuery(`${d.operation_name} ${d.category} ${d.work_uom}`, query)) && (!category || d.category === category)),
  );
  const nothingMatches = everything.length > 0 && all.length === 0;
  const emptyText = nothingMatches ? "No activities match these filters." : "No operations defined for this crop yet.";

  if (!canEdit) {
    return all.length === 0 ? (
      <p className="px-1 py-6 text-center text-[13px] text-[var(--sd-muted)]">{emptyText}</p>
    ) : (
      <div className="overflow-x-auto rounded-[var(--sd-radius-lg)] border border-[var(--sd-line)]">
        <table className="w-full min-w-[48rem] text-[13px]">
          <thead>
            <tr className="border-b border-[var(--sd-line)] text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
              <th className={TH}>Operation</th>
              <th className={TH}>Type</th>
              <th className={TH}>Colour</th>
              <th className={TH}>Category</th>
              <th className={TH}>Work unit</th>
              {canSeePay && <th className={`${TH} text-right`}>Default rate</th>}
              <th className={TH}>Harvest</th>
            </tr>
          </thead>
          <tbody>
            {all.map((d) => (
              <tr key={d.key} className="border-b border-[var(--sd-line-soft)] last:border-0">
                <td className="px-3 py-2.5 font-medium text-[var(--sd-ink)]">{d.operation_name}</td>
                <td className="px-3 py-2.5 text-[var(--sd-muted)]">{d.activity_type}</td>
                <td className="px-3 py-2.5">
                  {d.color ? <span aria-label={`Colour ${d.color}`} className="inline-block h-4 w-4 rounded-full border border-[var(--sd-line)]" style={{ background: d.color }} /> : "—"}
                </td>
                <td className="px-3 py-2.5 text-[var(--sd-muted)]">{d.category || "—"}</td>
                <td className="px-3 py-2.5 text-[var(--sd-muted)]">{d.work_uom || "—"}</td>
                {canSeePay && <td className="px-3 py-2.5 text-right tabular-nums">{kes(d.default_rate === "" ? null : Number(d.default_rate))}</td>}
                <td className="px-3 py-2.5 text-[var(--sd-muted)]">{d.is_harvest ? "Yes" : "No"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" className="rounded-full" onClick={add}>
          <Plus className="h-4 w-4" /> Add operation
        </Button>
      </div>
      {all.length === 0 ? (
        <p className="px-1 py-6 text-center text-[13px] text-[var(--sd-muted)]">{emptyText}</p>
      ) : (
        <div className="overflow-x-auto rounded-[var(--sd-radius-lg)] border border-[var(--sd-line)]">
          <table className="w-full min-w-[64rem] text-[13px]">
            <thead>
              <tr className="border-b border-[var(--sd-line)] text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
                <th className={TH}>Operation</th>
                <th className={TH}>Type</th>
                <th className={TH}>Colour</th>
                <th className={TH}>Category</th>
                <th className={TH}>Work unit</th>
                {canSeePay && <th className={`${TH} text-right`}>Default rate (KES)</th>}
                <th className={TH}>Harvest</th>
                <th className={TH} />
              </tr>
            </thead>
            <tbody>
              {all.map((d) => {
                const orig = d.name ? base.get(d.name) : undefined;
                const dirty = !orig || !same(d, orig);
                const valid = d.operation_name.trim() !== "";
                return (
                  <tr key={d.key} data-testid={`op-${d.name ?? d.key}`} className={cn("border-b border-[var(--sd-line-soft)] last:border-0", !d.name && "bg-[var(--sd-bg-soft)]/60")}>
                    <td className="px-3 py-2">
                      <Input aria-label="Operation name" className="h-8 min-w-[11rem]" value={d.operation_name} onChange={(e) => patch(d.key, { operation_name: e.target.value })} />
                    </td>
                    <td className="px-3 py-2">
                      <FilterSelect aria-label="Activity type" className="h-8" value={d.activity_type} placeholder="Type" options={ACTIVITY_TYPES.map((c) => ({ value: c, label: c }))} onChange={(v) => patch(d.key, { activity_type: v })} />
                    </td>
                    <td className="px-3 py-2">
                      <input type="color" aria-label="Activity colour" className="h-8 w-10 cursor-pointer rounded border border-[var(--sd-line)] bg-transparent p-0.5" value={d.color || NO_COLOUR} onChange={(e) => patch(d.key, { color: e.target.value })} />
                    </td>
                    <td className="px-3 py-2">
                      <FilterSelect aria-label="Category" className="h-8" value={d.category} placeholder="Category" options={CATEGORIES.map((c) => ({ value: c, label: c }))} onChange={(v) => patch(d.key, { category: v })} />
                    </td>
                    <td className="px-3 py-2">
                      <Input aria-label="Work unit" className="h-8 w-28" value={d.work_uom} onChange={(e) => patch(d.key, { work_uom: e.target.value })} />
                    </td>
                    {canSeePay && (
                      <td className="px-3 py-2 text-right">
                        <Input aria-label="Default rate" type="number" min="0" inputMode="decimal" className="ml-auto h-8 w-28 text-right tabular-nums" value={d.default_rate} onChange={(e) => patch(d.key, { default_rate: e.target.value })} />
                      </td>
                    )}
                    <td className="px-3 py-2">
                      <Switch aria-label="Harvest operation" checked={d.is_harvest} onCheckedChange={(v) => patch(d.key, { is_harvest: v })} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Button size="sm" variant="outline" className="h-8 rounded-full px-3 text-[12px]" disabled={!dirty || !valid || busy === d.key} onClick={() => save(d)} aria-label={`Save ${d.operation_name || "new operation"}`}>
                        {busy === d.key ? "Saving…" : "Save"}
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

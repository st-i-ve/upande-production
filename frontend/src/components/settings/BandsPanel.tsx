import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { RowsSkeleton } from "@/components/Loading";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { getBands, saveBands, type Band, type Bands, type Severity } from "@/lib/bands";
import { isError } from "@/lib/frappe";

const SEVERITIES: Severity[] = ["Good", "Watch", "Critical"];

interface Draft {
  band_set: string;
  label: string;
  metric: string;
  min: string;
  max: string;
  severity: Severity;
}

const toDraft = (b: Band): Draft => ({
  band_set: b.band_set, label: b.label, metric: b.metric, min: String(b.min), max: b.max == null ? "" : String(b.max), severity: b.severity,
});

/**
 * The colour bands every page uses (Forecast error, Estimate accuracy, Irrigation % of target, Fish survival,
 * Queen status, Grade A share). A row covers "from" up to but not including "up to"; leave "up to" empty for
 * no upper limit. Managers edit; everyone else reads.
 */
export function BandsPanel({ canEdit }: { canEdit: boolean }) {
  const toast = useToast();
  const [rows, setRows] = useState<Draft[] | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const r = await getBands();
    if (isError(r)) {
      setFailure(r.error);
      setRows([]);
      return;
    }
    setFailure(null);
    setRows(Object.values(r as Bands).flat().map(toDraft));
    setDirty(false);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (!rows) return <RowsSkeleton rows={4} />;
  if (failure) return <p role="alert" className="text-[13px] text-[var(--sd-muted)]">{failure}</p>;

  const sets = [...new Set(rows.map((r) => r.band_set))];
  const edit = (i: number, patch: Partial<Draft>) => {
    setRows((cur) => (cur ?? []).map((r, j) => (j === i ? { ...r, ...patch } : r)));
    setDirty(true);
  };
  const add = (set: string) => {
    setRows((cur) => [...(cur ?? []), { band_set: set, label: "", metric: (cur ?? []).find((r) => r.band_set === set)?.metric ?? "", min: "0", max: "", severity: "Good" }]);
    setDirty(true);
  };
  const remove = (i: number) => {
    setRows((cur) => (cur ?? []).filter((_, j) => j !== i));
    setDirty(true);
  };
  const save = async () => {
    setSaving(true);
    const payload = rows.map((r) => ({ band_set: r.band_set, label: r.label, metric: r.metric, min: Number(r.min) || 0, max: r.max.trim() === "" ? 0 : Number(r.max), severity: r.severity }));
    const r = await saveBands(payload);
    setSaving(false);
    if (isError(r)) return void toast(r.error, "error");
    toast("Bands saved.", "ok");
    void load();
  };

  return (
    <div className="space-y-6" data-testid="bands-panel">
      <p className="text-[13px] text-[var(--sd-muted)]">
        A row covers from its lower value up to, but not including, its upper value. Leave the upper value empty for no upper limit.
      </p>
      {sets.map((set) => (
        <section key={set} data-testid={`band-set-${set}`}>
          <div className="mb-2 flex items-center justify-between">
            <h3 className="text-[14px] font-semibold">{set}</h3>
            {canEdit && (
              <Button type="button" variant="ghost" size="sm" onClick={() => add(set)}>
                <Plus className="mr-1 h-3.5 w-3.5" />
                Add row
              </Button>
            )}
          </div>
          <div className="overflow-x-auto rounded-[var(--sd-radius-lg)] border border-[var(--sd-line)]">
            <table className="w-full min-w-[34rem] text-[13px]">
              <thead>
                <tr className="border-b border-[var(--sd-line)] text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
                  <th className="px-3 py-2 font-medium">Label</th>
                  <th className="w-24 px-3 py-2 font-medium">From</th>
                  <th className="w-24 px-3 py-2 font-medium">Up to</th>
                  <th className="w-32 px-3 py-2 font-medium">Severity</th>
                  <th className="w-10" />
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) =>
                  r.band_set !== set ? null : (
                    <tr key={i} className="border-b border-[var(--sd-line-soft)] last:border-0">
                      <td className="px-3 py-1.5"><Input aria-label={`${set} label`} value={r.label} disabled={!canEdit} onChange={(e) => edit(i, { label: e.target.value })} /></td>
                      <td className="px-3 py-1.5"><Input aria-label={`${set} from`} type="number" step="any" value={r.min} disabled={!canEdit} onChange={(e) => edit(i, { min: e.target.value })} /></td>
                      <td className="px-3 py-1.5"><Input aria-label={`${set} up to`} type="number" step="any" value={r.max} disabled={!canEdit} onChange={(e) => edit(i, { max: e.target.value })} /></td>
                      <td className="px-3 py-1.5">
                        <select
                          aria-label={`${set} severity`}
                          value={r.severity}
                          disabled={!canEdit}
                          onChange={(e) => edit(i, { severity: e.target.value as Severity })}
                          className="h-9 w-full rounded-md border border-[var(--sd-line)] bg-transparent px-2 text-[13px]"
                        >
                          {SEVERITIES.map((s) => <option key={s}>{s}</option>)}
                        </select>
                      </td>
                      <td className="px-1">
                        {canEdit && (
                          <button type="button" aria-label={`Remove ${set} row`} onClick={() => remove(i)} className="p-1.5 text-[var(--sd-quiet)] hover:text-[var(--sd-data-red)]">
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        </section>
      ))}
      {canEdit && (
        <div className="flex justify-end">
          <Button type="button" onClick={() => void save()} disabled={!dirty || saving}>
            {saving ? "Saving" : "Save bands"}
          </Button>
        </div>
      )}
    </div>
  );
}

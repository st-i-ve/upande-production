import { useCallback, useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { DatePicker } from "@/components/DatePicker";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { kes, shortDate } from "@/lib/format";
import { isError } from "@/lib/frappe";
import { deleteRate, getLabourSettings, listRates, saveRate, type RatePeriod } from "@/lib/labourpay-api";
import { todayISO } from "@/lib/utils";

interface Draft {
  name?: string;
  valid_from: string;
  valid_to: string;
  rate: string;
  daily_target: string;
  note: string;
}

const blank = (): Draft => ({ valid_from: todayISO(), valid_to: "", rate: "", daily_target: "", note: "" });
const toDraft = (r: RatePeriod): Draft => ({
  name: r.name,
  valid_from: r.valid_from,
  valid_to: r.valid_to ?? "",
  rate: r.rate == null ? "" : String(r.rate),
  daily_target: r.daily_target ? String(r.daily_target) : "",
  note: r.note ?? "",
});

/** What a period with no rate of its own pays: the daily wage spread over the daily target. */
export function derivedRate(wage: number | null | undefined, target: number): number | null {
  return wage && target > 0 ? Math.round((wage / target) * 100) / 100 : null;
}

/**
 * An operation's rate periods: each has the dates it applies, a rate per work unit and/or a daily
 * target. Work is paid at the rate of the period its date falls in; periods may not overlap.
 */
export function RatePeriodsDialog({
  operation,
  operationName,
  workUom,
  canEdit,
  onClose,
}: {
  operation: string;
  operationName: string;
  workUom?: string;
  canEdit: boolean;
  onClose: () => void;
}) {
  const toast = useToast();
  const [rates, setRates] = useState<RatePeriod[] | null>(null);
  const [wage, setWage] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const r = await listRates(operation);
    if (isError(r)) {
      setError(r.error);
      setRates([]);
      return;
    }
    setError(null);
    setRates(r.rates);
  }, [operation]);

  useEffect(() => {
    void load();
    void getLabourSettings().then((s) => {
      if (!isError(s) && s.daily_wage != null) setWage(Number(s.daily_wage));
    });
  }, [load]);

  const set = (p: Partial<Draft>) => setDraft((d) => (d ? { ...d, ...p } : d));

  async function save() {
    if (!draft) return;
    setBusy(true);
    const r = await saveRate({
      operation,
      valid_from: draft.valid_from,
      valid_to: draft.valid_to || null,
      rate: draft.rate === "" ? null : Number(draft.rate),
      daily_target: draft.daily_target === "" ? null : Number(draft.daily_target),
      note: draft.note.trim(),
      ...(draft.name ? { name: draft.name } : {}),
    });
    setBusy(false);
    if (isError(r)) return void toast(r.error, "error");
    toast("Rate period saved.");
    setDraft(null);
    void load();
  }

  async function remove(p: RatePeriod) {
    if (!window.confirm(`Delete the rate period starting ${shortDate(p.valid_from)}?`)) return;
    const r = await deleteRate(p.name);
    if (isError(r)) return void toast(r.error, "error");
    toast("Rate period deleted.");
    void load();
  }

  const hint = draft && draft.rate === "" && Number(draft.daily_target) > 0;
  const derived = hint ? derivedRate(wage, Number(draft!.daily_target)) : null;
  const unit = workUom || "unit";

  return (
    <Dialog open onOpenChange={(o) => !o && !busy && onClose()}>
      <DialogContent className="max-w-3xl" aria-describedby="rp-desc">
        <DialogHeader>
          <DialogTitle>Rate periods: {operationName}</DialogTitle>
          <DialogDescription id="rp-desc">
            Work is paid at the rate of the period its date falls in. Periods for one operation may not overlap; leave Valid to blank for a period that has no end.
          </DialogDescription>
        </DialogHeader>

        {error ? (
          <p role="alert" className="text-[13px] text-[var(--sd-muted)]">{error}</p>
        ) : !rates ? (
          <p className="text-[13px] text-[var(--sd-muted)]">Loading rate periods…</p>
        ) : rates.length === 0 ? (
          <p className="text-[13px] text-[var(--sd-muted)]">No rate periods yet. Work is paid at the operation's default rate.</p>
        ) : (
          <div className="overflow-x-auto rounded-[var(--sd-radius-lg)] border border-[var(--sd-line)]">
            <table className="w-full text-[13px]">
              <thead>
                <tr className="border-b border-[var(--sd-line)] text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
                  <th className="px-3 py-2 font-medium">Valid from</th>
                  <th className="px-3 py-2 font-medium">Valid to</th>
                  <th className="px-3 py-2 text-right font-medium">Rate</th>
                  <th className="px-3 py-2 text-right font-medium">Daily target</th>
                  <th className="px-3 py-2 font-medium">Note</th>
                  <th className="w-24" />
                </tr>
              </thead>
              <tbody>
                {rates.map((p) => (
                  <tr key={p.name} className="border-b border-[var(--sd-line-soft)] last:border-0">
                    <td className="px-3 py-2 tabular-nums">{shortDate(p.valid_from)}</td>
                    <td className="px-3 py-2 tabular-nums text-[var(--sd-muted)]">{p.valid_to ? shortDate(p.valid_to) : "Open"}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{p.rate == null ? "from daily wage" : kes(p.rate)}</td>
                    <td className="px-3 py-2 text-right tabular-nums text-[var(--sd-muted)]">{p.daily_target ? `${p.daily_target} ${p.uom ?? ""}`.trim() : "—"}</td>
                    <td className="px-3 py-2 text-[var(--sd-muted)]">{p.note || "—"}</td>
                    <td className="px-3 py-2 text-right">
                      {canEdit && (
                        <span className="inline-flex gap-1">
                          <Button size="sm" variant="outline" className="h-7 rounded-full px-3 text-[12px]" onClick={() => setDraft(toDraft(p))} aria-label={`Edit period from ${p.valid_from}`}>
                            Edit
                          </Button>
                          <button type="button" aria-label={`Delete period from ${p.valid_from}`} onClick={() => void remove(p)} className="p-1.5 text-[var(--sd-quiet)] hover:text-[var(--sd-data-red)]">
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {draft ? (
          <div className="grid gap-3 rounded-[var(--sd-radius-lg)] bg-[var(--sd-bg-soft)] p-4 sm:grid-cols-2" data-testid="rate-form">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rp-from">Valid from</Label>
              <DatePicker id="rp-from" aria-label="Valid from" value={draft.valid_from} onChange={(v) => set({ valid_from: v })} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rp-to">Valid to (blank = open)</Label>
              <div className="flex items-center gap-2">
                <DatePicker id="rp-to" aria-label="Valid to" value={draft.valid_to} onChange={(v) => set({ valid_to: v })} placeholder="Open" />
                {draft.valid_to && (
                  <Button type="button" variant="ghost" size="sm" onClick={() => set({ valid_to: "" })}>
                    Clear
                  </Button>
                )}
              </div>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rp-rate">Rate per {unit}</Label>
              <Input id="rp-rate" type="number" min="0" inputMode="decimal" value={draft.rate} onChange={(e) => set({ rate: e.target.value })} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="rp-target">Daily target ({unit} per person)</Label>
              <Input id="rp-target" type="number" min="0" inputMode="decimal" value={draft.daily_target} onChange={(e) => set({ daily_target: e.target.value })} />
            </div>
            {hint && (
              <p className="text-[12.5px] text-[var(--sd-muted)] sm:col-span-2" data-testid="rate-hint">
                With no rate, pay is the daily wage ÷ the daily target
                {derived != null ? ` = ${kes(derived)} per ${unit}` : ""}.
              </p>
            )}
            <div className="flex flex-col gap-1.5 sm:col-span-2">
              <Label htmlFor="rp-note">Note</Label>
              <Input id="rp-note" value={draft.note} onChange={(e) => set({ note: e.target.value })} />
            </div>
            <div className="flex justify-end gap-2 sm:col-span-2">
              <Button variant="outline" onClick={() => setDraft(null)} disabled={busy}>
                Cancel
              </Button>
              <Button onClick={() => void save()} disabled={busy || !draft.valid_from}>
                {busy ? "Saving…" : "Save period"}
              </Button>
            </div>
          </div>
        ) : (
          canEdit && (
            <div>
              <Button size="sm" className="rounded-full" onClick={() => setDraft(blank())}>
                <Plus className="h-4 w-4" /> Add rate period
              </Button>
            </div>
          )
        )}
      </DialogContent>
    </Dialog>
  );
}

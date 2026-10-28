import { useEffect, useMemo, useState } from "react";
import { DatePicker } from "@/components/DatePicker";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { useToast } from "@/components/Toast";
import { saveDryMatter, type DryMatterPage } from "@/lib/avocado-api";
import { isError } from "@/lib/frappe";
import { cn } from "@/lib/utils";

type Form = DryMatterPage["form"];

/** Same rule the server uses (avocadomaturity._dry_matter): a moisture fraction, a moisture percentage, or a figure already dry matter. */
export function dryMatterOf(v: string): number | null {
  const n = Number(v);
  if (!v.trim() || !Number.isFinite(n) || n <= 0) return null;
  if (n <= 1) return Math.round((1 - n) * 1000) / 10;
  if (n >= 50) return Math.round((100 - n) * 10) / 10;
  return Math.round(n * 10) / 10;
}

export function windowOf(dm: number, form: Pick<Form, "min_pct" | "max_pct">): "under" | "in" | "over" {
  return dm >= form.max_pct ? "over" : dm >= form.min_pct ? "in" : "under";
}

const WIN_TEXT = { under: "text-[var(--sd-data-red)]", in: "text-[var(--sd-data-green)]", over: "text-[var(--sd-target)]" };

export function RecordSampleDialog({
  open,
  onOpenChange,
  form,
  defaultBlock,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  form: Form;
  defaultBlock?: string;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [block, setBlock] = useState("");
  const [area, setArea] = useState("");
  const [week, setWeek] = useState(String(form.week_number));
  const [date, setDate] = useState(form.today);
  const [vals, setVals] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (open) {
      setBlock(defaultBlock ?? "");
      setArea("");
      setWeek(String(form.week_number));
      setDate(form.today);
      setVals({});
      setTried(false);
    }
  }, [open, defaultBlock, form.week_number, form.today]);

  const rows = useMemo(
    () => form.sizes.map((s) => ({ ...s, dm: dryMatterOf(vals[s.count] ?? ""), raw: vals[s.count] ?? "" })),
    [form.sizes, vals],
  );
  const entered = rows.filter((r) => r.dm != null);
  const bad = rows.filter((r) => r.raw.trim() !== "" && r.dm == null);
  const avg = entered.length ? Math.round((entered.reduce((t, r) => t + (r.dm as number), 0) / entered.length) * 10) / 10 : null;
  const ready = entered.filter((r) => (r.dm as number) >= form.min_pct).length;
  const win = avg != null ? windowOf(avg, form) : null;
  const weekN = Number(week);

  const problems: string[] = [];
  if (!block && !area.trim()) problems.push("Name the block, or the planting area the test was run for.");
  if (!Number.isInteger(weekN) || weekN < 1 || weekN > 53) problems.push("Week number must be between 1 and 53.");
  if (!entered.length) problems.push("Enter at least one moisture reading.");
  if (bad.length) problems.push(`Cannot read the moisture for ${bad.map((b) => `${b.count}s`).join(", ")}.`);

  const save = async () => {
    setTried(true);
    if (problems.length) return;
    setBusy(true);
    const r = await saveDryMatter({
      readings: entered.map((e) => ({ count_size: e.count, moisture: e.raw.trim() })),
      orchard_block: block || undefined,
      planting_area: block ? undefined : area.trim(),
      week_number: weekN,
      test_date: date,
    });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(`${r.saved.length} reading${r.saved.length === 1 ? "" : "s"} saved.`, "ok", { hint: r.verdict });
    onOpenChange(false);
    onSaved();
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Record a sample</DialogTitle>
          <DialogDescription>
            Enter the moisture the lab reported, as 0.77 or as 77. Dry matter is worked out for you. A size you did not dry is left blank, not zero.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5 sm:col-span-2">
            <Label htmlFor="dm-block">Block</Label>
            <Picker
              id="dm-block"
              label="Block"
              value={block}
              onChange={setBlock}
              placeholder="Choose a block, or leave for an area test"
              clearable
              clearLabel="None, an area test"
              options={form.blocks.map((b) => ({ value: b.block, label: b.farm ? `${b.block} · ${b.farm}` : b.block }))}
            />
            <p className="text-[12px] text-[var(--sd-quiet)]">
              A planting-area reading is inherited by every block planted that year, so only use it when the test really was run for a whole area.
            </p>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="dm-area">Planting area</Label>
            <Input id="dm-area" list="dm-areas" value={area} disabled={!!block} onChange={(e) => setArea(e.target.value)} placeholder="23 Ha" />
            <datalist id="dm-areas">{form.areas.map((a) => <option key={a} value={a} />)}</datalist>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="dm-week">Week number</Label>
              <Input id="dm-week" type="number" min={1} max={53} value={week} onChange={(e) => setWeek(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Test date</Label>
              <DatePicker value={date} onChange={setDate} aria-label="Test date" className="w-full" />
            </div>
          </div>
        </div>

        <div className="overflow-x-auto rounded-xl border border-[var(--sd-line)]">
          <table className="w-full text-[13px]">
            <thead>
              <tr className="border-b border-[var(--sd-line)] text-left text-[11px] uppercase tracking-[0.1em] text-[var(--sd-quiet)]">
                <th className="px-3 py-2 font-medium">Count</th>
                <th className="px-3 py-2 font-medium">Fruit size</th>
                <th className="px-3 py-2 text-right font-medium">Moisture</th>
                <th className="px-3 py-2 text-right font-medium">Dry matter</th>
                <th className="px-3 py-2 font-medium" title={`The export window runs from ${form.min_pct}% to ${form.max_pct}% dry matter`}>Window</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const w = r.dm != null ? windowOf(r.dm, form) : null;
                return (
                  <tr key={r.count} className="border-b border-[var(--sd-line-soft)] last:border-0">
                    <td className="px-3 py-1.5 font-semibold">{r.count}s</td>
                    <td className="px-3 py-1.5 text-[var(--sd-muted)]">{r.min_g}–{r.max_g} g</td>
                    <td className="px-3 py-1.5 text-right">
                      <Input
                        aria-label={`Moisture for count ${r.count}`}
                        inputMode="decimal"
                        placeholder="0.77"
                        value={r.raw}
                        onChange={(e) => setVals((v) => ({ ...v, [r.count]: e.target.value }))}
                        className={cn("ml-auto h-8 w-24 text-right tabular-nums", r.raw.trim() && r.dm == null && "border-[var(--sd-data-red)]")}
                      />
                    </td>
                    <td className={cn("px-3 py-1.5 text-right font-semibold tabular-nums", w && WIN_TEXT[w])}>{r.dm != null ? `${r.dm.toFixed(1)}%` : "—"}</td>
                    <td className={cn("px-3 py-1.5 text-[12px]", w ? WIN_TEXT[w] : "text-[var(--sd-quiet)]")}>
                      {r.dm == null ? "—" : w === "over" ? "over window, pick now" : w === "in" ? "in window" : `short by ${(form.min_pct - r.dm).toFixed(1)} points`}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div
          data-testid="dm-verdict"
          className={cn("rounded-xl px-4 py-3 text-[13px] font-medium", win ? "bg-[var(--sd-bg-soft)]" : "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]", win && WIN_TEXT[win])}
        >
          {avg == null
            ? `Nothing entered · export floor ${form.min_pct}%`
            : `Average ${avg.toFixed(1)}% · ${ready} of ${entered.length} sizes at or above ${form.min_pct}% · ${
                win === "in" ? "ready to pick" : win === "over" ? "past the top of the window, pick now" : "not pickable for export yet"
              }`}
        </div>

        {tried && problems.length > 0 && (
          <ul role="alert" className="list-disc space-y-0.5 pl-5 text-[12.5px] text-[var(--sd-data-red)]">
            {problems.map((p) => <li key={p}>{p}</li>)}
          </ul>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>Cancel</Button>
          <Button onClick={save} disabled={busy}>{busy ? "Saving…" : "Save sample"}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

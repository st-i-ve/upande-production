import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, X } from "lucide-react";
import { DatePicker } from "@/components/DatePicker";
import { KpiCard } from "@/components/KpiCard";
import { RowsSkeleton, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { FilterSelect } from "@/components/FilterSelect";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { ToolbarButton } from "@/components/ToolbarButton";
import { useToast } from "@/components/Toast";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Picker } from "@/components/ui/picker";
import { listUnits, type UnitRow } from "@/lib/api";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { listDryMatterTests, saveDryMatterTest, type DryMatterTest } from "@/lib/drymatter-api";
import { isError } from "@/lib/frappe";
import { shortDate } from "@/lib/format";
import { cn, todayISO } from "@/lib/utils";

const READY = "bg-[var(--sd-alert-ok)] text-[var(--sd-sev-moderate)]";
const NOT_YET = "bg-[var(--sd-alert-warn)] text-[var(--sd-sev-high)]";

/** Mean of the readings, 2 dp, the same figure the server stores. */
export function averageOf(values: number[]): number | null {
  return values.length ? Math.round((values.reduce((t, v) => t + v, 0) / values.length) * 100) / 100 : null;
}

function Badge({ ready }: { ready: boolean }) {
  return (
    <span data-testid="dm-badge" className={cn("inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium", ready ? READY : NOT_YET)}>
      {ready ? "Ready to pick" : "Not yet"}
    </span>
  );
}

/** Dry matter tests for crops that switch them on (potatoes, mangoes ...). Avocado has its own page. */
export function DryMatterTests() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const [rows, setRows] = useState<DryMatterTest[] | null>(null);
  const [units, setUnits] = useState<UnitRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [unit, setUnit] = useState("");
  const [recording, setRecording] = useState(false);
  const target = crop.dry_matter_target_pct ?? null;
  const on = crop.dry_matter_on || "Fruit";

  const load = useCallback(async () => {
    setLoading(true);
    const r = await listDryMatterTests(crop.name, unit || null);
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setRows((r as { rows: DryMatterTest[] }).rows ?? []);
  }, [crop.name, unit, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    let live = true;
    void listUnits(crop.name).then((r) => {
      if (live && !isError(r)) setUnits((r as { units: UnitRow[] }).units.filter((u) => !u.is_group));
    });
    return () => {
      live = false;
    };
  }, [crop.name]);

  const first = firstLoad(loading, !!rows);
  const total = rows?.length ?? 0;
  const ready = (rows ?? []).filter((r) => !!Number(r.ready)).length;
  const unitOptions = useMemo(() => units.map((u) => u.name), [units]);

  return (
    <PageShell
      title={viewLabel("dry-matter-tests", crop)}
      eyebrow={crop.name}
      description={`Dry matter of the ${on.toLowerCase()}${target != null ? `, ready at ${target}% or more` : ""}. Several samples per test; the average decides.`}
      actions={
        <>
          <FilterSelect label={crop.unit_label} value={unit} onChange={setUnit} options={unitOptions} allLabel={`All ${crop.unit_label.toLowerCase()}s`} />
          <ClearFiltersPill active={!!unit} onClear={() => setUnit("")} />
          <RefreshButton onClick={load} loading={loading} label="the tests" />
          <ToolbarButton onClick={() => setRecording(true)}>
            <Plus className="h-4 w-4" />
            Record a test
          </ToolbarButton>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-3">
        <KpiCard loading={first} label="Tests" value={rows ? total : "—"} hint="recorded" />
        <KpiCard loading={first} label="Ready" value={rows ? `${ready} of ${total}` : "—"} hint={target != null ? `average at or above ${target}%` : "average at or above target"} tone={ready ? "good" : "default"} />
        <KpiCard loading={first} label="Not yet" value={rows ? total - ready : "—"} hint="below target" tone={total - ready ? "warning" : "default"} />
      </div>

      <Card className="mt-4 overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Tests</CardTitle>
            <CardDescription>Newest first. Green means the average reached the target.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first ? (
          <div className="px-5 pb-6"><RowsSkeleton rows={4} /></div>
        ) : rows && rows.length ? (
          <ScrollTable>
            <table className="w-full text-[13px]">
              <thead className={STICKY_HEAD}>
                <tr className={THEAD_ROW}>
                  <th className={TH}>Date</th>
                  <th className={TH}>{crop.unit_label}</th>
                  <th className={TH}>Variety</th>
                  <th className={THR}>Samples</th>
                  <th className={THR}>Average</th>
                  <th className={THR}>Target</th>
                  <th className={TH}>Verdict</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((t) => (
                  <tr key={t.name} className={BODY_ROW} data-testid={`dm-row-${t.name}`}>
                    <td className={cn(TD, "font-semibold tabular-nums")}>{shortDate(t.test_date)}</td>
                    <td className={TD}>{t.unit}</td>
                    <td className={cn(TD, "text-[var(--sd-muted)]")}>{t.variety || "—"}</td>
                    <td className={TDR}>{t.samples.length}</td>
                    <td className={cn(TDR, "font-semibold")}>{t.avg_pct.toFixed(1)}%</td>
                    <td className={cn(TDR, "text-[var(--sd-muted)]")}>{t.target_pct != null ? `${t.target_pct}%` : "—"}</td>
                    <td className={TD}><Badge ready={!!Number(t.ready)} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollTable>
        ) : (
          <p className="px-5 py-8 text-center text-[13px] text-[var(--sd-quiet)]">
            {unit ? `No test recorded for ${unit} yet.` : "No tests recorded yet. Use Record a test to add one."}
          </p>
        )}
      </Card>

      <RecordTestDialog open={recording} onOpenChange={setRecording} unitOptions={unitOptions} defaultUnit={unit} target={target} crop={crop.name} onSaved={load} />
    </PageShell>
  );
}

function RecordTestDialog({
  open,
  onOpenChange,
  unitOptions,
  defaultUnit,
  target,
  crop,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  unitOptions: string[];
  defaultUnit: string;
  target: number | null;
  crop: string;
  onSaved: () => void;
}) {
  const toast = useToast();
  const [unit, setUnit] = useState("");
  const [date, setDate] = useState(todayISO());
  const [vals, setVals] = useState<string[]>(["", "", ""]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setUnit(defaultUnit);
      setDate(todayISO());
      setVals(["", "", ""]);
    }
  }, [open, defaultUnit]);

  const nums = vals.map((v) => (v.trim() === "" ? null : Number(v)));
  const valid = nums.filter((n): n is number => n != null && Number.isFinite(n) && n > 0 && n < 100);
  const bad = nums.some((n, i) => vals[i].trim() !== "" && (n == null || !Number.isFinite(n) || n <= 0 || n >= 100));
  const avg = averageOf(valid);
  const isReady = avg != null && target != null && avg >= target;

  async function save() {
    setBusy(true);
    const r = await saveDryMatterTest({
      crop,
      unit,
      test_date: date,
      samples: valid.map((v, i) => ({ sample_no: i + 1, dry_matter_pct: v })),
    });
    setBusy(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    toast(`Test saved: average ${r.avg_pct.toFixed(1)}%, ${r.ready ? "ready to pick" : "not yet ready"}.`);
    onOpenChange(false);
    onSaved();
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <DialogContent className="max-w-md" aria-describedby="dmt-desc">
        <DialogHeader>
          <DialogTitle>Record a dry matter test</DialogTitle>
          <DialogDescription id="dmt-desc">Enter the dry matter % of each sample. The average is compared with the target.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label>Where</Label>
          <Picker label="Where" value={unit} onChange={setUnit} options={unitOptions} placeholder="Choose where" />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label>Test date</Label>
          <DatePicker value={date} onChange={setDate} aria-label="Test date" className="w-full" />
        </div>
        <div className="flex flex-col gap-2">
          <Label>Samples (dry matter %)</Label>
          {vals.map((v, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="w-16 text-[12px] text-[var(--sd-quiet)]">Sample {i + 1}</span>
              <Input
                inputMode="decimal"
                aria-label={`Sample ${i + 1} dry matter`}
                value={v}
                onChange={(e) => setVals((a) => a.map((x, j) => (j === i ? e.target.value : x)))}
              />
              {vals.length > 1 && (
                <button type="button" aria-label={`Remove sample ${i + 1}`} className="text-[var(--sd-quiet)] hover:text-[var(--sd-ink)]" onClick={() => setVals((a) => a.filter((_, j) => j !== i))}>
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
          <Button variant="outline" className="self-start" onClick={() => setVals((a) => [...a, ""])}>
            Add a sample
          </Button>
        </div>
        <div className="flex items-center gap-2 text-[13px]" data-testid="dmt-average">
          <span className="text-[var(--sd-muted)]">Average</span>
          <span className="font-semibold tabular-nums">{avg != null ? `${avg.toFixed(1)}%` : "—"}</span>
          {avg != null && target != null && <Badge ready={isReady} />}
          {target != null && <span className="text-[var(--sd-quiet)]">target {target}%</span>}
        </div>
        {bad && <p className="text-[12px] text-[var(--sd-data-red)]">Each sample must be a percentage between 0 and 100.</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </Button>
          <Button onClick={() => void save()} disabled={busy || !unit || !valid.length || bad}>
            {busy ? "Saving…" : "Save test"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

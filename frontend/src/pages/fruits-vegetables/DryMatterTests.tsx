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
import { listDryMatterDue, listDryMatterTests, saveDryMatterTest, type DryMatterTest, type DueList, type DueRow } from "@/lib/drymatter-api";
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

const DUE = "bg-[var(--sd-alert-warn)] text-[var(--sd-sev-high)]";
const RECENT = "bg-[var(--sd-alert-ok)] text-[var(--sd-sev-moderate)]";
const WAITING = "bg-[var(--sd-bg-soft)] text-[var(--sd-quiet)]";

function DueChip({ r, days }: { r: DueRow; days: number }) {
  if (r.state === "due")
    return (
      <span data-testid="due-chip" className={cn("inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium", DUE)}>
        {r.last_test ? `Due, last test ${r.days_since} d ago` : "Due, never sampled"}
      </span>
    );
  if (r.state === "recent")
    return (
      <span data-testid="due-chip" className={cn("inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium", RECENT)}>
        Tested {r.days_since === 0 ? "today" : `${r.days_since} d ago`}
      </span>
    );
  return (
    <span data-testid="due-chip" title={`Sampling starts at ${r.from_stage ?? "the first stage"}; retest after ${days} days`} className={cn("inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium", WAITING)}>
      Not yet at {r.from_stage}
    </span>
  );
}

/** Dry matter tests for the varieties that are tested (potatoes, onions, cabbage ...). Avocado has its own page. */
export function DryMatterTests() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const [rows, setRows] = useState<DryMatterTest[] | null>(null);
  const [due, setDue] = useState<DueList | null>(null);
  const [recordFor, setRecordFor] = useState("");
  const [units, setUnits] = useState<UnitRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [unit, setUnit] = useState("");
  const [recording, setRecording] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await listDryMatterTests(crop.name, unit || null);
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setRows((r as { rows: DryMatterTest[] }).rows ?? []);
    const d = await listDryMatterDue(crop.name);
    if (!isError(d)) setDue(d as DueList);
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
  const dueRows = useMemo(() => (due?.rows ?? []).filter((r) => !unit || r.unit === unit), [due, unit]);
  const dueNow = dueRows.filter((r) => r.state === "due").length;
  const dueOf = (u: string) => (due?.rows ?? []).find((r) => r.unit === u) ?? null;

  return (
    <PageShell
      title={viewLabel("dry-matter-tests", crop)}
      eyebrow={crop.name}
      description="Each variety is tested on its own part (tuber, bulb, head, fruit) and is ready at its own target. Sampling is due from the variety's sampling stage. Several samples per test; the average decides."
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
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <KpiCard loading={first} label="Due for sampling" value={due ? dueNow : "—"} hint={due ? `no test in ${due.retest_days} days, in or past the sampling stage` : ""} tone={dueNow ? "warning" : "default"} />
        <KpiCard loading={first} label="Tests" value={rows ? total : "—"} hint="recorded" />
        <KpiCard loading={first} label="Ready" value={rows ? `${ready} of ${total}` : "—"} hint="average at or above the variety's target" tone={ready ? "good" : "default"} />
        <KpiCard loading={first} label="Not yet" value={rows ? total - ready : "—"} hint="below target" tone={total - ready ? "warning" : "default"} />
      </div>

      <Card className="mt-4 overflow-hidden" data-testid="dm-due">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Due for sampling</CardTitle>
            <CardDescription>
              {due ? `A ${crop.unit_label.toLowerCase()} is due when its crop is in or past the variety's sampling stage and has no test in the last ${due.retest_days} days (Production Settings).` : "Blocks that are in or past their sampling stage."}
            </CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !due ? (
          <div className="px-5 pb-6"><RowsSkeleton rows={3} /></div>
        ) : dueRows.length ? (
          <ScrollTable>
            <table className="w-full text-[13px]">
              <thead className={STICKY_HEAD}>
                <tr className={THEAD_ROW}>
                  <th className={TH}>{crop.unit_label}</th>
                  <th className={TH}>Variety</th>
                  <th className={TH}>Stage now</th>
                  <th className={TH}>Sample from</th>
                  <th className={TH}>Tested on</th>
                  <th className={THR}>Last test</th>
                  <th className={THR}>Target</th>
                  <th className={TH}>Sampling</th>
                  <th className={TH}><span className="sr-only">Record</span></th>
                </tr>
              </thead>
              <tbody>
                {dueRows.map((r) => (
                  <tr key={r.unit} className={BODY_ROW} data-testid={`due-row-${r.unit}`}>
                    <td className={cn(TD, "font-semibold")}>{r.unit}</td>
                    <td className={cn(TD, "text-[var(--sd-muted)]")}>{r.variety || "—"}</td>
                    <td className={TD}>{r.stage || "—"}</td>
                    <td className={cn(TD, "text-[var(--sd-muted)]")}>{r.from_stage || "from the start"}</td>
                    <td className={cn(TD, "text-[var(--sd-muted)]")}>{r.on || "—"}</td>
                    <td className={cn(TDR, "tabular-nums")}>{r.last_test ? `${shortDate(r.last_test)}${r.last_pct != null ? ` · ${r.last_pct.toFixed(1)}%` : ""}` : "never"}</td>
                    <td className={cn(TDR, "text-[var(--sd-muted)]")}>{r.target_pct != null ? `${r.target_pct}%` : "—"}</td>
                    <td className={TD}><DueChip r={r} days={due.retest_days} /></td>
                    <td className={TD}>
                      {r.state !== "not_yet" && (
                        <Button variant="outline" size="sm" aria-label={`Record a test for ${r.unit}`} onClick={() => { setRecordFor(r.unit); setRecording(true); }}>Record</Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollTable>
        ) : (
          <p className="px-5 py-8 text-center text-[13px] text-[var(--sd-quiet)]">No {crop.unit_label.toLowerCase()} with a tested variety{unit ? ` for ${unit}` : ""} has an open cycle.</p>
        )}
      </Card>

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
                  <th className={TH}>Stage</th>
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
                    <td className={cn(TD, "text-[var(--sd-muted)]")} data-testid={`dm-stage-${t.name}`}>{t.stage || "—"}</td>
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

      <RecordTestDialog open={recording} onOpenChange={(o) => { setRecording(o); if (!o) setRecordFor(""); }} unitOptions={unitOptions} defaultUnit={recordFor || unit} dueOf={dueOf} fallbackTarget={crop.dry_matter_target_pct ?? null} crop={crop.name} onSaved={load} />
    </PageShell>
  );
}

function RecordTestDialog({
  open,
  onOpenChange,
  unitOptions,
  defaultUnit,
  dueOf,
  fallbackTarget,
  crop,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  unitOptions: string[];
  defaultUnit: string;
  dueOf: (unit: string) => DueRow | null;
  /** The crop's default target, used until a block (and so a variety) is chosen. */
  fallbackTarget: number | null;
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
  const info = dueOf(unit);
  const target = info?.target_pct ?? fallbackTarget;
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
          {info && (
            <span className="text-[12px] text-[var(--sd-quiet)]" data-testid="dmt-variety">
              {info.variety ?? "No variety"}{info.stage ? `, now in ${info.stage}` : ""}{info.on ? `, tested on the ${info.on.toLowerCase()}` : ""}
            </span>
          )}
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

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Plus } from "lucide-react";
import { AccentScope } from "@/components/avocado/calendar-grid";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { DateRangePicker, type DateRange } from "@/components/DateRangePicker";
import { FilterSelect } from "@/components/FilterSelect";
import { GradeBars, GradeLegend } from "@/components/fv/GradeBars";
import { GradeTrend } from "@/components/fv/GradeTrend";
import { GradingDialog } from "@/components/fv/GradingDialog";
import { ReasonBreakdown } from "@/components/fv/ReasonBreakdown";
import { dayMonth, defaultRange, fmtNum, weeklySeries } from "@/components/fv/fv-format";
import { KpiCard } from "@/components/KpiCard";
import { Bar, ChartSkeleton, firstLoad, TableRowsSkeleton } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { ToolbarButton } from "@/components/ToolbarButton";
import { useToast } from "@/components/Toast";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { TableBody } from "@/components/ui/table";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { getGrading, type GradingPage } from "@/lib/fv-api";
import { todayISO } from "@/lib/utils";

/** Grading: how each harvest split by grade, rejects and why, week by week. */
export function Grading() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#3f7d3a";
  const initial = useMemo(defaultRange, []);
  const [range, setRange] = useState<DateRange>(initial);
  const [unit, setUnit] = useState("");
  const [item, setItem] = useState("");
  const [data, setData] = useState<GradingPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [recording, setRecording] = useState(false);
  const seq = useRef(0);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setLoading(true);
    const r = await getGrading({ from_date: range.from, to_date: range.to, unit: unit || undefined, item: item || undefined });
    if (mine !== seq.current) return;
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setData(r as GradingPage);
  }, [range, unit, item, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const first = firstLoad(loading, !!data);
  const k = data?.kpis;
  const dirty = !!unit || !!item || range.from !== initial.from || range.to !== initial.to;
  const clear = () => {
    setUnit("");
    setItem("");
    setRange(initial);
  };

  return (
    <PageShell
      title={viewLabel("grading", crop)}
      eyebrow={crop.name}
      description={data ? `${data.kpis.logs} grading log${data.kpis.logs === 1 ? "" : "s"} · ${fmtNum(data.kpis.received_kg)} kg received` : undefined}
      actions={
        <>
          <DateRangePicker label="Period" value={range} onChange={setRange} max={todayISO()} />
          <FilterSelect label="Block" value={unit} onChange={setUnit} options={data?.units ?? []} allLabel="All blocks" />
          <FilterSelect label="Crop item" value={item} onChange={setItem} options={data?.items ?? []} allLabel="All crops" />
          <ClearFiltersPill active={dirty} onClear={clear} />
          <RefreshButton onClick={load} loading={loading} label="the grading logs" />
          <ToolbarButton onClick={() => setRecording(true)} disabled={!data}>
            <Plus className="h-4 w-4" />
            Record grading
          </ToolbarButton>
        </>
      }
    >
      <AccentScope accent={accent} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <KpiCard loading={first} label="Graded" value={k ? `${fmtNum(k.graded_kg)} kg` : "—"} hint={k ? `of ${fmtNum(k.received_kg)} kg received` : undefined} series={data ? weeklySeries(data.series, (s) => s.graded_kg) : undefined} goodDirection="up" />
          <KpiCard loading={first} label="Class 1" value={k ? `${fmtNum(k.class1_pct, 1)}%` : "—"} hint="share of graded kg" series={data ? weeklySeries(data.series, (s) => s.class1_pct) : undefined} goodDirection="up" tone="good" />
          <KpiCard loading={first} label="Rejects" value={k ? `${fmtNum(k.reject_pct, 1)}%` : "—"} hint={k ? `${fmtNum(k.rejects_kg)} kg of what was received` : undefined} series={data ? weeklySeries(data.series, (s) => s.reject_pct) : undefined} goodDirection="down" tone={k && k.reject_pct > 6 ? "warning" : "default"} />
          <KpiCard loading={first} label="Top reject reason" value={k?.top_reject_reason ?? (k ? "None" : "—")} hint={k?.top_reject_reason ? `${fmtNum(k.top_reject_pct, 0)}% of rejected kg` : undefined} />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Grade split by crop</CardTitle>
                <CardDescription>Each bar is the kg that came in, split by grade and rejects.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            {first || !data ? <div className="px-5 pb-5"><ChartSkeleton height={160} /></div> : (
              <>
                <GradeLegend grades={data.grades} accent={accent} />
                <GradeBars rows={data.by_item} grades={data.grades} accent={accent} testId="by-item" />
              </>
            )}
          </Card>
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Reject reasons</CardTitle>
                <CardDescription>Kg rejected, by the reason given at grading.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            {first || !data ? <div className="px-5 pb-5"><Bar className="h-24 w-full" /></div> : <ReasonBreakdown reasons={data.reasons} />}
          </Card>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Grade split by block</CardTitle>
                <CardDescription>Which blocks give the best class 1.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            {first || !data ? <div className="px-5 pb-5"><ChartSkeleton height={160} /></div> : <GradeBars rows={data.by_block} grades={data.grades} accent={accent} testId="by-block" />}
          </Card>
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Weekly trend</CardTitle>
                <CardDescription>Volume graded and class 1 share.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            {first || !data ? <div className="px-5 pb-5"><ChartSkeleton height={180} /></div> : <GradeTrend series={data.series} accent={accent} />}
          </Card>
        </div>

        <Card>
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>Grading logs</CardTitle>
              <CardDescription>Newest first.</CardDescription>
            </CardHeading>
          </CardHeaderRow>
          <div className="px-5 pb-5">
            {data && !data.rows.length ? (
              <p className="py-6 text-center text-[13px] text-[var(--sd-quiet)]" data-testid="no-logs">No grading in this period. Widen the dates, or record a grading.</p>
            ) : (
              <ScrollTable tall>
                <table className="w-full text-[13px]">
                  <thead className={STICKY_HEAD}>
                    <tr className={THEAD_ROW}>
                      <th className={TH}>Date</th>
                      <th className={TH}>Block</th>
                      <th className={TH}>Crop</th>
                      <th className={THR}>Received kg</th>
                      <th className={THR}>Class 1 kg</th>
                      <th className={THR}>Graded kg</th>
                      <th className={THR}>Rejects kg</th>
                      <th className={TH}>Reason</th>
                    </tr>
                  </thead>
                  <TableBody>
                    {first || !data ? (
                      <TableRowsSkeleton cols={8} rows={5} />
                    ) : (
                      data.rows.map((r) => (
                        <tr key={r.name} className={BODY_ROW} data-testid="grading-row">
                          <td className={TD}>{dayMonth(r.grading_date)}</td>
                          <td className={TD}>{r.unit}</td>
                          <td className={TD}>{r.item ?? "—"}</td>
                          <td className={TDR}>{fmtNum(r.received_kg, 1)}</td>
                          <td className={TDR}>{fmtNum(r.class1_kg, 1)}</td>
                          <td className={TDR}>{fmtNum(r.graded_kg, 1)}</td>
                          <td className={TDR}>{fmtNum(r.rejects_kg, 1)}</td>
                          <td className={TD}>{r.reject_reason ?? "—"}</td>
                        </tr>
                      ))
                    )}
                  </TableBody>
                </table>
              </ScrollTable>
            )}
          </div>
        </Card>
      </AccentScope>
      {data && <GradingDialog open={recording} onOpenChange={setRecording} form={data.form} defaultUnit={unit || undefined} onSaved={load} />}
    </PageShell>
  );
}

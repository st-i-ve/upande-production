import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Plus } from "lucide-react";
import { AccentScope } from "@/components/avocado/calendar-grid";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { DateRangePicker, type DateRange } from "@/components/DateRangePicker";
import { FaultList } from "@/components/fv/FaultList";
import { IrrigationDialog } from "@/components/fv/IrrigationDialog";
import { PivotMap } from "@/components/fv/PivotMap";
import { RunTimeline } from "@/components/fv/RunTimeline";
import { defaultRange, fmtNum, weeklySeries } from "@/components/fv/fv-format";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard } from "@/components/KpiCard";
import { Bar, ChartSkeleton, firstLoad } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ToolbarButton } from "@/components/ToolbarButton";
import { useToast } from "@/components/Toast";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { getIrrigation, type IrrigationPage } from "@/lib/fv-api";
import { todayISO } from "@/lib/utils";

/** Irrigation: pivot runs, water applied per slice against the weekly target, and faults. */
export function Irrigation() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#3f7d3a";
  const initial = useMemo(defaultRange, []);
  const [range, setRange] = useState<DateRange>(initial);
  const [pivot, setPivot] = useState("");
  const [data, setData] = useState<IrrigationPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [recording, setRecording] = useState(false);
  const seq = useRef(0);

  const load = useCallback(async () => {
    const mine = ++seq.current;
    setLoading(true);
    const r = await getIrrigation({ from_date: range.from, to_date: range.to, pivot: pivot || undefined });
    if (mine !== seq.current) return;
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setData(r as IrrigationPage);
  }, [range, pivot, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const first = firstLoad(loading, !!data);
  const k = data?.kpis;
  const dirty = !!pivot || range.from !== initial.from || range.to !== initial.to;
  const clear = () => {
    setPivot("");
    setRange(initial);
  };

  return (
    <PageShell
      title={viewLabel("irrigation", crop)}
      eyebrow={crop.name}
      description={data ? `Target ${fmtNum(data.target.weekly_mm, 0)} mm per slice per week · ${fmtNum(data.target.period_mm, 0)} mm over this period` : undefined}
      actions={
        <>
          <DateRangePicker label="Period" value={range} onChange={setRange} max={todayISO()} />
          <FilterSelect label="Pivot" value={pivot} onChange={setPivot} options={data?.pivot_names ?? []} allLabel="All pivots" />
          <ClearFiltersPill active={dirty} onClear={clear} />
          <RefreshButton onClick={load} loading={loading} label="the irrigation runs" />
          <ToolbarButton onClick={() => setRecording(true)} disabled={!data}>
            <Plus className="h-4 w-4" />
            Record run
          </ToolbarButton>
        </>
      }
    >
      <AccentScope accent={accent} className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <KpiCard loading={first} label="Runs" value={k ? fmtNum(k.runs) : "—"} hint={k ? `${fmtNum(k.hours, 0)} pivot hours` : undefined} series={data ? weeklySeries(data.series, (s) => s.runs) : undefined} goodDirection="up" />
          <KpiCard loading={first} label="Water per slice" value={k ? `${fmtNum(k.mm_per_slice_avg, 0)} mm` : "—"} hint={k ? `${fmtNum(k.mm_total, 0)} mm applied in total · ${k.slices_on_target} of ${k.slices} slices on target` : undefined} series={data ? weeklySeries(data.series, (s) => s.mm_per_slice) : undefined} goodDirection="up" tone="good" />
          <KpiCard loading={first} label="Pivot utilisation" value={k ? `${fmtNum(k.utilisation_pct, 1)}%` : "—"} hint="hours run of hours in the period" series={data ? weeklySeries(data.series, (s) => s.hours) : undefined} />
          <KpiCard loading={first} label="Faults" value={k ? fmtNum(k.faults) : "—"} hint={k ? (k.faults ? "runs cut short or stopped" : "no faults") : undefined} tone={k?.faults ? "critical" : "default"} />
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Water applied by slice</CardTitle>
                <CardDescription>Each slice shaded by the mm it received against the period target.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <div className="px-5 pb-5">
              {first || !data ? (
                <ChartSkeleton height={420} />
              ) : data.map.bounds ? (
                <PivotMap data={data} accent={accent} />
              ) : (
                <p className="py-10 text-center text-[13px] text-[var(--sd-quiet)]">No slice has a map outline yet, so the map is empty. The table to the right still shows the figures.</p>
              )}
            </div>
          </Card>
          <Card>
            <CardHeaderRow>
              <CardHeading>
                <CardTitle>Pivots</CardTitle>
                <CardDescription>Average mm per slice against target.</CardDescription>
              </CardHeading>
            </CardHeaderRow>
            <ul className="flex flex-col gap-4 px-5 pb-5" data-testid="pivot-summary">
              {first || !data
                ? [0, 1, 2, 3].map((i) => <li key={i}><Bar className="h-10 w-full" /></li>)
                : data.pivots.map((p) => {
                    const pct = data.target.period_mm ? Math.min((p.mm_per_slice / data.target.period_mm) * 100, 140) : 0;
                    return (
                      <li key={p.name} data-testid={`pivot-${p.name}`}>
                        <div className="flex items-baseline justify-between text-[13px]">
                          <span className="font-medium">{p.name}</span>
                          <span className="tabular-nums">{fmtNum(p.mm_per_slice, 0)} mm · {fmtNum(p.utilisation_pct, 0)}% used</span>
                        </div>
                        <div className="relative mt-1.5 h-2 rounded-full bg-[var(--sd-line-soft)]">
                          <span className="absolute left-0 top-0 h-full rounded-full" style={{ width: `${Math.min(pct, 100) / 1.4}%`, background: p.faults ? "#e0a030" : accent }} />
                          <span className="absolute top-[-3px] h-[14px] w-px bg-[var(--sd-ink)]" style={{ left: `${100 / 1.4}%` }} title="Target" />
                        </div>
                        <div className="mt-1 text-[12px] text-[var(--sd-quiet)]">
                          {p.runs} runs · {fmtNum(p.hours, 0)} h{p.faults ? ` · ${p.faults} fault${p.faults === 1 ? "" : "s"}` : ""}
                        </div>
                      </li>
                    );
                  })}
            </ul>
          </Card>
        </div>

        <Card>
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>Run timeline</CardTitle>
              <CardDescription>One lane per pivot. Red bars are runs that had a fault; hover a bar for the detail.</CardDescription>
            </CardHeading>
          </CardHeaderRow>
          {first || !data ? (
            <div className="px-5 pb-5"><ChartSkeleton height={160} /></div>
          ) : data.runs.length ? (
            <RunTimeline data={data} accent={accent} />
          ) : (
            <p className="px-5 pb-6 text-[13px] text-[var(--sd-quiet)]" data-testid="no-runs">No irrigation runs in this period. Widen the dates, or record a run.</p>
          )}
        </Card>

        <Card>
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>Faults</CardTitle>
              <CardDescription>Runs that stopped or were cut short, newest first.</CardDescription>
            </CardHeading>
          </CardHeaderRow>
          {first || !data ? <div className="px-5 pb-5"><Bar className="h-16 w-full" /></div> : <FaultList faults={data.faults} />}
        </Card>
      </AccentScope>
      {data && <IrrigationDialog open={recording} onOpenChange={setRecording} form={data.form} defaultPivot={pivot || undefined} onSaved={load} />}
    </PageShell>
  );
}

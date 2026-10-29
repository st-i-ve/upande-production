import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { AccentScope } from "@/components/avocado/calendar-grid";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { DateRangePicker, type DateRange } from "@/components/DateRangePicker";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard } from "@/components/KpiCard";
import { Bar, ChartSkeleton, firstLoad, TableRowsSkeleton } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { ToolbarButton } from "@/components/ToolbarButton";
import { useToast } from "@/components/Toast";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { GroupHealthCard } from "@/components/apiary/GroupHealthCard";
import { HealthTrendChart } from "@/components/apiary/charts";
import { InspectionDialog } from "@/components/apiary/InspectionDialog";
import { Chip, daysAgo, dayMonthYear, EmptyNote, fmt, MITE_LABEL, MITE_TONE, TONE } from "@/components/apiary/ui";
import { getHiveInspections, type HiveInspectionsPage } from "@/lib/apiary-api";
import { bandTone } from "@/lib/bands";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { todayISO } from "@/lib/utils";

const defaultRange = (): DateRange => ({ from: daysAgo(84), to: todayISO() });

export function HiveInspections() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#d9a514";
  const [data, setData] = useState<HiveInspectionsPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [unit, setUnit] = useState("");
  const [recording, setRecording] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await getHiveInspections({ from_date: range.from, to_date: range.to, unit: unit || undefined });
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setData(r as HiveInspectionsPage);
  }, [range, unit, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const first = firstLoad(loading, !!data);
  const k = data?.kpis;
  const threshold = data?.threshold ?? null;
  const dirty = !!unit || range.from !== defaultRange().from || range.to !== defaultRange().to;
  const unitOptions = useMemo(() => (data?.form.units ?? []).map((u) => ({ value: u.value, label: u.label })), [data]);
  const spark = (pick: (s: HiveInspectionsPage["series"][number]) => number | null) =>
    data?.series.filter((s) => pick(s) != null).map((s) => ({ week: s.week, value: pick(s) as number }));
  const trend = k?.mites_trend;

  return (
    <PageShell
      title={viewLabel("hive-inspections", crop)}
      eyebrow={crop.name}
      description={data ? `${dayMonthYear(data.from_date)} to ${dayMonthYear(data.to_date)} ${threshold != null ? `· treat colonies above ${threshold} mites per 100 bees` : "· set a mite threshold on the Apiary crop"}` : undefined}
      actions={
        <>
          <DateRangePicker label="Period" value={range} onChange={setRange} max={todayISO()} />
          <FilterSelect label="Hive group" value={unit} onChange={setUnit} options={unitOptions} allLabel="All hive groups" />
          <ClearFiltersPill active={dirty} onClear={() => { setUnit(""); setRange(defaultRange()); }} />
          <RefreshButton onClick={load} loading={loading} label="the inspections" />
          <ToolbarButton onClick={() => setRecording(true)} disabled={!data}>
            <Plus className="h-4 w-4" />
            Record inspection
          </ToolbarButton>
        </>
      }
    >
      <AccentScope accent={accent} className="grid grid-cols-2 gap-4 xl:grid-cols-3">
        <KpiCard loading={first} label="Inspections" value={k?.inspections ?? "—"} hint={k ? `${fmt(k.colonies)} colonies opened` : undefined} series={spark((s) => s.inspections)} showDelta={false} />
        <KpiCard loading={first} label="Colonies inspected" value={k?.colonies ?? "—"} hint="counted once per visit" series={spark((s) => s.colonies)} showDelta={false} />
        <KpiCard loading={first} label="Queenright" value={k?.queenright_pct != null ? `${fmt(k.queenright_pct, 1)}%` : "—"} hint="colonies with a laying queen" tone={bandTone(data?.bands, "Queen status", k?.queenright_pct)} series={spark((s) => s.queenright_pct)} showDelta={false} />
        <KpiCard
          loading={first}
          label="Average mite load"
          value={k?.avg_mites != null ? fmt(k.avg_mites, 1) : "—"}
          hint={trend == null ? "per 100 bees" : `per 100 bees · ${trend > 0 ? "up" : trend < 0 ? "down" : "level"} ${fmt(Math.abs(trend), 2)} on the previous period`}
          tone={k?.avg_mites != null && threshold != null && k.avg_mites > threshold ? "critical" : "default"}
          series={spark((s) => s.avg_mites)}
          goodDirection="down"
          deltaLabel="vs prev inspected week"
        />
        <KpiCard loading={first} label={threshold != null ? `Colonies over ${threshold} mites` : "Colonies over the mite limit"} value={k?.colonies_above_threshold ?? "—"} hint={k ? `${k.groups_above_threshold} hive group${k.groups_above_threshold === 1 ? "" : "s"}, by latest count` : undefined} tone={k?.colonies_above_threshold ? "critical" : "good"} />
        <KpiCard loading={first} label="Disease flags" value={k?.disease_flags ?? "—"} hint="inspections noting disease signs" tone={k?.disease_flags ? "warning" : "default"} series={spark((s) => s.disease_flags)} showDelta={false} />
      </AccentScope>

      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3" data-testid="hg-cards">
        {first || !data
          ? [0, 1, 2].map((i) => (
              <Card key={i} className="space-y-3 p-5" aria-busy="true">
                <Bar className="h-5 w-32" />
                <Bar className="h-9 w-24" />
                <Bar className="h-[110px] w-full" />
              </Card>
            ))
          : data.groups.map((g) => <GroupHealthCard key={g.unit} g={g} threshold={threshold} accent={accent} />)}
      </div>
      {data && !data.groups.length && (
        <p className="mt-4 rounded-2xl bg-[var(--sd-card)] px-5 py-10 text-center text-[13px] text-[var(--sd-quiet)] shadow-[var(--sd-shadow-1)]">
          No hive groups yet. Add Production Units for the Apiary crop to start recording.
        </p>
      )}

      <Card className="mt-4 overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Colony health by week</CardTitle>
            <CardDescription>Average mites per 100 bees against the treatment limit, with the share of colonies that have a laying queen.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? (
          <div className="px-5 pb-6"><ChartSkeleton height={260} /></div>
        ) : data.rows.length ? (
          <HealthTrendChart series={data.series} threshold={threshold} accent={accent} />
        ) : (
          <EmptyNote>No inspections in this period.</EmptyNote>
        )}
      </Card>

      <Card className="mt-4 overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Inspection log</CardTitle>
            <CardDescription>Newest first. One row per visit to a hive group.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? (
          <ScrollTable>
            <table className="w-full text-[13px]"><tbody><TableRowsSkeleton cols={8} rows={5} /></tbody></table>
          </ScrollTable>
        ) : data.rows.length ? (
          <ScrollTable>
            <table className="w-full text-[13px]" data-testid="inspection-table">
              <thead className={STICKY_HEAD}>
                <tr className={THEAD_ROW}>
                  <th className={TH}>Date</th>
                  <th className={TH}>Hive group</th>
                  <th className={THR}>Colonies</th>
                  <th className={THR}>Queenright</th>
                  <th className={THR}>Mites / 100</th>
                  <th className={TH}>Brood</th>
                  <th className={TH}>Temper</th>
                  <th className={TH}>Disease</th>
                  <th className={THR}>Frames b / h / s</th>
                  <th className={TH}>Notes</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.name} className={BODY_ROW}>
                    <td className={`${TD} font-semibold`}>{dayMonthYear(r.inspection_date)}</td>
                    <td className={TD}>{r.unit_label}</td>
                    <td className={TDR}>{r.colonies_inspected}</td>
                    <td className={TDR}>
                      {r.colonies_queenright}
                      {r.colonies_queenright < r.colonies_inspected && <Chip className={`ml-2 ${TONE.warn}`}>queenless</Chip>}
                    </td>
                    <td className={TDR}>
                      {r.varroa_per_100 != null ? fmt(r.varroa_per_100, 1) : "—"}
                      {r.mite_status === "high" && <Chip className={`ml-2 ${MITE_TONE.high}`}>{MITE_LABEL.high}</Chip>}
                    </td>
                    <td className={TD}>{r.brood_pattern ?? "—"}</td>
                    <td className={TD}>{r.temperament ?? "—"}</td>
                    <td className={TD}>
                      {r.disease_signs && r.disease_signs !== "None" ? <Chip className={TONE.warn}>{r.disease_signs}</Chip> : <span className="text-[var(--sd-quiet)]">None</span>}
                    </td>
                    <td className={TDR}>{fmt(r.frames_brood, 1)} / {fmt(r.frames_honey, 1)} / {fmt(r.frames_stores, 1)}</td>
                    <td className={`${TD} max-w-[22rem] truncate text-[var(--sd-muted)]`} title={r.actions ?? undefined}>{r.actions ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollTable>
        ) : (
          <EmptyNote>{unit || dirty ? "No inspections match these filters." : "No inspections recorded yet. Use Record inspection to add one."}</EmptyNote>
        )}
      </Card>

      {data && <InspectionDialog open={recording} onOpenChange={setRecording} form={data.form} defaultUnit={unit} onSaved={load} />}
    </PageShell>
  );
}

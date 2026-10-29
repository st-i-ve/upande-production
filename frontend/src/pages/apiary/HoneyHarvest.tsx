import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { AccentScope } from "@/components/avocado/calendar-grid";
import { BODY_ROW, TD, TDR, TH, THEAD_ROW, THR } from "@/components/blocks/tableStyles";
import { ClearFiltersPill } from "@/components/ClearFiltersPill";
import { DateRangePicker, type DateRange } from "@/components/DateRangePicker";
import { FilterSelect } from "@/components/FilterSelect";
import { KpiCard } from "@/components/KpiCard";
import { ChartSkeleton, firstLoad, TableRowsSkeleton } from "@/components/Loading";
import { PageShell } from "@/components/PageShell";
import { RefreshButton } from "@/components/RefreshButton";
import { ScrollTable, STICKY_HEAD } from "@/components/ScrollTable";
import { ToolbarButton } from "@/components/ToolbarButton";
import { useToast } from "@/components/Toast";
import { Card, CardDescription, CardHeaderRow, CardHeading, CardTitle } from "@/components/ui/card";
import { HoneyChart, MoistureChart } from "@/components/apiary/charts";
import { HarvestDialog } from "@/components/apiary/HarvestDialog";
import { Chip, daysAgo, dayMonth, dayMonthYear, EmptyNote, fmt, TONE } from "@/components/apiary/ui";
import { getHoneyHarvest, type HoneyHarvestPage } from "@/lib/apiary-api";
import { bandTone } from "@/lib/bands";
import { useCurrentCrop, viewLabel } from "@/lib/crops";
import { isError } from "@/lib/frappe";
import { todayISO } from "@/lib/utils";

const defaultRange = (): DateRange => ({ from: daysAgo(364), to: todayISO() });
const GRADE_TONE: Record<string, string> = { A: TONE.ok, B: TONE.warn, C: TONE.bad };

export function HoneyHarvest() {
  const crop = useCurrentCrop();
  const toast = useToast();
  const accent = crop.accent_color || "#d9a514";
  const [data, setData] = useState<HoneyHarvestPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState<DateRange>(defaultRange);
  const [unit, setUnit] = useState("");
  const [recording, setRecording] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    const r = await getHoneyHarvest({ from_date: range.from, to_date: range.to, unit: unit || undefined });
    setLoading(false);
    if (isError(r)) {
      toast(r.error, "error");
      return;
    }
    setData(r as HoneyHarvestPage);
  }, [range, unit, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const first = firstLoad(loading, !!data);
  const k = data?.kpis;
  const limit = data?.form.moisture_limit ?? null;
  const dirty = !!unit || range.from !== defaultRange().from || range.to !== defaultRange().to;
  const unitOptions = useMemo(() => (data?.form.units ?? []).map((u) => ({ value: u.value, label: u.label })), [data]);
  const spark = (pick: (s: HoneyHarvestPage["series"][number]) => number | null) =>
    data?.series.filter((s) => pick(s) != null).map((s) => ({ week: s.week, value: pick(s) as number }));

  return (
    <PageShell
      title={viewLabel("honey-harvest", crop)}
      eyebrow={crop.name}
      description={data ? `${dayMonthYear(data.from_date)} to ${dayMonthYear(data.to_date)} ${limit != null ? `· honey under ${limit}% moisture keeps` : ""}` : undefined}
      actions={
        <>
          <DateRangePicker label="Period" value={range} onChange={setRange} max={todayISO()} />
          <FilterSelect label="Hive group" value={unit} onChange={setUnit} options={unitOptions} allLabel="All hive groups" />
          <ClearFiltersPill active={dirty} onClear={() => { setUnit(""); setRange(defaultRange()); }} />
          <RefreshButton onClick={load} loading={loading} label="the harvests" />
          <ToolbarButton onClick={() => setRecording(true)} disabled={!data}>
            <Plus className="h-4 w-4" />
            Record harvest
          </ToolbarButton>
        </>
      }
    >
      <AccentScope accent={accent} className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <KpiCard loading={first} label="Honey" value={k ? `${fmt(k.kg, 1)} kg` : "—"} hint={k ? `${k.harvests} harvest${k.harvests === 1 ? "" : "s"} · ${fmt(k.wax_kg, 1)} kg wax` : undefined} tone="good" series={spark((s) => s.kg)} showDelta={false} />
        <KpiCard loading={first} label="Per hive" value={k?.kg_per_hive != null ? `${fmt(k.kg_per_hive, 2)} kg` : "—"} hint={k ? `across ${fmt(k.colonies)} colonies` : undefined} />
        <KpiCard loading={first} label="Average moisture" value={k?.avg_moisture != null ? `${fmt(k.avg_moisture, 1)}%` : "—"} hint={limit != null ? `weighted by kg · limit ${limit}%` : "weighted by kg"} tone={k?.avg_moisture != null && limit != null && k.avg_moisture > limit ? "critical" : "default"} series={spark((s) => s.avg_moisture)} showDelta={false} />
        <KpiCard loading={first} label="Grade A" value={k?.grade_a_pct != null ? `${fmt(k.grade_a_pct, 0)}%` : "—"} hint="of honey by weight" tone={bandTone(data?.bands, "Grade A share", k?.grade_a_pct) === "good" ? "default" : bandTone(data?.bands, "Grade A share", k?.grade_a_pct)} series={spark((s) => s.grade_a_pct)} showDelta={false} />
      </AccentScope>

      <Card className="mt-4 overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Honey by week</CardTitle>
            <CardDescription>Kilograms taken off, by the week of the harvest. The peaks are the flow months.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? (
          <div className="px-5 pb-6"><ChartSkeleton height={260} /></div>
        ) : data.rows.length ? (
          <HoneyChart series={data.series} accent={accent} />
        ) : (
          <EmptyNote>No honey harvested in this period.</EmptyNote>
        )}
      </Card>

      {data && data.rows.some((r) => r.moisture_pct != null) && (
        <Card className="mt-4 overflow-hidden">
          <CardHeaderRow>
            <CardHeading>
              <CardTitle>Moisture</CardTitle>
              <CardDescription>Weekly average. Honey above the limit ferments in storage and drops a grade.</CardDescription>
            </CardHeading>
          </CardHeaderRow>
          <MoistureChart series={data.series} limit={limit} accent={accent} />
        </Card>
      )}

      <Card className="mt-4 overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>By hive group</CardTitle>
            <CardDescription>Kilograms per hive uses the colonies from each group's latest inspection.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? (
          <ScrollTable><table className="w-full text-[13px]"><tbody><TableRowsSkeleton cols={7} rows={2} /></tbody></table></ScrollTable>
        ) : data.groups.length ? (
          <ScrollTable>
            <table className="w-full text-[13px]" data-testid="group-table">
              <thead className={STICKY_HEAD}>
                <tr className={THEAD_ROW}>
                  <th className={TH}>Hive group</th>
                  <th className={THR}>Harvests</th>
                  <th className={THR}>Honey kg</th>
                  <th className={THR}>Colonies</th>
                  <th className={THR}>Kg per hive</th>
                  <th className={THR}>Moisture</th>
                  <th className={THR}>Grade A</th>
                  <th className={THR}>Wax kg</th>
                  <th className={TH}>Last harvest</th>
                </tr>
              </thead>
              <tbody>
                {data.groups.map((g) => (
                  <tr key={g.unit} className={BODY_ROW}>
                    <td className={`${TD} font-semibold`}>{g.label}</td>
                    <td className={TDR}>{g.harvests}</td>
                    <td className={`${TDR} font-semibold`}>{fmt(g.kg, 1)}</td>
                    <td className={TDR}>{g.colonies || "—"}</td>
                    <td className={TDR}>{fmt(g.kg_per_hive, 2)}</td>
                    <td className={TDR}>{g.avg_moisture != null ? `${fmt(g.avg_moisture, 1)}%` : "—"}</td>
                    <td className={TDR}>{g.grade_a_pct != null ? `${fmt(g.grade_a_pct, 0)}%` : "—"}</td>
                    <td className={TDR}>{fmt(g.wax_kg, 1)}</td>
                    <td className={TD}>{g.last_harvest ? dayMonthYear(g.last_harvest) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollTable>
        ) : (
          <EmptyNote>No hive groups yet.</EmptyNote>
        )}
      </Card>

      <Card className="mt-4 overflow-hidden">
        <CardHeaderRow>
          <CardHeading>
            <CardTitle>Harvest log</CardTitle>
            <CardDescription>Newest first. Each harvest also lands in the Overview and Costs figures.</CardDescription>
          </CardHeading>
        </CardHeaderRow>
        {first || !data ? (
          <ScrollTable><table className="w-full text-[13px]"><tbody><TableRowsSkeleton cols={8} rows={5} /></tbody></table></ScrollTable>
        ) : data.rows.length ? (
          <ScrollTable>
            <table className="w-full text-[13px]" data-testid="harvest-table">
              <thead className={STICKY_HEAD}>
                <tr className={THEAD_ROW}>
                  <th className={TH}>Date</th>
                  <th className={TH}>Hive group</th>
                  <th className={THR}>Supers</th>
                  <th className={THR}>Frames</th>
                  <th className={THR}>Honey kg</th>
                  <th className={THR}>Moisture</th>
                  <th className={TH}>Grade</th>
                  <th className={THR}>Wax kg</th>
                  <th className={TH}>Notes</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.name} className={BODY_ROW}>
                    <td className={`${TD} font-semibold`}>{dayMonth(r.harvest_date)} {r.harvest_date.slice(0, 4)}</td>
                    <td className={TD}>{r.unit_label}</td>
                    <td className={TDR}>{r.supers_removed || "—"}</td>
                    <td className={TDR}>{r.frames_extracted || "—"}</td>
                    <td className={`${TDR} font-semibold`}>{fmt(r.honey_kg, 1)}</td>
                    <td className={TDR}>
                      {r.moisture_pct != null ? `${fmt(r.moisture_pct, 1)}%` : "—"}
                      {r.moisture_pct != null && limit != null && r.moisture_pct > limit && <Chip className={`ml-2 ${TONE.warn}`}>wet</Chip>}
                    </td>
                    <td className={TD}>{r.grade ? <Chip className={GRADE_TONE[r.grade] ?? TONE.quiet}>Grade {r.grade}</Chip> : "—"}</td>
                    <td className={TDR}>{fmt(r.wax_kg, 1)}</td>
                    <td className={`${TD} max-w-[18rem] truncate text-[var(--sd-muted)]`}>{r.notes ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollTable>
        ) : (
          <EmptyNote>{dirty ? "No harvests match these filters." : "No honey recorded yet. Use Record harvest to add one."}</EmptyNote>
        )}
      </Card>

      {data && <HarvestDialog open={recording} onOpenChange={setRecording} form={data.form} defaultUnit={unit} onSaved={load} />}
    </PageShell>
  );
}
